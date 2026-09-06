"""Internal assessment reporting implementation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifact_validation import validate_assessment_results
from .render_plan import load_json, render_plan, resolve_groups


JsonObject = dict[str, Any]
RESULT_SCHEMA = "compliance.example/assessment-results/v4"
STATUS_SCHEMA = "compliance.example/assessment-status/v1"
GROUP_STATUS_SCHEMA = "compliance.example/assessment-group-status/v1"
EXPLANATION_SCHEMA = "compliance.example/assessment-explanation/v1"
FRAMEWORK_STATUS_SCHEMA = "compliance.example/framework-mapping-status/v1alpha1"
SUMMARY_STATUSES = ("pass", "fail", "unknown", "not_applicable", "error", "waived")
STATE_PRIORITY = {
    "invalid": 0,
    "error": 1,
    "fail": 2,
    "unknown": 3,
    "outdated": 4,
    "unassigned": 5,
    "no_controls": 6,
    "pending": 7,
    "waived": 8,
    "pass": 9,
    "not_applicable": 10,
    "inactive": 11,
}
STATE_SYMBOLS = {
    "invalid": "!",
    "error": "!",
    "fail": "×",
    "unknown": "?",
    "outdated": "↻",
    "unassigned": "!",
    "no_controls": "!",
    "pending": "…",
    "waived": "◇",
    "pass": "✓",
    "not_applicable": "○",
    "inactive": "○",
}
STATE_COLORS = {
    "invalid": "\033[31m",
    "error": "\033[31m",
    "fail": "\033[31m",
    "unknown": "\033[33m",
    "outdated": "\033[33m",
    "unassigned": "\033[33m",
    "no_controls": "\033[33m",
    "pending": "\033[36m",
    "waived": "\033[35m",
    "pass": "\033[32m",
    "not_applicable": "\033[2m",
    "inactive": "\033[2m",
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


def result_state(report: JsonObject) -> str:
    summaries = (
        report.get("requirement_baseline_summary", {}),
        report.get("requirement_summary", {}),
        report.get("summary", {}),
    )
    for status in ("error", "fail", "unknown", "waived", "pass", "not_applicable"):
        if any(summary.get(status, 0) for summary in summaries):
            return status
    return "no_controls"


def latest_report(reports: list[JsonObject]) -> JsonObject | None:
    if not reports:
        return None
    return max(reports, key=lambda report: report.get("evaluated_at", ""))


def reports_for_plan(
    plan: JsonObject,
    reports: list[JsonObject],
) -> tuple[JsonObject | None, JsonObject | None]:
    subject_reports = [
        report for report in reports
        if report.get("subject_id") == plan["subject"]["id"]
    ]
    current_reports = [
        report for report in subject_reports
        if report.get("plan_id") == plan["id"]
    ]
    return latest_report(current_reports), latest_report(subject_reports)


def status_row(plan: JsonObject, reports: list[JsonObject]) -> JsonObject:
    """Combine one rendered plan with result history without conflating the two."""
    subject_id = plan["subject"]["id"]
    current, previous = reports_for_plan(plan, reports)
    coverage = plan["coverage"]

    if coverage["status"] == "invalid":
        state = "invalid"
    elif coverage["status"] == "inactive":
        state = "inactive"
    elif coverage["status"] == "unassigned":
        state = "unassigned"
    elif not coverage["assessable"]:
        state = "no_controls"
    elif current is not None:
        state = result_state(current)
    elif previous is not None:
        state = "outdated"
    else:
        state = "pending"

    visible_report = current or previous
    summary = {
        status: int((visible_report or {}).get("summary", {}).get(status, 0))
        for status in SUMMARY_STATUSES
    }
    requirement_summary = {
        status: int((visible_report or {}).get("requirement_summary", {}).get(status, 0))
        for status in SUMMARY_STATUSES
    }
    return {
        "subject_id": subject_id,
        "subject_type": plan["subject"]["type"],
        "lifecycle": plan["subject"]["status"],
        "groups": [group["id"] for group in plan["resolved_groups"]],
        "state": state,
        "coverage": coverage,
        "plan_id": plan["id"],
        "current_result": current is not None,
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
        "state": "invalid",
        "coverage": {
            "status": "invalid",
            "assessable": False,
            "reason": "render-error",
            "assignment_count": 0,
            "active_control_count": 0,
            "excluded_control_count": 0,
        },
        "plan_id": None,
        "current_result": False,
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

    rows.sort(key=lambda row: (STATE_PRIORITY[row["state"]], row["subject_id"]))
    now = generated_at or datetime.now(UTC).replace(microsecond=0)
    return status_report(rows, now)


def summarize_rows(rows: list[JsonObject]) -> JsonObject:
    counts = Counter(row["state"] for row in rows)
    coverage_counts = Counter(row["coverage"]["status"] for row in rows)
    return {
        "total": len(rows),
        "coverage": {
            status: coverage_counts[status]
            for status in ("assigned", "unassigned", "inactive", "invalid")
            if coverage_counts[status]
        },
        "assessable": sum(1 for row in rows if row["coverage"]["assessable"]),
        "states": {state: counts[state] for state in STATE_PRIORITY if counts[state]},
    }


def status_report(
    rows: list[JsonObject],
    generated_at: datetime,
    filters: JsonObject | None = None,
) -> JsonObject:
    return {
        "schema": STATUS_SCHEMA,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "filters": filters or {"groups": [], "states": []},
        "summary": summarize_rows(rows),
        "subjects": rows,
    }


def filter_status_report(
    report: JsonObject,
    group_ids: list[str],
    states: list[str],
) -> JsonObject:
    selected = report["subjects"]
    if group_ids:
        requested_groups = set(group_ids)
        selected = [row for row in selected if requested_groups.intersection(row["groups"])]
    if states:
        selected = [row for row in selected if row["state"] in set(states)]
    generated_at = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
    return status_report(
        selected,
        generated_at,
        filters={"groups": sorted(set(group_ids)), "states": sorted(set(states))},
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
            "states": report["filters"]["states"],
        },
        "groups": rows,
    }


def _mapped_result_status(
    current: JsonObject | None,
    previous: JsonObject | None,
    results_key: str,
    identity_key: str,
    identity: str,
) -> tuple[str, str | None, str | None]:
    """Return current status, assessment time, and last known status."""
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
            result.get("status", "unknown") if result else "unknown",
            current.get("evaluated_at"),
            None,
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
            "outdated",
            previous.get("evaluated_at"),
            previous_result.get("status") if previous_result else None,
        )
    return "pending", None, None


def build_framework_report(
    subjects: dict[str, JsonObject],
    groups: list[JsonObject],
    assignments: list[JsonObject],
    policies_root: Path,
    reports: list[JsonObject],
    *,
    group_ids: list[str] | None = None,
    external_refs: list[str] | None = None,
    levels: list[str] | None = None,
    generated_at: datetime | None = None,
    config=None,
) -> JsonObject:
    """Expose objective and technical mappings without claiming equivalence."""
    selected_groups = set(group_ids or [])
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
            status, evaluated_at, last_status = _mapped_result_status(
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
                    "status": status,
                    "alignment": "realized" if requirement.get("realization") else "not_implemented",
                    "evaluated_at": evaluated_at,
                    **({"last_status": last_status} if last_status else {}),
                })

        for control in plan.get("controls", []):
            status, evaluated_at, last_status = _mapped_result_status(
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
                    "status": status,
                    "alignment": alignment,
                    "evaluated_at": evaluated_at,
                    **({"last_status": last_status} if last_status else {}),
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
                    "status": "excluded",
                    "alignment": control.get("alignment", "deviated"),
                    "evaluated_at": None,
                })

    mappings = [
        mapping
        for mapping in mappings
        if (not selected_refs or mapping["external_ref"] in selected_refs)
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
            "external_refs": sorted(selected_refs),
            "levels": sorted(selected_levels),
        },
        "summary": {
            "reference_count": len({item["external_ref"] for item in mappings}),
            "mapping_count": len(mappings),
            "levels": dict(sorted(Counter(item["mapping_level"] for item in mappings).items())),
            "statuses": dict(sorted(Counter(item["status"] for item in mappings).items())),
            "alignments": dict(sorted(Counter(item["alignment"] for item in mappings).items())),
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

    headers = ("EXTERNAL REFERENCE", "LEVEL", "STATUS", "ALIGNMENT", "SUBJECT", "POLICY OBJECT")
    rows = [(
        mapping["external_ref"],
        mapping["mapping_level"].upper(),
        mapping["status"].replace("_", " ").upper(),
        mapping["alignment"].replace("_", " ").upper(),
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


def state_label(state: str, color: bool) -> str:
    label = f'{STATE_SYMBOLS[state]} {state.replace("_", " ").upper()}'
    if color:
        return f"{STATE_COLORS[state]}{label}{ANSI_RESET}"
    return label


def render_table(report: JsonObject, color: bool = False) -> str:
    rows = report["subjects"]
    state_counts = report["summary"]["states"]
    state_summary = "  ".join(
        f'{state.replace("_", " ").upper()} {count}'
        for state, count in state_counts.items()
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
    if filters.get("states"):
        rendered_filters.append("state=" + ",".join(filters["states"]))
    if rendered_filters:
        lines.append("Filters   " + "  ".join(rendered_filters))
    lines.extend([f"Coverage  {coverage_summary}", f"Status    {state_summary}", ""])

    headers = (
        "STATE", "SUBJECT", "TYPE", "COVERAGE", "CONTROLS A/X",
        "OBJECTIVES P/F/?/E/W", "CHECKS P/F/?/E/W", "ASSESSED (UTC)",
    )
    rendered_rows = []
    for row in rows:
        coverage = row["coverage"]
        rendered_rows.append((
            state_label(row["state"], False),
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
            plain_state = values[0]
            padding = " " * (widths[0] - len(plain_state))
            values = (state_label(source["state"], True) + padding, *values[1:])
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
    if filters.get("states"):
        rendered_filters.append("state=" + ",".join(filters["states"]))
    if rendered_filters:
        lines.append("Filters  " + "  ".join(rendered_filters))
    lines.append("")

    headers = ("GROUP", "SUBJECTS", "ASSESSABLE", "COVERAGE A/U/I/X", "STATES")
    rendered_rows = []
    for group in report["groups"]:
        states = ", ".join(
            f'{state.replace("_", " ").upper()}={count}'
            for state, count in group["states"].items()
        ) or "-"
        rendered_rows.append((
            group["group_id"],
            str(group["total"]),
            str(group["assessable"]),
            compact_counts(
                group["coverage"],
                ("assigned", "unassigned", "inactive", "invalid"),
            ),
            states,
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
        f'State: {state_label(status["state"], color)}',
        (
            f'Coverage: {status["coverage"]["status"]} '
            f'(assessable={str(status["coverage"]["assessable"]).lower()}, '
            f'reason={status["coverage"]["reason"]})'
        ),
        f'Plan: {plan["id"]}',
        f'Policy revision: {plan["policy_revision"]}',
        "Policy sources: " + (
            ", ".join(
                f'{source["name"]}={source["digest"]}'
                for source in plan["policy_sources"]
            )
        ),
        f'Inventory revision: {plan["inventory_revision"]}',
        f'Assignment revision: {plan["assignment_revision"]}',
        "Waiver revision: " + (
            visible_result.get("waiver_revision", "not assessed")
            if visible_result
            else "not assessed"
        ),
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
        lines.append(f'Assessment: current, evaluated {current["evaluated_at"]}')
    elif previous is not None:
        lines.append(
            f'Assessment: outdated result from {previous["evaluated_at"]} '
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
        baseline_state = result.get("status", "pending") if result else "pending"
        lines.append(f'  {state_label(baseline_state, color)}  {reference}')
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
        requirement_state = result.get("status", "pending") if result else "pending"
        lines.append(
            f'  {state_label(requirement_state, color)}  {requirement["reference"]}: '
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
        control_state = result.get("status", "pending") if result else "pending"
        suffix = " (outdated)" if previous is not None and current is None and result else ""
        lines.append(
            f'  {state_label(control_state, color)}  {control["instance_id"]}{suffix}'
        )
        if result and result.get("reason"):
            lines.append(f'    {result["reason"]}')
        if result:
            for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
                for diagnostic in result.get('observed', {}).get(field, []):
                    lines.append('    ' + json.dumps(diagnostic, sort_keys=True))
        if result and result.get("status") != "pass" and result.get("severity"):
            lines.append(f'    severity: {result["severity"]}')
        if result and result.get("status") != "pass" and result.get("remediation"):
            lines.append(f'    remediation: {result["remediation"]}')
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
