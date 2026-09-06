"""Validate persisted assessment plans and immutable result envelopes."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ._canonical_json import canonical_json_bytes


JsonObject = dict[str, Any]
RESULT_STATUSES = (
    "pass",
    "fail",
    "unknown",
    "not_applicable",
    "error",
    "waived",
)
CHECK_STATUSES = (*RESULT_STATUSES, "missing")


class ArtifactValidationError(ValueError):
    """A generated or stored assessment artifact violates its contract."""


def assessment_plan_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas/assessment-plan-v4.schema.json"


def assessment_results_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas/assessment-results-v4.schema.json"


def _pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else "/"


def _raise(label: str, details: list[str], source: Path | None = None) -> None:
    location = f" in {source}" if source is not None else ""
    raise ArtifactValidationError(
        f"{label}{location} failed validation: " + "; ".join(details)
    )


def _validate_schema(
    document: JsonObject,
    schema_path: Path,
    label: str,
    source: Path | None,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(document),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )
    if errors:
        _raise(
            label,
            [f"{_pointer(error.absolute_path)}: {error.message}" for error in errors],
            source,
        )


def _content_digest(value: Any) -> str:
    encoded = canonical_json_bytes(value)
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _criteria_state(control: JsonObject) -> JsonObject:
    return {
        "evidence": control.get("policy_inputs", {}).get("instance", {}).get("evidence", {}),
        "implementation": control["implementation"],
        "parameters": control["parameters"],
        "disposition": control["disposition"],
    }


def validate_assessment_plan(
    document: JsonObject,
    *,
    source: Path | None = None,
) -> None:
    """Validate the v4 envelope and domain invariants."""
    from .assessment_provenance import validate_provenance
    _validate_schema(document, assessment_plan_schema_path(), "assessment plan", source)
    errors: list[str] = []
    from .policy_parameters import validate_frozen
    try:
        validate_frozen(document)
    except (ValueError, KeyError) as error:
        errors.append("invalid frozen policy parameters: " + str(error))

    resolution = document["resolution"]
    if (resolution["status"] == "valid") != (not resolution["errors"]):
        errors.append(
            "/resolution: valid requires no errors and invalid requires at least one error"
        )

    identity_sets = {
        "/assignments": [item["id"] for item in document["assignments"]],
        "/resolved_groups": [item["id"] for item in document["resolved_groups"]],
        "/controls": [item["instance_id"] for item in document["controls"]],
        "/excluded_controls": [
            item["instance_id"] for item in document["excluded_controls"]
        ],
        "/requirements": [item["reference"] for item in document["requirements"]],
    }
    for path, identities in identity_sets.items():
        duplicates = _duplicates(identities)
        if duplicates:
            errors.append(f"{path}: duplicate identities: {', '.join(duplicates)}")

    active_ids = set(identity_sets["/controls"])
    excluded_ids = set(identity_sets["/excluded_controls"])
    overlap = sorted(active_ids & excluded_ids)
    if overlap:
        errors.append(
            "/controls: identities cannot also be excluded: " + ", ".join(overlap)
        )

    for collection_name in ("controls", "excluded_controls"):
        for index, control in enumerate(document[collection_name]):
            derivations = control["derivations"]
            recorded_deviations = [
                derivation["deviation"]
                for derivation in derivations
                if "deviation" in derivation
            ]
            recorded_deviation_values = {
                json.dumps(item, sort_keys=True, separators=(",", ":"))
                for item in recorded_deviations
            }
            control_deviation_values = {
                json.dumps(item, sort_keys=True, separators=(",", ":"))
                for item in control["deviations"]
            }
            if recorded_deviation_values != control_deviation_values:
                errors.append(
                    f"/{collection_name}/{index}/derivations: deviation records "
                    "must exactly match the control deviations"
                )
            for derivation_index, derivation in enumerate(derivations):
                lineage_entry = {
                    "baseline": derivation["overlay"],
                    "operation": derivation["operation"],
                }
                if lineage_entry not in control["lineage"]:
                    errors.append(
                        f"/{collection_name}/{index}/derivations/{derivation_index}: "
                        "overlay operation is missing from control lineage"
                    )
            if derivations and not any(
                derivation["after"] == _criteria_state(control)
                for derivation in derivations
            ):
                errors.append(
                    f"/{collection_name}/{index}/derivations: at least one after "
                    "state must match the effective control criteria"
                )

    for index, requirement in enumerate(document["requirements"]):
        technical_ids = requirement["technical_instance_ids"]
        duplicates = _duplicates(technical_ids)
        if duplicates:
            errors.append(
                f"/requirements/{index}/technical_instance_ids: duplicate identities: "
                + ", ".join(duplicates)
            )
        missing = sorted(set(technical_ids) - active_ids)
        if missing and resolution["status"] == "valid":
            errors.append(
                f"/requirements/{index}/technical_instance_ids: controls are missing: "
                + ", ".join(missing)
            )
        all_of = requirement["satisfaction"]["allOf"]
        if all_of != technical_ids:
            errors.append(
                f"/requirements/{index}: satisfaction.allOf and "
                "technical_instance_ids must be identical"
            )
        adoption_status = requirement["adoption"]["status"]
        if adoption_status == "implemented":
            if not technical_ids:
                errors.append(
                    f"/requirements/{index}/technical_instance_ids: an implemented "
                    "realization must contain at least one technical check"
                )
            if "realization" not in requirement:
                errors.append(
                    f"/requirements/{index}/realization: required for implemented adoption"
                )
        elif adoption_status == "not_implemented" and "realization" in requirement:
            errors.append(
                f"/requirements/{index}/realization: not_implemented must not select a realization"
            )

    if errors:
        _raise("assessment plan", errors, source)

    try:
        validate_provenance(document, plan=True)
    except ValueError as error:
        _raise("assessment plan", [str(error)], source)


def _summary(items: list[JsonObject], statuses: tuple[str, ...]) -> JsonObject:
    return {
        status: sum(1 for item in items if item.get("status") == status)
        for status in statuses
    }


def _expected_rollup_status(counts: JsonObject, *, baseline: bool = False) -> str:
    if counts.get("fail", 0):
        return "fail"
    if counts.get("error", 0):
        return "error"
    if counts.get("missing", 0) or counts.get("unknown", 0):
        return "unknown"
    if not baseline and counts.get("not_applicable", 0):
        return "unknown"
    if counts.get("waived", 0):
        return "waived"
    total = sum(counts.values())
    if baseline and total and counts.get("not_applicable", 0) == total:
        return "not_applicable"
    return "pass"


def validate_assessment_results(
    document: JsonObject,
    *,
    source: Path | None = None,
) -> None:
    """Validate the v4 envelope and domain invariants."""
    from .assessment_provenance import validate_provenance
    _validate_schema(document, assessment_results_schema_path(), "assessment results", source)
    errors: list[str] = []

    collections = (
        ("summary", "results", RESULT_STATUSES),
        ("requirement_summary", "requirement_assessments", RESULT_STATUSES),
        (
            "requirement_baseline_summary",
            "requirement_baseline_assessments",
            RESULT_STATUSES,
        ),
    )
    for summary_key, items_key, statuses in collections:
        expected = _summary(document[items_key], statuses)
        if document[summary_key] != expected:
            errors.append(
                f"/{summary_key}: expected counts {expected}, got {document[summary_key]}"
            )

    result_ids = [item["instance_id"] for item in document["results"]]
    duplicates = _duplicates(result_ids)
    if duplicates:
        errors.append("/results: duplicate instance IDs: " + ", ".join(duplicates))
    waiver_ids = [
        item["waiver"]["id"]
        for item in document["results"]
        if "waiver" in item
    ]
    duplicates = _duplicates(waiver_ids)
    if duplicates:
        errors.append("/results: duplicate waiver IDs: " + ", ".join(duplicates))
    for index, result in enumerate(document["results"]):
        expected_fields = {
            "subject_id": document["subject_id"],
            "plan_id": document["plan_id"],
        }
        if "waiver_revision" in document:
            expected_fields["waiver_revision"] = document["waiver_revision"]
        elif "waiver_revision" in result:
            errors.append(
                f"/results/{index}/waiver_revision: envelope waiver revision is missing"
            )
        for field, expected in expected_fields.items():
            if field not in result:
                errors.append(
                    f"/results/{index}/{field}: required when present on the envelope"
                )
            elif result[field] != expected:
                errors.append(
                    f"/results/{index}/{field}: must match envelope value {expected}"
                )
        waiver = result.get("waiver")
        if waiver is not None:
            if "waiver_revision" not in document:
                errors.append(
                    f"/results/{index}/waiver: envelope waiver revision is required"
                )
            if waiver["subject_id"] != result["subject_id"]:
                errors.append(
                    f"/results/{index}/waiver/subject_id: must match the result subject"
                )
            if waiver["instance_id"] != result["instance_id"]:
                errors.append(
                    f"/results/{index}/waiver/instance_id: must match the result instance"
                )
            unsigned_waiver = {
                key: value
                for key, value in waiver.items()
                if key not in {"digest", "underlying_status"}
            }
            expected_digest = _content_digest(unsigned_waiver)
            if waiver["digest"] != expected_digest:
                errors.append(
                    f"/results/{index}/waiver/digest: content digest is "
                    f"{expected_digest}, got {waiver['digest']}"
                )
            evaluated_at = datetime.fromisoformat(
                document["evaluated_at"].replace("Z", "+00:00")
            )
            valid_from = datetime.fromisoformat(
                waiver["valid_from"].replace("Z", "+00:00")
            )
            expires_at = datetime.fromisoformat(
                waiver["expires_at"].replace("Z", "+00:00")
            )
            approved_at = datetime.fromisoformat(
                waiver["approved_at"].replace("Z", "+00:00")
            )
            if valid_from >= expires_at:
                errors.append(
                    f"/results/{index}/waiver: valid_from must precede expires_at"
                )
            if approved_at > valid_from:
                errors.append(
                    f"/results/{index}/waiver/approved_at: must not be later "
                    "than valid_from"
                )
            if not valid_from <= evaluated_at < expires_at:
                errors.append(
                    f"/results/{index}/waiver: assessment time is outside the "
                    "waiver validity window"
                )

    requirement_refs = [
        item["requirement"] for item in document["requirement_assessments"]
    ]
    duplicates = _duplicates(requirement_refs)
    if duplicates:
        errors.append(
            "/requirement_assessments: duplicate requirements: "
            + ", ".join(duplicates)
        )
    for index, assessment in enumerate(document["requirement_assessments"]):
        checks = assessment.get("checks", [])
        expected_summary = _summary(checks, CHECK_STATUSES)
        if assessment["check_summary"] != expected_summary:
            errors.append(
                f"/requirement_assessments/{index}/check_summary: expected "
                f"{expected_summary}, got {assessment['check_summary']}"
            )
        adoption_status = assessment["adoption"]["status"]
        if adoption_status == "not_applicable":
            expected_status = "not_applicable"
        elif adoption_status == "not_implemented":
            expected_status = "fail"
        else:
            expected_status = _expected_rollup_status(expected_summary)
        if assessment["status"] != expected_status:
            errors.append(
                f"/requirement_assessments/{index}/status: expected "
                f"{expected_status}, got {assessment['status']}"
            )
        check_ids = [item["instance_id"] for item in checks]
        if adoption_status == "implemented" and check_ids != assessment[
            "technical_instance_ids"
        ]:
            errors.append(
                f"/requirement_assessments/{index}/checks: order and identities "
                "must match technical_instance_ids"
            )
        if adoption_status != "implemented" and checks:
            errors.append(
                f"/requirement_assessments/{index}/checks: non-implemented or "
                "not-applicable adoption must not contain technical results"
            )

    baseline_refs = [
        item["baseline"]
        for item in document["requirement_baseline_assessments"]
    ]
    duplicates = _duplicates(baseline_refs)
    if duplicates:
        errors.append(
            "/requirement_baseline_assessments: duplicate baselines: "
            + ", ".join(duplicates)
        )
    for index, assessment in enumerate(
        document["requirement_baseline_assessments"]
    ):
        counts = Counter(item["status"] for item in assessment["requirements"])
        expected_status = _expected_rollup_status(dict(counts), baseline=True)
        if assessment["status"] != expected_status:
            errors.append(
                f"/requirement_baseline_assessments/{index}/status: expected "
                f"{expected_status}, got {assessment['status']}"
            )
        unknown_requirements = sorted(
            item["requirement"]
            for item in assessment["requirements"]
            if item["status"] != "missing"
            and item["requirement"] not in set(requirement_refs)
        )
        if unknown_requirements:
            errors.append(
                f"/requirement_baseline_assessments/{index}/requirements: "
                "no matching requirement assessment for "
                + ", ".join(unknown_requirements)
            )

    if errors:
        _raise("assessment results", errors, source)
    try:
        validate_provenance(document, plan=False)
    except ValueError as error:
        _raise("assessment results", [str(error)], source)
