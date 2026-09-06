"""Internal assessment reporting implementation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifact_validation import validate_assessment_plan, validate_assessment_results
from .render_plan import load_json, render_plan, resolve_groups


JsonObject = dict[str, Any]
RESULT_SCHEMA = "compliance.example/assessment-results/v4"
STATUS_SCHEMA = "compliance.example/assessment-status/v1"
GROUP_STATUS_SCHEMA = "compliance.example/assessment-group-status/v1"
EXPLANATION_SCHEMA = "compliance.example/assessment-explanation/v1"
FRAMEWORK_STATUS_SCHEMA = "compliance.example/framework-mapping-status/v1alpha1"
SUMMARY_STATUSES = ("pass", "fail", "unknown", "not_applicable", "error", "waived")
HISTORICAL_OUTCOMES = (*SUMMARY_STATUSES, "no_controls", "no_assessment")
PLAN_ALIGNMENTS = ("plan_aligned", "different_plan", "plan_alignment_unavailable")
OUTCOME_PRIORITY = {
    "error": 1,
    "fail": 2,
    "unknown": 3,
    "no_controls": 6,
    "no_assessment": 7,
    "waived": 8,
    "pass": 9,
    "not_applicable": 10,
}
OUTCOME_SYMBOLS = {
    "error": "!",
    "fail": "×",
    "unknown": "?",
    "no_controls": "!",
    "no_assessment": "…",
    "waived": "◇",
    "pass": "✓",
    "not_applicable": "○",
}
OUTCOME_COLORS = {
    "error": "\033[31m",
    "fail": "\033[31m",
    "unknown": "\033[33m",
    "no_controls": "\033[33m",
    "no_assessment": "\033[36m",
    "waived": "\033[35m",
    "pass": "\033[32m",
    "not_applicable": "\033[2m",
}
ANSI_RESET = "\033[0m"


def load_result_reports(path: Path | None) -> list[JsonObject]:
    """Load assessment result envelopes from one file or a directory tree."""
    if path is None:
        return []
    if not path.exists():
        raise ValueError(f"results path does not exist: {path}")

    paths = [path] if path.is_file() else sorted(path.rglob("*.json"))
    reports = []
    for candidate in paths:
        document = load_json(candidate)
        if isinstance(document, dict) and str(document.get("schema", "")).startswith("compliance.example/assessment-results/"):
            validate_assessment_results(document, source=candidate)
            reports.append(document)
    return reports


def load_assessment_plans(paths: list[Path]) -> list[JsonObject]:
    """Load a bounded plan file/directory set and index only by semantic plan ID."""
    plans: dict[str, JsonObject] = {}
    for path in paths:
        if not path.exists():
            raise ValueError(f"assessment plan input does not exist: {path}")
        candidates = [path] if path.is_file() else sorted(path.rglob("*.json"))
        found = False
        for candidate in candidates:
            document = load_json(candidate)
            if not isinstance(document, dict) or document.get("schema") != "compliance.example/assessment-plan/v4":
                if path.is_file():
                    raise ValueError(f"assessment plan input is not a v4 plan: {path}")
                continue
            found = True
            validate_assessment_plan(document, source=candidate)
            existing = plans.get(document["id"])
            if existing is not None and existing != document:
                raise ValueError("multiple distinct plans have the same exact plan identity")
            plans[document["id"]] = document
        if path.is_dir() and not found:
            raise ValueError(f"assessment plan directory contains no v4 plans: {path}")
    return [plans[identity] for identity in sorted(plans)]


def result_state(report: JsonObject) -> str:
    return report["outcome"]


def latest_report(reports: list[JsonObject]) -> JsonObject | None:
    if not reports:
        return None
    latest = max(report.get("evaluated_at", "") for report in reports)
    candidates = [report for report in reports if report.get("evaluated_at", "") == latest]
    if len({report["id"] for report in candidates}) != 1:
        raise ValueError("multiple distinct results exist for the exact plan and instant")
    return candidates[0]


def reports_for_plan(
    plan: JsonObject,
    reports: list[JsonObject],
) -> tuple[JsonObject | None, JsonObject | None]:
    current_reports = [
        report for report in reports
        if report.get("plan_id") == plan["id"]
    ]
    from .assessment_provenance import validate_result_against_plan
    for report in current_reports:
        validate_result_against_plan(report, plan)
    return latest_report(current_reports), None


def status_row(plan: JsonObject, reports: list[JsonObject]) -> JsonObject:
    """Combine one rendered plan with result history without conflating the two."""
    subject_id = plan["subject"]["id"]
    current, previous = reports_for_plan(plan, reports)
    from .operation import plan_coverage
    coverage = plan_coverage(plan)

    visible_report = current or previous
    historical_outcome = result_state(visible_report) if visible_report else "no_assessment"
    plan_alignment = ("plan_aligned" if current is not None else
                      "different_plan" if previous is not None else
                      "plan_alignment_unavailable")
    summary_counts = Counter(
        item["status"] for item in (visible_report or {}).get("results", [])
    )
    requirement_counts = Counter(
        item["status"]
        for item in (visible_report or {}).get("requirement_assessments", [])
    )
    summary = {status: summary_counts[status] for status in SUMMARY_STATUSES}
    requirement_summary = {
        status: requirement_counts[status] for status in SUMMARY_STATUSES
    }
    return {
        "subject_id": subject_id,
        "subject_type": plan["subject"]["type"],
        "lifecycle": plan["subject"]["status"],
        "groups": [group["id"] for group in plan["resolved_groups"]],
        "historical_outcome": historical_outcome,
        "plan_alignment": plan_alignment,
        "coverage": coverage,
        "plan_id": plan["id"],
        "matching_plan_result": current is not None,
        "evaluated_at": (visible_report or {}).get("evaluated_at"),
        "result_summary": summary,
        "requirement_summary": requirement_summary,
        "resolution_errors": plan["resolution"]["errors"],
    }


def invalid_status_row(
    subject: JsonObject,
    groups: list[JsonObject],
    error: Exception,
) -> JsonObject:
    """Keep a catalog-wide overview useful when one subject cannot be rendered."""
    return {
        "subject_id": subject["id"],
        "subject_type": subject["type"],
        "lifecycle": subject["status"],
        "groups": [
            group["id"]
            for group in resolve_groups({group["id"]: group for group in groups}, subject)
        ],
        "historical_outcome": "no_assessment",
        "plan_alignment": "plan_alignment_unavailable",
        "coverage": {
            "status": "invalid",
            "assessable": False,
            "reason": "render-error",
            "assignment_count": 0,
            "active_control_count": 0,
            "excluded_control_count": 0,
        },
        "plan_id": None,
        "matching_plan_result": False,
        "evaluated_at": None,
        "result_summary": {status: 0 for status in SUMMARY_STATUSES},
        "requirement_summary": {status: 0 for status in SUMMARY_STATUSES},
        "resolution_errors": [{"type": "render-error", "message": str(error)}],
    }


def build_status_report(
    subjects: dict[str, JsonObject],
    groups: list[JsonObject],
    assignments: list[JsonObject],
    policies_root: Path,
    reports: list[JsonObject],
    generated_at: datetime | None = None,
    config=None,
) -> JsonObject:
    rows = []
    for subject_id in sorted(subjects):
        subject = subjects[subject_id]
        try:
            plan = render_plan(subject, groups, assignments, policies_root, config=config)
            rows.append(status_row(plan, reports))
        except (KeyError, TypeError, ValueError) as error:
            rows.append(invalid_status_row(subject, groups, error))

    rows.sort(key=lambda row: (_attention_rank(row), row["subject_id"]))
    now = generated_at or datetime.now(UTC).replace(microsecond=0)
    return status_report(rows, now)


def _attention_rank(row: JsonObject) -> int:
    """Presentation order only; never a semantic status or aggregation source."""
    coverage_rank = {"invalid": 0, "unassigned": 5, "inactive": 11}
    if row["coverage"]["status"] in coverage_rank:
        return coverage_rank[row["coverage"]["status"]]
    if row["plan_alignment"] == "different_plan":
        return 4
    return OUTCOME_PRIORITY[row["historical_outcome"]]


def summarize_rows(rows: list[JsonObject]) -> JsonObject:
    outcome_counts = Counter(row["historical_outcome"] for row in rows)
    alignment_counts = Counter(row["plan_alignment"] for row in rows)
    coverage_counts = Counter(row["coverage"]["status"] for row in rows)
    return {
        "total": len(rows),
        "coverage": {
            status: coverage_counts[status]
            for status in ("assigned", "unassigned", "inactive", "invalid")
            if coverage_counts[status]
        },
        "assessable": sum(1 for row in rows if row["coverage"]["assessable"]),
        "historical_outcomes": {
            outcome: outcome_counts[outcome] for outcome in HISTORICAL_OUTCOMES
            if outcome_counts[outcome]
        },
        "plan_alignment": {
            alignment: alignment_counts[alignment] for alignment in PLAN_ALIGNMENTS
            if alignment_counts[alignment]
        },
    }


def status_report(
    rows: list[JsonObject],
    generated_at: datetime,
    filters: JsonObject | None = None,
) -> JsonObject:
    return {
        "schema": STATUS_SCHEMA,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "filters": filters or {"groups": [], "outcomes": [], "plan_alignment": []},
        "summary": summarize_rows(rows),
        "subjects": rows,
    }


def filter_status_report(
    report: JsonObject,
    group_ids: list[str],
    outcomes: list[str],
    plan_alignments: list[str],
) -> JsonObject:
    selected = report["subjects"]
    if group_ids:
        requested_groups = set(group_ids)
        selected = [row for row in selected if requested_groups.intersection(row["groups"])]
    if outcomes:
        selected = [row for row in selected if row["historical_outcome"] in set(outcomes)]
    if plan_alignments:
        selected = [row for row in selected if row["plan_alignment"] in set(plan_alignments)]
    generated_at = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
    return status_report(
        selected,
        generated_at,
        filters={"groups": sorted(set(group_ids)), "outcomes": sorted(set(outcomes)),
                 "plan_alignment": sorted(set(plan_alignments))},
    )


def build_group_report(
    report: JsonObject,
    group_ids: list[str],
    group_filter: list[str] | None = None,
) -> JsonObject:
    rows = []
    for group_id in sorted(group_ids):
        members = [row for row in report["subjects"] if group_id in row["groups"]]
        rows.append({"group_id": group_id, **summarize_rows(members)})
    return {
        "schema": GROUP_STATUS_SCHEMA,
        "generated_at": report["generated_at"],
        "filters": {
            "groups": sorted(set(group_filter or [])),
            "outcomes": report["filters"]["outcomes"],
            "plan_alignment": report["filters"]["plan_alignment"],
        },
        "groups": rows,
    }


def _mapped_result_status(
    current: JsonObject | None,
    previous: JsonObject | None,
    results_key: str,
    identity_key: str,
    identity: str,
) -> tuple[str, str, str | None]:
    """Return immutable outcome, exact-plan alignment, and assessment time."""
    if current is not None:
        result = next(
            (
                item
                for item in current.get(results_key, [])
                if item.get(identity_key) == identity
            ),
            None,
        )
        return (
            result.get("status", "unknown") if result else "no_assessment",
            "plan_aligned",
            current.get("evaluated_at"),
        )
    if previous is not None:
        previous_result = next(
            (
                item
                for item in previous.get(results_key, [])
                if item.get(identity_key) == identity
            ),
            None,
        )
        return (
            previous_result.get("status", "unknown") if previous_result else "no_assessment",
            "different_plan",
            previous.get("evaluated_at"),
        )
    return "no_assessment", "plan_alignment_unavailable", None


def build_framework_report(
    subjects: dict[str, JsonObject],
    groups: list[JsonObject],
    assignments: list[JsonObject],
    policies_root: Path,
    reports: list[JsonObject],
    *,
    group_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    plan_alignments: list[str] | None = None,
    external_refs: list[str] | None = None,
    levels: list[str] | None = None,
    generated_at: datetime | None = None,
    config=None,
) -> JsonObject:
    """Expose objective and technical mappings without claiming equivalence."""
    selected_groups = set(group_ids or [])
    selected_outcomes = set(outcomes or [])
    selected_plan_alignments = set(plan_alignments or [])
    selected_refs = set(external_refs or [])
    selected_levels = set(levels or [])
    mappings: list[JsonObject] = []

    for subject_id in sorted(subjects):
        plan = render_plan(subjects[subject_id], groups, assignments, policies_root, config=config)
        resolved_group_ids = {group["id"] for group in plan["resolved_groups"]}
        if selected_groups and not selected_groups.intersection(resolved_group_ids):
            continue
        current, previous = reports_for_plan(plan, reports)

        for requirement in plan.get("requirements", []):
            historical_outcome, plan_alignment, evaluated_at = _mapped_result_status(
                current,
                previous,
                "requirement_assessments",
                "requirement",
                requirement["reference"],
            )
            for external_ref in requirement.get("external_refs", []):
                mappings.append({
                    "external_ref": external_ref,
                    "mapping_level": "objective",
                    "claim": "objective_assessment",
                    "subject_id": subject_id,
                    "policy_object": requirement["reference"],
                    "historical_outcome": historical_outcome,
                    "plan_alignment": plan_alignment,
                    "policy_alignment": "realized" if requirement.get("realization") else "not_implemented",
                    "evaluated_at": evaluated_at,
                })

        for control in plan.get("controls", []):
            historical_outcome, plan_alignment, evaluated_at = _mapped_result_status(
                current,
                previous,
                "results",
                "instance_id",
                control["instance_id"],
            )
            alignment = control.get("alignment", "unaltered")
            claim = {
                "unaltered": "aligned_technical_check",
                "annotated": "aligned_technical_check",
                "tailored": "company_deviation",
                "deviated": "company_deviation",
                "substituted": "substituted_check",
            }.get(alignment, "technical_mapping")
            for external_ref in control.get("external_refs", []):
                mappings.append({
                    "external_ref": external_ref,
                    "mapping_level": "technical",
                    "claim": claim,
                    "subject_id": subject_id,
                    "policy_object": control["instance_id"],
                    "implementation": control["implementation"],
                    "historical_outcome": historical_outcome,
                    "plan_alignment": plan_alignment,
                    "policy_alignment": alignment,
                    "evaluated_at": evaluated_at,
                })

        for control in plan.get("excluded_controls", []):
            for external_ref in control.get("external_refs", []):
                mappings.append({
                    "external_ref": external_ref,
                    "mapping_level": "technical",
                    "claim": "excluded_technical_mapping",
                    "subject_id": subject_id,
                    "policy_object": control["instance_id"],
                    "implementation": control["implementation"],
                    "historical_outcome": "no_assessment",
                    "plan_alignment": ("plan_aligned" if current is not None else
                                       "different_plan" if previous is not None else
                                       "plan_alignment_unavailable"),
                    "policy_alignment": control.get("alignment", "deviated"),
                    "evaluated_at": None,
                })

    mappings = [
        mapping
        for mapping in mappings
        if (not selected_outcomes or mapping["historical_outcome"] in selected_outcomes)
        and (not selected_plan_alignments or mapping["plan_alignment"] in selected_plan_alignments)
        and (not selected_refs or mapping["external_ref"] in selected_refs)
        and (not selected_levels or mapping["mapping_level"] in selected_levels)
    ]
    mappings.sort(key=lambda item: (
        item["external_ref"],
        item["mapping_level"],
        item["subject_id"],
        item["policy_object"],
    ))
    now = generated_at or datetime.now(UTC).replace(microsecond=0)
    return {
        "schema": FRAMEWORK_STATUS_SCHEMA,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "scope": "project",
        "disclaimer": (
            "External references are traceability mappings. Technical results do not "
            "by themselves assert complete framework conformance; alignment and "
            "company deviations remain explicit."
        ),
        "filters": {
            "groups": sorted(selected_groups),
            "outcomes": sorted(selected_outcomes),
            "plan_alignment": sorted(selected_plan_alignments),
            "external_refs": sorted(selected_refs),
            "levels": sorted(selected_levels),
        },
        "summary": {
            "reference_count": len({item["external_ref"] for item in mappings}),
            "mapping_count": len(mappings),
            "levels": dict(sorted(Counter(item["mapping_level"] for item in mappings).items())),
            "historical_outcomes": dict(sorted(Counter(
                item["historical_outcome"] for item in mappings).items())),
            "plan_alignment": dict(sorted(Counter(
                item["plan_alignment"] for item in mappings).items())),
            "policy_alignment": dict(sorted(Counter(
                item["policy_alignment"] for item in mappings).items())),
        },
        "mappings": mappings,
    }


def render_framework_table(report: JsonObject) -> str:
    """Render traceability mappings as an operator-scannable table."""
    summary = report["summary"]
    lines = [
        (
            f'External framework mappings ({summary["reference_count"]} references, '
            f'{summary["mapping_count"]} mappings)'
        ),
        report["disclaimer"],
    ]
    filters = report.get("filters", {})
    rendered_filters = []
    if filters.get("groups"):
        rendered_filters.append("group=" + ",".join(filters["groups"]))
    if filters.get("external_refs"):
        rendered_filters.append("reference=" + ",".join(filters["external_refs"]))
    if filters.get("levels"):
        rendered_filters.append("level=" + ",".join(filters["levels"]))
    if rendered_filters:
        lines.append("Filters  " + "  ".join(rendered_filters))
    lines.append("")

    headers = ("EXTERNAL REFERENCE", "LEVEL", "HISTORICAL OUTCOME", "PLAN ALIGNMENT",
               "POLICY ALIGNMENT", "SUBJECT", "POLICY OBJECT")
    rows = [(
        mapping["external_ref"],
        mapping["mapping_level"].upper(),
        mapping["historical_outcome"].replace("_", " ").upper(),
        mapping["plan_alignment"].replace("_", " ").upper(),
        mapping["policy_alignment"].replace("_", " ").upper(),
        mapping["subject_id"],
        mapping["policy_object"],
    ) for mapping in report["mappings"]]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def format_row(values: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        ).rstrip()

    lines.append(format_row(headers))
    lines.append(format_row(tuple("─" * width for width in widths)))
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)


def build_explanation(plan: JsonObject, reports: list[JsonObject]) -> JsonObject:
    current, latest = reports_for_plan(plan, reports)
    return {
        "schema": EXPLANATION_SCHEMA,
        "status": status_row(plan, reports),
        "plan": plan,
        "result": current,
        "latest_previous_result": latest if current is None else None,
    }


def result_counts(row: JsonObject) -> str:
    summary = row["result_summary"]
    if not row["evaluated_at"]:
        return "-"
    return f'{summary["pass"]}/{summary["fail"]}/{summary["unknown"]}/{summary["error"]}/{summary["waived"]}'


def requirement_counts(row: JsonObject) -> str:
    summary = row["requirement_summary"]
    if not row["evaluated_at"] or not any(summary.values()):
        return "-"
    return f'{summary["pass"]}/{summary["fail"]}/{summary["unknown"]}/{summary["error"]}/{summary["waived"]}'


def shorten_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ").replace("Z", "")


def outcome_label(outcome: str, color: bool) -> str:
    label = f'{OUTCOME_SYMBOLS[outcome]} {outcome.replace("_", " ").upper()}'
    if color:
        return f"{OUTCOME_COLORS[outcome]}{label}{ANSI_RESET}"
    return label


def render_table(report: JsonObject, color: bool = False) -> str:
    rows = report["subjects"]
    outcome_summary = "  ".join(
        f'{outcome.replace("_", " ").upper()} {count}'
        for outcome, count in report["summary"]["historical_outcomes"].items()
    ) or "NO SUBJECTS"
    alignment_summary = "  ".join(
        f'{alignment.replace("_", " ").upper()} {count}'
        for alignment, count in report["summary"]["plan_alignment"].items()
    ) or "NO SUBJECTS"
    coverage_summary = "  ".join(
        f"{status.upper()} {count}"
        for status, count in report["summary"]["coverage"].items()
    ) or "NO SUBJECTS"
    coverage_summary += f'  ASSESSABLE {report["summary"]["assessable"]}'
    total = report["summary"]["total"]
    noun = "subject" if total == 1 else "subjects"
    lines = [
        f"Assessment overview ({total} {noun})",
    ]
    filters = report.get("filters", {})
    rendered_filters = []
    if filters.get("groups"):
        rendered_filters.append("group=" + ",".join(filters["groups"]))
    if filters.get("outcomes"):
        rendered_filters.append("outcome=" + ",".join(filters["outcomes"]))
    if filters.get("plan_alignment"):
        rendered_filters.append("plan-alignment=" + ",".join(filters["plan_alignment"]))
    if rendered_filters:
        lines.append("Filters   " + "  ".join(rendered_filters))
    lines.extend([f"Coverage   {coverage_summary}", f"Outcomes   {outcome_summary}",
                  f"Plan align {alignment_summary}", ""])

    headers = (
        "HISTORICAL OUTCOME", "PLAN ALIGNMENT", "SUBJECT", "TYPE", "COVERAGE", "CONTROLS A/X",
        "OBJECTIVES P/F/?/E/W", "CHECKS P/F/?/E/W", "ASSESSED (UTC)",
    )
    rendered_rows = []
    for row in rows:
        coverage = row["coverage"]
        rendered_rows.append((
            outcome_label(row["historical_outcome"], False),
            row["plan_alignment"].replace("_", " ").upper(),
            row["subject_id"],
            row["subject_type"],
            coverage["status"].upper(),
            f'{coverage["active_control_count"]}/{coverage["excluded_control_count"]}',
            requirement_counts(row),
            result_counts(row),
            shorten_timestamp(row["evaluated_at"]),
        ))

    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def format_row(values: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values)).rstrip()

    lines.append(format_row(headers))
    lines.append(format_row(tuple("─" * width for width in widths)))
    for source, values in zip(rows, rendered_rows, strict=True):
        if color:
            plain_outcome = values[0]
            padding = " " * (widths[0] - len(plain_outcome))
            values = (outcome_label(source["historical_outcome"], True) + padding, *values[1:])
        lines.append(format_row(values))
    return "\n".join(lines)


def compact_counts(values: JsonObject, keys: tuple[str, ...]) -> str:
    return "/".join(str(values.get(key, 0)) for key in keys)


def render_group_table(report: JsonObject) -> str:
    filters = report.get("filters", {})
    lines = [
        f'Group assessment overview ({len(report["groups"])} groups)',
        "Subjects are counted in every resolved DAG group.",
    ]
    rendered_filters = []
    if filters.get("groups"):
        rendered_filters.append("group=" + ",".join(filters["groups"]))
    if filters.get("outcomes"):
        rendered_filters.append("outcome=" + ",".join(filters["outcomes"]))
    if filters.get("plan_alignment"):
        rendered_filters.append("plan-alignment=" + ",".join(filters["plan_alignment"]))
    if rendered_filters:
        lines.append("Filters  " + "  ".join(rendered_filters))
    lines.append("")

    headers = ("GROUP", "SUBJECTS", "ASSESSABLE", "COVERAGE A/U/I/X",
               "HISTORICAL OUTCOMES", "PLAN ALIGNMENT")
    rendered_rows = []
    for group in report["groups"]:
        outcomes = ", ".join(
            f'{outcome.replace("_", " ").upper()}={count}'
            for outcome, count in group["historical_outcomes"].items()
        ) or "-"
        alignments = ", ".join(
            f'{alignment.replace("_", " ").upper()}={count}'
            for alignment, count in group["plan_alignment"].items()
        ) or "-"
        rendered_rows.append((
            group["group_id"],
            str(group["total"]),
            str(group["assessable"]),
            compact_counts(
                group["coverage"],
                ("assigned", "unassigned", "inactive", "invalid"),
            ),
            outcomes,
            alignments,
        ))

    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def format_row(values: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values)).rstrip()

    lines.append(format_row(headers))
    lines.append(format_row(tuple("─" * width for width in widths)))
    lines.extend(format_row(row) for row in rendered_rows)
    return "\n".join(lines)


def membership_description(group: JsonObject) -> str:
    descriptions = []
    for source in group["sources"]:
        membership = source["membership"]
        if membership == "selector":
            labels = source["source"]["match_labels"]
            descriptions.append(
                "selector "
                + ",".join(f"{key}={value}" for key, value in sorted(labels.items()))
            )
        elif membership == "explicit":
            descriptions.append("explicit membership")
        else:
            descriptions.append("inherited via " + ",".join(source["via"]))
    return "; ".join(descriptions)


def provenance_paths(control: JsonObject) -> list[str]:
    return sorted({
        f'{item["group"]} -> {item["assignment"]} -> {item["baseline"]}'
        for item in control.get("provenance", [])
    })


def effective_criteria(control: JsonObject) -> str:
    """Render the exact resolved parameters without control-specific invention."""
    return json.dumps(
        control.get("parameters", {}),
        sort_keys=True,
        separators=(",", ":"),
    )


def lineage_description(control: JsonObject) -> str:
    """Explain the ordered baseline or realization steps for one definition."""
    def source(item: JsonObject) -> str:
        return item.get("baseline") or item.get("realization") or item["reference"]

    return " -> ".join(
        f'{source(item)} ({item["operation"]})'
        for item in control.get("lineage", [])
    )


def criteria_state_description(state: JsonObject) -> str:
    parameters = json.dumps(
        state["parameters"],
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        f'implementation={state["implementation"]}, '
        f'disposition={state["disposition"]}, criteria={parameters}'
    )


def append_derivation_details(lines: list[str], control: JsonObject) -> None:
    """Show the immutable inherited and resulting state for normative changes."""
    for derivation in control.get("derivations", []):
        inherited_from = " -> ".join(
            f'{item.get("baseline", item.get("realization"))} '
            f'({item["operation"]})'
            for item in derivation["inherited_lineage"]
        )
        lines.extend([
            f'    derivation: {derivation["operation"]} by {derivation["overlay"]}',
            f"      inherited from: {inherited_from}",
            f'      before: {criteria_state_description(derivation["before"])}',
            f'      after: {criteria_state_description(derivation["after"])}',
        ])
        if equivalence_ref := derivation.get("equivalence_ref"):
            lines.append(f"      equivalence: {equivalence_ref}")


def append_deviation_details(lines: list[str], control: JsonObject) -> None:
    """Render complete reviewed deviation metadata below a control."""
    deviations = control.get("deviations", [])
    if not deviations:
        return
    lines.append(
        "    alignment: " + control.get("alignment", "deviated").replace("_", " ")
    )
    for deviation in deviations:
        lines.extend([
            f'    deviation {deviation["id"]} ({deviation["classification"]})',
            f'      rationale: {deviation["rationale"]}',
            f'      approval: {deviation["approval_ref"]}',
            f'      review after: {deviation["review_after"]}',
        ])


def render_explanation(explanation: JsonObject, color: bool = False) -> str:
    status = explanation["status"]
    plan = explanation["plan"]
    current = explanation["result"]
    previous = explanation["latest_previous_result"]
    visible_result = current or previous
    result_by_instance = {
        result["instance_id"]: result
        for result in (visible_result or {}).get("results", [])
    }
    requirement_result_by_reference = {
        result["requirement"]: result
        for result in (visible_result or {}).get("requirement_assessments", [])
    }
    baseline_result_by_reference = {
        result["baseline"]: result
        for result in (visible_result or {}).get("requirement_baseline_assessments", [])
    }

    lines = [
        f'Subject: {status["subject_id"]}',
        f'Type: {status["subject_type"]}',
        f'Lifecycle: {status["lifecycle"]}',
        f'Historical outcome: {outcome_label(status["historical_outcome"], color)}',
        f'Plan alignment: {status["plan_alignment"].replace("_", " ")}',
        (
            f'Coverage: {status["coverage"]["status"]} '
            f'(assessable={str(status["coverage"]["assessable"]).lower()}, '
            f'reason={status["coverage"]["reason"]})'
        ),
        f'Plan: {plan["id"]}',
        f'Operation: {plan["operation"]["operation_id"]}',
        f'Member plan: {next(member["member_plan_digest"] for member in plan["operation"]["members"] if member["subject_id"] == plan["subject"]["id"])}',
        f'Planning composition: {plan["provenance"]["planningComposition"]["compositionDigest"]}',
        "Policy sources: " + (
            ", ".join(
                f'{source["name"]}={source["content"]["digest"]}'
                for source in plan["provenance"]["planningComposition"]["actual"]["policySources"]
            )
        ),
        "Applied waivers: " + str(sum(
            1 for result in (visible_result or {}).get("results", [])
            if "waiver" in result
        )),
        "",
        "Resolved groups:",
    ]
    if not plan["resolved_groups"]:
        lines.append("  none")
    for group in plan["resolved_groups"]:
        lines.append(f'  {group["id"]}: {membership_description(group)}')

    lines.append("Assignments:")
    if not plan["assignments"]:
        lines.append("  none")
    for assignment in plan["assignments"]:
        lines.append(
            f'  {assignment["group"]} -> {assignment["id"]} -> '
            + ", ".join(assignment["baselines"])
        )

    if current is not None:
        lines.append(f'Assessment: historical result for matching plan, evaluated {current["evaluated_at"]}')
    elif previous is not None:
        lines.append(
            f'Assessment: historical result for a different plan from {previous["evaluated_at"]} '
            f'for plan {previous["plan_id"]}'
        )
    else:
        lines.append("Assessment: no result available for this subject")

    lines.append("Control-objective baselines:")
    if not plan.get("resolved_requirement_baselines"):
        lines.append("  none")
    seen_requirement_baselines = set()
    for baseline in plan.get("resolved_requirement_baselines", []):
        reference = baseline["reference"]
        if reference in seen_requirement_baselines:
            continue
        seen_requirement_baselines.add(reference)
        result = baseline_result_by_reference.get(reference)
        baseline_state = result.get("status", "no_assessment") if result else "no_assessment"
        lines.append(f'  {outcome_label(baseline_state, color)}  {reference}')
        if result and result.get("reason"):
            lines.append(f'    {result["reason"]}')
        if result:
            for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
                for diagnostic in result.get('observed', {}).get(field, []):
                    lines.append('    ' + json.dumps(diagnostic, sort_keys=True))

    lines.append("Control objectives:")
    if not plan.get("requirements"):
        lines.append("  none")
    for requirement in plan.get("requirements", []):
        result = requirement_result_by_reference.get(requirement["reference"])
        requirement_state = result.get("status", "no_assessment") if result else "no_assessment"
        lines.append(
            f'  {outcome_label(requirement_state, color)}  {requirement["reference"]}: '
            f'{requirement["title"]}'
        )
        lines.append(f'    adoption: {requirement["adoption"]["status"]}')
        facts = requirement.get('parameter_facts', {})
        for name, slot in sorted(facts.get('states', {}).items()):
            lines.append(f"    parameter {name}: " + json.dumps(slot, sort_keys=True))
        for consumption in facts.get('consumption', []):
            lines.append("    consumption: " + json.dumps(consumption, sort_keys=True))
        if requirement.get("external_refs"):
            lines.append("    external refs: " + ", ".join(requirement["external_refs"]))
        if realization := requirement.get("realization"):
            lines.append(f'    realization: {realization["reference"]}')
            if based_on := realization.get("based_on"):
                lines.append(f'    based on: {based_on["realization"]}')
        if result and result.get("reason"):
            lines.append(f'    {result["reason"]}')
        if result:
            for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
                for diagnostic in result.get('observed', {}).get(field, []):
                    lines.append('    ' + json.dumps(diagnostic, sort_keys=True))

    lines.append("Active controls:")
    if not plan["controls"]:
        lines.append("  none")
    for control in plan["controls"]:
        result = result_by_instance.get(control["instance_id"])
        control_state = result.get("status", "no_assessment") if result else "no_assessment"
        suffix = " (different plan)" if previous is not None and current is None and result else ""
        lines.append(
            f'  {outcome_label(control_state, color)}  {control["instance_id"]}{suffix}'
        )
        if result and result.get("reason"):
            lines.append(f'    {result["reason"]}')
        if result:
            for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
                for diagnostic in result.get('observed', {}).get(field, []):
                    lines.append('    ' + json.dumps(diagnostic, sort_keys=True))
        if result and result.get("status") != "pass":
            lines.append(f'    severity: {control["severity"]}')
            if control.get("remediation"):
                lines.append(f'    remediation: {control["remediation"]}')
        if result and (waiver := result.get("waiver")):
            lines.extend([
                f'    waiver: {waiver["id"]}',
                f'      underlying status: {waiver["underlying_status"]}',
                f'      valid: {waiver["valid_from"]} through '
                f'{waiver["expires_at"]} (exclusive)',
                f'      rationale: {waiver["rationale"]}',
                f'      owner: {waiver["owner"]}',
                f'      approval: {waiver["approval_ref"]}',
                f'      approved by: {waiver["approved_by"]} at '
                f'{waiver["approved_at"]}',
                f'      digest: {waiver["digest"]}',
            ])
        lines.append(f"    effective criteria: {effective_criteria(control)}")
        lines.append("    policy evidence requirements: " + json.dumps(control.get('evidence', control.get('policy_inputs', {}).get('instance', {}).get('evidence', {})), sort_keys=True))
        if control.get("external_refs"):
            lines.append("    external refs: " + ", ".join(control["external_refs"]))
        if lineage := lineage_description(control):
            lines.append(f"    lineage: {lineage}")
        append_derivation_details(lines, control)
        append_deviation_details(lines, control)
        for path in provenance_paths(control):
            lines.append(f"    via {path}")

    lines.append("Excluded controls:")
    if not plan["excluded_controls"]:
        lines.append("  none")
    for control in plan["excluded_controls"]:
        lines.append(f'  ○ EXCLUDED  {control["instance_id"]}')
        lines.append(f"    effective criteria: {effective_criteria(control)}")
        lines.append("    policy evidence requirements: " + json.dumps(control.get('evidence', control.get('policy_inputs', {}).get('instance', {}).get('evidence', {})), sort_keys=True))
        if control.get("external_refs"):
            lines.append("    external refs: " + ", ".join(control["external_refs"]))
        if lineage := lineage_description(control):
            lines.append(f"    lineage: {lineage}")
        append_derivation_details(lines, control)
        append_deviation_details(lines, control)
        for path in provenance_paths(control):
            lines.append(f"    via {path}")

    if plan["resolution"]["errors"]:
        lines.append("Resolution errors:")
        for error in plan["resolution"]["errors"]:
            lines.append("  " + json.dumps(error, sort_keys=True))
    return "\n".join(lines)
