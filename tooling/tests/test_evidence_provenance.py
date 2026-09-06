from __future__ import annotations

import copy
import unittest

from tools.evidence_provenance import (
    EVIDENCE_DOCUMENT_DIGEST_ALGORITHM,
    EVIDENCE_SET_DIGEST_ALGORITHM,
    evidence_document_digest,
    evidence_set_provenance,
)


class EvidenceProvenanceTests(unittest.TestCase):
    def _evidence(self, evidence_id: str, value: int) -> dict:
        return {
            "schema": "compliance.example/evidence/v1",
            "id": evidence_id,
            "subject": {"id": "host/example", "type": "linux-host"},
            "type": "example/v1",
            "collected_at": "2026-08-30T00:00:00Z",
            "collector": {"id": "test", "version": "1.0.0"},
            "payload": {"value": value},
        }

    def test_document_digest_covers_complete_semantic_document(self) -> None:
        document = self._evidence("evidence:a", 1)
        same = copy.deepcopy(document)
        changed_collector = copy.deepcopy(document)
        changed_collector["collector"]["version"] = "1.0.1"
        changed_payload = copy.deepcopy(document)
        changed_payload["payload"]["value"] = 2
        changed_extension = copy.deepcopy(document)
        changed_extension["integrity"] = {"digest": "opaque-extension-value"}
        self.assertEqual(evidence_document_digest(document), evidence_document_digest(same))
        self.assertNotEqual(
            evidence_document_digest(document),
            evidence_document_digest(changed_collector),
        )
        self.assertNotEqual(
            evidence_document_digest(document),
            evidence_document_digest(changed_payload),
        )
        self.assertNotEqual(
            evidence_document_digest(document),
            evidence_document_digest(changed_extension),
        )

    def test_set_identity_is_order_independent_and_preserves_membership(self) -> None:
        first = self._evidence("evidence:a", 1)
        second = self._evidence("evidence:b", 2)
        forward = evidence_set_provenance([first, second])
        reverse = evidence_set_provenance([second, first])
        self.assertEqual(forward, reverse)
        self.assertEqual(
            forward["documentDigestAlgorithm"],
            EVIDENCE_DOCUMENT_DIGEST_ALGORITHM,
        )
        self.assertEqual(forward["setDigestAlgorithm"], EVIDENCE_SET_DIGEST_ALGORITHM)
        self.assertTrue(forward["setDigest"].startswith("sha256:"))
        self.assertEqual([item["id"] for item in forward["documents"]], ["evidence:a", "evidence:b"])

        changed = evidence_set_provenance([first])
        self.assertNotEqual(forward["setDigest"], changed["setDigest"])

    def test_fixed_jcs_document_and_set_vectors(self) -> None:
        # Fixed with the RFC 8785 Appendix A ECMAScript canonicalizer and Node SHA-256.
        self.assertEqual(
            EVIDENCE_DOCUMENT_DIGEST_ALGORITHM,
            "compliance.example/evidence-document-digest/v1alpha1",
        )
        self.assertEqual(
            EVIDENCE_SET_DIGEST_ALGORITHM,
            "compliance.example/evidence-set-digest/v1alpha1",
        )
        first = {
            "id": "evidence:β",
            "payload": {"value": 1e-7},
            "schema": "compliance.example/evidence/v1",
        }
        second = {
            "schema": "compliance.example/evidence/v1",
            "payload": {"value": -0.0, "label": "Å"},
            "id": "evidence:a",
        }
        first_digest = "sha256:e4edd3c7aa025f4e53434c166d8d03b901e114b9db4b819d91e8a7c064d51c21"
        second_digest = "sha256:5ceb46e96ca461f74073ba94f5c2dd29968e0e82042db9ba01375548d031e96b"
        set_digest = "sha256:f2a07f66351b333a1624686d1200b330e734d60eec30c5101e0d81a082f951b0"

        self.assertEqual(evidence_document_digest(first), first_digest)
        self.assertEqual(evidence_document_digest(second), second_digest)
        provenance = evidence_set_provenance([first, second])
        self.assertEqual(provenance["setDigest"], set_digest)
        self.assertEqual(
            provenance["documents"],
            [
                {"id": "evidence:a", "digest": second_digest},
                {"id": "evidence:β", "digest": first_digest},
            ],
        )


if __name__ == "__main__":
    unittest.main()
