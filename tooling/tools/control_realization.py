"""Internal deterministic roll-up from technical checks to requirements."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .render_plan import content_digest


JsonObject = dict[str, Any]
TECHNICAL_STATUSES = {
    "pass",
    "fail",
    "unknown",
    "not_applicable",
    "error",
    "waived",
}


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


def select_realization(
    requirement: JsonObject,
    subject: JsonObject,
    realizations: list[JsonObject],
) -> JsonObject:
    """Select exactly one complete realization; never use ordering precedence."""
    valid_realizations = []
    semantic_errors = []
    for realization in realizations:
        errors = validate_realization(requirement, realization)
        if errors:
            semantic_errors.extend(
                f"{_reference(realization)}: {error}" for error in errors
            )
        elif realization_applies(realization, subject):
            valid_realizations.append(realization)
    if semantic_errors:
        raise ControlRealizationError("; ".join(semantic_errors))
    if not valid_realizations:
        raise ControlRealizationError(
            f"no realization applies to subject {subject.get('id')!r}; "
            "the requirement is not implemented for this subject"
        )
    if len(valid_realizations) > 1:
        references = ", ".join(sorted(_reference(item) for item in valid_realizations))
        raise ControlRealizationError(
            f"multiple realizations apply to subject {subject.get('id')!r}: {references}"
        )
    return valid_realizations[0]


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


def roll_up_realization(
    requirement: JsonObject,
    realization: JsonObject,
    technical_report: JsonObject,
) -> JsonObject:
    """Calculate one requirement result from a selected realization's checks."""
    errors = validate_realization(requirement, realization)
    if errors:
        raise ControlRealizationError("; ".join(errors))

    subject = technical_report.get("subject", {})
    if not realization_applies(realization, subject):
        raise ControlRealizationError(
            f"realization {_reference(realization)!r} does not apply to subject "
            f"{subject.get('id')!r}"
        )

    adoption = realization["spec"]["adoption"]
    base: JsonObject = {
        "schema": "compliance.example/requirement-assessment/v1alpha1",
        "subject": subject,
        "plan_id": technical_report.get("plan_id"),
        "requirement": _reference(requirement),
        "requirement_digest": content_digest(requirement),
        "external_refs": list(requirement.get("spec", {}).get("external_refs", [])),
        "realization": _reference(realization),
        **(
            {"realization_based_on": realization["spec"]["based_on"]}
            if "based_on" in realization["spec"]
            else {}
        ),
        "adoption": adoption,
        "check_summary": _empty_summary(),
        "checks": [],
    }
    if adoption["status"] == "not_applicable":
        return {
            **base,
            "status": "not_applicable",
            "reason": "The approved realization marks the requirement not applicable.",
        }
    if adoption["status"] == "not_implemented":
        return {
            **base,
            "status": "fail",
            "reason": "The applicable requirement has no implemented realization.",
        }

    results_by_id: dict[str, JsonObject] = {}
    for result in technical_report.get("results", []):
        instance_id = result.get("instance_id")
        status = result.get("status")
        if not isinstance(instance_id, str):
            raise ControlRealizationError("technical result has no instance_id")
        if instance_id in results_by_id:
            raise ControlRealizationError(f"duplicate technical result: {instance_id}")
        if status not in TECHNICAL_STATUSES:
            raise ControlRealizationError(
                f"technical result {instance_id!r} has unsupported status {status!r}"
            )
        results_by_id[instance_id] = result

    required_ids = realization["spec"]["satisfaction"]["allOf"]
    mapped_results = []
    for instance_id in required_ids:
        result = results_by_id.get(instance_id)
        if result is None:
            mapped_results.append({"instance_id": instance_id, "status": "missing"})
        else:
            mapped_results.append({
                "instance_id": instance_id,
                "status": result["status"],
                **({"reason": result["reason"]} if "reason" in result else {}),
            })

    counts = Counter(result["status"] for result in mapped_results)
    summary = _empty_summary()
    summary.update(counts)
    failed = [result["instance_id"] for result in mapped_results if result["status"] == "fail"]
    errored = [result["instance_id"] for result in mapped_results if result["status"] == "error"]
    inconclusive = [
        result["instance_id"]
        for result in mapped_results
        if result["status"] in {"unknown", "not_applicable", "missing"}
    ]
    waived = [result["instance_id"] for result in mapped_results if result["status"] == "waived"]

    if failed:
        status = "fail"
        reason = "Required technical checks failed: " + ", ".join(failed)
    elif errored:
        status = "error"
        reason = "Required technical checks could not be evaluated: " + ", ".join(errored)
    elif inconclusive:
        status = "unknown"
        reason = "Required technical checks are inconclusive: " + ", ".join(inconclusive)
    elif waived:
        status = "waived"
        reason = "Required technical checks include accepted failures: " + ", ".join(waived)
    else:
        status = "pass"
        reason = "Every required technical check in the selected realization passed."

    return {
        **base,
        "status": status,
        "reason": reason,
        "check_summary": summary,
        "checks": mapped_results,
    }


def roll_up_requirement_baseline(
    baseline: JsonObject,
    requirement_assessments: list[JsonObject],
) -> JsonObject:
    """Calculate the top-level baseline tick without hiding requirement states."""
    assessments_by_ref: dict[str, JsonObject] = {}
    for assessment in requirement_assessments:
        reference = assessment.get("requirement")
        if not isinstance(reference, str):
            raise ControlRealizationError("requirement assessment has no requirement reference")
        if reference in assessments_by_ref:
            raise ControlRealizationError(f"duplicate requirement assessment: {reference}")
        assessments_by_ref[reference] = assessment

    required_pins = [
        pin
        for pin in baseline["spec"]["requirements"]
        if pin["required"]
    ]
    if not required_pins:
        raise ControlRealizationError("requirement baseline has no required requirements")
    required_refs = [pin["requirement"] for pin in required_pins]
    duplicate_refs = sorted(
        reference
        for reference, count in Counter(required_refs).items()
        if count > 1
    )
    if duplicate_refs:
        raise ControlRealizationError(
            "duplicate required requirement pins: " + ", ".join(duplicate_refs)
        )
    selected = []
    for pin in required_pins:
        reference = pin["requirement"]
        assessment = assessments_by_ref.get(reference)
        if assessment is None:
            selected.append({"requirement": reference, "status": "missing"})
        else:
            if assessment.get("requirement_digest") != pin["digest"]:
                raise ControlRealizationError(
                    f"requirement assessment digest for {reference!r} does not match baseline pin"
                )
            if assessment.get("status") not in TECHNICAL_STATUSES:
                raise ControlRealizationError(
                    f"requirement assessment {reference!r} has unsupported status "
                    f"{assessment.get('status')!r}"
                )
            selected.append({
                "requirement": reference,
                "status": assessment["status"],
                "adoption": assessment["adoption"]["status"],
            })

    counts = Counter(item["status"] for item in selected)
    if counts["fail"]:
        status = "fail"
        reason = "One or more required control objectives failed."
    elif counts["error"]:
        status = "error"
        reason = "One or more required control objectives could not be evaluated."
    elif counts["unknown"] or counts["missing"]:
        status = "unknown"
        reason = "One or more required control objectives are inconclusive or missing."
    elif counts["waived"]:
        status = "waived"
        reason = "One or more required control objectives contain accepted failures."
    elif counts["not_applicable"] == len(selected):
        status = "not_applicable"
        reason = "Every required control objective is explicitly not applicable."
    else:
        status = "pass"
        reason = "Every applicable required control objective passed."

    return {
        "schema": "compliance.example/requirement-baseline-assessment/v1alpha1",
        "baseline": _reference(baseline),
        "status": status,
        "reason": reason,
        "requirement_summary": dict(sorted(counts.items())),
        "requirements": selected,
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


def copy_json(value: Any) -> Any:
    """Copy JSON-compatible values without sharing mutable plan structures."""
    return json.loads(json.dumps(value))
