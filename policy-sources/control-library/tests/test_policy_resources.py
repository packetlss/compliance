"""Reusable-source contracts, independent of any adopting project or policy."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from tools.policy_sources import PolicySource
from tools.render_plan import load_policy_catalogs, validate_rego_entrypoints

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ROOT / "policies"
EXPECTED_CONTROL_IDS = {
    "organization.assertion.required",
    "iam.integration.required",
    "aws.account.number_at_least",
    "aws.account.setting_equals",
    "aws.s3.account_public_access_block_required",
    "linux.access.setting_equals",
    "linux.packages.required",
    "linux.sysctl.required",
    "macos.homebrew.formulae_required",
    "macos.security.setting_equals",
    "macos.system.minimum_version",
    "saas.tenant.number_at_least",
    "saas.tenant.setting_equals",
}
EXPECTED_EVIDENCE_PAYLOADS = {
    "aws.account.configuration/v1": {
        "account": {"id": "111122223333"},
        "root_user": {"mfa_enabled": True},
        "cloudtrail": {"multi_region_enabled": True, "retention_days": 90},
    },
    "aws.s3.account-public-access-block/v1": {
        "block_public_acls": True,
        "block_public_policy": True,
        "ignore_public_acls": True,
        "restrict_public_buckets": True,
    },
    "iam.integration.observation/v1": {
        "consumer": "host/test",
        "service": "service/iam",
        "asserted_by": "test-collector",
        "source_assertion_locator": "assertion://iam/current",
        "integrated": True,
    },
    "iam.service.observation/v1": {
        "consumer": "host/test",
        "source_assertion": {
            "subject_id": "service/iam",
            "asserted_by": "test-collector",
            "source_locator": "assertion://iam/current",
            "condition": "available",
            "outcome": "positive",
        },
    },
    "linux.access.configuration/v1": {
        "packages": {"sssd_installed": True},
        "sssd": {"domain": "example.invalid"},
        "ssh": {"allowed_groups": ["operators"]},
        "accounts": {"unmanaged_interactive_accounts": []},
    },
    "linux.packages/v1": {
        "ecosystem": "linux-native",
        "packages": [{"id": "auditd", "version": "1"}],
    },
    "linux.sysctl/v1": {
        "settings": [{"key": "kernel.randomize_va_space", "value": "2"}],
    },
    "macos.homebrew/v1": {
        "formulae": [{"name": "opa", "version": "1"}],
        "casks": [],
    },
    "macos.security/v1": {
        "gatekeeper": {"status": "enabled"},
        "sip": {"status": "enabled"},
    },
    "macos.system/v1": {
        "product_name": "macOS",
        "product_version": "15.0",
        "build_version": "24A000",
        "architecture": "arm64",
    },
    "organization.assertion/v1": {
        "beneficiary": "entity/test",
        "asserted_by": "test-collector",
        "source_locator": "assertion://organization/current",
        "scheme": "test-assurance",
        "outcome": "positive",
        "valid_from": "2026-09-01T00:00:00Z",
        "valid_until": "2026-10-01T00:00:00Z",
    },
    "saas.tenant.configuration/v1": {
        "tenant": {"id": "test", "provider": "example"},
        "authentication": {"sso_enforced": True, "mfa_enforced": True},
        "audit_log": {"retention_days": 180},
    },
}
SUBJECT_IDS = {
    "aws-account": "cloud-account/test",
    "entity": "entity/test",
    "linux-host": "host/test",
    "macos-workstation": "workstation/test",
    "saas-tenant": "saas/test",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def external_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "external_refs" and isinstance(item, list):
                yield from item
            else:
                yield from external_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from external_refs(item)


def evidence_document(schema, payload):
    evidence_type = schema["properties"]["type"]["const"]
    subject_type = schema["properties"]["subject"]["properties"]["type"]["const"]
    return {
        "schema": "compliance.example/evidence/v1",
        "id": f"evidence:{evidence_type}",
        "subject": {"id": SUBJECT_IDS[subject_type], "type": subject_type},
        "type": evidence_type,
        "collected_at": "2026-09-01T00:00:00Z",
        "collector": {"id": "test-collector", "version": "1"},
        "payload": payload,
    }


class PolicyResourceTests(unittest.TestCase):
    def test_all_library_schemas_are_valid(self):
        schemas = sorted(POLICIES.rglob("*.schema.json"))
        schemas.extend(sorted((ROOT / "release").glob("*.schema.json")))
        self.assertTrue(schemas)
        for path in schemas:
            with self.subTest(path=path.relative_to(ROOT)):
                Draft202012Validator.check_schema(read_json(path))

    def test_authored_policy_and_check_meaning_is_required_non_whitespace(self):
        digest = "sha256:" + "0" * 64
        cases = {
            "control.schema.json": (
                read_json(POLICIES / "controls/linux/sysctl-required/control.json"),
                ("title", "purpose"),
            ),
            "baseline.schema.json": (
                {"title": "Technical policy", "controls": []},
                ("title",),
            ),
            "baseline-overlay.schema.json": (
                {
                    "title": "Technical policy overlay",
                    "extends": [{"baseline": "test.base@1", "digest": digest}],
                    "operations": [],
                },
                ("title",),
            ),
            "requirement-baseline.schema.json": (
                {
                    "title": "Objective policy",
                    "requirements": [{
                        "requirement": "test.requirement@1",
                        "digest": digest,
                        "required": True,
                    }],
                },
                ("title",),
            ),
        }
        schema_root = POLICIES / "schemas/policy"
        for filename, (valid_spec, names) in cases.items():
            full_schema = read_json(schema_root / filename)
            validator = Draft202012Validator(full_schema)
            valid_document = {
                "apiVersion": (
                    "compliance.example/v1alpha1"
                    if filename == "requirement-baseline.schema.json"
                    else "compliance.example/v1"
                ),
                "kind": {
                    "control.schema.json": "Control",
                    "baseline.schema.json": "Baseline",
                    "baseline-overlay.schema.json": "BaselineOverlay",
                    "requirement-baseline.schema.json": "RequirementBaseline",
                }[filename],
                "metadata": {
                    "id": "test.meaning",
                    **(
                        {"version": 1}
                        if filename == "control.schema.json"
                        else {"revision": 1}
                    ),
                },
                "spec": valid_spec,
            }
            if filename == "control.schema.json":
                valid_document = valid_spec
            self.assertTrue(validator.is_valid(valid_document), filename)
            for name in names:
                for invalid in (None, "", " \t\n"):
                    changed = json.loads(json.dumps(valid_document))
                    if invalid is None:
                        changed["spec"].pop(name)
                    else:
                        changed["spec"][name] = invalid
                    with self.subTest(
                        schema=filename,
                        field=name,
                        invalid=invalid,
                    ):
                        self.assertFalse(validator.is_valid(changed))

    def test_reusable_catalog_and_rego_entrypoints(self):
        source = PolicySource("control-library", POLICIES)
        controls, baselines, errors = load_policy_catalogs(source)
        self.assertEqual(errors, [])
        self.assertEqual(baselines, {})
        manifests = sorted(POLICIES.rglob("control.json"))
        expected = {read_json(path)["metadata"]["id"] for path in manifests}
        self.assertEqual(expected, EXPECTED_CONTROL_IDS)
        self.assertEqual(len(expected), len(manifests), "control identities must be unique")
        self.assertEqual(set(controls), expected)
        self.assertEqual(validate_rego_entrypoints(source, controls), [])

    def test_evidence_contracts_are_required_only_without_payload_integrity(self):
        control_schema = read_json(POLICIES / "schemas/policy/control.schema.json")
        dependency = control_schema["$defs"]["evidenceRequirement"]
        self.assertNotIn("required", dependency["properties"])
        self.assertNotIn("required", dependency["required"])

        for path in sorted(POLICIES.glob("controls/*/*/control.json")):
            with self.subTest(control=path.relative_to(ROOT)):
                for evidence in read_json(path)["spec"]["evidence"]:
                    self.assertNotIn("required", evidence)

        for path in sorted(POLICIES.glob("schemas/evidence/*.schema.json")):
            with self.subTest(schema=path.relative_to(ROOT)):
                schema = read_json(path)
                self.assertNotIn("integrity", schema["required"])
                self.assertNotIn("integrity", schema["properties"])
                self.assertTrue(schema["additionalProperties"])

    def test_all_active_evidence_types_accept_minimal_full_envelopes(self):
        schemas = sorted(POLICIES.glob("schemas/evidence/*.schema.json"))
        actual_types = {
            read_json(path)["properties"]["type"]["const"] for path in schemas
        }
        self.assertEqual(actual_types, set(EXPECTED_EVIDENCE_PAYLOADS))
        self.assertEqual(len(schemas), 12)

        for path in schemas:
            with self.subTest(schema=path.relative_to(ROOT)):
                schema = read_json(path)
                evidence_type = schema["properties"]["type"]["const"]
                document = evidence_document(
                    schema,
                    EXPECTED_EVIDENCE_PAYLOADS[evidence_type],
                )
                errors = list(Draft202012Validator(
                    schema,
                    format_checker=FormatChecker(),
                ).iter_errors(document))
                self.assertEqual(errors, [])

    def test_new_optional_configuration_facts_are_typed_when_present(self):
        cases = (
            (
                "aws-account-configuration-v1.schema.json",
                "security_contact",
                "configured",
            ),
            (
                "saas-tenant-configuration-v1.schema.json",
                "guest_access",
                "allowed",
            ),
        )
        for filename, section, setting in cases:
            schema = read_json(POLICIES / "schemas/evidence" / filename)
            evidence_type = schema["properties"]["type"]["const"]
            for value in (True, False, None):
                payload = copy.deepcopy(EXPECTED_EVIDENCE_PAYLOADS[evidence_type])
                payload[section] = {setting: value}
                with self.subTest(schema=filename, value=value):
                    Draft202012Validator(schema).validate(
                        evidence_document(schema, payload)
                    )

            payload = copy.deepcopy(EXPECTED_EVIDENCE_PAYLOADS[evidence_type])
            payload[section] = {setting: "undetermined"}
            errors = list(Draft202012Validator(schema).iter_errors(
                evidence_document(schema, payload)
            ))
            self.assertEqual(len(errors), 1)
            self.assertEqual(
                list(errors[0].absolute_path),
                ["payload", section, setting],
            )

    def test_aws_control_parameters_admit_only_declared_typed_facts(self):
        boolean_schema = read_json(
            POLICIES / "controls/aws/account-setting-equals/parameters.schema.json"
        )
        numeric_schema = read_json(
            POLICIES / "controls/aws/account-number-at-least/parameters.schema.json"
        )
        boolean_validator = Draft202012Validator(boolean_schema)
        numeric_validator = Draft202012Validator(numeric_schema)

        for section, setting in (
            ("root_user", "mfa_enabled"),
            ("cloudtrail", "multi_region_enabled"),
            ("security_contact", "configured"),
        ):
            with self.subTest(section=section, setting=setting):
                boolean_validator.validate({
                    "section": section,
                    "setting": setting,
                    "expected": True,
                })
        numeric_validator.validate({
            "section": "cloudtrail",
            "setting": "retention_days",
            "minimum": 90,
        })

        for validator, parameters in (
            (boolean_validator, {
                "section": "opaque_extension",
                "setting": "enabled",
                "expected": True,
            }),
            (boolean_validator, {
                "section": "cloudtrail",
                "setting": "retention_days",
                "expected": True,
            }),
            (numeric_validator, {
                "section": "opaque_extension",
                "setting": "retention_days",
                "minimum": 90,
            }),
            (numeric_validator, {
                "section": "root_user",
                "setting": "mfa_enabled",
                "minimum": 1,
            }),
        ):
            with self.subTest(parameters=parameters):
                self.assertFalse(validator.is_valid(parameters))

    def test_saas_control_parameters_admit_only_declared_typed_facts(self):
        boolean_schema = read_json(
            POLICIES / "controls/saas/tenant-setting-equals/parameters.schema.json"
        )
        numeric_schema = read_json(
            POLICIES / "controls/saas/tenant-number-at-least/parameters.schema.json"
        )
        boolean_validator = Draft202012Validator(boolean_schema)
        numeric_validator = Draft202012Validator(numeric_schema)

        for section, setting in (
            ("authentication", "sso_enforced"),
            ("authentication", "mfa_enforced"),
            ("guest_access", "allowed"),
        ):
            with self.subTest(section=section, setting=setting):
                boolean_validator.validate({
                    "section": section,
                    "setting": setting,
                    "expected": True,
                })
        numeric_validator.validate({
            "section": "audit_log",
            "setting": "retention_days",
            "minimum": 180,
        })

        for validator, parameters in (
            (boolean_validator, {
                "section": "opaque_extension",
                "setting": "enabled",
                "expected": True,
            }),
            (boolean_validator, {
                "section": "audit_log",
                "setting": "retention_days",
                "expected": True,
            }),
            (numeric_validator, {
                "section": "opaque_extension",
                "setting": "retention_days",
                "minimum": 180,
            }),
            (numeric_validator, {
                "section": "authentication",
                "setting": "sso_enforced",
                "minimum": 1,
            }),
        ):
            with self.subTest(parameters=parameters):
                self.assertFalse(validator.is_valid(parameters))

    def test_linux_access_control_parameters_admit_only_declared_typed_facts(self):
        schema = read_json(
            POLICIES / "controls/linux/access-setting-equals/parameters.schema.json"
        )
        validator = Draft202012Validator(schema)
        valid = (
            {"section": "packages", "setting": "sssd_installed", "expected": True},
            {"section": "sssd", "setting": "domain", "expected": "company.example"},
            {"section": "ssh", "setting": "allowed_groups", "expected": ["operators"]},
            {
                "section": "accounts",
                "setting": "unmanaged_interactive_accounts",
                "expected": [],
            },
        )
        for parameters in valid:
            with self.subTest(parameters=parameters):
                validator.validate(parameters)

        invalid = (
            {"section": "opaque_extension", "setting": "enabled", "expected": True},
            {"section": "packages", "setting": "sssd_installed", "expected": "yes"},
            {"section": "sssd", "setting": "domain", "expected": True},
            {"section": "ssh", "setting": "allowed_groups", "expected": "operators"},
            {
                "section": "accounts",
                "setting": "unmanaged_interactive_accounts",
                "expected": False,
            },
        )
        for parameters in invalid:
            with self.subTest(parameters=parameters):
                self.assertFalse(validator.is_valid(parameters))

    def test_linux_sysctl_control_uses_keyed_parameter_contract(self):
        schema = read_json(
            POLICIES / "controls/linux/sysctl-required/parameters.schema.json"
        )
        validator = Draft202012Validator(schema)

        for parameters in (
            {"settings": {"kernel.randomize_va_space": "2"}},
            {
                "settings": {
                    "kernel.randomize_va_space": "2",
                    "net.ipv4.ip_forward": "0",
                }
            },
        ):
            with self.subTest(parameters=parameters):
                validator.validate(parameters)

        for parameters in (
            {"settings": {}},
            {"settings": {"invalid": "2"}},
            {"settings": {"net.ipv4.ip_forward": 0}},
            {"settings": [{"key": "net.ipv4.ip_forward", "value": "0"}]},
        ):
            with self.subTest(parameters=parameters):
                self.assertFalse(validator.is_valid(parameters))

    def test_configuration_evidence_extensions_remain_schema_valid(self):
        for filename, extension in (
            ("aws-account-configuration-v1.schema.json", {"organization": {"id": "o-test"}}),
            ("saas-tenant-configuration-v1.schema.json", {"billing": {"tier": "test"}}),
            ("linux-access-configuration-v1.schema.json", {"pam": {"profile": "test"}}),
        ):
            schema = read_json(POLICIES / "schemas/evidence" / filename)
            evidence_type = schema["properties"]["type"]["const"]
            payload = copy.deepcopy(EXPECTED_EVIDENCE_PAYLOADS[evidence_type])
            payload.update(extension)
            with self.subTest(schema=filename):
                Draft202012Validator(schema).validate(
                    evidence_document(schema, payload)
                )

    def test_schema_identities_are_unique(self):
        schemas = sorted(POLICIES.rglob("*.schema.json"))
        identities = [
            document["$id"]
            for path in schemas
            if "$id" in (document := read_json(path))
        ]
        self.assertTrue(identities)
        self.assertEqual(len(identities), len(set(identities)))

    def test_broken_library_contracts_are_rejected(self):
        # Mutate copies of this producer's actual resources. No consumer policy
        # or environment data is needed to prove the rejection boundary.
        cases = (
            ("controls/linux/sysctl-required/parameters.schema.json", None,
             "control-parameters-schema-unavailable"),
            ("schemas/evidence/linux-sysctl-v1.schema.json", None,
             "control-evidence-schema-missing"),
            ("controls/linux/sysctl-required/parameters.schema.json", {"type": "invalid"},
             "control-parameters-schema-invalid"),
            ("controls/linux/sysctl-required/control.json", {},
             "control-manifest-schema-invalid"),
        )
        for relative, replacement, expected in cases:
            with self.subTest(path=relative, expected=expected), tempfile.TemporaryDirectory() as temporary:
                policy = Path(temporary) / "policy"
                shutil.copytree(POLICIES, policy)
                target = policy / relative
                if replacement is None:
                    target.unlink()
                else:
                    target.write_text(json.dumps(replacement), encoding="utf-8")
                _, _, errors = load_policy_catalogs(PolicySource("control-library", policy))
                self.assertIn(expected, {error["type"] for error in errors}, errors)

    def test_configuration_facet_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            policy = Path(temporary) / "policy"
            shutil.copytree(POLICIES, policy)
            manifest_path = policy / "controls/linux/sysctl-required/control.json"
            manifest = read_json(manifest_path)
            manifest["spec"]["configuration"] = {
                "intent_type": "linux.sysctl.values/v1",
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            _, _, errors = load_policy_catalogs(PolicySource("control-library", policy))
            self.assertIn(
                "control-manifest-schema-invalid",
                {error["type"] for error in errors},
                errors,
            )

    def test_missing_rego_entrypoint_is_rejected(self):
        source = PolicySource("control-library", POLICIES)
        controls, _, errors = load_policy_catalogs(source)
        self.assertEqual(errors, [])
        controls["linux.sysctl.required"]["spec"]["entrypoint"] = "data.compliance.missing.result"
        self.assertTrue(validate_rego_entrypoints(source, controls))


class PolicySourceBoundaryTests(unittest.TestCase):
    def test_only_complete_reusable_controls_shared_rego_and_schemas_are_present(self):
        expected_control_files = {
            "control.json", "parameters.schema.json", "policy.rego", "policy_test.rego",
        }
        control_manifests = sorted((POLICIES / "controls").glob("*/*/control.json"))
        self.assertTrue(control_manifests)
        for manifest_path in control_manifests:
            with self.subTest(path=manifest_path.parent.relative_to(ROOT)):
                actual = {path.name for path in manifest_path.parent.iterdir() if path.is_file()}
                self.assertEqual(actual, expected_control_files)
                self.assertEqual(read_json(manifest_path)["kind"], "Control")

        expected_control_paths = {
            path
            for manifest_path in control_manifests
            for path in (
                manifest_path,
                manifest_path.parent / "parameters.schema.json",
                manifest_path.parent / "policy.rego",
                manifest_path.parent / "policy_test.rego",
            )
        }
        expected_control_paths.add(POLICIES / "controls/common/result.rego")
        actual_control_paths = {
            path for path in (POLICIES / "controls").rglob("*") if path.is_file()
        }
        self.assertEqual(actual_control_paths, expected_control_paths)

        schema_root = POLICIES / "schemas"
        schema_files = {path for path in schema_root.rglob("*") if path.is_file()}
        self.assertTrue(schema_files)
        self.assertTrue(all(path.name.endswith(".schema.json") for path in schema_files))
        self.assertTrue(all(path.parent.name in {"policy", "evidence"} for path in schema_files))
        self.assertFalse((schema_root / "configuration").exists())

        actual_policy_files = {path for path in POLICIES.rglob("*") if path.is_file()}
        self.assertEqual(actual_policy_files, actual_control_paths | schema_files)

    def test_controls_are_assessment_only_and_assurance_references_remain_available(self):
        manifests = sorted((POLICIES / "controls").glob("*/*/control.json"))
        self.assertEqual(
            {read_json(path)["metadata"]["id"] for path in manifests},
            EXPECTED_CONTROL_IDS,
        )
        for path in manifests:
            with self.subTest(path=path.relative_to(ROOT)):
                spec = read_json(path)["spec"]
                self.assertNotIn("configuration", spec)
                self.assertNotIn("intent_type", spec)
                self.assertEqual(spec["parameters_schema"], "parameters.schema.json")

        policy_schemas = POLICIES / "schemas/policy"
        for name in ("baseline.schema.json", "control-realization.schema.json"):
            with self.subTest(schema=name):
                control_instance = read_json(policy_schemas / name)["$defs"]["controlInstance"]
                self.assertEqual(
                    set(control_instance["required"]),
                    {"instance_id", "implementation"},
                )
                self.assertIn("parameters", control_instance["properties"])

        for name in (
            "baseline-overlay.schema.json",
            "baseline.schema.json",
            "control-realization.schema.json",
            "control-requirement.schema.json",
            "requirement-baseline.schema.json",
        ):
            with self.subTest(schema=name):
                self.assertTrue((policy_schemas / name).is_file())

    def test_no_adoption_specific_resources_are_authored_in_this_source(self):
        adoption_kinds = {
            "Baseline", "BaselineOverlay", "ControlRequirement", "ControlRealization",
            "RequirementBaseline",
        }
        authored_resources = [
            path for path in POLICIES.rglob("*.json")
            if not path.name.endswith(".schema.json")
        ]
        self.assertTrue(authored_resources)
        for path in authored_resources:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(read_json(path).get("kind"), adoption_kinds)

    def test_external_adoption_mappings_remain_outside_this_source(self):
        for path in POLICIES.rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(list(external_refs(read_json(path))), [])


if __name__ == "__main__":
    unittest.main()
