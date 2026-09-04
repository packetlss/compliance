"""Load, validate, select, and explain project-owned waiver resources."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from ._canonical_json import canonical_json_bytes


JsonObject = dict[str, Any]


class WaiverValidationError(ValueError):
    """An authored waiver catalog violates its schema or semantic contract."""


def waiver_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas/waivers/resource.schema.json"


def _content_digest(value: Any) -> str:
    encoded = canonical_json_bytes(value)
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else "/"


def parse_timestamp(value: str, *, field: str = "timestamp") -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise WaiverValidationError(f"{field} is not a valid date-time: {value!r}") from error
    if parsed.tzinfo is None:
        raise WaiverValidationError(f"{field} must include a timezone: {value!r}")
    return parsed.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _resource_paths(path: Path | None) -> list[Path]:
    if path is None or not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file()
        and candidate.suffix.lower() in {".json", ".yaml", ".yml"}
    )


def _load_documents(path: Path) -> list[tuple[Path, int, Any]]:
    try:
        with path.open(encoding="utf-8") as stream:
            if path.suffix.lower() == ".json":
                return [(path, 1, json.load(stream))]
            return [
                (path, index, document)
                for index, document in enumerate(yaml.safe_load_all(stream), start=1)
                if document is not None
            ]
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as error:
        raise WaiverValidationError(f"cannot read waiver resource {path}: {error}") from error


def _normalize(document: JsonObject) -> JsonObject:
    spec = document["spec"]
    approval = spec["approval"]
    valid_from = parse_timestamp(spec["validFrom"], field="spec.validFrom")
    expires_at = parse_timestamp(spec["expiresAt"], field="spec.expiresAt")
    approved_at = parse_timestamp(
        approval["approvedAt"], field="spec.approval.approvedAt"
    )
    if valid_from >= expires_at:
        raise WaiverValidationError("spec.validFrom must be earlier than spec.expiresAt")
    if approved_at > valid_from:
        raise WaiverValidationError(
            "spec.approval.approvedAt must not be later than spec.validFrom"
        )
    waiver = {
        "id": document["metadata"]["name"],
        "subject_id": spec["subjectRef"]["id"],
        "instance_id": spec["controlRef"]["instanceId"],
        "valid_from": _format_timestamp(valid_from),
        "expires_at": _format_timestamp(expires_at),
        "rationale": spec["rationale"],
        "owner": spec["owner"],
        "approval_ref": approval["reference"],
        "approved_by": approval["approvedBy"],
        "approved_at": _format_timestamp(approved_at),
    }
    return {**waiver, "digest": _content_digest(waiver)}


def load_waivers(path: Path | None) -> tuple[list[JsonObject], str]:
    """Return a deterministic normalized waiver catalog and its revision."""
    schema = json.loads(waiver_schema_path().read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    waivers: list[JsonObject] = []
    sources: dict[str, str] = {}
    for resource_path in _resource_paths(path):
        for source, document_index, document in _load_documents(resource_path):
            errors = sorted(
                validator.iter_errors(document),
                key=lambda error: (
                    tuple(str(part) for part in error.absolute_path),
                    error.message,
                ),
            )
            locator = f"{source} document {document_index}"
            if errors:
                rendered = "; ".join(
                    f"{_pointer(error.absolute_path)}: {error.message}"
                    for error in errors
                )
                raise WaiverValidationError(
                    f"waiver schema validation failed for {locator}: {rendered}"
                )
            try:
                waiver = _normalize(document)
            except WaiverValidationError as error:
                raise WaiverValidationError(
                    f"invalid waiver {locator}: {error}"
                ) from error
            if waiver["id"] in sources:
                raise WaiverValidationError(
                    f"duplicate waiver {waiver['id']!r}: "
                    f"{sources[waiver['id']]} and {locator}"
                )
            sources[waiver["id"]] = locator
            waivers.append(waiver)

    waivers.sort(key=lambda item: item["id"])
    by_target: dict[tuple[str, str], list[JsonObject]] = {}
    for waiver in waivers:
        by_target.setdefault(
            (waiver["subject_id"], waiver["instance_id"]), []
        ).append(waiver)
    for (subject_id, instance_id), targeted in sorted(by_target.items()):
        targeted.sort(
            key=lambda item: (item["valid_from"], item["expires_at"], item["id"])
        )
        for previous, current in zip(targeted, targeted[1:]):
            if parse_timestamp(current["valid_from"]) < parse_timestamp(
                previous["expires_at"]
            ):
                raise WaiverValidationError(
                    "overlapping waivers for "
                    f"{subject_id}/{instance_id}: {previous['id']} and {current['id']}"
                )
    return waivers, _content_digest(waivers)


def waiver_state(waiver: JsonObject, at: datetime) -> str:
    if at.tzinfo is None:
        raise WaiverValidationError("waiver lifecycle time must include a timezone")
    instant = at.astimezone(UTC)
    if instant < parse_timestamp(waiver["valid_from"]):
        return "scheduled"
    if instant < parse_timestamp(waiver["expires_at"]):
        return "active"
    return "expired"


def active_waiver(
    waivers: list[JsonObject],
    subject_id: str,
    instance_id: str,
    at: datetime,
) -> JsonObject | None:
    matches = [
        waiver
        for waiver in waivers
        if waiver["subject_id"] == subject_id
        and waiver["instance_id"] == instance_id
        and waiver_state(waiver, at) == "active"
    ]
    if len(matches) > 1:
        raise WaiverValidationError(
            f"multiple active waivers for {subject_id}/{instance_id}: "
            + ", ".join(item["id"] for item in matches)
        )
    return matches[0] if matches else None


def waiver_catalog_document(
    waivers: list[JsonObject],
    revision: str,
    at: datetime,
    *,
    subject_id: str | None = None,
    states: set[str] | None = None,
) -> JsonObject:
    selected = []
    for waiver in waivers:
        state = waiver_state(waiver, at)
        if subject_id and waiver["subject_id"] != subject_id:
            continue
        if states and state not in states:
            continue
        selected.append({**waiver, "state": state})
    counts = Counter(item["state"] for item in selected)
    return {
        "schema": "compliance.example/waiver-catalog/v1alpha1",
        "generated_at": _format_timestamp(at),
        "revision": revision,
        "summary": {
            state: counts[state] for state in ("active", "scheduled", "expired")
        },
        "waivers": selected,
    }
