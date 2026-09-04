from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackageSchemaMirrorTests(unittest.TestCase):
    def test_inventory_and_waiver_package_data_match_sources(self) -> None:
        for relative in (
            Path("schemas/inventory/resource.schema.json"),
            Path("schemas/waivers/resource.schema.json"),
        ):
            packaged = ROOT / "package-data" / relative
            self.assertTrue(packaged.is_file(), packaged)
            self.assertEqual((ROOT / relative).read_bytes(), packaged.read_bytes(), relative)

    def test_removed_configuration_artifact_schemas_are_not_package_data(self) -> None:
        self.assertEqual(
            list((ROOT / "tools/schemas").glob("configuration-*.schema.json")),
            [],
        )
        self.assertEqual(
            list((ROOT / "package-data/schemas").glob("configuration-*.schema.json")),
            [],
        )


if __name__ == "__main__":
    unittest.main()
