"""Ephemeral current coverage projections over the existing planner."""

from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any

from .operation import plan_disposition
from .render_plan import render_plan


JsonObject = dict[str, Any]
COVERAGE_CLASSES = (
    "result_required",
    "inactive",
    "unassigned",
    "no_assessable_policy",
    "invalid_resolution",
)


def _coverage_class(plan: JsonObject) -> str:
    disposition = plan_disposition(plan)
    return "invalid_resolution" if disposition == "invalid" else disposition


def resolve_coverage_plans(
    subjects: dict[str, JsonObject],
    groups: list[JsonObject],
    assignments: list[JsonObject],
    policy_sources: Any,
    *,
    config: Any = None,
) -> list[JsonObject]:
    """Resolve current policy once per supplied asset through the sole planner."""
    return [
        render_plan(
            subjects[asset_id],
            groups,
            assignments,
            policy_sources,
            config=config,
        )
        for asset_id in sorted(subjects)
    ]


def _counts(plans: list[JsonObject]) -> JsonObject:
    values = Counter(_coverage_class(plan) for plan in plans)
    return {name: values[name] for name in COVERAGE_CLASSES}


def _asset_row(plan: JsonObject) -> JsonObject:
    coverage_class = _coverage_class(plan)
    valid = plan["resolution"]["status"] == "valid"
    return {
        "asset_id": plan["subject"]["id"],
        "asset_type": plan["subject"]["type"],
        "lifecycle": plan["subject"]["status"],
        "coverage_class": coverage_class,
        "group_count": len(plan["resolved_groups"]),
        "assignment_count": len(plan["assignments"]),
        "assessable_check_count": (
            len(plan["controls"]) if coverage_class == "result_required" else 0
        ),
        "excluded_check_count": len(plan["excluded_controls"]) if valid else 0,
        "objective_count": len(plan["requirements"]) if valid else 0,
        "resolution_error_count": len(plan["resolution"]["errors"]),
    }


def _assignment_contributes(item: JsonObject, assignment_id: str) -> bool:
    return any(
        provenance.get("assignment") == assignment_id
        for provenance in item.get("provenance", [])
    )


def build_coverage_list(
    resource: str,
    subjects: dict[str, JsonObject],
    groups: list[JsonObject],
    assignments: list[JsonObject],
    plans: list[JsonObject],
) -> JsonObject:
    """Build deterministic current coverage views without persisting plan state."""
    plans_by_asset = {plan["subject"]["id"]: plan for plan in plans}
    ordered_plans = [plans_by_asset[asset_id] for asset_id in sorted(subjects)]
    if resource == "assets":
        return {
            "schema": "compliance.example/coverage-assets-view/v1alpha1",
            "summary": {
                "asset_count": len(ordered_plans),
                "coverage_classes": _counts(ordered_plans),
            },
            "assets": [_asset_row(plan) for plan in ordered_plans],
        }

    members_by_group: dict[str, list[JsonObject]] = {
        group["id"]: [
            plan
            for plan in ordered_plans
            if group["id"] in {item["id"] for item in plan["resolved_groups"]}
        ]
        for group in groups
    }
    assignments_by_group: dict[str, list[JsonObject]] = {
        group["id"]: sorted(
            [item for item in assignments if item["target"]["group"] == group["id"]],
            key=lambda item: item["id"],
        )
        for group in groups
    }
    if resource == "groups":
        rows = []
        for group in sorted(groups, key=lambda item: item["id"]):
            members = members_by_group[group["id"]]
            rows.append(
                {
                    "group_id": group["id"],
                    "current_asset_count": len(members),
                    "direct_assignment_count": len(assignments_by_group[group["id"]]),
                    "direct_assignments": [
                        item["id"] for item in assignments_by_group[group["id"]]
                    ],
                    "assigned_asset_count": sum(
                        bool(plan["assignments"]) for plan in members
                    ),
                    "assessable_check_count": sum(
                        len(plan["controls"])
                        for plan in members
                        if _coverage_class(plan) == "result_required"
                    ),
                    "objective_count": sum(
                        len(plan["requirements"])
                        for plan in members
                        if _coverage_class(plan) == "result_required"
                    ),
                    "coverage_classes": _counts(members),
                }
            )
        return {
            "schema": "compliance.example/coverage-groups-view/v1alpha1",
            "groups": rows,
        }

    if resource == "assignments":
        rows = []
        for assignment in sorted(assignments, key=lambda item: item["id"]):
            assignment_id = assignment["id"]
            members = members_by_group[assignment["target"]["group"]]
            rows.append(
                {
                    "assignment_id": assignment_id,
                    "target_group": assignment["target"]["group"],
                    "policy_references": sorted(assignment["baselines"]),
                    "current_asset_count": len(members),
                    "assessable_asset_count": sum(
                        _coverage_class(plan) == "result_required"
                        and (
                            any(
                                _assignment_contributes(item, assignment_id)
                                for item in plan["controls"]
                            )
                            or any(
                                _assignment_contributes(item, assignment_id)
                                for item in plan["requirements"]
                            )
                        )
                        for plan in members
                    ),
                    "assessable_check_count": sum(
                        _assignment_contributes(control, assignment_id)
                        for plan in members
                        if _coverage_class(plan) == "result_required"
                        for control in plan["controls"]
                    ),
                    "excluded_check_count": sum(
                        _assignment_contributes(control, assignment_id)
                        for plan in members
                        if plan["resolution"]["status"] == "valid"
                        for control in plan["excluded_controls"]
                    ),
                    "objective_count": sum(
                        _assignment_contributes(requirement, assignment_id)
                        for plan in members
                        if _coverage_class(plan) == "result_required"
                        for requirement in plan["requirements"]
                    ),
                    "coverage_classes": _counts(members),
                }
            )
        return {
            "schema": "compliance.example/coverage-assignments-view/v1alpha1",
            "assignments": rows,
        }
    raise ValueError(f"unknown coverage resource: {resource}")


def _evidence(dependencies: list[JsonObject]) -> list[JsonObject]:
    rows = []
    for dependency in dependencies:
        row = {
            "dependency_id": dependency["id"],
            "evidence_type": dependency["type"],
            "max_age": dependency["max_age"],
        }
        if dependency.get("inputs"):
            row["inputs"] = copy.deepcopy(dependency["inputs"])
        rows.append(row)
    return sorted(rows, key=lambda item: item["dependency_id"])


def _check(control: JsonObject) -> JsonObject:
    row: JsonObject = {
        "instance_id": control["instance_id"],
        "title": control["title"],
        "purpose": control["purpose"],
        "disposition": control["disposition"],
        "alignment": control["alignment"],
        "parameters": copy.deepcopy(control.get("parameters", {})),
        "required_evidence": _evidence(control.get("evidence", [])),
    }
    if control.get("deviations"):
        row["deviations"] = [
            {
                field: deviation[field]
                for field in (
                    "id",
                    "classification",
                    "rationale",
                    "approval_ref",
                    "review_after",
                )
            }
            for deviation in control["deviations"]
        ]
    return row


def _realization(requirement: JsonObject) -> JsonObject | None:
    realization = requirement.get("realization")
    if realization is None:
        return None
    return {
        "reference": realization["reference"],
    }


def _objective_parameters(requirement: JsonObject) -> list[JsonObject]:
    rows = []
    states = requirement.get("parameter_facts", {}).get("states", {})
    for slot, state in sorted(states.items()):
        if not state.get("bound"):
            continue
        row: JsonObject = {
            "slot": slot,
            "effective_value": copy.deepcopy(state["value"]),
            "binding_mode": state["declaration"]["binding_mode"],
        }
        composition = state.get("composition")
        if composition is not None:
            row["composition"] = {
                "kind": composition["kind"],
                "base_value": copy.deepcopy(composition["base_value"]),
                "base_applicability": [
                    {
                        "baseline": origin["baseline"],
                        "applicability": copy.deepcopy(origin["applicability"]),
                    }
                    for origin in composition["base_origins"]
                ],
                "contributions": [
                    {
                        "identity": copy.deepcopy(item["identity"]),
                        "members": copy.deepcopy(item["members"]),
                        "applicability": copy.deepcopy(item["applicability"]),
                    }
                    for item in composition["contributions"]
                ],
                "member_origins": [
                    {
                        "member": item["member"],
                        "origins": [
                            (
                                {
                                    "kind": "base",
                                    "baseline": origin["baseline"],
                                    "applicability": copy.deepcopy(origin["applicability"]),
                                }
                                if origin["kind"] == "base"
                                else {
                                    "kind": "contribution",
                                    "identity": copy.deepcopy(origin["identity"]),
                                }
                            )
                            for origin in item["origins"]
                        ],
                    }
                    for item in composition["member_origins"]
                ],
            }
        rows.append(row)
    return rows


_FAILURE_CONTEXT_FIELDS = {
    "subject_id": "asset_id",
    "subject_type": "asset_type",
    "group": "group_id",
    "assignment": "assignment_id",
    "baseline": "policy_reference",
    "requirement": "objective_reference",
    "realization": "realization_reference",
    "realizations": "candidate_realizations",
    "instance_id": "check_id",
    "implementation": "check_implementation",
    "target": "target_check_id",
    "operation": "policy_operation",
    "path": "authored_path",
    "fields": "affected_fields",
}


def _resolution_failure(error: JsonObject) -> JsonObject:
    failure: JsonObject = {"reason": str(error.get("type", "resolution-failed"))}
    for source, target in _FAILURE_CONTEXT_FIELDS.items():
        value = error.get(source)
        if isinstance(value, str):
            failure[target] = value
        elif isinstance(value, list) and all(
            isinstance(item, str) for item in value
        ):
            failure[target] = sorted(set(value))
    return failure


def _resolution(plan: JsonObject) -> JsonObject:
    return {
        "status": plan["resolution"]["status"],
        "failures": [
            _resolution_failure(error) for error in plan["resolution"]["errors"]
        ],
    }


def _matches_path(item: JsonObject, assignment_id: str, reference: str) -> bool:
    return any(
        provenance.get("assignment") == assignment_id
        and provenance.get("baseline") == reference
        for provenance in item.get("provenance", [])
    )


def _matches_objective_path(
    item: JsonObject,
    assignment_id: str,
    reference: str,
    requirement_reference: str,
) -> bool:
    return any(
        provenance.get("assignment") == assignment_id
        and provenance.get("baseline") == reference
        and provenance.get("requirement") == requirement_reference
        for provenance in item.get("provenance", [])
    )


def _unresolved_policy_paths(plan: JsonObject) -> list[JsonObject]:
    return [
        {
            "assignment_id": assignment["id"],
            "group_id": assignment["group"],
            "policies": [
                {
                    "policy_type": "unresolved",
                    "reference": reference,
                    "title": None,
                    "objectives": [],
                    "checks": [],
                }
                for reference in sorted(assignment["baselines"])
            ],
        }
        for assignment in plan["assignments"]
    ]


def _policy_paths(plan: JsonObject) -> list[JsonObject]:
    if plan["resolution"]["status"] != "valid":
        return _unresolved_policy_paths(plan)
    active = plan["controls"]
    excluded = plan["excluded_controls"]
    paths = []
    technical = {
        (item["assignment"], item["reference"]): item
        for item in plan["resolved_baselines"]
    }
    objective = {
        (item["assignment"], item["reference"]): item
        for item in plan["resolved_requirement_baselines"]
    }
    for assignment in plan["assignments"]:
        assignment_row = {
            "assignment_id": assignment["id"],
            "group_id": assignment["group"],
            "policies": [],
        }
        for reference in sorted(assignment["baselines"]):
            key = (assignment["id"], reference)
            technical_policy = technical.get(key)
            objective_policy = objective.get(key)
            if objective_policy is not None:
                objectives = []
                for requirement in plan["requirements"]:
                    if not _matches_path(requirement, assignment["id"], reference):
                        continue
                    checks = [
                        _check(control)
                        for control in [*active, *excluded]
                        if _matches_objective_path(
                            control,
                            assignment["id"],
                            reference,
                            requirement["reference"],
                        )
                    ]
                    objective_row: JsonObject = {
                        "reference": requirement["reference"],
                        "title": requirement["title"],
                        "statement": requirement["statement"],
                        "required": requirement["required"],
                        "adoption": copy.deepcopy(requirement["adoption"]),
                        "parameters": _objective_parameters(requirement),
                        "checks": sorted(
                            checks, key=lambda item: item["instance_id"]
                        ),
                    }
                    if realization := _realization(requirement):
                        objective_row["realization"] = realization
                    objectives.append(objective_row)
                assignment_row["policies"].append(
                    {
                        "policy_type": "objective",
                        "reference": reference,
                        "title": objective_policy["title"],
                        "objectives": sorted(
                            objectives, key=lambda item: item["reference"]
                        ),
                        "checks": [],
                    }
                )
            elif technical_policy is not None:
                checks = [
                    _check(control)
                    for control in [*active, *excluded]
                    if _matches_path(control, assignment["id"], reference)
                ]
                assignment_row["policies"].append(
                    {
                        "policy_type": "technical",
                        "reference": reference,
                        "title": technical_policy["title"],
                        "objectives": [],
                        "checks": sorted(
                            checks, key=lambda item: item["instance_id"]
                        ),
                    }
                )
            else:
                assignment_row["policies"].append(
                    {
                        "policy_type": "unresolved",
                        "reference": reference,
                        "title": None,
                        "objectives": [],
                        "checks": [],
                    }
                )
        paths.append(assignment_row)
    return paths


def build_coverage_explanation(plan: JsonObject) -> JsonObject:
    subject = plan["subject"]
    return {
        "schema": "compliance.example/coverage-asset-explanation/v1alpha1",
        "asset": {
            "asset_id": subject["id"],
            "asset_type": subject["type"],
            "lifecycle": subject["status"],
        },
        "coverage_class": _coverage_class(plan),
        "resolved_groups": copy.deepcopy(plan["resolved_groups"]),
        "assignments": _policy_paths(plan),
        "resolution": _resolution(plan),
    }


def _membership(source: JsonObject) -> str:
    if source["membership"] == "explicit":
        return "explicit member"
    if source["membership"] == "selector":
        labels = source["source"]["match_labels"]
        return "selector " + ",".join(
            f"{key}={value}" for key, value in sorted(labels.items())
        )
    return "inherited via " + ", ".join(source["via"])


def _format_check(lines: list[str], check: JsonObject, indent: str) -> None:
    lines.extend(
        [
            f'{indent}Check: {check["title"]}',
            f'{indent}  ID: {check["instance_id"]}',
            f'{indent}  Purpose: {check["purpose"]}',
            f'{indent}  Disposition: {check["disposition"]}',
            f'{indent}  Policy alignment: {check["alignment"]}',
            f"{indent}  Effective parameters: "
            + json.dumps(
                check["parameters"], sort_keys=True, separators=(",", ":")
            ),
        ]
    )
    if not check["required_evidence"]:
        lines.append(f"{indent}  Required evidence: none")
    for dependency in check["required_evidence"]:
        lines.append(
            f'{indent}  Required evidence: {dependency["evidence_type"]} '
            f'(dependency {dependency["dependency_id"]}, max age {dependency["max_age"]})'
        )
        if dependency.get("inputs"):
            lines.append(
                f"{indent}    Inputs: "
                + json.dumps(
                    dependency["inputs"], sort_keys=True, separators=(",", ":")
                )
            )
    for deviation in check.get("deviations", []):
        lines.extend(
            [
                f'{indent}  Approved deviation: {deviation["rationale"]}',
                f'{indent}    ID: {deviation["id"]}',
                f'{indent}    Classification: {deviation["classification"]}',
                f'{indent}    Approval: {deviation["approval_ref"]}',
                f'{indent}    Review after: {deviation["review_after"]}',
            ]
        )


def format_coverage_explanation(document: JsonObject) -> str:
    asset = document["asset"]
    lines = [
        f'Asset: {asset["asset_id"]}',
        f'Type: {asset["asset_type"]}',
        f'Lifecycle: {asset["lifecycle"]}',
        f'Coverage: {document["coverage_class"]}',
        "Membership:",
    ]
    if not document["resolved_groups"]:
        lines.append("  none")
    for group in document["resolved_groups"]:
        lines.append(
            f'  {group["id"]}: '
            + "; ".join(_membership(source) for source in group["sources"])
        )
    lines.append("Applicable assignments:")
    if not document["assignments"]:
        lines.append("  none")
    if document["resolution"]["status"] != "valid":
        lines.append("Policy resolution: INVALID; no resolved policy is trustworthy.")
        for failure in document["resolution"]["failures"]:
            lines.append(
                "  Failure: " + failure["reason"].replace("-", " ").capitalize()
            )
            lines.append(f'    Code: {failure["reason"]}')
            for field, value in failure.items():
                if field == "reason":
                    continue
                label = field.replace("_", " ").capitalize()
                rendered = ", ".join(value) if isinstance(value, list) else value
                lines.append(f"    {label}: {rendered}")
    for assignment in document["assignments"]:
        lines.append(
            f'  Assignment: {assignment["assignment_id"]} via {assignment["group_id"]}'
        )
        for policy in assignment["policies"]:
            title = policy["title"] or "unresolved policy"
            lines.append(f"    Applicable policy: {title}")
            lines.append(f'      Reference: {policy["reference"]}')
            for objective in policy["objectives"]:
                lines.extend(
                    [
                        f'      Objective: {objective["title"]}',
                        f'        Reference: {objective["reference"]}',
                        f'        Meaning: {objective["statement"]}',
                        f'        Adoption: {objective["adoption"]["status"]}',
                    ]
                )
                for parameter in objective["parameters"]:
                    lines.append(
                        f'        Effective parameter {parameter["slot"]}: '
                        + json.dumps(
                            parameter["effective_value"],
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                    composition = parameter.get("composition")
                    if composition is not None:
                        lines.append(
                            f'          Composition: {composition["kind"]}; base '
                            + json.dumps(
                                composition["base_value"],
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                        )
                        for contribution in composition["contributions"]:
                            identity = contribution["identity"]
                            lines.append(
                                f'          Contribution: {identity["baseline"]} '
                                f'#{identity["id"]} via '
                                f'{len(contribution["applicability"])} path(s): '
                                + json.dumps(
                                    contribution["members"],
                                    sort_keys=True,
                                    separators=(",", ":"),
                                )
                            )
                if realization := objective.get("realization"):
                    lines.append(f'        Realization: {realization["reference"]}')
                for check in objective["checks"]:
                    _format_check(lines, check, "        ")
            for check in policy["checks"]:
                _format_check(lines, check, "      ")
    return "\n".join(lines)


def _table(title: str, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render(values: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        ).rstrip()

    lines = [title, "", render(headers), render(tuple("─" * width for width in widths))]
    lines.extend(render(row) for row in rows)
    return "\n".join(lines)


def format_coverage_list(document: JsonObject) -> str:
    schema = document["schema"]
    if schema.endswith("coverage-assets-view/v1alpha1"):
        rows = [
            (
                item["asset_id"],
                item["asset_type"],
                item["lifecycle"].upper(),
                item["coverage_class"].upper(),
                str(item["assignment_count"]),
                str(item["assessable_check_count"]),
                str(item["excluded_check_count"]),
                str(item["objective_count"]),
            )
            for item in document["assets"]
        ]
        return _table(
            f"Current asset coverage ({len(rows)})",
            (
                "ASSET",
                "TYPE",
                "LIFECYCLE",
                "COVERAGE",
                "ASSIGNMENTS",
                "CHECKS",
                "EXCLUDED",
                "OBJECTIVES",
            ),
            rows,
        )
    if schema.endswith("coverage-groups-view/v1alpha1"):
        rows = [
            (
                item["group_id"],
                str(item["current_asset_count"]),
                str(item["direct_assignment_count"]),
                str(item["assigned_asset_count"]),
                str(item["assessable_check_count"]),
                str(item["objective_count"]),
                *(
                    str(item["coverage_classes"][name])
                    for name in COVERAGE_CLASSES
                ),
            )
            for item in document["groups"]
        ]
        return _table(
            f"Current group coverage ({len(rows)})",
            (
                "GROUP",
                "ASSETS",
                "DIRECT ASSIGNMENTS",
                "ASSIGNED ASSETS",
                "CHECKS",
                "OBJECTIVES",
                "RESULT REQUIRED",
                "INACTIVE",
                "UNASSIGNED",
                "NO ASSESSABLE",
                "INVALID",
            ),
            rows,
        )
    if schema.endswith("coverage-assignments-view/v1alpha1"):
        rows = [
            (
                item["assignment_id"],
                item["target_group"],
                str(item["current_asset_count"]),
                str(item["assessable_asset_count"]),
                str(item["assessable_check_count"]),
                str(item["excluded_check_count"]),
                str(item["objective_count"]),
                *(
                    str(item["coverage_classes"][name])
                    for name in COVERAGE_CLASSES
                ),
            )
            for item in document["assignments"]
        ]
        return _table(
            f"Current assignment coverage ({len(rows)})",
            (
                "ASSIGNMENT",
                "TARGET GROUP",
                "ASSETS",
                "ASSESSABLE ASSETS",
                "CHECKS",
                "EXCLUDED",
                "OBJECTIVES",
                "RESULT REQUIRED",
                "INACTIVE",
                "UNASSIGNED",
                "NO ASSESSABLE",
                "INVALID",
            ),
            rows,
        )
    raise ValueError(f"unsupported coverage view schema: {schema}")
