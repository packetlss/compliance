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

from .assessment_history import (
    ValidatedHistoricalAssessmentContext,
    load_assessment_plans,
    load_result_reports,
)
from .evidence_provenance import evidence_document_digest
from .render_plan import load_json
from .waivers import parse_timestamp


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
ACCOUNTING_DISPOSITIONS = (
    "result_required", "inactive", "unassigned", "no_assessable_policy",
)


def load_retained_evidence(path: Path | None) -> dict[tuple[str, str], JsonObject]:
    """Index optional retained Evidence only by exact ID and document digest.

    Historical interpretation never depends on this input.  No current evidence
    schema is applied: an assessment-time-invalid document may still be the exact
    retained content named by a result-owned disposition.
    """

    if path is None:
        return {}
    if not path.exists():
        raise ValueError(f"retained evidence path does not exist: {path}")
    candidates = [path] if path.is_file() else sorted(path.rglob("*.json"))
    indexed: dict[tuple[str, str], JsonObject] = {}
    for candidate in candidates:
        document = load_json(candidate)
        if not isinstance(document, dict) or document.get("schema") != (
            "compliance.example/evidence/v1"
        ):
            if path.is_file():
                raise ValueError(f"retained evidence input is not Evidence: {path}")
            continue
        evidence_id = document.get("id")
        collector = document.get("collector")
        if (
            not isinstance(evidence_id, str)
            or not evidence_id
            or not isinstance(collector, dict)
            or not isinstance(collector.get("id"), str)
            or not collector["id"]
            or not isinstance(collector.get("version"), str)
            or not collector["version"]
        ):
            raise ValueError(f"retained Evidence lacks bounded collector facts: {candidate}")
        key = (evidence_id, evidence_document_digest(document))
        indexed[key] = document
    return indexed


def _validate_external_refusal_information(document: JsonObject) -> JsonObject:
    """Validate the bounded query shape before binding it to exact history."""

    if not isinstance(document, dict):
        raise ValueError("external refusal information must be a JSON object")
    if set(document) != {"operation_id", "assessment_instant", "refusals"}:
        raise ValueError(
            "external refusal information requires operation_id, "
            "assessment_instant, and refusals only"
        )
    if not isinstance(document["refusals"], list):
        raise ValueError("external refusal information refusals must be a list")
    seen: set[str] = set()
    for item in document["refusals"]:
        if not isinstance(item, dict) or set(item) != {
            "asset_id", "authority", "reference", "reason"
        }:
            raise ValueError(
                "each external refusal requires asset_id, authority, reference, and reason"
            )
        if any(not isinstance(item[field], str) or not item[field].strip() for field in item):
            raise ValueError("external refusal fields must be non-empty strings")
        if item["asset_id"] in seen:
            raise ValueError("duplicate external refusal asset identity")
        seen.add(item["asset_id"])
    return copy.deepcopy(document)


def load_external_refusal_information(path: Path | None) -> JsonObject | None:
    """Load caller-trusted external orchestration facts used only by a query."""

    if path is None:
        return None
    return _validate_external_refusal_information(load_json(path))


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
        no_required_evidence = not evidence["controls"]
        evidence_view = {
            "status": (
                "not_applicable"
                if no_required_evidence
                else "reassessment_due_and_partly_unavailable"
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


def _asset_status(
    member: JsonObject,
    query_instant: str | None,
    groups: list[str],
    external_refusal: JsonObject | None = None,
) -> JsonObject:
    return {
        "asset_id": member["subject_id"],
        "asset_type": member["subject"]["type"],
        "groups": groups,
        "expected_result_slot": _slot(member),
        "historical_outcome": member.get("historical_outcome"),
        "implementation_gap": member["implementation_gap"],
        "historical_interpretation": member["historical_interpretation"],
        "current_qualification": _qualification(member, query_instant),
        "external_refusal": copy.deepcopy(external_refusal),
    }


def _validated_external_refusals(
    context: ValidatedHistoricalAssessmentContext,
    information: JsonObject | None,
) -> list[JsonObject]:
    if information is None:
        return []
    information = _validate_external_refusal_information(information)
    if information["operation_id"] != context.account["operation"]["operation_id"]:
        raise ValueError("external refusal information names a different operation")
    instant = parse_timestamp(
        information["assessment_instant"], field="external refusal assessment instant"
    ).isoformat().replace("+00:00", "Z")
    if instant != context.assessment_instant:
        raise ValueError("external refusal information names a different assessment instant")
    members = {member["subject_id"]: member for member in context.account["members"]}
    rows = []
    for item in information["refusals"]:
        member = members.get(item["asset_id"])
        if member is None:
            raise ValueError("external refusal asset is outside the exact frozen operation")
        if (
            member["accounting_disposition"] != "result_required"
            or member["result_present"]
        ):
            raise ValueError(
                "external refusal information may qualify only a missing expected result slot"
            )
        rows.append(copy.deepcopy(item))
    return sorted(rows, key=lambda item: item["asset_id"])


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
                "implementation_gap": member["implementation_gap"],
            }
            for member in account["members"]
        ],
    }


def _request_text(request: JsonObject) -> str:
    if request["all"]:
        return "all assets"
    parts = []
    if request["subjects"]:
        parts.append("assets " + ", ".join(request["subjects"]))
    if request["groups"]:
        parts.append("groups " + ", ".join(request["groups"]))
    return "; ".join(parts)


def render_run_view(view: JsonObject) -> str:
    summary = view["summary"]
    lines = [
        "Assessment run",
        f'Scope: {_request_text(view["operation"]["request"])}',
        f'Assessment instant: {view["operation"]["evaluated_at"]}',
        (
            f'Exact accounting: {summary["filled_result_slots"]}/'
            f'{summary["expected_result_slots"]} required result slots filled; '
            f'accounting_complete={str(summary["accounting_complete"]).lower()}; '
            f'all_passed={str(summary["all_passed"]).lower()}'
        ),
        "",
        "ASSET  EXPECTATION  RESULT SLOT  HISTORICAL OUTCOME  IMPLEMENTATION GAP",
    ]
    for asset in view["assets"]:
        slot = asset["expected_result_slot"]
        expectation = slot["accounting_disposition"].replace("_", " ").upper()
        presence = (
            "FILLED" if slot["present"] else "MISSING" if slot["required"] else "NOT REQUIRED"
        )
        outcome = (asset["historical_outcome"] or "-").replace("_", " ").upper()
        lines.append(f'{asset["asset_id"]}  {expectation}  {presence}  {outcome}  {"GAP" if asset["implementation_gap"] else "-"}')
    return "\n".join(lines)


def _matches_member_filters(
    member: JsonObject,
    groups: set[str],
    outcomes: set[str],
    alignments: set[str],
    memberships: JsonObject,
) -> bool:
    return (
        (
            not groups
            or any(member["subject_id"] in memberships.get(group, []) for group in groups)
        )
        and (not outcomes or member.get("historical_outcome") in outcomes)
        and (not alignments or member.get("plan_alignment") in alignments)
    )


def _current_qualification_summary(
    members: list[JsonObject],
    query_instant: str | None,
) -> JsonObject:
    qualifications = [_qualification(member, query_instant) for member in members]
    return {
        "assets": len(members),
        "plan_alignment": dict(sorted(Counter(
            item["plan_alignment"] for item in qualifications
        ).items())),
        "selected_evidence": dict(sorted(Counter(
            item["selected_evidence"]["status"] for item in qualifications
        ).items())),
        "recorded_waivers": dict(sorted(Counter(
            waiver["qualification"]
            for item in qualifications
            for waiver in item["recorded_waivers"]
        ).items())),
    }


def _group_status(
    group_id: str,
    all_members: list[JsonObject],
    visible_members: list[JsonObject],
    member_ids: list[str],
    query_instant: str | None,
) -> JsonObject:
    selected = set(member_ids)
    frozen = [
        member for member in all_members
        if member["subject_id"] in selected
    ]
    visible = [
        member for member in visible_members
        if member["subject_id"] in selected
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
            "accounting_dispositions": {
                disposition: sum(
                    member["accounting_disposition"] == disposition
                    for member in frozen
                )
                for disposition in ACCOUNTING_DISPOSITIONS
                if any(
                    member["accounting_disposition"] == disposition
                    for member in frozen
                )
            },
            "expected_result_slots": len(required),
            "filled_result_slots": sum(m["result_present"] for m in required),
            "missing_result_slots": sum(not m["result_present"] for m in required),
            "accounting_complete": group_complete,
            "all_passed": bool(required) and group_interpretable and all(
                m["historical_outcome"] == "pass" and not m["implementation_gap"] for m in required
            ) and len(required) == len(frozen),
        },
        "visible_assets": len(visible),
        "historical_outcomes": {
            outcome: outcomes[outcome]
            for outcome in HISTORICAL_OUTCOMES
            if outcomes[outcome]
        },
        "current_qualification": _current_qualification_summary(
            visible, query_instant
        ),
    }


def build_status_view(
    account: JsonObject,
    *,
    group_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    plan_alignments: list[str] | None = None,
    by_group: bool = False,
    external_refusals: list[JsonObject] | None = None,
) -> JsonObject:
    """Build status from exact accounting and separately derived qualification."""
    selected_groups = set(group_ids or [])
    selected_outcomes = set(outcomes or [])
    selected_alignments = set(plan_alignments or [])
    refusals_by_asset = {
        item["asset_id"]: item for item in (external_refusals or [])
    }
    from .operation import frozen_group_memberships

    memberships = frozen_group_memberships(account["operation"])
    visible = [
        member
        for member in account["members"]
        if _matches_member_filters(
            member,
            selected_groups,
            selected_outcomes,
            selected_alignments,
            memberships,
        )
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
            "request": copy.deepcopy(account["operation"]["request"]),
            "evaluated_at": account["evaluated_at"],
        },
        "query_instant": account["query_instant"],
        "filters": filters,
        "filtered": bool(any(filters.values())),
        "whole_operation": _operation_summary(account),
        "view": "groups" if by_group else "assets",
        "external_orchestration": {
            "refusals": copy.deepcopy(external_refusals or []),
            "note": (
                "Expected result absence is not refusal evidence. Entries here are "
                "separately supplied caller-trusted external orchestration facts."
            ),
        },
    }
    if by_group:
        known_groups = sorted(memberships)
        selected = sorted(selected_groups) if selected_groups else known_groups
        view["groups"] = [
            _group_status(
                group_id,
                account["members"],
                visible,
                memberships[group_id],
                account["query_instant"],
            )
            for group_id in selected
        ]
    else:
        view["assets"] = [
            _asset_status(
                member,
                account["query_instant"],
                [
                    group_id
                    for group_id, member_ids in memberships.items()
                    if member["subject_id"] in member_ids
                ],
                refusals_by_asset.get(member["subject_id"]),
            )
            for member in visible
        ]
    return view


def _filters_line(filters: JsonObject) -> str | None:
    values = []
    for key in ("groups", "outcomes", "plan_alignment", "external_refs", "levels"):
        if filters.get(key):
            values.append(f'{key.replace("_", "-")}=' + ",".join(filters[key]))
    return "Filters: " + "  ".join(values) if values else None


def _counts_text(counts: JsonObject) -> str:
    return ",".join(
        f'{key.replace("_", " ").upper()}={value}' for key, value in counts.items()
    ) or "-"


def _asset_waivers_text(qualification: JsonObject) -> str:
    return ",".join(
        f'{waiver["waiver_id"]}={waiver["qualification"].replace("_", " ").upper()}'
        for waiver in qualification["recorded_waivers"]
    ) or "-"


def render_status_view(view: JsonObject) -> str:
    summary = view["whole_operation"]
    lines = [
        "Assessment status",
        f'Scope: {_request_text(view["operation"]["request"])}',
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
            "GROUP  VISIBLE/FROZEN  EXPECTED/FILLED/MISSING  ACCOUNTING COMPLETE  "
            "DISPOSITIONS  HISTORICAL OUTCOMES  CURRENT PLAN  CURRENT EVIDENCE  "
            "CURRENT WAIVERS"
        )
        for group in view["groups"]:
            frozen = group["frozen_accounting"]
            current = group["current_qualification"]
            lines.append(
                f'{group["group_id"]}  {group["visible_assets"]}/'
                f'{frozen["selected_assets"]}  '
                f'{frozen["expected_result_slots"]}/{frozen["filled_result_slots"]}/'
                f'{frozen["missing_result_slots"]}  '
                f'{str(frozen["accounting_complete"]).upper()}  '
                f'{_counts_text(frozen["accounting_dispositions"])}  '
                f'{_counts_text(group["historical_outcomes"])}  '
                f'{_counts_text(current["plan_alignment"])}  '
                f'{_counts_text(current["selected_evidence"])}  '
                f'{_counts_text(current["recorded_waivers"])}'
            )
        for refusal in view["external_orchestration"]["refusals"]:
            lines.append(
                f'External refusal for {refusal["asset_id"]}: '
                f'{refusal["reason"]} ({refusal["authority"]}; '
                f'{refusal["reference"]})'
            )
        return "\n".join(lines)
    lines.append(
        "ASSET  ACCOUNTING DISPOSITION  RESULT SLOT  HISTORICAL OUTCOME  IMPLEMENTATION GAP  PLAN ALIGNMENT  "
        "CURRENT EVIDENCE  CURRENT WAIVERS  EXTERNAL REFUSAL"
    )
    for asset in view["assets"]:
        slot = asset["expected_result_slot"]
        presence = (
            "FILLED" if slot["present"] else "MISSING" if slot["required"] else "NOT REQUIRED"
        )
        outcome = (asset["historical_outcome"] or "-").replace("_", " ").upper()
        current = asset["current_qualification"]
        lines.append(
            f'{asset["asset_id"]}  '
            f'{slot["accounting_disposition"].replace("_", " ").upper()}  '
            f'{presence}  {outcome}  '
            f'{"GAP" if asset["implementation_gap"] else "-"}  '
            f'{current["plan_alignment"].replace("_", " ").upper()}  '
            f'{current["selected_evidence"]["status"].replace("_", " ").upper()}  '
            f'{_asset_waivers_text(current)}  '
            f'{"RECORDED SEPARATELY" if asset["external_refusal"] else "-"}'
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


def _mapping_policy_titles(
    plan: JsonObject | None,
    item: JsonObject | None,
) -> list[JsonObject]:
    if plan is None or item is None:
        return []
    titles = {
        row["reference"]: row["title"]
        for field in ("resolved_baselines", "resolved_requirement_baselines")
        for row in plan.get(field, [])
    }
    references = {
        provenance["baseline"]
        for provenance in item.get("provenance", [])
        if provenance.get("baseline") in titles
    }
    return [
        {"reference": reference, "title": titles[reference]}
        for reference in sorted(references)
    ]


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
    from .operation import frozen_group_memberships

    reports_by_id = _result_index(reports)
    plans_by_id = _plan_index(assessed_plans)
    memberships = frozen_group_memberships(account["operation"])
    selected_groups = set(group_ids or [])
    selected_outcomes = set(outcomes or [])
    selected_alignments = set(plan_alignments or [])
    selected_refs = set(external_refs or [])
    selected_levels = set(levels or [])
    mappings: list[JsonObject] = []
    for member in account["members"]:
        if selected_groups and not any(
            member["subject_id"] in memberships.get(group, [])
            for group in selected_groups
        ):
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
                        exact_item["implementation_state"]
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
                        "policy_object_title": (
                            exact_item.get("title") if exact_item else None
                        ),
                        "applicable_policies": _mapping_policy_titles(
                            plan, exact_item
                        ),
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
        "MAPPING  LEVEL  ASSET  POLICY OBJECT  POLICY TITLE  HISTORICAL OUTCOME  IMPLEMENTATION GAP  PLAN ALIGNMENT  POLICY ALIGNMENT",
    ])
    for mapping in view["mappings"]:
        outcome = (mapping["historical_outcome"] or "-").replace("_", " ").upper()
        lines.append(
            f'{mapping["external_ref"]}  {mapping["mapping_level"].upper()}  '
            f'{mapping["asset_id"]}  {mapping["policy_object"]}  '
            f'{mapping["policy_object_title"] or "-"}  {outcome}  '
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


def _retained_evidence_enrichment(
    reference: JsonObject,
    retained_evidence: dict[tuple[str, str], JsonObject],
) -> JsonObject | None:
    document = retained_evidence.get(
        (reference["evidence_id"], reference["evidence_digest"])
    )
    if document is None:
        return None
    if (
        "collected_at" in reference
        and document.get("collected_at") != reference["collected_at"]
    ):
        return None
    collector = document["collector"]
    return {
        "match": "exact_evidence_id_and_digest",
        "collector": {
            "id": collector["id"],
            "version": collector["version"],
        },
    }


def _dependency_fact(
    control: JsonObject,
    dependency: JsonObject,
    disposition: JsonObject | None,
    selection: JsonObject | None,
    timeliness: JsonObject | None,
    retained_evidence: dict[tuple[str, str], JsonObject],
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
    if dependency.get("inputs"):
        fact["inputs"] = copy.deepcopy(dependency["inputs"])
    if selection:
        fact["selected_evidence"] = {
            key: selection[key]
            for key in ("evidence_id", "evidence_digest", "collected_at")
        }
        enrichment = _retained_evidence_enrichment(selection, retained_evidence)
        if enrichment is not None:
            fact["selected_evidence"]["retained_evidence"] = enrichment
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
                facts = copy.deepcopy(disposition[key])
                for reference in facts:
                    enrichment = _retained_evidence_enrichment(
                        reference, retained_evidence
                    )
                    if enrichment is not None:
                        reference["retained_evidence"] = enrichment
                fact[key] = facts
    if timeliness is not None:
        fact["current_timeliness"] = timeliness["qualification"]
    return fact


def _policy_attribution(control: JsonObject) -> list[JsonObject]:
    paths = {
        (item["baseline"], item["group"], item["assignment"])
        for item in control["provenance"]
    }
    return [
        {"policy_reference": reference, "group": group, "assignment": assignment}
        for reference, group, assignment in sorted(paths)
    ]


def _check_explanation(
    control: JsonObject,
    result: JsonObject | None,
    dispositions: dict[tuple[str, str], JsonObject],
    selections: dict[tuple[str, str], JsonObject],
    timeliness: dict[tuple[str, str], JsonObject],
    waiver_qualification: dict[str, JsonObject],
    retained_evidence: dict[tuple[str, str], JsonObject],
) -> JsonObject:
    instance_id = control["instance_id"]
    dependencies = [
        _dependency_fact(
            control,
            dependency,
            dispositions.get((instance_id, dependency["id"])),
            selections.get((instance_id, dependency["id"])),
            timeliness.get((instance_id, dependency["id"])),
            retained_evidence,
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
        "policy_attribution": _policy_attribution(control),
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
    *,
    retained_evidence: dict[tuple[str, str], JsonObject] | None = None,
    external_refusal: JsonObject | None = None,
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
        "implementation_gap": member["implementation_gap"],
        "current_qualification": _qualification(member, account["query_instant"]),
        "external_refusal": copy.deepcopy(external_refusal),
    }
    if result is None:
        base["interpretation"] = (
            "exact_result_slot_missing" if slot["required"] else "result_not_required"
        )
        base["explanation"] = (
            "The exact frozen operation requires a result for this asset, but its "
            "slot is missing. No result was synthesized."
            if slot["required"]
            else (
                "The frozen member accounting disposition is "
                f'{slot["accounting_disposition"].replace("_", " ")}; '
                "no result is required."
            )
        )
        if plan is not None:
            base["applicable_policies"] = _applicable_policies(plan)
            base["objectives"] = _objectives(plan, None)
            base["checks"] = [
                _check_explanation(
                    control, None, {}, {}, {}, {}, retained_evidence or {}
                )
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
                "unavailable. Only raw result-owned facts and separately derived "
                "recorded-waiver window qualification are shown; full policy, "
                "dependency-timeliness, roll-up, and plan-alignment interpretation "
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
                retained_evidence or {},
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
            policy = policies.setdefault(
                item["reference"],
                {
                    "title": item["title"],
                    "reference": item["reference"],
                    "kind": kind,
                    "paths": [],
                    "objective_references": [],
                    "check_instance_ids": [],
                },
            )
            path = {"group": item["group"], "assignment": item["assignment"]}
            if path not in policy["paths"]:
                policy["paths"].append(path)
    for control in [*plan["controls"], *plan["excluded_controls"]]:
        for attribution in _policy_attribution(control):
            policy = policies.get(attribution["policy_reference"])
            if policy is not None and control["instance_id"] not in policy["check_instance_ids"]:
                policy["check_instance_ids"].append(control["instance_id"])
    for requirement in plan["requirements"]:
        for attribution in requirement["provenance"]:
            policy = policies.get(attribution["baseline"])
            if policy is None:
                continue
            if requirement["reference"] not in policy["objective_references"]:
                policy["objective_references"].append(requirement["reference"])
            for instance_id in requirement["technical_instance_ids"]:
                if instance_id not in policy["check_instance_ids"]:
                    policy["check_instance_ids"].append(instance_id)
    for policy in policies.values():
        policy["paths"].sort(key=lambda item: (item["group"], item["assignment"]))
        policy["objective_references"].sort()
        policy["check_instance_ids"].sort()
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
            "adoption": requirement.get("adoption", {}).get("status"),
            "implementation_state": requirement["implementation_state"],
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
            "historical_reason": (
                statuses[requirement["reference"]]["reason"]
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
            "policy_attribution": _policy_attribution(control),
            "deviations": copy.deepcopy(control.get("deviations", [])),
        }
        for control in plan["excluded_controls"]
    ]


def render_explanation_view(view: JsonObject) -> str:
    def inline(value: Any) -> str:
        """Escape terminal control characters without changing retained view facts."""
        return json.dumps(str(value), ensure_ascii=False)[1:-1]

    slot = view["expected_result_slot"]
    outcome = (view["historical_outcome"] or "-").replace("_", " ").upper()
    current = view["current_qualification"]
    lines = [
        f'Asset: {view["asset"]["id"]}',
        f'Historical outcome: {outcome}',
        f'Implementation gap: {view["implementation_gap"]}',
        "Exact result slot: " + (
            "filled" if slot["present"] else "missing" if slot["required"] else "not required"
        ),
        "Frozen accounting disposition: "
        + slot["accounting_disposition"].replace("_", " "),
        f'Assessment instant: {view["operation"]["evaluated_at"]}',
        f'Current qualification as of: {current["as_of"]}',
        f'Current plan alignment: {current["plan_alignment"].replace("_", " ")}',
        f'Current selected-evidence qualification: {current["selected_evidence"]["status"].replace("_", " ")}',
        "Current recorded-waiver qualification: " + _asset_waivers_text(current),
    ]
    if "explanation" in view:
        lines.extend(["", view["explanation"]])
    if refusal := view.get("external_refusal"):
        lines.extend([
            "",
            "Separately supplied external orchestration refusal:",
            f'  Authority: {refusal["authority"]}',
            f'  Reference: {refusal["reference"]}',
            f'  Reason: {refusal["reason"]}',
            "  This does not create an AssessmentResult or fill the expected slot.",
        ])
    if view["interpretation"] == "limited_without_exact_plan":
        waiver_qualification = {
            item["instance_id"]: item
            for item in current["recorded_waivers"]
        }
        for item in view["raw_result_facts"]:
            lines.append(
                f'  Check identity {item["instance_id"]}: '
                f'{(item["historical_outcome"] or "-").upper()} — {item.get("reason") or ""}'
            )
            for disposition in item["dependency_dispositions"]:
                lines.append(
                    f'    dependency {disposition["dependency_id"]}: '
                    f'{disposition["disposition"]}'
                )
            if waiver := item.get("waiver"):
                qualification = waiver_qualification.get(item["instance_id"], {})
                lines.append(
                    f'    Recorded waiver {waiver["id"]}: underlying '
                    f'{waiver["underlying_status"].upper()}; valid from '
                    f'{waiver["valid_from"]} until {waiver["expires_at"]}; '
                    f'current qualification '
                    f'{qualification.get("qualification", "unavailable").replace("_", " ")}'
                )
                lines.append(
                    f'      Governance: owner {waiver["owner"]}; approval '
                    f'{waiver["approval_ref"]} by {waiver["approved_by"]} at '
                    f'{waiver["approved_at"]}; rationale {waiver["rationale"]}'
                )
        return "\n".join(lines)
    if policies := view.get("applicable_policies"):
        lines.extend(["", "Applicable policies:"])
        for policy in policies:
            lines.append(f'  {policy["title"]} ({policy["reference"]})')
            for path in policy["paths"]:
                lines.append(
                    f'    Applies via: {path["group"]} -> {path["assignment"]}'
                )
    if objectives := view.get("objectives"):
        lines.append("Objectives:")
        for objective in objectives:
            status = (objective["historical_outcome"] or "-").upper()
            lines.append(
                f'  {objective["title"]} ({objective["reference"]}) [{status}]'
            )
            lines.append(f'    {objective["statement"]}')
            lines.append(
                f'    Implementation: {objective["implementation_state"].replace("_", " ")}'
            )
            if objective["historical_reason"]:
                lines.append(f'    Historical reason: {objective["historical_reason"]}')
            if objective["realization"]:
                lines.append(f'    Realization: {objective["realization"]}')
            if objective["realization_based_on"]:
                lines.append(f'    Based on: {objective["realization_based_on"]}')
            if objective["check_instance_ids"]:
                lines.append(
                    "    Realized by checks: "
                    + ", ".join(objective["check_instance_ids"])
                )
    if "checks" in view:
        lines.append("Checks:")
        policy_titles = {
            policy["reference"]: policy["title"]
            for policy in view.get("applicable_policies", [])
        }
        for item in view["checks"]:
            check = item["check"]
            historical = item["historical_result"]
            status = (historical or {}).get("historical_outcome") or "-"
            lines.append(
                f'  {check["title"]} ({check["instance_id"]}) [{status.upper()}]'
            )
            lines.append(f'    Purpose: {check["purpose"]}')
            for attribution in item["policy_attribution"]:
                reference = attribution["policy_reference"]
                title = policy_titles.get(reference, reference)
                lines.append(
                    f'    Policy: {title} ({reference}); applies via '
                    f'{attribution["group"]} -> {attribution["assignment"]}'
                )
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
                    f'(dependency {dependency["dependency_id"]}, '
                    f'max age {dependency["assessed_max_age"]})'
                )
                if dependency.get("inputs"):
                    lines.append(
                        "      Governed dependency inputs: "
                        + json.dumps(
                            dependency["inputs"],
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                selected = dependency.get("selected_evidence", {})
                if enrichment := selected.get("retained_evidence"):
                    collector = enrichment["collector"]
                    lines.append(
                        "      Retained Evidence collector (exact ID+digest match): "
                        f'{collector["id"]}@{collector["version"]}'
                    )
                if dependency.get("assessment_explanation"):
                    lines.append(f'      {dependency["assessment_explanation"]}')
                if dependency["selection"] == "invalid":
                    for diagnostic in dependency["diagnostics"]:
                        lines.append(
                            f'      Rejected evidence: {inline(diagnostic["evidence_id"])}; '
                            f'digest {diagnostic["evidence_digest"]}'
                        )
                        lines.append(
                            f'        Schema constraint: keyword '
                            f'{diagnostic["keyword"]} at '
                            f'{diagnostic["schema_path"]}; '
                            f'code {diagnostic["code"]}'
                        )
                        if enrichment := diagnostic.get("retained_evidence"):
                            collector = enrichment["collector"]
                            lines.append(
                                "        Retained Evidence collector (exact ID+digest match): "
                                f'{collector["id"]}@{collector["version"]}'
                            )
                elif dependency["selection"] == "ambiguous":
                    lines.append("      Selected evidence: none")
                    for candidate in dependency["candidates"]:
                        lines.append(
                            f'      Competing candidate: {inline(candidate["evidence_id"])}; '
                            f'digest {candidate["evidence_digest"]}; '
                            f'collected at {candidate["collected_at"]}'
                        )
                        if enrichment := candidate.get("retained_evidence"):
                            collector = enrichment["collector"]
                            lines.append(
                                "        Retained Evidence collector (exact ID+digest match): "
                                f'{collector["id"]}@{collector["version"]}'
                            )
            if historical and historical.get("current_waiver_qualification"):
                waiver = historical["current_waiver_qualification"]
                lines.append(
                    f'    Recorded waiver {waiver["waiver_id"]}: '
                    f'{waiver["qualification"].replace("_", " ")}'
                )
    if excluded := view.get("excluded_checks"):
        lines.append("Excluded checks:")
        policy_titles = {
            policy["reference"]: policy["title"]
            for policy in view.get("applicable_policies", [])
        }
        for item in excluded:
            lines.append(
                f'  {item["title"]} ({item["instance_id"]}) [EXCLUDED POLICY DISPOSITION]'
            )
            lines.append(f'    Purpose: {item["purpose"]}')
            for attribution in item["policy_attribution"]:
                reference = attribution["policy_reference"]
                title = policy_titles.get(reference, reference)
                lines.append(
                    f'    Policy: {title} ({reference}); applies via '
                    f'{attribution["group"]} -> {attribution["assignment"]}'
                )
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


def _validate_context_groups(
    context: ValidatedHistoricalAssessmentContext,
    group_ids: list[str] | None,
) -> None:
    from .operation import frozen_group_memberships

    known = set(frozen_group_memberships(context.account["operation"]))
    unknown = sorted(set(group_ids or []) - known)
    if unknown:
        raise ValueError("unknown frozen operation group(s): " + ", ".join(unknown))


def project_status_view(
    context: ValidatedHistoricalAssessmentContext,
    *,
    group_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    plan_alignments: list[str] | None = None,
    by_group: bool = False,
    external_refusal_information: JsonObject | None = None,
) -> JsonObject:
    """Supported Assessment status projection from validated exact history."""

    _validate_context_groups(context, group_ids)
    refusals = _validated_external_refusals(
        context, external_refusal_information
    )
    return build_status_view(
        context.account,
        group_ids=group_ids,
        outcomes=outcomes,
        plan_alignments=plan_alignments,
        by_group=by_group,
        external_refusals=refusals,
    )


def project_mappings_view(
    context: ValidatedHistoricalAssessmentContext,
    *,
    group_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    plan_alignments: list[str] | None = None,
    external_refs: list[str] | None = None,
    levels: list[str] | None = None,
) -> JsonObject:
    """Supported attributable mappings projection from validated exact history."""

    _validate_context_groups(context, group_ids)
    return build_mappings_view(
        context.account,
        list(context.reports),
        list(context.assessed_plans),
        group_ids=group_ids,
        outcomes=outcomes,
        plan_alignments=plan_alignments,
        external_refs=external_refs,
        levels=levels,
    )


def project_explanation_view(
    context: ValidatedHistoricalAssessmentContext,
    asset_id: str,
    *,
    retained_evidence: dict[tuple[str, str], JsonObject] | None = None,
    external_refusal_information: JsonObject | None = None,
) -> JsonObject:
    """Supported one-asset explanation projection from validated exact history."""

    selected = [
        member
        for member in context.account["members"]
        if member["subject_id"] == asset_id
    ]
    if not selected:
        raise ValueError("asset is absent from frozen operation selection")
    member = selected[0]
    refusals = {
        item["asset_id"]: item
        for item in _validated_external_refusals(
            context, external_refusal_information
        )
    }
    return build_explanation_view(
        context.account,
        member,
        context.plans_by_id.get(member["plan_id"]),
        context.reports_by_id.get(member["result_id"]),
        retained_evidence=retained_evidence,
        external_refusal=refusals.get(asset_id),
    )
