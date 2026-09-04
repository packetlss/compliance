import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


COLLECTOR_PATH = (
    Path(__file__).resolve().parents[1] / "collectors/mock-api/collect.py"
)
SPEC = importlib.util.spec_from_file_location("mock_api_collector", COLLECTOR_PATH)
assert SPEC is not None and SPEC.loader is not None
COLLECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COLLECTOR)


class MockCollectorTests(unittest.TestCase):
    def test_payload_integrity_uses_fixed_jcs_vector(self):
        self.assertEqual(
            COLLECTOR.canonical_digest({"z": 1e-7, "a": "Å"}),
            "sha256:1531e7cc8993627321363a8b4aa683a03bd68205286da4a2b02e4bfe87c588a2",
        )

    def test_fixed_collection_instant_is_normalized_and_persisted(self):
        collected_at = COLLECTOR.parse_collected_at("2026-09-01T02:00:00+02:00")
        fixture = {
            "subject": {"id": "host/example", "type": "linux-host"},
            "type": "linux.packages/v1",
            "collector": {"id": "mock-api/test", "version": "1"},
            "payload": {"ecosystem": "linux-native", "packages": []},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "packages-api.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")

            evidence = COLLECTOR.collect_fixture(path, collected_at)

        self.assertEqual(evidence["collected_at"], "2026-09-01T00:00:00Z")
        self.assertIn("2026-09-01T00:00:00Z", evidence["id"])

    def test_fixed_collection_instant_requires_timezone(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            COLLECTOR.parse_collected_at("2026-09-01T00:00:00")


if __name__ == "__main__":
    unittest.main()
