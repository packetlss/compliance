"""Canonical ADR 0019 semantic identifier and schema-URI grammar."""

from __future__ import annotations

import re


SEGMENT = r"[a-z0-9]+(?:-[a-z0-9]+)*"
ID = rf"{SEGMENT}(?:\.{SEGMENT})*"
SLOT = r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*"
REVISION = r"[a-z0-9]+(?:[.-][a-z0-9]+)*"
NUMBER = r"[1-9][0-9]*"
WIRE = rf"v{NUMBER}(?:(?:alpha|beta){NUMBER})?"
REFERENCE = rf"{ID}@{REVISION}"
EVIDENCE_TYPE = rf"{ID}/v{NUMBER}"
SCHEMA_CONTRACT_VERSION = rf"v{NUMBER}"

ID_PATTERN = rf"^{ID}$"
SLOT_PATTERN = rf"^{SLOT}$"
REVISION_PATTERN = rf"^{REVISION}$"
REFERENCE_PATTERN = rf"^{REFERENCE}$"
EVIDENCE_TYPE_PATTERN = rf"^{EVIDENCE_TYPE}$"
WIRE_PATTERN = rf"^{WIRE}$"


def canonical_control_parameter_schema_id(control_id: str) -> re.Pattern[str]:
    prefix = re.escape(
        f"https://compliance.example/schemas/controls/{control_id}/parameters/"
    )
    return re.compile(rf"^{prefix}{SCHEMA_CONTRACT_VERSION}\.schema\.json$")


def canonical_control_evidence_inputs_schema_id(
    control_id: str,
    dependency_id: str,
) -> re.Pattern[str]:
    prefix = re.escape(
        "https://compliance.example/schemas/controls/"
        f"{control_id}/evidence/{dependency_id}/inputs/"
    )
    return re.compile(rf"^{prefix}{SCHEMA_CONTRACT_VERSION}\.schema\.json$")


def canonical_requirement_parameter_schema_id(
    requirement_id: str,
    slot: str,
) -> re.Pattern[str]:
    prefix = re.escape(
        "https://compliance.example/schemas/requirements/"
        f"{requirement_id}/parameters/{slot}/"
    )
    return re.compile(rf"^{prefix}{SCHEMA_CONTRACT_VERSION}\.schema\.json$")


def canonical_evidence_schema_id(evidence_type: str) -> str | None:
    match = re.fullmatch(rf"(?P<id>{ID})/v(?P<version>[1-9][0-9]*)", evidence_type)
    if match is None:
        return None
    return (
        "https://compliance.example/schemas/evidence/"
        f"{match.group('id')}/v{match.group('version')}.schema.json"
    )
