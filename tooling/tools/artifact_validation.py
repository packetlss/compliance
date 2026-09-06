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
    from .assessment_provenance import validate_plan_provenance
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
        validate_plan_provenance(document)
    except ValueError as error:
        _raise("assessment plan", [str(error)], source)


def result_outcome(document: JsonObject) -> str:
    """Derive the immutable overall outcome from the recorded outcome sets."""
    items = [
        *document.get("results", []),
        *document.get("requirement_assessments", []),
        *document.get("requirement_baseline_assessments", []),
    ]
    for status in ("error", "fail", "unknown", "waived", "pass", "not_applicable"):
        if any(item.get("status") == status for item in items):
            return status
    return "no_controls"


def validate_assessment_results(
    document: JsonObject,
    *,
    source: Path | None = None,
) -> None:
    """Validate the v4 envelope and domain invariants."""
    from .assessment_provenance import validate_result_provenance
    _validate_schema(document, assessment_results_schema_path(), "assessment results", source)
    errors: list[str] = []

    result_ids = [item["instance_id"] for item in document["results"]]
    if result_ids != sorted(set(result_ids)):
        errors.append("/results: instance IDs must be unique and canonically ordered")
    waiver_ids = [
        item["waiver"]["id"]
        for item in document["results"]
        if "waiver" in item
    ]
    duplicates = _duplicates(waiver_ids)
    if duplicates:
        errors.append("/results: duplicate waiver IDs: " + ", ".join(duplicates))
    for index, result in enumerate(document["results"]):
        waiver = result.get("waiver")
        if result["status"] == "waived" and waiver is None:
            errors.append(f"/results/{index}/waiver: waived outcome requires an applied waiver")
        if result["status"] != "waived" and waiver is not None:
            errors.append(f"/results/{index}/waiver: only an underlying fail may be waived")
        if waiver is not None:
            if waiver["subject_id"] != document["subject_id"]:
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
    if requirement_refs != sorted(set(requirement_refs)):
        errors.append("/requirement_assessments: references must be unique and canonically ordered")

    baseline_refs = [
        item["baseline"]
        for item in document["requirement_baseline_assessments"]
    ]
    if baseline_refs != sorted(set(baseline_refs)):
        errors.append("/requirement_baseline_assessments: references must be unique and canonically ordered")
    expected_outcome = result_outcome(document)
    if document["outcome"] != expected_outcome:
        errors.append(
            f"/outcome: expected {expected_outcome!r} from recorded outcomes, "
            f"got {document['outcome']!r}"
        )

    if errors:
        _raise("assessment results", errors, source)
    try:
        validate_result_provenance(document)
    except ValueError as error:
        _raise("assessment results", [str(error)], source)
