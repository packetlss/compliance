"""Content-addressed identity for evidence documents consumed by assessment runtime."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from ._canonical_json import canonical_json_bytes


EVIDENCE_DOCUMENT_DIGEST_ALGORITHM = (
    "compliance.example/evidence-document-digest/v1alpha1"
)
EVIDENCE_SET_DIGEST_ALGORITHM = "compliance.example/evidence-set-digest/v1alpha1"


class EvidenceProvenanceError(ValueError):
    """Evidence input cannot be represented by the provenance contract."""


def evidence_document_digest(document: dict[str, Any]) -> str:
    """Hash the complete semantic JSON evidence document, independent of file layout."""
    return f"sha256:{hashlib.sha256(canonical_json_bytes(document)).hexdigest()}"


def evidence_set_provenance(
    documents: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Describe an order/path-independent subject evidence snapshot."""
    entries: list[dict[str, str]] = []
    for document in documents:
        evidence_id = document.get("id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise EvidenceProvenanceError("evidence document lacks a stable non-empty id")
        entries.append({
            "id": evidence_id,
            "digest": evidence_document_digest(document),
        })
    entries.sort(key=lambda item: (item["id"], item["digest"]))
    set_digest = f"sha256:{hashlib.sha256(canonical_json_bytes(entries)).hexdigest()}"
    return {
        "documentDigestAlgorithm": EVIDENCE_DOCUMENT_DIGEST_ALGORITHM,
        "setDigestAlgorithm": EVIDENCE_SET_DIGEST_ALGORITHM,
        "setDigest": set_digest,
        "documents": entries,
    }
