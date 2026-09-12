"""ADR 0019 schema URI structure is publisher-host independent and offline."""

import unittest

from tools.identifiers import (
    is_canonical_control_evidence_inputs_schema_id,
    is_canonical_control_parameter_schema_id,
    is_canonical_evidence_schema_id,
    is_canonical_requirement_parameter_schema_id,
)


class SchemaIdentityTests(unittest.TestCase):
    def test_adopter_https_host_is_valid_for_each_owner_role(self):
        host = "https://schemas.adopter.example"
        self.assertTrue(is_canonical_control_parameter_schema_id(
            host + "/schemas/controls/adopter.control/parameters/v2.schema.json",
            "adopter.control",
        ))
        self.assertTrue(is_canonical_control_evidence_inputs_schema_id(
            host + "/schemas/controls/adopter.control/evidence/observation/inputs/v3.schema.json",
            "adopter.control",
            "observation",
        ))
        self.assertTrue(is_canonical_requirement_parameter_schema_id(
            host + "/schemas/requirements/adopter.requirement/parameters/review_age/v4.schema.json",
            "adopter.requirement",
            "review_age",
        ))
        self.assertTrue(is_canonical_evidence_schema_id(
            host + "/schemas/evidence/adopter.observation/v5.schema.json",
            "adopter.observation/v5",
        ))
        self.assertTrue(is_canonical_control_parameter_schema_id(
            "https://SCHEMAS.ADOPTER.EXAMPLE/schemas/controls/"
            "adopter.control/parameters/v1.schema.json",
            "adopter.control",
        ))

    def test_wrong_owner_path_role_and_version_are_rejected(self):
        host = "https://schemas.adopter.example"
        invalid_control_parameters = (
            host + "/schemas/controls/other.control/parameters/v1.schema.json",
            host + "/schemas/requirements/adopter.control/parameters/value/v1.schema.json",
            host + "/schemas/controls/adopter.control/evidence/value/inputs/v1.schema.json",
            host + "/schemas/controls/adopter.control/parameters/v0.schema.json",
            host + "/schemas/controls/adopter.control/parameters/v01.schema.json",
            host + "/schemas/controls/adopter.control/parameters/v1alpha1.schema.json",
        )
        for value in invalid_control_parameters:
            with self.subTest(control_parameter=value):
                self.assertFalse(is_canonical_control_parameter_schema_id(
                    value,
                    "adopter.control",
                ))

        self.assertFalse(is_canonical_control_evidence_inputs_schema_id(
            host + "/schemas/controls/other.control/evidence/observation/inputs/v1.schema.json",
            "adopter.control",
            "observation",
        ))
        self.assertFalse(is_canonical_control_evidence_inputs_schema_id(
            host + "/schemas/controls/adopter.control/evidence/other_slot/inputs/v1.schema.json",
            "adopter.control",
            "observation",
        ))
        self.assertFalse(is_canonical_requirement_parameter_schema_id(
            host + "/schemas/requirements/other.requirement/parameters/review_age/v1.schema.json",
            "adopter.requirement",
            "review_age",
        ))
        self.assertFalse(is_canonical_requirement_parameter_schema_id(
            host + "/schemas/requirements/adopter.requirement/parameters/other_slot/v1.schema.json",
            "adopter.requirement",
            "review_age",
        ))
        self.assertFalse(is_canonical_evidence_schema_id(
            host + "/schemas/evidence/adopter.other/v5.schema.json",
            "adopter.observation/v5",
        ))
        self.assertFalse(is_canonical_evidence_schema_id(
            host + "/schemas/evidence/adopter.observation/v6.schema.json",
            "adopter.observation/v5",
        ))

    def test_uri_must_be_absolute_https_dns_without_resolution_metadata(self):
        path = "/schemas/controls/adopter.control/parameters/v1.schema.json"
        invalid = (
            "http://schemas.adopter.example" + path,
            "//schemas.adopter.example" + path,
            "https://user@schemas.adopter.example" + path,
            "https://schemas.adopter.example:443" + path,
            "https://schemas.adopter.example:" + path,
            "https://192.0.2.1" + path,
            "https://schemas.adopter.example" + path + "?revision=1",
            "https://schemas.adopter.example" + path + "#schema",
            "https://schemas.\nadopter.example" + path,
            "https://schemas.\tadopter.example" + path,
            " https://schemas.adopter.example" + path,
            "https://schemas.adopter.example" + path + "\r",
        )
        for value in invalid:
            with self.subTest(uri=value):
                self.assertFalse(is_canonical_control_parameter_schema_id(
                    value,
                    "adopter.control",
                ))


if __name__ == "__main__":
    unittest.main()
