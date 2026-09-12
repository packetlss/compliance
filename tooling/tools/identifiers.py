"""Canonical ADR 0019 semantic identifier and schema-URI grammar."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit


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

_DNS_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _is_stable_dns_host(host: str | None) -> bool:
    if host is None or len(host) > 253:
        return False
    labels = host.split(".")
    if not all(_DNS_LABEL.fullmatch(label) for label in labels):
        return False
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return True
    return False


def _is_canonical_https_schema_uri(value: str, path_pattern: str) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and port is None
        and _is_stable_dns_host(parsed.hostname)
        and not parsed.query
        and not parsed.fragment
        and bool(re.fullmatch(path_pattern, parsed.path))
    )


def is_canonical_control_parameter_schema_id(
    value: str,
    control_id: str,
) -> bool:
    if not re.fullmatch(ID, control_id):
        return False
    path = re.escape(f"/schemas/controls/{control_id}/parameters/")
    return _is_canonical_https_schema_uri(
        value,
        rf"{path}{SCHEMA_CONTRACT_VERSION}\.schema\.json",
    )


def is_canonical_control_evidence_inputs_schema_id(
    value: str,
    control_id: str,
    dependency_id: str,
) -> bool:
    if not re.fullmatch(ID, control_id) or not re.fullmatch(SLOT, dependency_id):
        return False
    path = re.escape(
        f"/schemas/controls/{control_id}/evidence/{dependency_id}/inputs/"
    )
    return _is_canonical_https_schema_uri(
        value,
        rf"{path}{SCHEMA_CONTRACT_VERSION}\.schema\.json",
    )


def is_canonical_requirement_parameter_schema_id(
    value: str,
    requirement_id: str,
    slot: str,
) -> bool:
    if not re.fullmatch(ID, requirement_id) or not re.fullmatch(SLOT, slot):
        return False
    path = re.escape(
        f"/schemas/requirements/{requirement_id}/parameters/{slot}/"
    )
    return _is_canonical_https_schema_uri(
        value,
        rf"{path}{SCHEMA_CONTRACT_VERSION}\.schema\.json",
    )


def canonical_evidence_schema_path(evidence_type: str) -> str | None:
    match = re.fullmatch(rf"(?P<id>{ID})/v(?P<version>[1-9][0-9]*)", evidence_type)
    if match is None:
        return None
    return (
        f"/schemas/evidence/{match.group('id')}/"
        f"v{match.group('version')}.schema.json"
    )


def is_canonical_evidence_schema_id(value: str, evidence_type: str) -> bool:
    path = canonical_evidence_schema_path(evidence_type)
    return path is not None and _is_canonical_https_schema_uri(
        value,
        re.escape(path),
    )
