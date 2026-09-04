import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from tools.waivers import (
    WaiverValidationError,
    active_waiver,
    load_waivers,
    waiver_catalog_document,
)


def waiver_document(
    name="test-waiver",
    *,
    valid_from="2026-08-01T00:00:00Z",
    expires_at="2026-09-01T00:00:00Z",
):
    return f"""\
apiVersion: compliance.example/v1alpha1
kind: Waiver
metadata:
  name: {name}
spec:
  subjectRef:
    id: host/test
  controlRef:
    instanceId: test.control
  validFrom: \"{valid_from}\"
  expiresAt: \"{expires_at}\"
  rationale: Temporary rollout constraint.
  owner: platform-operations
  approval:
    reference: risk/TEST-1
    approvedBy: risk-owner
    approvedAt: \"2026-07-31T00:00:00Z\"
"""


class WaiverCatalogTests(unittest.TestCase):
    def test_fixed_jcs_waiver_and_catalog_vectors(self):
        document = waiver_document("unicode-waiver").replace(
            "Temporary rollout constraint.", "Tillfällig åtgärd."
        ).replace("platform-operations", "säkerhet")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "waiver.yaml").write_text(document, encoding="utf-8")
            waivers, revision = load_waivers(root)

        self.assertEqual(
            waivers[0]["digest"],
            "sha256:e0b88316fb3844e5655e73d287440cd6403cc175442b62758917f4e24560ba95",
        )
        self.assertEqual(
            revision,
            "sha256:45a07d5010a4af4dfdd2b634d664ea423ebf259016d5f5bdad6754f113f91c2b",
        )

    def test_loads_normalized_catalog_and_selects_active_waiver(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "waiver.yaml").write_text(waiver_document(), encoding="utf-8")

            waivers, revision = load_waivers(root)
            selected = active_waiver(
                waivers,
                "host/test",
                "test.control",
                datetime(2026, 8, 15, tzinfo=UTC),
            )

        self.assertEqual(revision[:7], "sha256:")
        self.assertEqual(selected["id"], "test-waiver")
        self.assertEqual(selected["approval_ref"], "risk/TEST-1")
        self.assertIn("digest", selected)

    def test_validity_window_is_start_inclusive_and_end_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "waiver.yaml").write_text(waiver_document(), encoding="utf-8")
            waivers, _ = load_waivers(root)

            at_start = active_waiver(
                waivers,
                "host/test",
                "test.control",
                datetime(2026, 8, 1, tzinfo=UTC),
            )
            at_end = active_waiver(
                waivers,
                "host/test",
                "test.control",
                datetime(2026, 9, 1, tzinfo=UTC),
            )

        self.assertIsNotNone(at_start)
        self.assertIsNone(at_end)

    def test_rejects_overlapping_waivers_for_one_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "first.yaml").write_text(waiver_document("first"), encoding="utf-8")
            (root / "second.yaml").write_text(
                waiver_document(
                    "second",
                    valid_from="2026-08-15T00:00:00Z",
                    expires_at="2026-10-01T00:00:00Z",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(WaiverValidationError, "overlapping waivers"):
                load_waivers(root)

    def test_rejects_approval_after_waiver_start(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = waiver_document().replace(
                "2026-07-31T00:00:00Z",
                "2026-08-02T00:00:00Z",
            )
            (root / "waiver.yaml").write_text(document, encoding="utf-8")

            with self.assertRaisesRegex(WaiverValidationError, "approvedAt"):
                load_waivers(root)

    def test_catalog_view_exposes_lifecycle_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "waiver.yaml").write_text(waiver_document(), encoding="utf-8")
            waivers, revision = load_waivers(root)

            document = waiver_catalog_document(
                waivers,
                revision,
                datetime(2026, 8, 15, tzinfo=UTC),
            )

        self.assertEqual(document["summary"], {
            "active": 1,
            "scheduled": 0,
            "expired": 0,
        })
        self.assertEqual(document["waivers"][0]["state"], "active")

    def test_lifecycle_rejects_naive_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "waiver.yaml").write_text(waiver_document(), encoding="utf-8")
            waivers, revision = load_waivers(root)

            with self.assertRaisesRegex(WaiverValidationError, "timezone"):
                waiver_catalog_document(
                    waivers,
                    revision,
                    datetime(2026, 8, 15),
                )


if __name__ == "__main__":
    unittest.main()
