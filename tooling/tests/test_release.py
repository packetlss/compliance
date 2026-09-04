from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.release import (
    CLI_NAME,
    DISTRIBUTION_NAME,
    RELEASE_METADATA_SCHEMA,
    tooling_release_identity,
)
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM


ROOT = Path(__file__).resolve().parents[1]


def _ci_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (ROOT / "scripts/ci-versions.env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value
    return values


class ToolingReleaseIdentityTests(unittest.TestCase):
    def test_installed_or_editable_identity_is_machine_readable(self) -> None:
        identity = tooling_release_identity()
        self.assertEqual(identity.schema, RELEASE_METADATA_SCHEMA)
        self.assertEqual(identity.distribution, DISTRIBUTION_NAME)
        self.assertEqual(identity.cli, CLI_NAME)
        self.assertNotEqual(identity.version, "uninstalled")
        self.assertEqual(identity.tested_opa_version, _ci_versions()["OPA_VERSION"])
        self.assertEqual(
            identity.source_digest_algorithm,
            TOOLING_SOURCE_DIGEST_ALGORITHM,
        )
        if identity.source_digest is not None:
            self.assertRegex(identity.source_digest, re.compile(r"^sha256:[0-9a-f]{64}$"))

        document = identity.document()
        self.assertEqual(
            document["build_kind"],
            "release" if identity.source_digest else "development",
        )
        self.assertEqual(document["source_digest"], identity.source_digest)
        self.assertEqual(
            document["source_digest_algorithm"],
            TOOLING_SOURCE_DIGEST_ALGORITHM,
        )


if __name__ == "__main__":
    unittest.main()
