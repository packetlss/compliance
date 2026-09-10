"""Bounded operator projections over exact frozen assessment operations.

The semantic owners remain ``operation.py`` for exact accounting and current
qualification, the assessed plan for resolved meaning, and the result for the
immutable conclusion. This module only prepares deterministic CLI views.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .artifact_validation import validate_assessment_plan, validate_assessment_results
from .render_plan import load_json


JsonObject = dict[str, Any]
RUN_SCHEMA = "compliance.example/assessment-run-view/v1alpha1"
STATUS_SCHEMA = "compliance.example/assessment-status-view/v1alpha1"
MAPPINGS_SCHEMA = "compliance.example/assessment-mappings-view/v1alpha1"
EXPLANATION_SCHEMA = "compliance.example/assessment-explanation-view/v1alpha1"

# Missing slots and non-assessable dispositions deliberately do not appear in
# this result-owned outcome vocabulary.
HISTORICAL_OUTCOMES = (
    "pass", "fail", "unknown", "error", "waived", "not_applicable",
)
PLAN_ALIGNMENTS = ("plan_aligned", "different_plan", "plan_alignment_unavailable")


def load_result_reports(path: Path | None) -> list[JsonObject]:
    """Load intrinsically valid result envelopes from one bounded input."""
    if path is None:
        return []
    if not path.exists():
        raise ValueError(f"results path does not exist: {path}")
    paths = [path] if path.is_file() else sorted(path.rglob("*.json"))
    reports: list[JsonObject] = []
    for candidate in paths:
        document = load_json(candidate)
        if isinstance(document, dict) and str(document.get("schema", "")).startswith(
            "compliance.example/assessment-results/"
        ):
            validate_assessment_results(document, source=candidate)
            reports.append(document)
    return reports


def load_assessment_plans(paths: list[Path]) -> list[JsonObject]:
    """Load a bounded plan set indexed only by exact semantic plan ID."""
    plans: dict[str, JsonObject] = {}
    for path in paths:
        if not path.exists():
            raise ValueError(f"assessment plan input does not exist: {path}")
        candidates = [path] if path.is_file() else sorted(path.rglob("*.json"))
        found = False
        for candidate in candidates:
            document = load_json(candidate)
            if not isinstance(document, dict) or document.get("schema") != (
                "compliance.example/assessment-plan/v4"
            ):
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
    """Return the immutable result-owned operation outcome."""
    return report["outcome"]


def _result_index(reports: list[JsonObject]) -> dict[str, JsonObject]:
    return {report["id"]: report for report in reports}


def _plan_index(plans: list[JsonObject]) -> dict[str, JsonObject]:
    return {plan["id"]: plan for plan in plans}


def _slot(member: JsonObject) -> JsonObject:
    required = member["accounting_disposition"] == "result_required"
    return {
        "required": required,
        "present": member["result_present"],
        "accounting_disposition": member["accounting_disposition"],
        "expected_plan_id": member["plan_id"],
        "result_id": member["result_id"],
    }


def _qualification(member: JsonObject, query_instant: str | None) -> JsonObject:
    evidence = member.get("evidence_timeliness", {"qualification": "unavailable"})
    if evidence.get("qualification") == "unavailable":
        evidence_view: JsonObject = {"status": "unavailable"}
    else:
        reassessment_due = bool(evidence["controls_needing_reassessment"])
        timeliness_unavailable = bool(evidence["controls_with_unavailable_timeliness"])
        evidence_view = {
            "status": (
                "reassessment_due_and_partly_unavailable"
                if reassessment_due and timeliness_unavailable
                else "reassessment_due"
                if reassessment_due
                else "partly_unavailable"
                if timeliness_unavailable
                else "within_recorded_age_limits"
            ),
            "reassessment_due": reassessment_due,
            "timeliness_unavailable": timeliness_unavailable,
            "timely_selected_dependencies": evidence["timely_selected_dependencies"],
            "stale_selected_dependencies": evidence["stale_selected_dependencies"],
            "unavailable_required_dependencies": evidence[
                "unavailable_required_dependencies"
            ],
        }
    waivers = member.get("recorded_waiver_qualification", {}).get("waivers", [])
    return {
        "as_of": query_instant,
        "plan_alignment": member.get("plan_alignment", "plan_alignment_unavailable"),
        "selected_evidence": evidence_view,
        "recorded_waivers": [
            {
                "instance_id": waiver["instance_id"],
                "waiver_id": waiver["waiver_id"],
                "qualification": waiver["qualification"],
                "valid_from": waiver["valid_from"],
                "expires_at": waiver["expires_at"],
            }
            for waiver in waivers
        ],
    }


def _asset_status(member: JsonObject, query_instant: str | None) -> JsonObject:
    return {
        "asset_id": member["subject_id"],
        "asset_type": member["subject"]["type"],
        "groups": [group["id"] for group in member["resolved_groups"]],
        "expected_result_slot": _slot(member),
        "historical_outcome": member.get("historical_outcome"),
        "historical_interpretation": member["historical_interpretation"],
        "current_qualification": _qualification(member, query_instant),
    }


def _operation_summary(account: JsonObject) -> JsonObject:
    members = account["members"]
    required = [m for m in members if m["accounting_disposition"] == "result_required"]
    outcomes = Counter(
        (
            member.get("historical_outcome")
            if "historical_outcome" in member
            else member["state"] if member["result_present"] else None
        )
        for member in members
    )
    outcomes.pop(None, None)
    return {
        "selected_assets": len(members),
        "expected_result_slots": len(required),
        "filled_result_slots": sum(m["result_present"] for m in required),
        "missing_result_slots": sum(not m["result_present"] for m in required),
        "historical_outcomes": {
            outcome: outcomes[outcome]
            for outcome in HISTORICAL_OUTCOMES
            if outcomes[outcome]
        },
        "accounting_complete": account["accounting_complete"],
        "historical_interpretation_complete": account[
            "historical_interpretation_complete"
        ],
        "all_passed": account["all_passed"],
    }


def build_run_view(
    account: JsonObject,
    plans: list[JsonObject],
    reports: list[JsonObject],
) -> JsonObject:
    """Project one completed exact operation without embedding its artifacts."""
    del plans, reports  # Exact accounting already validated these inputs.
    return {
        "schema": RUN_SCHEMA,
        "operation": {
            "operation_id": account["operation"]["operation_id"],
            "request": copy.deepcopy(account["operation"]["request"]),
            "evaluated_at": account["evaluated_at"],
        },
        "summary": _operation_summary(account),
        "assets": [
            {
                "asset_id": member["subject_id"],
                "asset_type": member["subject"]["type"],
                "expected_result_slot": _slot(member),
                "historical_outcome": member["state"] if member["result_present"] else None,
            }
            for member in account["members"]
        ],
    }


def render_run_view(view: JsonObject) -> str:
    summary = view["summary"]
    lines = [
        f'Assessment operation {view["operation"]["operation_id"]}',
        f'Assessment instant: {view["operation"]["evaluated_at"]}',
        (
            f'Exact accounting: {summary["filled_result_slots"]}/'
            f'{summary["expected_result_slots"]} required result slots filled; '
            f'accounting_complete={str(summary["accounting_complete"]).lower()}; '
            f'all_passed={str(summary["all_passed"]).lower()}'
        ),
        "",
        "ASSET  EXPECTATION  RESULT SLOT  HISTORICAL OUTCOME",
    ]
    for asset in view["assets"]:
        slot = asset["expected_result_slot"]
        expectation = slot["accounting_disposition"].replace("_", " ").upper()
        presence = (
            "FILLED" if slot["present"] else "MISSING" if slot["required"] else "NOT REQUIRED"
        )
        outcome = (asset["historical_outcome"] or "-").replace("_", " ").upper()
        lines.append(f'{asset["asset_id"]}  {expectation}  {presence}  {outcome}')
    return "\n".join(lines)


def _matches_member_filters(
    member: JsonObject,
    groups: set[str],
    outcomes: set[str],
    alignments: set[str],
) -> bool:
    member_groups = {group["id"] for group in member["resolved_groups"]}
    return (
        (not groups or bool(groups & member_groups))
        and (not outcomes or member.get("historical_outcome") in outcomes)
        and (not alignments or member.get("plan_alignment") in alignments)
    )


def _group_status(
    group_id: str,
    all_members: list[JsonObject],
    visible_members: list[JsonObject],
) -> JsonObject:
    frozen = [
        member for member in all_members
        if group_id in {group["id"] for group in member["resolved_groups"]}
    ]
    visible = [
        member for member in visible_members
        if group_id in {group["id"] for group in member["resolved_groups"]}
    ]
    required = [m for m in frozen if m["accounting_disposition"] == "result_required"]
    outcomes = Counter(m.get("historical_outcome") for m in visible)
    outcomes.pop(None, None)
    group_complete = all(m["result_present"] for m in required)
    group_interpretable = all(
        m["result_present"] and m["historical_interpretation"] == "validated"
        for m in required
    )
    return {
        "group_id": group_id,
        "frozen_accounting": {
            "selected_assets": len(frozen),
            "expected_result_slots": len(required),
            "filled_result_slots": sum(m["result_present"] for m in required),
            "missing_result_slots": sum(not m["result_present"] for m in required),
            "accounting_complete": group_complete,
            "all_passed": bool(required) and group_interpretable and all(
                m["historical_outcome"] == "pass" for m in required
            ) and len(required) == len(frozen),
        },
        "visible_assets": len(visible),
        "historical_outcomes": {
            outcome: outcomes[outcome]
            for outcome in HISTORICAL_OUTCOMES
            if outcomes[outcome]
        },
    }


def build_status_view(
    account: JsonObject,
    *,
    group_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    plan_alignments: list[str] | None = None,
    by_group: bool = False,
) -> JsonObject:
    """Build status from exact accounting and separately derived qualification."""
    selected_groups = set(group_ids or [])
    selected_outcomes = set(outcomes or [])
    selected_alignments = set(plan_alignments or [])
    visible = [
        member
        for member in account["members"]
        if _matches_member_filters(member, selected_groups, selected_outcomes, selected_alignments)
    ]
    filters = {
        "groups": sorted(selected_groups),
        "outcomes": sorted(selected_outcomes),
        "plan_alignment": sorted(selected_alignments),
    }
    view: JsonObject = {
        "schema": STATUS_SCHEMA,
        "operation": {
            "operation_id": account["operation"]["operation_id"],
            "evaluated_at": account["evaluated_at"],
        },
        "query_instant": account["query_instant"],
        "filters": filters,
        "filtered": bool(any(filters.values())),
        "whole_operation": _operation_summary(account),
        "view": "groups" if by_group else "assets",
    }
    if by_group:
        known_groups = sorted({
            group["id"]
            for member in account["members"]
            for group in member["resolved_groups"]
        })
        selected = sorted(selected_groups) if selected_groups else known_groups
        view["groups"] = [
            _group_status(group_id, account["members"], visible) for group_id in selected
        ]
    else:
        view["assets"] = [
            _asset_status(member, account["query_instant"]) for member in visible
        ]
    return view


def _filters_line(filters: JsonObject) -> str | None:
    values = []
    for key in ("groups", "outcomes", "plan_alignment", "external_refs", "levels"):
        if filters.get(key):
            values.append(f'{key.replace("_", "-")}=' + ",".join(filters[key]))
    return "Filters: " + "  ".join(values) if values else None


def render_status_view(view: JsonObject) -> str:
    summary = view["whole_operation"]
    lines = [
        f'Assessment status for operation {view["operation"]["operation_id"]}',
        f'Historical assessment instant: {view["operation"]["evaluated_at"]}',
        f'Current qualification as of: {view["query_instant"]}',
        (
            f'Whole-operation accounting: {summary["filled_result_slots"]}/'
            f'{summary["expected_result_slots"]} exact slots filled; '
            f'accounting_complete={str(summary["accounting_complete"]).lower()}; '
            f'all_passed={str(summary["all_passed"]).lower()}'
        ),
    ]
    if filter_line := _filters_line(view["filters"]):
        lines.extend([filter_line, "Filtered rows do not change whole-operation accounting."])
    lines.append("")
    if view["view"] == "groups":
        lines.append(
            "GROUP  ASSETS  EXPECTED/FILLED/MISSING  ACCOUNTING COMPLETE  HISTORICAL OUTCOMES"
        )
        for group in view["groups"]:
            frozen = group["frozen_accounting"]
            outcomes = ",".join(
                f"{key.upper()}={value}" for key, value in group["historical_outcomes"].items()
            ) or "-"
            lines.append(
                f'{group["group_id"]}  {frozen["selected_assets"]}  '
                f'{frozen["expected_result_slots"]}/{frozen["filled_result_slots"]}/'
                f'{frozen["missing_result_slots"]}  '
                f'{str(frozen["accounting_complete"]).upper()}  {outcomes}'
            )
        return "\n".join(lines)
    lines.append("ASSET  RESULT SLOT  HISTORICAL OUTCOME  PLAN ALIGNMENT  CURRENT EVIDENCE")
    for asset in view["assets"]:
        slot = asset["expected_result_slot"]
        presence = (
            "FILLED" if slot["present"] else "MISSING" if slot["required"] else "NOT REQUIRED"
        )
        outcome = (asset["historical_outcome"] or "-").replace("_", " ").upper()
        current = asset["current_qualification"]
        lines.append(
            f'{asset["asset_id"]}  {presence}  {outcome}  '
            f'{current["plan_alignment"].replace("_", " ").upper()}  '
            f'{current["selected_evidence"]["status"].replace("_", " ").upper()}'
        )
    return "\n".join(lines)


def _specific_outcome(
    member: JsonObject,
    report: JsonObject | None,
    result_key: str,
    identity_key: str,
    identity: str,
) -> str | None:
    if report is None or member["historical_interpretation"] != "validated":
        return None
    match = next(
        (item for item in report.get(result_key, []) if item.get(identity_key) == identity),
        None,
    )
    return match.get("status") if match else None


def build_mappings_view(
    account: JsonObject,
    reports: list[JsonObject],
    assessed_plans: list[JsonObject],
    *,
    group_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    plan_alignments: list[str] | None = None,
    external_refs: list[str] | None = None,
    levels: list[str] | None = None,
) -> JsonObject:
    """Project exact attributable mapping facts without a completeness claim."""
    reports_by_id = _result_index(reports)
    plans_by_id = _plan_index(assessed_plans)
    selected_groups = set(group_ids or [])
    selected_outcomes = set(outcomes or [])
    selected_alignments = set(plan_alignments or [])
    selected_refs = set(external_refs or [])
    selected_levels = set(levels or [])
    mappings: list[JsonObject] = []
    for member in account["members"]:
        member_groups = {group["id"] for group in member["resolved_groups"]}
        if selected_groups and not selected_groups.intersection(member_groups):
            continue
        report = reports_by_id.get(member["result_id"])
        plan = plans_by_id.get(member["plan_id"])
        plan_requirements = {
            item["reference"]: item for item in (plan or {}).get("requirements", [])
        }
        plan_controls = {
            item["instance_id"]: item
            for field in ("controls", "excluded_controls")
            for item in (plan or {}).get(field, [])
        }
        for level, policy_key, result_key, identity_key in (
            ("objective", "requirements", "requirement_assessments", "requirement"),
            ("technical", "controls", "results", "instance_id"),
        ):
            for item in member["policy"][policy_key]:
                identity = item["reference" if level == "objective" else "instance_id"]
                outcome = _specific_outcome(member, report, result_key, identity_key, identity)
                if level == "objective":
                    exact_item = plan_requirements.get(identity)
                    policy_alignment = (
                        "realized"
                        if exact_item and exact_item.get("realization")
                        else "not_implemented"
                        if exact_item
                        else "unavailable"
                    )
                else:
                    exact_item = plan_controls.get(identity)
                    policy_alignment = (
                        exact_item.get("alignment", item["disposition"])
                        if exact_item
                        else "unavailable"
                    )
                for reference in item["external_refs"]:
                    row = {
                        "external_ref": reference,
                        "mapping_level": level,
                        "asset_id": member["subject_id"],
                        "policy_object": identity,
                        "policy_disposition": item.get("disposition", "active"),
                        "policy_alignment": policy_alignment,
                        "expected_result_slot": _slot(member),
                        "historical_outcome": outcome,
                        "historical_interpretation": member["historical_interpretation"],
                        "current_qualification": {
                            "plan_alignment": member["plan_alignment"],
                        },
                    }
                    if (
                        (not selected_outcomes or outcome in selected_outcomes)
                        and (not selected_alignments or member["plan_alignment"] in selected_alignments)
                        and (not selected_refs or reference in selected_refs)
                        and (not selected_levels or level in selected_levels)
                    ):
                        mappings.append(row)
    mappings.sort(
        key=lambda item: (
            item["external_ref"], item["mapping_level"], item["asset_id"], item["policy_object"],
        )
    )
    filters = {
        "groups": sorted(selected_groups),
        "outcomes": sorted(selected_outcomes),
        "plan_alignment": sorted(selected_alignments),
        "external_refs": sorted(selected_refs),
        "levels": sorted(selected_levels),
    }
    return {
        "schema": MAPPINGS_SCHEMA,
        "operation": {
            "operation_id": account["operation"]["operation_id"],
            "evaluated_at": account["evaluated_at"],
        },
        "query_instant": account["query_instant"],
        "scope": "exact_frozen_operation",
        "note": (
            "Mappings are attributable traceability facts. They do not establish "
            "coverage, conformity, certification, an audit opinion, or legal compliance."
        ),
        "filters": filters,
        "whole_operation": _operation_summary(account),
        "summary": {
            "references": len({item["external_ref"] for item in mappings}),
            "mappings": len(mappings),
            "levels": dict(sorted(Counter(item["mapping_level"] for item in mappings).items())),
        },
        "mappings": mappings,
    }


def render_mappings_view(view: JsonObject) -> str:
    lines = [
        (
            f'Assessment mappings ({view["summary"]["references"]} references, '
            f'{view["summary"]["mappings"]} mappings)'
        ),
        view["note"],
    ]
    if filter_line := _filters_line(view["filters"]):
        lines.append(filter_line)
    lines.extend([
        "",
        "MAPPING  LEVEL  ASSET  POLICY OBJECT  HISTORICAL OUTCOME  PLAN ALIGNMENT  POLICY ALIGNMENT",
    ])
    for mapping in view["mappings"]:
        outcome = (mapping["historical_outcome"] or "-").replace("_", " ").upper()
        lines.append(
            f'{mapping["external_ref"]}  {mapping["mapping_level"].upper()}  '
            f'{mapping["asset_id"]}  {mapping["policy_object"]}  {outcome}  '
            f'{mapping["current_qualification"]["plan_alignment"].replace("_", " ").upper()}  '
            f'{mapping["policy_alignment"].replace("_", " ").upper()}'
        )
    if not view["mappings"]:
        lines.append("No attributable mappings matched this exact frozen operation and filter.")
    return "\n".join(lines)


def _safe_result_fact(result: JsonObject) -> JsonObject:
    fact = {
        "instance_id": result["instance_id"],
        "historical_outcome": result["status"],
        "reason": result.get("reason"),
    }
    if "evaluation_error" in result:
        fact["evaluation_error"] = copy.deepcopy(result["evaluation_error"])
    if "waiver" in result:
        waiver = result["waiver"]
        fact["waiver"] = {
            key: copy.deepcopy(waiver[key])
            for key in (
                "id", "underlying_status", "valid_from", "expires_at", "rationale",
                "owner", "approval_ref", "approved_by", "approved_at",
            )
        }
    return fact


def _error_explanation(error: JsonObject) -> str:
    return {
        "criterion_execution_failed": (
            "Criterion execution failed; the immutable historical outcome is ERROR."
        ),
        "criterion_decision_invalid": (
            "The criterion decision was unusable; the immutable historical outcome is ERROR."
        ),
        "criterion_reported_error": (
            "The criterion returned a structurally valid ERROR decision; the immutable "
            "historical outcome is ERROR."
        ),
    }[error["code"]]


def _dependency_fact(
    control: JsonObject,
    dependency: JsonObject,
    disposition: JsonObject | None,
    selection: JsonObject | None,
    timeliness: JsonObject | None,
) -> JsonObject:
    del control
    fact: JsonObject = {
        "dependency_id": dependency["id"],
        "evidence_type": dependency["type"],
        "assessed_max_age": dependency["max_age"],
        "selection": (
            "selected" if selection else disposition["disposition"] if disposition else "unavailable"
        ),
    }
    if selection:
        fact["selected_evidence"] = {
            key: selection[key]
            for key in ("evidence_id", "evidence_digest", "collected_at")
        }
    elif disposition is not None:
        kind = disposition["disposition"]
        fact["assessment_explanation"] = {
            "absent": (
                f'No matching routed {dependency["type"]} observation was available '
                "at assessment time."
            ),
            "stale": (
                f'The latest matching {dependency["type"]} observation(s) were older '
                f'than the exact assessed freshness limit ({dependency["max_age"]}) '
                "at assessment time."
            ),
            "invalid": (
                f'Matching {dependency["type"]} observation(s) did not satisfy the '
                "exact assessment-time evidence schema."
            ),
            "ambiguous": (
                f'Multiple distinct equally latest eligible {dependency["type"]} '
                "observations competed, so none was selected."
            ),
        }[kind]
        for key in ("latest_candidates", "candidates", "diagnostics"):
            if key in disposition:
                fact[key] = copy.deepcopy(disposition[key])
    if timeliness is not None:
        fact["current_timeliness"] = timeliness["qualification"]
    return fact


def _check_explanation(
    control: JsonObject,
    result: JsonObject | None,
    dispositions: dict[tuple[str, str], JsonObject],
    selections: dict[tuple[str, str], JsonObject],
    timeliness: dict[tuple[str, str], JsonObject],
    waiver_qualification: dict[str, JsonObject],
) -> JsonObject:
    instance_id = control["instance_id"]
    dependencies = [
        _dependency_fact(
            control,
            dependency,
            dispositions.get((instance_id, dependency["id"])),
            selections.get((instance_id, dependency["id"])),
            timeliness.get((instance_id, dependency["id"])),
        )
        for dependency in control["evidence"]
    ]
    historical: JsonObject | None = _safe_result_fact(result) if result else None
    if historical is not None:
        status = result["status"]
        blocking = [item for item in dependencies if item["selection"] != "selected"]
        if status == "error":
            historical["explanation"] = _error_explanation(result["evaluation_error"])
        elif status == "unknown" and not blocking:
            historical["explanation"] = (
                "All required observations were selected, but the criterion returned "
                f'UNKNOWN: {result.get("reason", "No bounded criterion reason was recorded.")}'
            )
        elif status == "unknown":
            historical["explanation"] = (
                "The check was UNKNOWN because required evidence selection did not "
                "succeed; each dependency disposition is shown separately."
            )
        elif status == "fail":
            historical["explanation"] = f'The check failed: {result.get("reason", "")}'.rstrip()
        elif status == "waived":
            historical["explanation"] = (
                f'The check failed: {result.get("reason", "")} Governance accepted '
                f'that failure under waiver {result["waiver"]["id"]}; the immutable '
                "historical outcome remains WAIVED."
            )
        elif status == "pass":
            historical["explanation"] = "The check passed at the assessment instant."
        else:
            historical["explanation"] = (
                "The criterion returned NOT APPLICABLE at the assessment instant."
            )
        if instance_id in waiver_qualification:
            historical["current_waiver_qualification"] = waiver_qualification[instance_id]
    return {
        "check": {
            "title": control["title"],
            "purpose": control["purpose"],
            "instance_id": instance_id,
            "implementation": control["implementation"],
            "severity": control["severity"],
            "remediation": control.get("remediation", ""),
        },
        "effective_parameters": copy.deepcopy(control["parameters"]),
        "policy_alignment": control.get("alignment", "unaltered"),
        "deviations": [
            {
                key: copy.deepcopy(deviation[key])
                for key in (
                    "id", "classification", "rationale", "approval_ref", "review_after"
                )
            }
            for deviation in control.get("deviations", [])
        ],
        "required_evidence": dependencies,
        "historical_result": historical,
    }


def build_explanation_view(
    account: JsonObject,
    member: JsonObject,
    plan: JsonObject | None,
    result: JsonObject | None,
) -> JsonObject:
    """Explain one exact slot, with a bounded result-only orphan fallback."""
    slot = _slot(member)
    base: JsonObject = {
        "schema": EXPLANATION_SCHEMA,
        "asset": {"id": member["subject_id"], "type": member["subject"]["type"]},
        "operation": {
            "operation_id": account["operation"]["operation_id"],
            "evaluated_at": account["evaluated_at"],
            "plan_id": member["plan_id"],
            "result_id": member["result_id"],
        },
        "expected_result_slot": slot,
        "historical_outcome": result["outcome"] if result else None,
        "current_qualification": _qualification(member, account["query_instant"]),
    }
    if result is None:
        base["interpretation"] = (
            "exact_result_slot_missing" if slot["required"] else "result_not_required"
        )
        base["explanation"] = (
            "The exact frozen operation requires a result for this asset, but its "
            "slot is missing. No result was synthesized."
            if slot["required"]
            else "The frozen member is non-assessable and no result is required."
        )
        if plan is not None:
            base["applicable_policies"] = _applicable_policies(plan)
            base["objectives"] = _objectives(plan, None)
            base["checks"] = [
                _check_explanation(control, None, {}, {}, {}, {})
                for control in plan["controls"]
            ]
            base["excluded_checks"] = _excluded_checks(plan)
        return base
    if plan is None:
        dispositions_by_instance: dict[str, list[JsonObject]] = {}
        for disposition in result["dependency_dispositions"]:
            dispositions_by_instance.setdefault(disposition["instance_id"], []).append(
                copy.deepcopy(disposition)
            )
        base.update({
            "interpretation": "limited_without_exact_plan",
            "explanation": (
                "The result artifact is retained, but its exact assessed plan is "
                "unavailable. Only raw result-owned facts are shown; full policy, "
                "dependency, timeliness, roll-up, and plan-alignment interpretation "
                "is unavailable."
            ),
            "raw_result_facts": [
                {
                    **_safe_result_fact(item),
                    "dependency_dispositions": dispositions_by_instance.get(
                        item["instance_id"], []
                    ),
                }
                for item in result["results"]
            ],
        })
        return base
    base["interpretation"] = "exact_plan_result_pair_validated"
    dispositions = {
        (item["instance_id"], item["dependency_id"]): item
        for item in result["dependency_dispositions"]
    }
    selections = {
        (item["instance_id"], item["dependency_id"]): item
        for item in result["provenance"]["selectedEvidence"]
    }
    timing = member.get("evidence_timeliness", {})
    timeliness = {
        (item["instance_id"], item["dependency_id"]): item
        for item in timing.get("dependencies", [])
    }
    waiver_qualification = {
        item["instance_id"]: item
        for item in member.get("recorded_waiver_qualification", {}).get("waivers", [])
    }
    results_by_instance = {item["instance_id"]: item for item in result["results"]}
    base.update({
        "applicable_policies": _applicable_policies(plan),
        "objectives": _objectives(plan, result),
        "checks": [
            _check_explanation(
                control,
                results_by_instance.get(control["instance_id"]),
                dispositions,
                selections,
                timeliness,
                waiver_qualification,
            )
            for control in plan["controls"]
        ],
        "excluded_checks": _excluded_checks(plan),
    })
    return base


def _applicable_policies(plan: JsonObject) -> list[JsonObject]:
    policies: dict[str, JsonObject] = {}
    for kind, field in (
        ("technical", "resolved_baselines"),
        ("objective", "resolved_requirement_baselines"),
    ):
        for item in plan.get(field, []):
            policies.setdefault(
                item["reference"],
                {"title": item["title"], "reference": item["reference"], "kind": kind},
            )
    return [policies[key] for key in sorted(policies)]


def _objectives(plan: JsonObject, result: JsonObject | None) -> list[JsonObject]:
    statuses = {
        item["requirement"]: item
        for item in (result or {}).get("requirement_assessments", [])
    }
    return [
        {
            "title": requirement["title"],
            "statement": requirement["statement"],
            "reference": requirement["reference"],
            "adoption": requirement["adoption"]["status"],
            "realization": (
                requirement["realization"]["reference"]
                if requirement.get("realization")
                else None
            ),
            "realization_based_on": (
                requirement["realization"].get("based_on", {}).get("realization")
                if requirement.get("realization")
                else None
            ),
            "check_instance_ids": copy.deepcopy(requirement["technical_instance_ids"]),
            "historical_outcome": (
                statuses[requirement["reference"]]["status"]
                if requirement["reference"] in statuses
                else None
            ),
        }
        for requirement in plan["requirements"]
    ]


def _excluded_checks(plan: JsonObject) -> list[JsonObject]:
    return [
        {
            "title": control["title"],
            "purpose": control["purpose"],
            "instance_id": control["instance_id"],
            "disposition": "excluded",
            "policy_alignment": control.get("alignment", "deviated"),
            "effective_parameters": copy.deepcopy(control["parameters"]),
            "deviations": copy.deepcopy(control.get("deviations", [])),
        }
        for control in plan["excluded_controls"]
    ]


def render_explanation_view(view: JsonObject) -> str:
    slot = view["expected_result_slot"]
    outcome = (view["historical_outcome"] or "-").replace("_", " ").upper()
    current = view["current_qualification"]
    lines = [
        f'Asset: {view["asset"]["id"]}',
        f'Historical outcome: {outcome}',
        "Exact result slot: " + (
            "filled" if slot["present"] else "missing" if slot["required"] else "not required"
        ),
        f'Operation: {view["operation"]["operation_id"]}',
        f'Plan: {view["operation"]["plan_id"]}',
        f'Assessment instant: {view["operation"]["evaluated_at"]}',
        f'Current qualification as of: {current["as_of"]}',
        f'Current plan alignment: {current["plan_alignment"].replace("_", " ")}',
        f'Current selected-evidence qualification: {current["selected_evidence"]["status"].replace("_", " ")}',
    ]
    if "explanation" in view:
        lines.extend(["", view["explanation"]])
    if view["interpretation"] == "limited_without_exact_plan":
        for item in view["raw_result_facts"]:
            lines.append(
                f'  Check identity {item["instance_id"]}: '
                f'{item["historical_outcome"].upper()} — {item.get("reason") or ""}'
            )
            for disposition in item["dependency_dispositions"]:
                lines.append(
                    f'    dependency {disposition["dependency_id"]}: '
                    f'{disposition["disposition"]}'
                )
        return "\n".join(lines)
    if policies := view.get("applicable_policies"):
        lines.extend(["", "Applicable policies:"])
        for policy in policies:
            lines.append(f'  {policy["title"]} ({policy["reference"]})')
    if objectives := view.get("objectives"):
        lines.append("Objectives:")
        for objective in objectives:
            status = (objective["historical_outcome"] or "-").upper()
            lines.append(
                f'  {objective["title"]} ({objective["reference"]}) [{status}]'
            )
            lines.append(f'    {objective["statement"]}')
            if objective["realization"]:
                lines.append(f'    Realization: {objective["realization"]}')
            if objective["realization_based_on"]:
                lines.append(f'    Based on: {objective["realization_based_on"]}')
    if "checks" in view:
        lines.append("Checks:")
        for item in view["checks"]:
            check = item["check"]
            historical = item["historical_result"]
            status = (historical or {}).get("historical_outcome") or "-"
            lines.append(
                f'  {check["title"]} ({check["instance_id"]}) [{status.upper()}]'
            )
            lines.append(f'    Purpose: {check["purpose"]}')
            lines.append(
                "    Effective parameters: "
                + json.dumps(item["effective_parameters"], sort_keys=True, separators=(",", ":"))
            )
            if historical and historical.get("explanation"):
                lines.append(f'    {historical["explanation"]}')
            if historical and historical["historical_outcome"] != "pass":
                lines.append(f'    Severity: {check["severity"]}')
                if check["remediation"]:
                    lines.append(f'    Remediation: {check["remediation"]}')
            if item["policy_alignment"] != "unaltered":
                lines.append(
                    f'    Policy alignment: {item["policy_alignment"].replace("_", " ")}'
                )
            for deviation in item["deviations"]:
                lines.append(
                    f'    Deviation {deviation["id"]} ({deviation["classification"]}): '
                    f'{deviation["rationale"]}; approval {deviation["approval_ref"]}; '
                    f'review after {deviation["review_after"]}'
                )
            for dependency in item["required_evidence"]:
                lines.append(
                    f'    Required evidence: {dependency["evidence_type"]} '
                    f'(max age {dependency["assessed_max_age"]})'
                )
                if dependency.get("assessment_explanation"):
                    lines.append(f'      {dependency["assessment_explanation"]}')
            if historical and historical.get("current_waiver_qualification"):
                waiver = historical["current_waiver_qualification"]
                lines.append(
                    f'    Recorded waiver {waiver["waiver_id"]}: '
                    f'{waiver["qualification"].replace("_", " ")}'
                )
    if excluded := view.get("excluded_checks"):
        lines.append("Excluded checks:")
        for item in excluded:
            lines.append(
                f'  {item["title"]} ({item["instance_id"]}) [EXCLUDED POLICY DISPOSITION]'
            )
            lines.append(f'    Purpose: {item["purpose"]}')
            lines.append(
                "    Effective parameters: "
                + json.dumps(
                    item["effective_parameters"],
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            if item["policy_alignment"] != "unaltered":
                lines.append(
                    f'    Policy alignment: {item["policy_alignment"].replace("_", " ")}'
                )
            for deviation in item["deviations"]:
                lines.append(
                    f'    Deviation {deviation["id"]} ({deviation["classification"]}): '
                    f'{deviation["rationale"]}; approval {deviation["approval_ref"]}; '
                    f'review after {deviation["review_after"]}'
                )
    return "\n".join(lines)
