"""Internal deterministic roll-up from technical checks to requirements."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .render_plan import content_digest


JsonObject = dict[str, Any]


class ControlRealizationError(ValueError):
    """A requirement realization or its technical results are inconsistent."""


def _reference(document: JsonObject) -> str:
    metadata = document.get("metadata", {})
    identifier = metadata.get("id")
    revision = metadata.get("revision")
    if not isinstance(identifier, str) or revision is None:
        raise ControlRealizationError("document has no stable id and revision")
    return f"{identifier}@{revision}"


def validate_realization(
    requirement: JsonObject,
    realization: JsonObject,
) -> list[str]:
    """Return semantic errors not expressible in the realization JSON Schema."""
    errors: list[str] = []
    requirement_ref = _reference(requirement)
    pin = realization.get("spec", {}).get("requirement", {})
    if pin.get("requirement") != requirement_ref:
        errors.append(
            f"requirement pin {pin.get('requirement')!r} does not select {requirement_ref!r}"
        )
    expected_digest = content_digest(requirement)
    if pin.get("digest") != expected_digest:
        errors.append(
            f"requirement digest {pin.get('digest')!r} does not match {expected_digest!r}"
        )

    spec = realization.get("spec", {})
    adoption = spec.get("adoption", {})
    status = adoption.get("status")
    checks = spec.get("checks", [])
    satisfaction = spec.get("satisfaction")
    if status == "implemented":
        check_ids = [check.get("instance_id") for check in checks]
        duplicates = sorted(
            instance_id
            for instance_id, count in Counter(check_ids).items()
            if count > 1
        )
        if duplicates:
            errors.append("duplicate technical check ids: " + ", ".join(duplicates))
        required_ids = satisfaction.get("allOf", []) if isinstance(satisfaction, dict) else []
        missing_definitions = sorted(set(required_ids) - set(check_ids))
        unreferenced_checks = sorted(set(check_ids) - set(required_ids))
        if missing_definitions:
            errors.append(
                "satisfaction references undefined checks: " + ", ".join(missing_definitions)
            )
        if unreferenced_checks:
            errors.append(
                "technical checks omitted from satisfaction: " + ", ".join(unreferenced_checks)
            )
    elif checks or satisfaction is not None:
        errors.append(f"{status!r} realization must not declare technical checks")
    return errors


def validate_realization_lineage(
    realization: JsonObject,
    base_realization: JsonObject | None,
) -> list[str]:
    """Validate optional provenance without inheriting or merging base content."""
    pin = realization.get("spec", {}).get("based_on")
    if pin is None:
        return []
    if base_realization is None:
        return ["based_on realization was not supplied for provenance validation"]

    errors = []
    base_reference = _reference(base_realization)
    if pin.get("realization") != base_reference:
        errors.append(
            f"based_on pin {pin.get('realization')!r} does not select {base_reference!r}"
        )
    expected_digest = content_digest(base_realization)
    if pin.get("digest") != expected_digest:
        errors.append(
            f"based_on digest {pin.get('digest')!r} does not match {expected_digest!r}"
        )
    return errors


def realization_applies(realization: JsonObject, subject: JsonObject) -> bool:
    """Match the deliberately small subject-type and trusted-label contract."""
    applicability = realization.get("spec", {}).get("applies_to", {})
    if subject.get("type") not in applicability.get("subject_types", []):
        return False
    labels = subject.get("labels", {})
    return all(
        labels.get(key) == value
        for key, value in applicability.get("match_labels", {}).items()
    )


def _empty_summary() -> dict[str, int]:
    return {
        status: 0
        for status in (
            "pass",
            "fail",
            "unknown",
            "not_applicable",
            "error",
            "waived",
            "missing",
        )
    }


def roll_up_plan_requirements(
    plan: JsonObject,
    technical_results: list[JsonObject],
) -> tuple[list[JsonObject], list[JsonObject]]:
    """Roll the requirement records frozen into a rendered plan up locally."""
    results_by_id = {
        result["instance_id"]: result
        for result in technical_results
        if isinstance(result.get("instance_id"), str)
    }
    requirement_assessments = []
    for requirement in plan.get("requirements", []):
        adoption = requirement["adoption"]
        assessment: JsonObject = {
            "requirement": requirement["reference"],
            "requirement_digest": requirement["digest"],
            "external_refs": list(requirement.get("external_refs", [])),
            "adoption": copy_json(adoption),
            "technical_instance_ids": list(requirement["technical_instance_ids"]),
            **(
                {"realization": copy_json(requirement["realization"])}
                if "realization" in requirement
                else {}
            ),
        }
        if adoption["status"] == "not_applicable":
            assessment.update({
                "status": "not_applicable",
                "reason": "The selected realization marks the requirement not applicable.",
                "check_summary": _empty_summary(),
            })
            requirement_assessments.append(assessment)
            continue
        if adoption["status"] == "not_implemented":
            assessment.update({
                "status": "fail",
                "reason": "The applicable requirement has no implemented realization.",
                "check_summary": _empty_summary(),
            })
            requirement_assessments.append(assessment)
            continue

        mapped = []
        for instance_id in requirement["technical_instance_ids"]:
            technical = results_by_id.get(instance_id)
            mapped.append({
                "instance_id": instance_id,
                "status": technical.get("status", "missing") if technical else "missing",
            })
        counts = Counter(item["status"] for item in mapped)
        summary = _empty_summary()
        summary.update(counts)
        if counts["fail"]:
            status, reason = "fail", "One or more required technical checks failed."
        elif counts["error"]:
            status, reason = "error", "One or more required technical checks errored."
        elif counts["missing"] or counts["unknown"] or counts["not_applicable"]:
            status, reason = "unknown", "One or more required technical checks are inconclusive."
        elif counts["waived"]:
            status, reason = "waived", "One or more required technical checks are waived."
        else:
            status, reason = "pass", "Every required technical check passed."
        assessment.update({
            "status": status,
            "reason": reason,
            "check_summary": summary,
            "checks": mapped,
        })
        requirement_assessments.append(assessment)

    assessments_by_ref = {
        assessment["requirement"]: assessment
        for assessment in requirement_assessments
    }
    baseline_assessments = []
    seen_baselines = set()
    for baseline in plan.get("resolved_requirement_baselines", []):
        reference = baseline["reference"]
        if reference in seen_baselines:
            continue
        seen_baselines.add(reference)
        states = []
        for pin in baseline["requirements"]:
            assessment = assessments_by_ref.get(pin["requirement"])
            states.append({
                "requirement": pin["requirement"],
                "status": assessment["status"] if assessment else "missing",
            })
        counts = Counter(item["status"] for item in states)
        if counts["fail"]:
            status, reason = "fail", "One or more required control objectives failed."
        elif counts["error"]:
            status, reason = "error", "One or more required control objectives errored."
        elif counts["missing"] or counts["unknown"]:
            status, reason = "unknown", "One or more required control objectives are inconclusive."
        elif counts["waived"]:
            status, reason = "waived", "One or more required control objectives are waived."
        elif counts["not_applicable"] == len(states):
            status, reason = "not_applicable", "Every required objective is not applicable."
        else:
            status, reason = "pass", "Every applicable required control objective passed."
        baseline_assessments.append({
            "baseline": reference,
            "digest": baseline["digest"],
            "status": status,
            "reason": reason,
            "requirements": states,
        })
    return requirement_assessments, baseline_assessments


def compact_plan_outcomes(
    plan: JsonObject,
    technical_results: list[JsonObject],
) -> tuple[list[JsonObject], list[JsonObject]]:
    """Return result-owned requirement outcomes without copying plan semantics."""
    requirements, baselines = roll_up_plan_requirements(plan, technical_results)
    compact_requirements = [
        {
            "requirement": item["requirement"],
            "status": item["status"],
            "reason": item["reason"],
        }
        for item in requirements
    ]
    compact_baselines = [
        {
            "baseline": item["baseline"],
            "status": item["status"],
            "reason": item["reason"],
        }
        for item in baselines
    ]
    compact_requirements.sort(key=lambda item: item["requirement"])
    compact_baselines.sort(key=lambda item: item["baseline"])
    return compact_requirements, compact_baselines


def copy_json(value: Any) -> Any:
    """Copy JSON-compatible values without sharing mutable plan structures."""
    return json.loads(json.dumps(value))
