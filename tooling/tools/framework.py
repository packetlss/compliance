"""Project-governed framework-obligation declarations and exact-history views.

Declarations are deliberately outside the policy and assessment artifact domains.
This module validates their own closed ledger and interprets it only from supplied,
already validated frozen plans and results.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .assessment_history import ValidatedHistoricalAssessmentContext
from .assessment_provenance import digest
from .operation import frozen_group_memberships
from .render_plan import (
    load_inventory_catalog, load_policy_catalogs, load_requirement_catalogs,
    load_resource_documents,
)

DECLARATION_SCHEMA = "compliance.example/framework-obligation-declaration/v1alpha1"
DECLARATION_DIGEST_ALGORITHM = "compliance.example/framework-obligation-declaration-digest/v1alpha1"
STATUS_SCHEMA = "compliance.example/framework-satisfaction-status/v1alpha1"
EXPLANATION_SCHEMA = "compliance.example/framework-satisfaction-explanation/v1alpha1"


def schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas/framework-obligation-declaration-v1alpha1.schema.json"


def _schema() -> dict[str, Any]:
    return json.loads(schema_path().read_text(encoding="utf-8"))


def _error(document: dict, source: Path) -> None:
    errors = sorted(Draft202012Validator(_schema(), format_checker=FormatChecker()).iter_errors(document), key=lambda e: (tuple(str(x) for x in e.absolute_path), e.message))
    if errors:
        rendered = "; ".join(f"/{'/'.join(str(x) for x in e.absolute_path)}: {e.message}" for e in errors)
        raise ValueError(f"invalid FrameworkObligationDeclaration in {source}: {rendered}")


def _refs(values: list[dict]) -> list[str]:
    return [item["name"] for item in values]


def _pin_key(pin: dict) -> tuple:
    return (pin["reference"], pin["digest"], tuple(_refs(pin["groupRefs"])))


def declaration_projection(document: dict) -> dict:
    """Return the sole declaration identity projection, with owned sets ordered."""
    public = copy.deepcopy(document)
    spec = public["spec"]
    spec["scope"]["groupRefs"] = sorted(spec["scope"]["groupRefs"], key=lambda x: x["name"])
    for obligation in spec["obligations"]:
        basis = obligation["basis"]
        for field in ("objectivePins", "directPolicyPins"):
            if field in basis:
                for pin in basis[field]:
                    pin["groupRefs"] = sorted(pin["groupRefs"], key=lambda x: x["name"])
                basis[field] = sorted(basis[field], key=_pin_key)
    spec["obligations"] = sorted(spec["obligations"], key=lambda x: x["id"])
    return {"domain": DECLARATION_DIGEST_ALGORITHM, "declaration": public}


def declaration_digest(document: dict) -> str:
    return digest(declaration_projection(document))


def _validate_semantics(document: dict, source: Path) -> None:
    metadata, spec = document["metadata"], document["spec"]
    if not metadata["revision"].strip():
        raise ValueError(f"declaration revision is empty: {source}")
    scope_refs = _refs(spec["scope"]["groupRefs"])
    if len(scope_refs) != len(set(scope_refs)):
        raise ValueError(f"duplicate declaration scope group reference: {source}")
    ids = [row["id"] for row in spec["obligations"]]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate framework obligation identity: {source}")
    for row in spec["obligations"]:
        if row["disposition"] != "applicable" and not row.get("rationale"):
            raise ValueError(f"excluded/not-applicable obligation requires rationale: {row['id']}")
        basis = row["basis"]
        category = basis["category"]
        has_governance = category in ("governance-declared", "mixed-governance-assessed")
        has_objective = category == "evidence-assessed-objective"
        has_direct = category == "direct-technical-policy"
        if has_governance != ("governance" in basis):
            raise ValueError(f"governance portion does not match basis category: {row['id']}")
        if category != "mixed-governance-assessed" and has_objective != bool(basis.get("objectivePins")):
            raise ValueError(f"objective pins do not match basis category: {row['id']}")
        if category != "mixed-governance-assessed" and has_direct != bool(basis.get("directPolicyPins")):
            raise ValueError(f"direct-policy pins do not match basis category: {row['id']}")
        if category == "mixed-governance-assessed" and not (basis.get("objectivePins") or basis.get("directPolicyPins")):
            raise ValueError(f"mixed basis requires an assessed objective or direct-policy pin: {row['id']}")
        if has_governance:
            governance = basis["governance"]
            determination = governance["determination"]
            if determination in ("affirmative", "negative") and "review" not in governance:
                raise ValueError(f"reviewed governance determination lacks review facts: {row['id']}")
        for field in ("objectivePins", "directPolicyPins"):
            pins = basis.get(field, [])
            keys = [_pin_key(pin) for pin in pins]
            if len(keys) != len(set(keys)):
                raise ValueError(f"duplicate {field} policy pin: {row['id']}")
            references = [pin["reference"] for pin in pins]
            if len(references) != len(set(references)):
                raise ValueError(f"contradictory {field} policy pin reference: {row['id']}")
            for pin in pins:
                groups = _refs(pin["groupRefs"])
                if len(groups) != len(set(groups)) or not set(groups).issubset(scope_refs):
                    raise ValueError(f"policy pin scope is duplicate or outside declared scope: {row['id']}")


def load_declarations(path: Path) -> list[dict]:
    if not path.exists():
        raise ValueError(f"framework declaration path does not exist: {path}")
    declarations = []
    for source, document in load_resource_documents(path):
        _error(document, source)
        _validate_semantics(document, source)
        declaration = copy.deepcopy(document)
        declaration["digestAlgorithm"] = DECLARATION_DIGEST_ALGORITHM
        declaration["digest"] = declaration_digest(document)
        declaration["_source"] = str(source)
        declarations.append(declaration)
    keys = [(d["metadata"]["name"], d["metadata"]["revision"]) for d in declarations]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate framework declaration identity/revision")
    return sorted(declarations, key=lambda d: (d["metadata"]["name"], d["metadata"]["revision"]))


def select_declaration(declarations: list[dict], name: str, revision: str | None = None) -> dict:
    selected = [d for d in declarations if d["metadata"]["name"] == name and (revision is None or d["metadata"]["revision"] == revision)]
    if len(selected) != 1:
        raise ValueError("declaration selection must identify exactly one name and revision")
    return selected[0]


def _baseline_includes(reference: str, required: str, baselines: dict, seen: frozenset[str] = frozenset()) -> bool:
    """Whether a currently assigned baseline retains a pinned baseline in its ancestry."""
    if reference == required:
        return True
    if reference in seen:
        return False
    baseline = baselines.get(reference)
    if baseline is None or baseline.get("kind") != "BaselineOverlay":
        return False
    for parent in baseline.get("spec", {}).get("extends", []):
        parent_reference = parent["baseline"]
        parent_resource = baselines.get(parent_reference)
        if (
            parent_resource is not None
            and parent_resource.get("_digest") == parent["digest"]
            and _baseline_includes(parent_reference, required, baselines, seen | {reference})
        ):
            return True
    return False


def _resolved_baseline_matches_pin(item: dict, pin: dict, group_names: list[str]) -> bool:
    return item.get("group") in group_names and any(
        entry.get("reference") == pin["reference"] and entry.get("digest") == pin["digest"]
        for entry in item.get("lineage", [])
    )


def validate_project_declarations(declarations: list[dict], *, inventory: Path, assignments: Path, resource_schema: Path, policy_sources) -> None:
    """Admit declarations against current project inputs without changing their IDs."""
    _, groups, project_assignments = load_inventory_catalog(inventory, assignments, resource_schema)
    group_ids = {group["id"] for group in groups}
    controls, baselines, errors = load_policy_catalogs(policy_sources)
    requirements, requirement_baselines, _, requirement_errors = load_requirement_catalogs(policy_sources, controls)
    if errors or requirement_errors:
        raise ValueError("framework declaration admission requires a valid policy catalog")
    for declaration in declarations:
        scope = set(_refs(declaration["spec"]["scope"]["groupRefs"]))
        unknown = sorted(scope - group_ids)
        if unknown:
            raise ValueError("declaration references unknown inventory group(s): " + ", ".join(unknown))
        for obligation in declaration["spec"]["obligations"]:
            for pin in obligation["basis"].get("objectivePins", []):
                resource = requirements.get(pin["reference"])
                if resource is None:
                    raise ValueError(f"objective pin is missing or wrong kind: {pin['reference']}")
                if resource["_digest"] != pin["digest"]:
                    raise ValueError(f"objective pin digest is stale: {pin['reference']}")
                for group in _refs(pin["groupRefs"]):
                    assigned = [assignment for assignment in project_assignments if assignment["target"]["group"] == group]
                    if not any(
                        pin["reference"] in {
                            requirement_pin["requirement"]
                            for requirement_pin in requirement_baselines[baseline]["spec"].get("requirements", [])
                        }
                        for assignment in assigned for baseline in assignment["baselines"]
                        if baseline in requirement_baselines
                    ):
                        raise ValueError(f"objective pin is incoherent with project group binding: {pin['reference']} / {group}")
            for pin in obligation["basis"].get("directPolicyPins", []):
                resource = baselines.get(pin["reference"])
                if resource is None:
                    raise ValueError(f"direct-policy pin is missing or wrong kind: {pin['reference']}")
                if resource["_digest"] != pin["digest"]:
                    raise ValueError(f"direct-policy pin digest is stale: {pin['reference']}")
                for group in _refs(pin["groupRefs"]):
                    if not any(
                        any(
                            _baseline_includes(assigned, pin["reference"], baselines)
                            for assigned in assignment["baselines"]
                        )
                        for assignment in project_assignments
                        if assignment["target"]["group"] == group
                    ):
                        raise ValueError(f"direct-policy pin is incoherent with project group binding: {pin['reference']} / {group}")


def _basis_state(obligation: dict, account: dict, plans: dict, reports: dict) -> tuple[str, list[dict]]:
    basis = obligation["basis"]
    category = basis["category"]
    facts: list[dict] = []
    states: list[str] = []
    if category in ("governance-declared", "mixed-governance-assessed"):
        governance = basis["governance"]
        determination = governance["determination"]
        state = {"affirmative": "pass", "negative": "fail", "not_established": "unknown"}[determination]
        facts.append({"kind": "governance", **copy.deepcopy(governance), "state": state})
        states.append(state)
    memberships = frozen_group_memberships(account["operation"])
    member_by_id = {member["subject_id"]: member for member in account["members"]}
    for field, kind in (("objectivePins", "objective"), ("directPolicyPins", "direct-policy")):
        for pin in basis.get(field, []):
            group_names = _refs(pin["groupRefs"])
            if any(group not in memberships for group in group_names):
                raise ValueError("operation anchor lacks required frozen group scope witness")
            subjects = sorted({subject for group in group_names for subject in memberships[group]})
            pin_states = []
            subject_support = []
            if not subjects:
                pin_states.append("unknown")
                missing_scope_reason = "declared_group_scope_has_no_frozen_subjects"
            else:
                missing_scope_reason = None
            for subject in subjects:
                member = member_by_id.get(subject)
                if member is None or member.get("accounting_disposition") != "result_required":
                    pin_states.append("unknown")
                    subject_support.append({
                        "subject_id": subject, "state": "unknown",
                        "reason": "missing_exact_result_slot",
                    })
                    continue
                qualification = {
                    key: copy.deepcopy(member[key])
                    for key in ("plan_alignment", "evidence_timeliness", "recorded_waiver_qualification")
                    if key in member
                }
                if member.get("historical_interpretation") != "validated" or member.get("result_id") is None:
                    pin_states.append("unknown")
                    subject_support.append({
                        "subject_id": subject, "state": "unknown",
                        "reason": "exact_retained_result_support_unavailable",
                        "qualifications": qualification,
                    })
                    continue
                plan, report = plans.get(member.get("plan_id")), reports.get(member["result_id"])
                if plan is None or report is None:
                    pin_states.append("unknown")
                    subject_support.append({
                        "subject_id": subject, "state": "unknown",
                        "reason": "exact_retained_plan_or_result_unavailable",
                        "qualifications": qualification,
                    })
                    continue
                if kind == "objective":
                    found = [item for item in plan["requirements"] if item["reference"] == pin["reference"] and item["digest"] == pin["digest"] and any(p["group"] in group_names for p in item["provenance"])]
                    outcome_rows = [item for item in report["requirement_assessments"] if item["requirement"] == pin["reference"]]
                    technical_instance_ids = {
                        instance_id
                        for item in found
                        for instance_id in item.get("technical_instance_ids", [])
                    }
                    technical_outcomes = [
                        item for item in report.get("results", [])
                        if item["instance_id"] in technical_instance_ids
                    ]
                else:
                    found = [
                        item for item in plan["resolved_baselines"]
                        if _resolved_baseline_matches_pin(item, pin, group_names)
                    ]
                    terminal_references = {item["reference"] for item in found}
                    control_ids = {
                        control["instance_id"] for control in plan["controls"]
                        if any(
                            provenance.get("baseline") in terminal_references
                            and provenance.get("group") in group_names
                            for provenance in control["provenance"]
                        ) and any(
                            lineage.get("baseline") == pin["reference"]
                            for lineage in control.get("lineage", [])
                        )
                    }
                    outcome_rows = [item for item in report["results"] if item["instance_id"] in control_ids]
                    technical_outcomes = []
                    if not control_ids:
                        found = []
                outcomes = [item["status"] for item in outcome_rows]
                if not found:
                    pin_states.append("unknown")
                    subject_support.append({
                        "subject_id": subject, "state": "unknown",
                        "reason": "pin_absent_from_exact_retained_plan_provenance",
                        "qualifications": qualification,
                    })
                    continue
                if not outcomes:
                    pin_states.append("unknown")
                    subject_support.append({
                        "subject_id": subject, "state": "unknown",
                        "reason": "pin_has_no_exact_retained_assessment_outcome",
                        "qualifications": qualification,
                    })
                    continue
                elif "fail" in outcomes:
                    pin_states.append("fail")
                elif all(outcome == "pass" for outcome in outcomes):
                    pin_states.append("pass")
                else:
                    pin_states.append("unknown")
                subject_support.append({
                    "subject_id": subject,
                    "outcomes": copy.deepcopy(outcome_rows),
                    **(
                        {"technical_outcomes": copy.deepcopy(technical_outcomes)}
                        if kind == "objective" else {}
                    ),
                    "qualifications": qualification,
                })
            state = "fail" if "fail" in pin_states else "pass" if pin_states and all(s == "pass" for s in pin_states) else "unknown"
            facts.append({
                "kind": kind,
                "reference": pin["reference"],
                "digest": pin["digest"],
                "groups": group_names,
                "subjects": subjects,
                "state": state,
                **({"reason": missing_scope_reason} if missing_scope_reason else {}),
                "subject_support": subject_support,
            })
            states.append(state)
    return ("fail" if "fail" in states else "pass" if states and all(s == "pass" for s in states) else "unknown"), facts


def _declared_basis_support(obligation: dict) -> list[dict]:
    """Expose excluded/N/A basis declarations without evaluating historical support."""
    basis = obligation["basis"]
    facts = []
    if "governance" in basis:
        facts.append({"kind": "governance", **copy.deepcopy(basis["governance"])})
    for field, kind in (("objectivePins", "objective"), ("directPolicyPins", "direct-policy")):
        for pin in basis.get(field, []):
            facts.append({
                "kind": kind,
                "reference": pin["reference"],
                "digest": pin["digest"],
                "groups": _refs(pin["groupRefs"]),
            })
    return facts


def _build_projection(declaration: dict, account: dict, plans: list[dict], reports: list[dict]) -> dict:
    plan_by_id = {plan["id"]: plan for plan in plans}
    report_by_id = {report["id"]: report for report in reports}
    scope = set(_refs(declaration["spec"]["scope"]["groupRefs"]))
    witness = account["operation"]["selection_witness"]
    witness_groups = {
        group["id"] for group in witness.get("groups", [])
    } if witness.get("mode") == "groups" else set()
    if not scope.issubset(witness_groups):
        raise ValueError("operation anchor lacks required frozen group scope witness")
    rows = []
    for obligation in declaration["spec"]["obligations"]:
        required = obligation["disposition"] == "applicable"
        if required:
            state, support = _basis_state(obligation, account, plan_by_id, report_by_id)
            effective = state
        else:
            support = _declared_basis_support(obligation)
            effective = "excluded"
        rows.append({"id": obligation["id"], "disposition": obligation["disposition"], "interpretation": obligation["interpretation"], "basis": obligation["basis"]["category"], "state": effective, "support": support, **({"rationale": obligation["rationale"]} if "rationale" in obligation else {})})
    required_states = [row["state"] for row in rows if row["disposition"] == "applicable"]
    state = "not_satisfied" if "fail" in required_states else "not_established" if not required_states or "unknown" in required_states else "satisfied"
    return {"declaration": {"name": declaration["metadata"]["name"], "revision": declaration["metadata"]["revision"], "digestAlgorithm": declaration["digestAlgorithm"], "digest": declaration["digest"]}, "framework": copy.deepcopy(declaration["spec"]["framework"]), "scope": copy.deepcopy(declaration["spec"]["scope"]), "operation": {"operation_id": account["operation"]["operation_id"], "evaluated_at": account["evaluated_at"], "query_instant": account.get("query_instant")}, "state": state, "statement": {"satisfied": "Satisfied under declared coverage.", "not_satisfied": "Not satisfied under declared coverage.", "not_established": "Satisfaction not established under declared coverage."}[state], "obligations": rows}


def build_status(declaration: dict, account: dict, plans: list[dict], reports: list[dict]) -> dict:
    """Build the concise bounded framework-ledger projection."""
    detailed = _build_projection(declaration, account, plans, reports)
    return {
        "schema": STATUS_SCHEMA,
        **{key: copy.deepcopy(detailed[key]) for key in (
            "declaration", "framework", "scope", "operation", "state", "statement",
        )},
        "obligations": [
            {key: row[key] for key in ("id", "disposition", "basis", "state")}
            for row in detailed["obligations"]
        ],
    }


def build_explanation(declaration: dict, account: dict, plans: list[dict], reports: list[dict]) -> dict:
    """Build the obligation-by-obligation causal support projection."""
    return {
        "schema": EXPLANATION_SCHEMA,
        **_build_projection(declaration, account, plans, reports),
    }


def project_status(
    declaration: dict,
    context: ValidatedHistoricalAssessmentContext,
) -> dict:
    """Project framework status over an admitted exact Assessment context."""

    return build_status(
        declaration,
        context.account,
        list(context.assessed_plans),
        list(context.reports),
    )


def project_explanation(
    declaration: dict,
    context: ValidatedHistoricalAssessmentContext,
) -> dict:
    """Project framework explanation over an admitted exact Assessment context."""

    return build_explanation(
        declaration,
        context.account,
        list(context.assessed_plans),
        list(context.reports),
    )


def render_status(document: dict) -> str:
    lines = [document["statement"], f"Declaration: {document['declaration']['name']}@{document['declaration']['revision']}", f"Operation: {document['operation']['operation_id']}", "", "OBLIGATION  DISPOSITION     BASIS                         STATE"]
    for row in document["obligations"]:
        lines.append(f"{row['id']:<11} {row['disposition']:<15} {row['basis']:<29} {row['state'].upper()}")
    return "\n".join(lines)


_SUPPORT_REASONS = {
    "declared_group_scope_has_no_frozen_subjects": (
        "The declared group scope has no subjects in the exact frozen operation."
    ),
    "missing_exact_result_slot": (
        "The frozen subject has no exact required result slot."
    ),
    "exact_retained_result_support_unavailable": (
        "Exact retained result support is unavailable."
    ),
    "exact_retained_plan_or_result_unavailable": (
        "The exact retained plan or result is unavailable."
    ),
    "pin_absent_from_exact_retained_plan_provenance": (
        "The declared policy pin is absent from exact retained plan provenance."
    ),
    "pin_has_no_exact_retained_assessment_outcome": (
        "The declared policy pin has no exact retained assessment outcome."
    ),
}


def _words(value: str) -> str:
    return value.replace("_", " ")


_PLAN_ALIGNMENT_TEXT = {
    "plan_aligned": "Aligned with the supplied comparison operation.",
    "different_plan": "Different from the supplied comparison operation.",
    "plan_alignment_unavailable": "Unavailable; no comparable plan was supplied.",
}

_WAIVER_QUALIFICATION_TEXT = {
    "within_window": "within its recorded validity window",
    "expired": "expired",
    "not_yet_in_window": "not yet within its recorded validity window",
}


def _count_text(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _render_evidence_timeliness(lines: list[str], evidence: dict) -> None:
    if evidence.get("qualification") == "unavailable":
        lines.append("        Evidence timeliness: Unavailable.")
        return
    dependencies = evidence.get("dependencies", [])
    controls = evidence.get("controls", [])
    timely = evidence.get("timely_selected_dependencies", 0)
    stale = evidence.get("stale_selected_dependencies", 0)
    unavailable = evidence.get("unavailable_required_dependencies", 0)
    if not controls and not dependencies:
        lines.append("        Evidence timeliness: Not applicable; no required evidence dependencies.")
    elif stale and unavailable:
        lines.append(
            "        Evidence stale — reassessment due; timeliness unavailable for "
            f"{_count_text(unavailable, 'required dependency')}."
        )
    elif stale:
        lines.append(
            "        Evidence stale — reassessment due for "
            f"{_count_text(stale, 'selected dependency')}."
        )
    elif unavailable:
        lines.append(
            "        Evidence timeliness unavailable for "
            f"{_count_text(unavailable, 'required dependency')}; "
            f"{_count_text(timely, 'selected dependency')} remains within recorded age limits."
        )
    else:
        lines.append(
            "        Selected evidence within recorded age limits: "
            f"{_count_text(timely, 'dependency')}."
        )
    for dependency in dependencies:
        qualification = dependency.get("qualification")
        condition = {
            "timely": "Timely",
            "stale": "Stale — reassessment due",
            "unavailable": "Timeliness unavailable",
        }.get(qualification, "Timeliness unavailable")
        details = []
        if dependency.get("evidence_id"):
            details.append(f"evidence {dependency['evidence_id']}")
        if dependency.get("collected_at"):
            details.append(f"collected {dependency['collected_at']}")
        if dependency.get("recorded_max_age"):
            details.append(f"recorded maximum age {dependency['recorded_max_age']}")
        suffix = f"; {', '.join(details)}" if details else ""
        lines.append(
            f"        Dependency {dependency.get('dependency_id', 'unknown')} for "
            f"{dependency.get('instance_id', 'unknown')}: {condition}{suffix}."
        )


def _render_recorded_waivers(lines: list[str], qualification: dict) -> None:
    waivers = qualification.get("waivers", [])
    if not waivers:
        lines.append("        Recorded waivers: None.")
        return
    for waiver in waivers:
        condition = _WAIVER_QUALIFICATION_TEXT.get(
            waiver.get("qualification"), "qualification unavailable",
        )
        lines.append(
            f"        Recorded waiver {waiver['waiver_id']} for {waiver['instance_id']}: "
            f"{condition}; valid from {waiver['valid_from']} until "
            f"{waiver['expires_at']} (exclusive)."
        )


def _render_qualifications(
    lines: list[str], qualifications: dict, query_instant: str | None,
) -> None:
    if not qualifications:
        return
    heading = "      Current qualification"
    if query_instant:
        heading += f" as of {query_instant}"
    lines.append(heading + ":")
    alignment = qualifications.get("plan_alignment", "plan_alignment_unavailable")
    lines.append(
        "        Plan alignment: "
        + _PLAN_ALIGNMENT_TEXT.get(alignment, "Unavailable.")
    )
    _render_evidence_timeliness(lines, qualifications.get("evidence_timeliness", {
        "qualification": "unavailable",
    }))
    _render_recorded_waivers(
        lines, qualifications.get("recorded_waiver_qualification", {}),
    )


def _render_outcomes(lines: list[str], label: str, outcomes: list[dict]) -> None:
    for outcome in outcomes:
        identity = outcome.get("requirement", outcome.get("instance_id", "outcome"))
        reason = f" — {outcome['reason']}" if outcome.get("reason") else ""
        lines.append(f"      {label} {identity}: {outcome['status'].upper()}{reason}")


def render_explanation(document: dict) -> str:
    """Render readable causal support without re-resolving current policy."""
    lines = [
        document["statement"],
        f"Declaration: {document['declaration']['name']}@{document['declaration']['revision']}",
        f"Operation: {document['operation']['operation_id']}",
        f"Declared scope: {document['scope']['id']}",
        "Scope groups: " + ", ".join(_refs(document["scope"]["groupRefs"])),
    ]
    for row in document["obligations"]:
        lines.extend([
            "",
            f"OBLIGATION {row['id']}",
            f"  Disposition: {_words(row['disposition'])}",
            f"  Interpretation: {row['interpretation']}",
            f"  Basis: {row['basis']}",
            f"  State: {row['state'].upper()}",
        ])
        if row.get("rationale"):
            lines.append(f"  Rationale: {row['rationale']}")
        for support in row["support"]:
            if support["kind"] == "governance":
                lines.extend([
                    f"  Governance subject: {support['subject']}",
                    f"    Governance owner: {support['owner']}",
                    f"    Determination: {_words(support['determination'])}",
                ])
                review = support.get("review")
                if review:
                    lines.extend([
                        f"    Review reference: {review['reference']}",
                        f"    Approved by: {review['approvedBy']}",
                        f"    Approved at: {review['approvedAt']}",
                    ])
                else:
                    lines.append("    Review: not recorded; governance support is not established.")
                continue
            label = "Objective" if support["kind"] == "objective" else "Direct policy"
            lines.extend([
                f"  {label}: {support['reference']}",
                f"    Pinned digest: {support['digest']}",
                f"    Declared groups: {', '.join(support['groups'])}",
            ])
            if row["disposition"] != "applicable":
                lines.append(
                    "    Exact assessment support: not required for this declared disposition."
                )
                continue
            lines.extend([
                f"    Frozen subjects: {', '.join(support['subjects']) or 'none'}",
                f"    Support state: {support['state'].upper()}",
            ])
            if support.get("reason"):
                lines.append(f"    Reason: {_SUPPORT_REASONS[support['reason']]}")
            for subject in support["subject_support"]:
                lines.append(f"    Frozen subject: {subject['subject_id']}")
                if subject.get("reason"):
                    lines.append(f"      Reason: {_SUPPORT_REASONS[subject['reason']]}")
                if support["kind"] == "objective":
                    _render_outcomes(lines, "Objective outcome", subject.get("outcomes", []))
                    _render_outcomes(lines, "Technical outcome", subject.get("technical_outcomes", []))
                else:
                    _render_outcomes(lines, "Technical outcome", subject.get("outcomes", []))
                _render_qualifications(
                    lines,
                    subject.get("qualifications", {}),
                    document["operation"].get("query_instant"),
                )
    return "\n".join(lines)
