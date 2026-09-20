import copy
import itertools
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from contract_fixtures import evidence_schema, fixture_root

from tools import policy_parameters as pp
from tools.artifact_validation import validate_assessment_plan
from tools.render_plan import (
    BaselineResolutionError,
    baseline_semantic_digest,
    content_digest,
    control_definition_fingerprint,
    load_baseline_catalog,
    load_control_catalog,
    load_evidence_schema_catalog,
    load_inventory_inputs,
    load_json,
    load_policy_catalogs,
    load_parameter_policy_catalogs,
    load_requirement_catalogs,
    load_resource_documents,
    normalize_subject,
    render_plan,
    resource_validation_errors,
    resolve_baseline,
    resolve_groups,
    source_tree_digest,
    validate_group_dag,
    validate_control_evidence_contracts,
    validate_policy_catalog,
    validate_rego_entrypoints,
)
from tools.policy_sources import PolicySource
from tools.operation import plan_disposition


class InventoryResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        cls.schema = load_json(
            cls.root / "schemas/inventory/resource.schema.json"
        )

    def test_loads_multiple_yaml_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resources.yaml"
            path.write_text(
                """\
apiVersion: compliance.example/v1alpha1
kind: InventoryGroup
metadata:
  name: first
spec: {}
---
apiVersion: compliance.example/v1alpha1
kind: InventoryGroup
metadata:
  name: second
spec: {}
""",
                encoding="utf-8",
            )

            documents = load_resource_documents(path)

        self.assertEqual(
            [document["metadata"]["name"] for _, document in documents],
            ["first", "second"],
        )

    def test_rejects_non_string_label_value(self):
        document = {
            "apiVersion": "compliance.example/v1alpha1",
            "kind": "Subject",
            "metadata": {"name": "test", "labels": {"managed": True}},
            "spec": {
                "id": "workstation/test",
                "type": "macos-workstation",
                "lifecycle": "active",
                "source": {
                    "name": "test",
                    "externalId": "test",
                    "observedAt": "2026-08-23T10:00:00Z",
                },
            },
        }

        errors = resource_validation_errors(document, self.schema)

        self.assertTrue(errors)

    def test_preserves_open_subject_attributes(self):
        document = {
            "apiVersion": "compliance.example/v1alpha1",
            "kind": "Subject",
            "metadata": {"name": "test"},
            "spec": {
                "id": "saas/test",
                "type": "saas-tenant",
                "lifecycle": "active",
                "source": {
                    "name": "test",
                    "externalId": "tenant-1",
                    "observedAt": "2026-08-23T10:00:00Z",
                },
                "attributes": {"providerSpecific": {"region": "eu"}},
            },
        }

        normalized = normalize_subject(document)

        self.assertEqual(
            normalized["attributes"],
            {"providerSpecific": {"region": "eu"}},
        )

    def test_assignment_rejects_noncanonical_baseline_identity(self):
        document = {
            "apiVersion": "compliance.example/v1alpha1",
            "kind": "PolicyAssignment",
            "metadata": {"name": "test"},
            "spec": {
                "targetRef": {"kind": "InventoryGroup", "name": "test"},
                "baselineRefs": [{"name": "test_legacy", "revision": "1"}],
            },
        }

        errors = resource_validation_errors(document, self.schema)

        self.assertTrue(errors)

    def assignment(self, **references):
        return {
            "apiVersion": "compliance.example/v1alpha1",
            "kind": "PolicyAssignment",
            "metadata": {"name": "test"},
            "spec": {
                "targetRef": {"kind": "InventoryGroup", "name": "test"},
                **references,
            },
        }

    def test_assignment_accepts_each_governed_reference_surface(self):
        baseline = [{"name": "company.technical", "revision": "1"}]
        parameter = [{"name": "company.parameters", "revision": "1"}]

        for document in (
            self.assignment(baselineRefs=baseline),
            self.assignment(parameterPolicyRefs=parameter),
            self.assignment(baselineRefs=baseline, parameterPolicyRefs=parameter),
        ):
            with self.subTest(spec=document["spec"]):
                self.assertEqual(resource_validation_errors(document, self.schema), [])

    def test_assignment_requires_at_least_one_governed_reference(self):
        errors = resource_validation_errors(self.assignment(), self.schema)

        self.assertTrue(errors)

    def test_parameter_policy_reference_is_not_a_baseline_reference(self):
        document = self.assignment(parameterPolicyRefs=[{
            "name": "company.parameters",
            "revision": "1",
        }])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "inventory"
            inventory.mkdir()
            (root / "assignment.json").write_text(json.dumps(document), encoding="utf-8")
            subject = inventory / "subject.json"
            groups = inventory / "groups.json"
            subject.write_text(json.dumps({
                "apiVersion": "compliance.example/v1alpha1",
                "kind": "Subject",
                "metadata": {"name": "test"},
                "spec": {
                    "id": "host/test",
                    "type": "host",
                    "lifecycle": "active",
                    "source": {
                        "name": "test",
                        "externalId": "test",
                        "observedAt": "2026-09-20T00:00:00Z",
                    },
                },
            }), encoding="utf-8")
            groups.write_text(json.dumps({
                "apiVersion": "compliance.example/v1alpha1",
                "kind": "InventoryGroup",
                "metadata": {"name": "test"},
                "spec": {"subjectRefs": [{"id": "host/test"}]},
            }), encoding="utf-8")
            _, _, assignments = load_inventory_inputs(
                inventory,
                root / "assignment.json",
                "host/test",
                self.root / "schemas/inventory/resource.schema.json",
            )

        self.assertEqual(assignments[0]["baselines"], [])
        self.assertEqual(assignments[0]["parameter_policies"], ["company.parameters@1"])


class GroupResolutionTests(unittest.TestCase):
    def setUp(self):
        self.groups = {
            "company-assets": {"id": "company-assets", "parents": []},
            "managed-workstations": {
                "id": "managed-workstations",
                "parents": ["company-assets"],
            },
            "developer-machines": {
                "id": "developer-machines",
                "parents": ["managed-workstations"],
                "selector": {"match_labels": {"persona": "developer"}},
            },
            "macos-devices": {
                "id": "macos-devices",
                "parents": ["managed-workstations"],
                "selector": {"match_labels": {"os": "macos"}},
            },
        }
        self.subject = {
            "id": "workstation/test",
            "type": "macos-workstation",
            "labels": {"persona": "developer", "os": "macos"},
        }

    def test_resolves_both_dag_branches_and_ancestors(self):
        validate_group_dag(self.groups)
        resolved = {group["id"]: group for group in resolve_groups(self.groups, self.subject)}

        self.assertEqual(
            set(resolved),
            {"company-assets", "managed-workstations", "developer-machines", "macos-devices"},
        )
        self.assertEqual(
            resolved["managed-workstations"]["sources"][0]["via"],
            ["developer-machines", "macos-devices"],
        )

    def test_rejects_cycle(self):
        self.groups["company-assets"]["parents"] = ["developer-machines"]

        with self.assertRaisesRegex(ValueError, "contains a cycle"):
            validate_group_dag(self.groups)


def catalog_document(document):
    prepared = copy.deepcopy(document)
    prepared["_digest"] = baseline_semantic_digest(document)
    prepared["_source"] = "test"
    return prepared


def deviation(deviation_id):
    return {
        "id": deviation_id,
        "classification": "test",
        "rationale": "Required by the test scenario.",
        "approval_ref": "test/approval",
        "review_after": "2027-01-31",
    }


class BaselineOverlayTests(unittest.TestCase):
    def setUp(self):
        self.base_reference = "benchmark.test@1"
        self.base = {
            "apiVersion": "compliance.example/v1",
            "kind": "Baseline",
            "metadata": {"id": "benchmark.test", "revision": 1},
            "spec": {
                "title": "Test benchmark policy",
                "controls": [
                    {
                        "instance_id": "benchmark.setting",
                        "implementation": "test.setting-equals",
                        "parameters": {"expected": "strict"},
                    },
                    {
                        "instance_id": "benchmark.optional",
                        "implementation": "test.setting-equals",
                        "parameters": {"expected": "enabled"},
                    },
                ]
            },
        }
        self.catalog = {self.base_reference: catalog_document(self.base)}
        resolved_base = resolve_baseline(self.base_reference, self.catalog)
        self.setting_fingerprint = resolved_base["controls"]["benchmark.setting"]["definition_fingerprint"]
        self.optional_fingerprint = resolved_base["controls"]["benchmark.optional"]["definition_fingerprint"]

    def company_overlay(self):
        return {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "company.test", "revision": 1},
            "spec": {
                "title": "Test company policy",
                "extends": [{
                    "baseline": self.base_reference,
                    "digest": self.catalog[self.base_reference]["_digest"],
                }],
                "operations": [
                    {
                        "op": "tailor",
                        "target": "benchmark.setting",
                        "expected_parent_fingerprint": self.setting_fingerprint,
                        "parameters": {"expected": "company"},
                        "deviation": deviation("DEV-TEST-1"),
                    },
                    {
                        "op": "exclude",
                        "target": "benchmark.optional",
                        "expected_parent_fingerprint": self.optional_fingerprint,
                        "deviation": deviation("DEV-TEST-2"),
                    },
                ],
            },
        }

    def add_parent_overlay(self, identifier, *, operations=None):
        overlay = self.company_overlay()
        overlay["metadata"]["id"] = identifier
        overlay["spec"]["operations"] = copy.deepcopy(operations or [])
        reference = f"{identifier}@1"
        self.catalog[reference] = catalog_document(overlay)
        return reference

    def combined_overlay(self, references, identifier="company.combined"):
        return {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": identifier, "revision": 1},
            "spec": {
                "title": "Combined test company policy",
                "extends": [
                    {"baseline": parent, "digest": self.catalog[parent]["_digest"]}
                    for parent in references
                ],
                "operations": [],
            },
        }

    def test_tailors_and_excludes_without_losing_lineage(self):
        overlay = self.company_overlay()
        self.catalog["company.test@1"] = catalog_document(overlay)

        resolved = resolve_baseline("company.test@1", self.catalog)

        tailored = resolved["controls"]["benchmark.setting"]
        excluded = resolved["controls"]["benchmark.optional"]
        self.assertEqual(tailored["parameters"], {"expected": "company"})
        self.assertEqual(tailored["alignment"], "tailored")
        self.assertEqual(excluded["disposition"], "excluded")
        self.assertEqual(
            tailored["derivations"][0]["before"]["parameters"],
            {"expected": "strict"},
        )
        self.assertEqual(
            tailored["derivations"][0]["after"]["parameters"],
            {"expected": "company"},
        )
        self.assertEqual(
            excluded["derivations"][0]["before"]["disposition"],
            "evaluate",
        )
        self.assertEqual(
            excluded["derivations"][0]["after"]["disposition"],
            "excluded",
        )
        self.assertEqual([item["id"] for item in resolved["deviations"]], ["DEV-TEST-1", "DEV-TEST-2"])
        self.assertEqual(
            [item["reference"] for item in resolved["lineage"]],
            ["benchmark.test@1", "company.test@1"],
        )

    def test_substitution_records_previous_and_effective_criteria(self):
        overlay = self.company_overlay()
        overlay["spec"]["operations"] = [{
            "op": "substitute",
            "target": "benchmark.setting",
            "expected_parent_fingerprint": self.setting_fingerprint,
            "implementation": "test.alternative-setting-equals",
            "parameters": {"expected": "strict"},
            "equivalence_ref": "test/equivalence-review",
        }]
        self.catalog["company.substitute@1"] = catalog_document(overlay)

        resolved = resolve_baseline("company.substitute@1", self.catalog)
        derivation = resolved["controls"]["benchmark.setting"]["derivations"][0]

        self.assertEqual(derivation["operation"], "substitute")
        self.assertEqual(
            derivation["before"]["implementation"],
            "test.setting-equals",
        )
        self.assertEqual(
            derivation["after"]["implementation"],
            "test.alternative-setting-equals",
        )
        self.assertEqual(derivation["equivalence_ref"], "test/equivalence-review")

    def test_substitution_can_replace_inherited_parameter_links(self):
        source = {
            "policy": "test.parameters@1",
            "digest": "sha256:" + "1" * 64,
            "slot": "expected",
            "declaration_digest": "sha256:" + "2" * 64,
            "schema_digest": "sha256:" + "3" * 64,
        }
        self.base["spec"]["parameter_links"] = [{
            "id": "old-link",
            "source": source,
            "destination": {
                "instance_id": "benchmark.setting",
                "implementation": {
                    "id": "test.setting-equals",
                    "version": 1,
                    "fingerprint": "sha256:" + "4" * 64,
                },
                "kind": "parameters",
                "path": "/expected",
            },
        }]
        self.catalog[self.base_reference] = catalog_document(self.base)
        self.setting_fingerprint = resolve_baseline(
            self.base_reference,
            self.catalog,
        )["controls"]["benchmark.setting"]["definition_fingerprint"]
        overlay = self.company_overlay()
        overlay["metadata"]["id"] = "company.substitute"
        overlay["spec"]["operations"] = [{
            "op": "substitute",
            "target": "benchmark.setting",
            "expected_parent_fingerprint": self.setting_fingerprint,
            "implementation": "test.alternative-setting-equals",
            "parameters": {"expected": "strict"},
            "equivalence_ref": "test/equivalence-review",
            "parameter_links": [{
                "id": "replacement-link",
                "source": source,
                "destination": {
                    "instance_id": "benchmark.setting",
                    "implementation": {
                        "id": "test.alternative-setting-equals",
                        "version": 1,
                        "fingerprint": "sha256:" + "5" * 64,
                    },
                    "kind": "parameters",
                    "path": "/expected",
                },
            }],
        }]
        self.catalog["company.substitute@1"] = catalog_document(overlay)

        resolved = resolve_baseline("company.substitute@1", self.catalog)

        self.assertEqual(
            [item["id"] for item in resolved["parameter_links"]],
            ["replacement-link"],
        )
        locator = [{"policy_source": "test", "path": "baselines/test.json"}]
        consumers = [
            {
                "kind": self.catalog[reference]["kind"],
                "reference": reference,
                "digest": self.catalog[reference]["_digest"],
                "policy_sources": locator,
                "document": pp.document(self.catalog[reference]),
            }
            for reference in (self.base_reference, "company.substitute@1")
        ]
        frozen = {
            "parameters": {"consumers": consumers},
            "resolved_baselines": [{
                "reference": "company.substitute@1",
                "lineage": [
                    {
                        "reference": item["reference"],
                        "digest": item["digest"],
                        "policy_sources": locator,
                    }
                    for item in consumers
                ],
            }],
        }
        self.assertEqual(
            [item["id"] for item in pp.frozen_technical_links(frozen)],
            ["replacement-link"],
        )
        frozen["parameters"]["consumers"].pop(0)
        with self.assertRaisesRegex(
            pp.ParameterResolutionError,
            "missing frozen technical consumer ancestor document",
        ):
            pp.frozen_technical_links(frozen)

    def test_substitution_rejects_replacement_link_for_another_check(self):
        overlay = self.company_overlay()
        overlay["metadata"]["id"] = "company.substitute"
        overlay["spec"]["operations"] = [{
            "op": "substitute",
            "target": "benchmark.setting",
            "expected_parent_fingerprint": self.setting_fingerprint,
            "implementation": "test.alternative-setting-equals",
            "equivalence_ref": "test/equivalence-review",
            "parameter_links": [{
                "id": "wrong-target",
                "source": {
                    "policy": "test.parameters@1",
                    "digest": "sha256:" + "1" * 64,
                    "slot": "expected",
                    "declaration_digest": "sha256:" + "2" * 64,
                    "schema_digest": "sha256:" + "3" * 64,
                },
                "destination": {
                    "instance_id": "benchmark.optional",
                    "implementation": {
                        "id": "test.alternative-setting-equals",
                        "version": 1,
                        "fingerprint": "sha256:" + "5" * 64,
                    },
                    "kind": "parameters",
                    "path": "/expected",
                },
            }],
        }]
        self.catalog["company.substitute@1"] = catalog_document(overlay)

        with self.assertRaisesRegex(
            BaselineResolutionError,
            "substitute-parameter-link-target-mismatch",
        ):
            resolve_baseline("company.substitute@1", self.catalog)

    def test_identical_multi_parent_controls_retain_each_derivation(self):
        first = self.company_overlay()
        first["metadata"]["id"] = "company.first"
        first["spec"]["operations"] = [first["spec"]["operations"][0]]
        first["spec"]["operations"][0]["deviation"] = deviation("DEV-FIRST")
        second = copy.deepcopy(first)
        second["metadata"]["id"] = "company.second"
        second["spec"]["operations"][0]["deviation"] = deviation("DEV-SECOND")
        self.catalog["company.first@1"] = catalog_document(first)
        self.catalog["company.second@1"] = catalog_document(second)
        combined = {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "company.combined", "revision": 1},
            "spec": {
                "title": "Combined test company policy",
                "extends": [
                    {
                        "baseline": reference,
                        "digest": self.catalog[reference]["_digest"],
                    }
                    for reference in ("company.first@1", "company.second@1")
                ],
                "operations": [],
            },
        }
        self.catalog["company.combined@1"] = catalog_document(combined)

        control = resolve_baseline(
            "company.combined@1",
            self.catalog,
        )["controls"]["benchmark.setting"]

        self.assertEqual(len(control["derivations"]), 2)
        self.assertEqual(
            {item["deviation"]["id"] for item in control["derivations"]},
            {"DEV-FIRST", "DEV-SECOND"},
        )
        self.assertEqual(
            {item["id"] for item in control["deviations"]},
            {"DEV-FIRST", "DEV-SECOND"},
        )

    def test_technical_parent_permutations_share_digest_and_resolved_state(self):
        parents = [
            self.add_parent_overlay(identifier)
            for identifier in ("company.parent-a", "company.parent-b", "company.parent-c")
        ]
        resolutions = []
        digests = set()
        for ordered in itertools.permutations(parents):
            document = self.combined_overlay(ordered)
            self.catalog["company.combined@1"] = catalog_document(document)
            digests.add(self.catalog["company.combined@1"]["_digest"])
            resolutions.append(resolve_baseline("company.combined@1", self.catalog))

        self.assertEqual(len(digests), 1)
        self.assertTrue(all(resolution == resolutions[0] for resolution in resolutions))

    def test_operation_order_remains_semantic(self):
        first = self.company_overlay()
        first["spec"]["operations"] = [
            {"op": "add", "control": {
                "instance_id": "company.first", "implementation": "test.setting-equals",
                "parameters": {"expected": "first"},
            }},
            {"op": "add", "control": {
                "instance_id": "company.second", "implementation": "test.setting-equals",
                "parameters": {"expected": "second"},
            }},
        ]
        second = copy.deepcopy(first)
        second["spec"]["operations"].reverse()

        self.assertNotEqual(baseline_semantic_digest(first), baseline_semantic_digest(second))

    def test_parent_pin_admission_precedes_lookup(self):
        pin = {"baseline": self.base_reference, "digest": self.catalog[self.base_reference]["_digest"]}
        duplicate = self.combined_overlay([self.base_reference, self.base_reference])
        duplicate["spec"]["extends"] = [pin, copy.deepcopy(pin)]
        self.catalog["company.combined@1"] = catalog_document(duplicate)
        with self.assertRaises(BaselineResolutionError) as raised:
            resolve_baseline("company.combined@1", self.catalog)
        self.assertEqual(raised.exception.details["type"], "duplicate-parent-pin")

        contradictory = self.combined_overlay([self.base_reference])
        contradictory["spec"]["extends"] = [
            pin,
            {"baseline": self.base_reference, "digest": "sha256:" + "0" * 64},
        ]
        self.catalog["company.combined@1"] = catalog_document(contradictory)
        with self.assertRaises(BaselineResolutionError) as raised:
            resolve_baseline("company.combined@1", self.catalog)
        self.assertEqual(raised.exception.details, {
            "type": "contradictory-parent-pins",
            "baseline": "company.combined@1",
            "parent": self.base_reference,
            "digests": sorted([pin["digest"], "sha256:" + "0" * 64]),
        })

    def test_missing_and_stale_parent_pins_remain_fail_closed(self):
        missing = self.combined_overlay([self.base_reference])
        missing["spec"]["extends"][0]["baseline"] = "missing.parent@1"
        self.catalog["company.combined@1"] = catalog_document(missing)
        with self.assertRaises(BaselineResolutionError) as raised:
            resolve_baseline("company.combined@1", self.catalog)
        self.assertEqual(raised.exception.details["type"], "unknown-baseline")

        stale = self.combined_overlay([self.base_reference])
        stale["spec"]["extends"][0]["digest"] = "sha256:" + "0" * 64
        self.catalog["company.combined@1"] = catalog_document(stale)
        with self.assertRaises(BaselineResolutionError) as raised:
            resolve_baseline("company.combined@1", self.catalog)
        self.assertEqual(raised.exception.details["type"], "parent-digest-mismatch")

    def test_complete_effective_state_is_required_for_parent_coalescence(self):
        excluded = self.company_overlay()
        excluded["metadata"]["id"] = "company.excluded"
        excluded["spec"]["operations"] = [excluded["spec"]["operations"][1]]
        self.catalog["company.excluded@1"] = catalog_document(excluded)
        combined = self.combined_overlay((self.base_reference, "company.excluded@1"))
        self.catalog["company.combined@1"] = catalog_document(combined)

        with self.assertRaises(BaselineResolutionError) as raised:
            resolve_baseline("company.combined@1", self.catalog)

        self.assertEqual(raised.exception.details["type"], "inherited-control-conflict")
        candidates = raised.exception.details["parents"]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            {candidate["disposition"] for candidate in candidates}, {"evaluate", "excluded"},
        )

    def test_divergent_parent_permutations_have_one_structured_failure(self):
        second = copy.deepcopy(self.base)
        second["metadata"]["id"] = "benchmark.second"
        second["spec"]["controls"][0]["parameters"] = {"expected": "different"}
        third = copy.deepcopy(self.base)
        third["metadata"]["id"] = "benchmark.third"
        third["spec"]["controls"][0]["parameters"] = {"expected": "also-different"}
        self.catalog["benchmark.second@1"] = catalog_document(second)
        self.catalog["benchmark.third@1"] = catalog_document(third)
        parents = (self.base_reference, "benchmark.second@1", "benchmark.third@1")
        failures = []
        for ordered in itertools.permutations(parents):
            self.catalog["company.combined@1"] = catalog_document(self.combined_overlay(ordered))
            with self.assertRaises(BaselineResolutionError) as raised:
                resolve_baseline("company.combined@1", self.catalog)
            failures.append(raised.exception.details)

        self.assertTrue(all(failure == failures[0] for failure in failures))
        self.assertEqual(len(failures[0]["parents"]), 3)

    def test_rebase_rejects_stale_control_fingerprint(self):
        overlay = self.company_overlay()
        changed_base = copy.deepcopy(self.base)
        changed_base["spec"]["controls"][0]["parameters"] = {"expected": "new-upstream"}
        self.catalog[self.base_reference] = catalog_document(changed_base)
        overlay["spec"]["extends"][0]["digest"] = self.catalog[self.base_reference]["_digest"]
        self.catalog["company.test@1"] = catalog_document(overlay)

        with self.assertRaises(BaselineResolutionError) as raised:
            resolve_baseline("company.test@1", self.catalog)

        self.assertEqual(raised.exception.details["type"], "parent-control-fingerprint-mismatch")

    def test_governed_descendant_can_tailor_inherited_control(self):
        company = self.company_overlay()
        self.catalog["company.test@1"] = catalog_document(company)
        resolved_company = resolve_baseline("company.test@1", self.catalog)

        child = {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "company.child", "revision": 1},
            "spec": {
                "title": "Child test company policy",
                "extends": [{
                    "baseline": "company.test@1",
                    "digest": self.catalog["company.test@1"]["_digest"],
                }],
                "operations": [{
                    "op": "tailor",
                    "target": "benchmark.setting",
                    "expected_parent_fingerprint": resolved_company["controls"]["benchmark.setting"]["definition_fingerprint"],
                    "parameters": {"expected": "weaker"},
                    "deviation": deviation("DEV-TEST-3"),
                }],
            },
        }
        self.catalog["company.child@1"] = catalog_document(child)

        resolved = resolve_baseline("company.child@1", self.catalog)
        self.assertEqual(
            resolved["controls"]["benchmark.setting"]["parameters"],
            {"expected": "weaker"},
        )


class PolicySchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        cls.schemas = cls.root / "shared/schemas/policy"

    def test_control_library_baselines_validate(self):
        catalog, errors = validate_policy_catalog(
            self.root / "shared"
        )

        self.assertEqual(len(catalog), 0)
        self.assertEqual(errors, [])

    def test_shared_and_verification_baselines_validate_together(self):
        catalog, errors = validate_policy_catalog((
            PolicySource(
                "control-library",
                self.root / "shared",
            ),
            PolicySource(
                "verification-policy",
                self.root / "selection",
            ),
        ))

        self.assertEqual(len(catalog), 10)
        self.assertEqual(errors, [])

    def test_equivalent_additive_parameter_documents_coalesce_after_normalization(self):
        repository = Path(__file__).resolve().parents[2]
        verification = repository / "policy-sources/verification-policy/policies"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first"
            second = root / "second"
            schema_target = first / "schemas/policy/parameter-policy.schema.json"
            schema_target.parent.mkdir(parents=True)
            shutil.copyfile(
                repository
                / "policy-sources/control-library/policies/schemas/policy/parameter-policy.schema.json",
                schema_target,
            )
            for name in (
                "company-authorized-software.json",
                "company-authorized-software-base.json",
            ):
                source = verification / "parameter-policies/company" / name
                target = first / "parameter-policies/company" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            copied = load_json(
                verification
                / "parameter-policies/company/company-authorized-software-base.json"
            )
            copied["spec"]["parameter_operations"][0]["to"].reverse()
            target = (
                second
                / "parameter-policies/company/company-authorized-software-base.json"
            )
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(copied), encoding="utf-8")

            outcomes = []
            sources = (
                PolicySource("first", first),
                PolicySource("second", second),
            )
            for ordered in (sources, tuple(reversed(sources))):
                catalog, errors = load_parameter_policy_catalogs(ordered)
                outcomes.append((catalog, errors))

        for catalog, errors in outcomes:
            self.assertEqual(errors, [])
            policy = catalog["company.authorized-software-base@1"]
            self.assertEqual(
                policy["spec"]["parameter_operations"][0]["to"],
                ["auditd", "curl"],
            )
            self.assertEqual(
                [item["policy_source"] for item in policy["_sources"]],
                ["first", "second"],
            )

    def test_policy_schemas_reject_removed_seal_operations(self):
        overlay = {
            "op": "seal",
            "target": "test.control",
            "expected_parent_fingerprint": "sha256:" + "0" * 64,
            "reason": "obsolete",
        }
        parameter = {
            "id": "obsolete",
            "op": "seal",
            "target": {
                "requirement": "test.requirement@1",
                "digest": "sha256:" + "0" * 64,
                "slot": "age",
                "declaration_digest": "sha256:" + "0" * 64,
                "schema_digest": "sha256:" + "0" * 64,
            },
            "expected_parent_fingerprint": "sha256:" + "0" * 64,
        }
        overlay_schema = load_json(self.schemas / "baseline-overlay.schema.json")
        requirement_schema = load_json(
            self.schemas / "requirement-baseline.schema.json"
        )
        self.assertFalse(
            Draft202012Validator(overlay_schema).is_valid(
                {"operations": [overlay]}
            )
        )
        self.assertFalse(
            Draft202012Validator(requirement_schema).is_valid(
                {"parameter_operations": [parameter]}
            )
        )


    def test_repository_control_manifests_validate(self):
        catalog, errors = load_control_catalog(
            self.root / "shared/controls",
            self.schemas / "control.schema.json",
        )

        self.assertEqual(len(catalog), 7)
        self.assertEqual(errors, [])

    def test_repository_evidence_contracts_resolve(self):
        controls, _ = load_control_catalog(
            self.root / "shared/controls",
            self.schemas / "control.schema.json",
        )

        evidence_schemas, errors = validate_control_evidence_contracts(
            self.root / "shared",
            controls,
        )

        self.assertEqual(len(evidence_schemas), 3)
        self.assertEqual(errors, [])

    def test_adopter_schema_publisher_host_is_accepted_by_generic_loaders(self):
        publisher = "https://schemas.adopter.example"
        with tempfile.TemporaryDirectory() as directory:
            adopter = Path(directory) / "adopter"
            control_path = adopter / "controls/test/minimum"
            shutil.copytree(
                self.root / "shared/controls/test/minimum",
                control_path,
            )
            parameter_path = control_path / "parameters.schema.json"
            parameter_schema = load_json(parameter_path)
            parameter_schema["$id"] = (
                publisher
                + "/schemas/controls/test.minimum/parameters/v2.schema.json"
            )
            parameter_path.write_text(json.dumps(parameter_schema), encoding="utf-8")
            manifest_path = control_path / "control.json"
            manifest = load_json(manifest_path)
            manifest["spec"]["evidence"][0]["inputs_schema"] = {
                "$id": (
                    publisher
                    + "/schemas/controls/test.minimum/evidence/observation/"
                    "inputs/v3.schema.json"
                ),
                "type": "object",
                "additionalProperties": False,
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            controls, control_errors = load_control_catalog(
                adopter / "controls",
                self.schemas / "control.schema.json",
            )

            evidence_path = adopter / "schemas/evidence/linux-host.schema.json"
            evidence_path.parent.mkdir(parents=True)
            evidence = load_json(
                self.root / "shared/schemas/evidence/linux-host.schema.json"
            )
            evidence["$id"] = (
                publisher
                + "/schemas/evidence/test.linux-host/v1.schema.json"
            )
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            evidence_catalog, evidence_errors = load_evidence_schema_catalog(
                PolicySource("adopter", adopter)
            )

            value_schema = {
                "$id": (
                    publisher
                    + "/schemas/requirements/adopter.requirement/"
                    "parameters/review_age/v4.schema.json"
                ),
                "type": "string",
            }
            requirement = {
                "apiVersion": "compliance.example/v1",
                "kind": "ControlRequirement",
                "metadata": {"id": "adopter.requirement", "revision": 1},
                "spec": {
                    "title": "Adopter-published requirement",
                    "statement": "Exercise generic publisher-host validation.",
                    "external_refs": [],
                    "parameters": {
                        "review_age": {
                            "required": True,
                            "binding_mode": "open",
                            "binding_scope": ["adopter.baseline"],
                            "schema": value_schema,
                            "schema_digest": content_digest(value_schema),
                        }
                    },
                },
            }
            requirement_path = adopter / "requirements/adopter/requirement.json"
            requirement_path.parent.mkdir(parents=True)
            requirement_path.write_text(json.dumps(requirement), encoding="utf-8")
            requirements, _, _, requirement_errors = load_requirement_catalogs((
                PolicySource("platform-contracts", self.root / "shared"),
                PolicySource("adopter", adopter),
            ))

        self.assertEqual(control_errors, [])
        self.assertEqual(controls["test.minimum"]["_parameters_schema"]["$id"], parameter_schema["$id"])
        self.assertEqual(evidence_errors, [])
        self.assertEqual(evidence_catalog["test.linux-host/v1"]["$id"], evidence["$id"])
        self.assertEqual(requirement_errors, [])
        self.assertEqual(
            requirements["adopter.requirement@1"]["spec"]["parameters"][
                "review_age"
            ]["schema"]["$id"],
            value_schema["$id"],
        )

    def test_identical_resources_coalesce_across_sources_with_provenance(self):
        shared = self.root / "shared"
        verification = self.root / "selection"
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            target = private / "realizations/company/company-linux-role-based-access.json"
            target.parent.mkdir(parents=True)
            shutil.copyfile(
                verification
                / "realizations/company/company-linux-role-based-access.json",
                target,
            )
            sources = (
                PolicySource("control-library", shared),
                PolicySource("verification-policy", verification),
                PolicySource("environment-private", private),
            )
            controls, _, errors = load_policy_catalogs(sources)
            _, _, realizations, requirement_errors = load_requirement_catalogs(
                sources,
                controls,
            )

        self.assertEqual(errors, [])
        self.assertEqual(requirement_errors, [])
        self.assertEqual(
            [source["policy_source"] for source in realizations[
                "company.linux.central-role-access@1"
            ]["_sources"]],
            ["environment-private", "verification-policy"],
        )

    def test_reversed_technical_parent_copies_coalesce_without_changing_raw_identity(self):
        selection = self.root / "selection"
        with tempfile.TemporaryDirectory() as directory:
            first_source = Path(directory) / "first-copy"
            private = Path(directory) / "second-copy"
            shutil.copytree(selection, first_source)
            for identifier in ("test.parent-a", "test.parent-b"):
                document = {
                    "apiVersion": "compliance.example/v1",
                    "kind": "Baseline",
                    "metadata": {"id": identifier, "revision": 1},
                    "spec": {"title": identifier, "controls": []},
                }
                target = first_source / f"baselines/{identifier}.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(document), encoding="utf-8")

            parents = [
                {
                    "baseline": f"{identifier}@1",
                    "digest": baseline_semantic_digest({
                        "apiVersion": "compliance.example/v1",
                        "kind": "Baseline",
                        "metadata": {"id": identifier, "revision": 1},
                        "spec": {"title": identifier, "controls": []},
                    }),
                }
                for identifier in ("test.parent-a", "test.parent-b")
            ]
            overlay = {
                "apiVersion": "compliance.example/v1",
                "kind": "BaselineOverlay",
                "metadata": {"id": "test.reversed-copy", "revision": 1},
                "spec": {"title": "reversed copy", "extends": parents, "operations": []},
            }
            first = first_source / "baselines/reversed-copy.json"
            first.write_text(json.dumps(overlay), encoding="utf-8")
            second = private / "baselines/reversed-copy.json"
            second.parent.mkdir(parents=True)
            reversed_overlay = copy.deepcopy(overlay)
            reversed_overlay["spec"]["extends"].reverse()
            second.write_text(json.dumps(reversed_overlay), encoding="utf-8")

            _, catalog, errors = load_policy_catalogs((
                PolicySource("control-library", self.root / "shared"),
                PolicySource("first-copy", first_source),
                PolicySource("second-copy", private),
            ))

            self.assertEqual(errors, [])
            self.assertEqual(
                [source["policy_source"] for source in catalog["test.reversed-copy@1"]["_sources"]],
                ["first-copy", "second-copy"],
            )
            raw_first = Path(directory) / "raw-first"
            raw_second = Path(directory) / "raw-second"
            (raw_first / "baselines").mkdir(parents=True)
            (raw_second / "baselines").mkdir(parents=True)
            (raw_first / "baselines/overlay.json").write_text(
                json.dumps(overlay), encoding="utf-8"
            )
            (raw_second / "baselines/overlay.json").write_text(
                json.dumps(reversed_overlay), encoding="utf-8"
            )
            self.assertNotEqual(source_tree_digest(raw_first), source_tree_digest(raw_second))

    def test_identical_control_meaning_coalesces_but_divergent_meaning_fails(self):
        shared = self.root / "shared"
        control_relative = Path("controls/linux/packages")
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            shutil.copytree(shared / control_relative, private / control_relative)
            sources = (
                PolicySource("control-library", shared),
                PolicySource("environment-private", private),
            )
            controls, _, errors = load_policy_catalogs(sources)
            self.assertEqual(errors, [])
            self.assertEqual(
                [source["policy_source"] for source in controls[
                    "linux.packages.required"
                ]["_sources"]],
                ["control-library", "environment-private"],
            )

            manifest_path = private / control_relative / "control.json"
            manifest = load_json(manifest_path)
            manifest["spec"]["purpose"] = "Different authored meaning."
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            conflicts = []
            for ordered in (sources, tuple(reversed(sources))):
                _, _, divergent_errors = load_policy_catalogs(ordered)
                conflicts.append(next(
                    error for error in divergent_errors
                    if error["type"] == "policy-resource-conflict"
                ))

        self.assertEqual(conflicts[0], conflicts[1])
        self.assertEqual(conflicts[0]["kind"], "Control")
        self.assertEqual(conflicts[0]["identity"], "linux.packages.required")

    def test_divergent_resource_identity_is_a_hard_error(self):
        shared = self.root / "shared"
        verification = self.root / "selection"
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private"
            target = private / "realizations/company/company-linux-role-based-access.json"
            target.parent.mkdir(parents=True)
            realization = load_json(
                verification
                / "realizations/company/company-linux-role-based-access.json"
            )
            realization["spec"]["adoption"]["owner"] = "different-owner"
            target.write_text(json.dumps(realization), encoding="utf-8")

            _, _, errors = load_policy_catalogs((
                PolicySource("control-library", shared),
                PolicySource("verification-policy", verification),
                PolicySource("environment-private", private),
            ))

        conflict = next(error for error in errors if error["type"] == "policy-resource-conflict")
        self.assertEqual(conflict["kind"], "ControlRealization")
        self.assertEqual(conflict["identity"], "company.linux.central-role-access@1")

    def test_policy_source_order_does_not_change_assembled_plan(self):
        shared = self.root / "shared"
        verification = self.root / "selection"
        private = self.root / "iam/policy"
        subject, groups, assignments = load_inventory_inputs(
            self.root / "iam/inventory",
            self.root / "iam/assignments",
            "host/restricted-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        sources = [
            PolicySource("control-library", shared),
            PolicySource("verification-policy", verification),
            PolicySource("environment-private", private),
        ]

        first = render_plan(subject, groups, assignments, sources)
        reordered = render_plan(subject, groups, assignments, list(reversed(sources)))

        self.assertEqual(first, reordered)
        self.assertEqual(
            [source["name"] for source in first["provenance"]["planningComposition"]["actual"]["policySources"]],
            ["control-library", "environment-private", "verification-policy"],
        )
        self.assertEqual(
            first["requirements"][0]["realization"]["policy_sources"][0][
                "policy_source"
            ],
            "environment-private",
        )

    def test_noncolliding_technical_and_requirement_assignments_plan_together(self):
        subject, groups, assignments = load_inventory_inputs(
            self.root / "iam/inventory",
            self.root / "iam/assignments",
            "host/restricted-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        assignments[0]["baselines"].append("test.linux@1")

        plan = render_plan(
            subject,
            groups,
            assignments,
            (
                PolicySource("control-library", self.root / "shared"),
                PolicySource("verification-policy", self.root / "selection"),
                PolicySource("environment-private", self.root / "iam/policy"),
            ),
        )

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertEqual(
            [item["reference"] for item in plan["resolved_baselines"]],
            ["test.linux@1"],
        )
        self.assertEqual(
            [item["reference"] for item in plan["resolved_requirement_baselines"]],
            ["test.iam@1"],
        )

    def test_cross_kind_assignment_reference_collision_is_order_independent(self):
        with tempfile.TemporaryDirectory() as directory:
            collision = Path(directory) / "collision"
            target = collision / "baselines/test-iam.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({
                "apiVersion": "compliance.example/v1",
                "kind": "Baseline",
                "metadata": {"id": "test.iam", "revision": 1},
                "spec": {"title": "Colliding technical baseline", "controls": []},
            }), encoding="utf-8")
            sources = (
                PolicySource("control-library", self.root / "shared"),
                PolicySource("verification-policy", self.root / "selection"),
                PolicySource("collision", collision),
            )
            collisions = []
            for ordered in (sources, tuple(reversed(sources))):
                _, _, errors = load_policy_catalogs(ordered)
                collisions.append(next(
                    error for error in errors
                    if error["type"] == "assignment-reference-kind-collision"
                ))

        self.assertEqual(collisions[0], collisions[1])
        self.assertEqual(collisions[0]["reference"], "test.iam@1")
        self.assertEqual(
            [source["policy_source"] for source in collisions[0]["technical_sources"]],
            ["collision"],
        )
        self.assertEqual(
            [source["policy_source"] for source in collisions[0]["requirement_sources"]],
            ["verification-policy"],
        )

    def test_policy_source_digest_pin_mismatch_is_invalid(self):
        shared = self.root / "shared"
        _, _, errors = load_policy_catalogs((PolicySource(
            "control-library",
            shared,
            "sha256:" + "0" * 64,
        ),))

        self.assertIn("policy-source-digest-mismatch", {error["type"] for error in errors})

    def test_divergent_effective_policy_schema_is_a_hard_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first/schemas/policy/control.schema.json"
            second = root / "second/schemas/policy/control.schema.json"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text(json.dumps({"type": "object"}), encoding="utf-8")
            second.write_text(
                json.dumps({"type": "object", "title": "divergent"}),
                encoding="utf-8",
            )

            _, _, errors = load_policy_catalogs((
                PolicySource("first", root / "first"),
                PolicySource("second", root / "second"),
            ))

        conflict = next(error for error in errors if error["type"] == "policy-schema-conflict")
        self.assertEqual(conflict["source"], "schemas/policy/control.schema.json")

    def test_missing_evidence_schema_is_a_policy_error(self):
        control = {
            "_source": "controls/test/control.json",
            "spec": {
                "applies_to": ["test-subject"],
                "evidence": [{"type": "test.missing/v1"}],
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            policies = Path(directory) / "policies"
            (policies / "schemas/evidence").mkdir(parents=True)

            _, errors = validate_control_evidence_contracts(
                policies,
                {"test.control": control},
            )

        self.assertEqual(errors[0]["type"], "control-evidence-schema-missing")
        self.assertEqual(errors[0]["evidence_type"], "test.missing/v1")

    def test_evidence_schema_catalog_rejects_nonconforming_envelopes(self):
        cases = (
            (
                "/required",
                lambda schema: schema["required"].remove("collected_at"),
            ),
            (
                "/properties",
                lambda schema: schema["properties"].update({
                    "expires_at": {"type": "string", "format": "date-time"},
                }),
            ),
            (
                "/properties/schema/const",
                lambda schema: schema["properties"]["schema"].update({
                    "const": "test/evidence/v1",
                }),
            ),
            (
                "/properties/subject/properties/type/const",
                lambda schema: schema["properties"]["subject"]["properties"][
                    "type"
                ].pop("const"),
            ),
            (
                "/properties/collector/additionalProperties",
                lambda schema: schema["properties"]["collector"].update({
                    "additionalProperties": False,
                }),
            ),
            (
                "/properties/payload",
                lambda schema: schema["properties"].update({"payload": True}),
            ),
        )
        for expected_path, mutate in cases:
            with self.subTest(path=expected_path), tempfile.TemporaryDirectory() as directory:
                policies = Path(directory) / "policies"
                schemas = policies / "schemas/evidence"
                schemas.mkdir(parents=True)
                schema = evidence_schema("test.evidence/v1", "test-subject")
                mutate(schema)
                (schemas / "test.schema.json").write_text(
                    json.dumps(schema),
                    encoding="utf-8",
                )

                catalog, errors = load_evidence_schema_catalog(policies)

            self.assertEqual(catalog, {})
            envelope_errors = [
                error for error in errors
                if error["type"] == "evidence-schema-envelope-invalid"
            ]
            self.assertIn(expected_path, {error["path"] for error in envelope_errors})

    def test_declared_rego_entrypoint_must_name_an_existing_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            policies = Path(directory) / "policies"
            module = policies / "controls/test/policy.rego"
            module.parent.mkdir(parents=True)
            module.write_text(
                "package test.control\n\nimport rego.v1\n\nevaluate := true\n",
                encoding="utf-8",
            )
            errors = validate_rego_entrypoints(
                policies,
                {
                    "test.control": {
                        "_source": "controls/test/control.json",
                        "spec": {"entrypoint": "data.test.control.missing"},
                    }
                },
            )

        self.assertEqual(errors[0]["type"], "control-entrypoint-missing")
        self.assertEqual(errors[0]["entrypoint"], "data.test.control.missing")

    def test_invalid_control_manifest_reports_json_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            controls = Path(directory) / "controls"
            control_directory = controls / "invalid"
            control_directory.mkdir(parents=True)
            (control_directory / "control.json").write_text(
                json.dumps({
                    "apiVersion": "compliance.example/v1",
                    "kind": "Control",
                    "metadata": {"id": "invalid.control", "version": 1},
                    "spec": {
                        "applies_to": ["test-subject"],
                        "evidence": [],
                        "parameters_schema": "parameters.schema.json",
                    },
                }),
                encoding="utf-8",
            )

            catalog, errors = load_control_catalog(
                controls,
                self.schemas / "control.schema.json",
            )

        self.assertEqual(catalog, {})
        self.assertEqual(errors[0]["type"], "control-manifest-schema-invalid")
        self.assertEqual(errors[0]["source"], "controls/invalid/control.json")
        self.assertEqual(errors[0]["path"], "/spec")
        self.assertIn("entrypoint", errors[0]["message"])

    def test_missing_parameter_schema_is_a_policy_error(self):
        with tempfile.TemporaryDirectory() as directory:
            controls = Path(directory) / "controls"
            control_directory = controls / "test"
            control_directory.mkdir(parents=True)
            (control_directory / "control.json").write_text(
                json.dumps({
                    "apiVersion": "compliance.example/v1",
                    "kind": "Control",
                    "metadata": {"id": "test.control", "version": 1},
                    "spec": {
                        "title": "Test control",
                        "purpose": "Verify the test control condition.",
                        "entrypoint": "data.test.control.evaluate",
                        "applies_to": ["test-subject"],
                        "evidence": [],
                        "parameters_schema": "missing.schema.json",
                    },
                }),
                encoding="utf-8",
            )

            catalog, errors = load_control_catalog(
                controls,
                self.schemas / "control.schema.json",
            )

        self.assertEqual(catalog, {})
        self.assertEqual(errors[0]["type"], "control-parameters-schema-unavailable")
        self.assertEqual(errors[0]["control"], "test.control")

    def test_invalid_authored_parameters_fail_policy_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            policies = Path(directory) / "policies"
            shutil.copytree(self.root / "shared", policies)
            baseline_path = policies / "baselines/test-invalid-parameters.json"
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_text(
                json.dumps({
                    "apiVersion": "compliance.example/v1",
                    "kind": "Baseline",
                    "metadata": {
                        "id": "test.invalid-authored-parameters",
                        "version": 1,
                    },
                    "spec": {
                        "title": "Invalid authored parameter policy",
                        "controls": [{
                            "instance_id": "test.macos.gatekeeper-enabled",
                            "implementation": "macos.security.setting-equals",
                            "parameters": {"setting": "gatekeeper"},
                        }],
                    },
                }),
                encoding="utf-8",
            )

            _, errors = validate_policy_catalog(policies)

        parameter_errors = [
            error for error in errors
            if error["type"] == "control-parameters-invalid"
        ]
        self.assertEqual(len(parameter_errors), 1)
        self.assertEqual(
            parameter_errors[0]["baseline"],
            "test.invalid-authored-parameters@1",
        )
        self.assertEqual(
            parameter_errors[0]["instance_id"],
            "test.macos.gatekeeper-enabled",
        )
        self.assertEqual(parameter_errors[0]["path"], "/")
        self.assertIn("expected", parameter_errors[0]["message"])

    def test_invalid_tailored_parameters_fail_after_overlay_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            shared = Path(directory) / "shared"
            verification = Path(directory) / "verification"
            shutil.copytree(self.root / "shared", shared)
            shutil.copytree(
                self.root / "selection",
                verification,
            )
            overlay_path = (
                verification / "baselines/company/company-aws-foundation.json"
            )
            overlay = load_json(overlay_path)
            overlay["spec"]["operations"][0]["parameters"]["minimum"] = "ninety"
            overlay_path.write_text(json.dumps(overlay), encoding="utf-8")

            _, errors = validate_policy_catalog((
                PolicySource("control-library", shared),
                PolicySource("verification-policy", verification),
            ))

        parameter_errors = [
            error for error in errors
            if error["type"] == "control-parameters-invalid"
        ]
        self.assertEqual(len(parameter_errors), 1)
        self.assertEqual(parameter_errors[0]["baseline"], "company.aws-foundation@1")
        self.assertEqual(parameter_errors[0]["instance_id"], "csa-ccm.aws.audit-log-retention")
        self.assertEqual(parameter_errors[0]["path"], "/minimum")

    def test_invalid_control_instance_reports_source_and_json_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            baselines = Path(directory) / "baselines"
            baselines.mkdir()
            (baselines / "invalid.json").write_text(
                json.dumps({
                    "apiVersion": "compliance.example/v1",
                    "kind": "Baseline",
                    "metadata": {"id": "invalid", "version": 1},
                    "spec": {
                        "title": "Invalid test policy",
                        "controls": [{"instance_id": "missing.implementation"}],
                    },
                }),
                encoding="utf-8",
            )

            catalog, errors = load_baseline_catalog(baselines, self.schemas)

        self.assertEqual(catalog, {})
        self.assertEqual(errors[0]["type"], "baseline-schema-invalid")
        self.assertEqual(errors[0]["source"], "baselines/invalid.json")
        self.assertEqual(errors[0]["path"], "/spec/controls/0")
        self.assertIn("implementation", errors[0]["message"])

    def test_tailor_operation_requires_documented_deviation(self):
        with tempfile.TemporaryDirectory() as directory:
            baselines = Path(directory) / "baselines"
            baselines.mkdir()
            (baselines / "invalid-overlay.json").write_text(
                json.dumps({
                    "apiVersion": "compliance.example/v1",
                    "kind": "BaselineOverlay",
                    "metadata": {"id": "invalid.overlay", "revision": 1},
                    "spec": {
                        "title": "Invalid test overlay",
                        "extends": [{
                            "baseline": "parent@1",
                            "digest": "sha256:" + "0" * 64,
                        }],
                        "operations": [{
                            "op": "tailor",
                            "target": "parent.control",
                            "expected_parent_fingerprint": "sha256:" + "1" * 64,
                            "parameters": {"expected": "value"},
                        }],
                    },
                }),
                encoding="utf-8",
            )

            _, errors = load_baseline_catalog(baselines, self.schemas)

        self.assertEqual(errors[0]["path"], "/spec/operations/0")
        self.assertIn("deviation", errors[0]["message"])

    def test_policy_validation_includes_baseline_resolution_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            policies = Path(directory) / "policies"
            (policies / "baselines").mkdir(parents=True)
            shutil.copytree(self.schemas, policies / "schemas/policy")
            control = {
                "instance_id": "duplicate.control",
                "implementation": "test.setting-equals",
                "parameters": {"expected": "value"},
            }
            (policies / "baselines/duplicate.json").write_text(
                json.dumps({
                    "apiVersion": "compliance.example/v1",
                    "kind": "Baseline",
                    "metadata": {"id": "duplicate", "version": 1},
                    "spec": {
                        "title": "Duplicate control test policy",
                        "controls": [control, control],
                    },
                }),
                encoding="utf-8",
            )

            _, errors = validate_policy_catalog(policies)

        self.assertEqual(errors[0]["type"], "duplicate-control-instance")
        self.assertEqual(errors[0]["baseline"], "duplicate@1")
        self.assertEqual(errors[0]["source"], "default:baselines/duplicate.json")

    def test_schema_failure_becomes_structured_plan_resolution_error(self):
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            self.root / "schemas/inventory/resource.schema.json",
        )
        with tempfile.TemporaryDirectory() as directory:
            shared = Path(directory) / "shared"
            verification = Path(directory) / "verification"
            shutil.copytree(self.root / "shared", shared)
            shutil.copytree(
                self.root / "selection",
                verification,
            )
            baseline_path = verification / "baselines/managed-workstation.json"
            baseline = load_json(baseline_path)
            del baseline["spec"]["controls"][0]["implementation"]
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")

            plan = render_plan(
                subject,
                groups,
                assignments,
                (
                    PolicySource("control-library", shared),
                    PolicySource("verification-policy", verification),
                ),
            )

        self.assertEqual(plan["resolution"]["status"], "invalid")
        self.assertEqual(plan_disposition(plan), "invalid")
        self.assertEqual(plan["resolution"]["errors"][0]["type"], "baseline-schema-invalid")
        self.assertEqual(plan["resolution"]["errors"][0]["path"], "/spec/controls/0")

    def test_control_manifest_failure_becomes_structured_plan_resolution_error(self):
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            self.root / "schemas/inventory/resource.schema.json",
        )
        with tempfile.TemporaryDirectory() as directory:
            policies = Path(directory) / "policies"
            shutil.copytree(self.root / "shared", policies)
            manifest_path = policies / "controls/macos/security-setting-equals/control.json"
            manifest = load_json(manifest_path)
            del manifest["spec"]["entrypoint"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            plan = render_plan(subject, groups, assignments, policies)

        self.assertEqual(plan["resolution"]["status"], "invalid")
        self.assertEqual(plan_disposition(plan), "invalid")
        self.assertEqual(
            plan["resolution"]["errors"][0]["type"],
            "control-manifest-schema-invalid",
        )
        self.assertEqual(plan["resolution"]["errors"][0]["path"], "/spec")


class PlanRevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        cls.subject, cls.groups, cls.assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            cls.root / "schemas/inventory/resource.schema.json",
        )
        cls.policy_sources = (
            PolicySource(
                "control-library",
                cls.root / "shared",
            ),
            PolicySource(
                "verification-policy",
                cls.root / "selection",
            ),
        )

    def test_source_order_does_not_change_plan_or_revisions(self):
        first = render_plan(
            self.subject,
            self.groups,
            self.assignments,
            self.policy_sources,
        )
        reordered = render_plan(
            self.subject,
            list(reversed(self.groups)),
            list(reversed(self.assignments)),
            self.policy_sources,
        )

        self.assertEqual(first["id"], reordered["id"])

    def test_resolution_consumed_inventory_change_produces_new_identity(self):
        changed_subject = copy.deepcopy(self.subject)
        changed_subject["labels"]["persona"] = "standard"

        first = render_plan(
            self.subject,
            self.groups,
            self.assignments,
            self.policy_sources,
        )
        changed = render_plan(
            changed_subject,
            self.groups,
            self.assignments,
            self.policy_sources,
        )

        self.assertNotEqual(first["id"], changed["id"])

    def test_overlapping_assignments_refuse_divergent_control_instances(self):
        with tempfile.TemporaryDirectory() as temporary:
            selection = Path(temporary) / "selection"
            shutil.copytree(self.root / "selection", selection)
            baseline = load_json(selection / "baselines/managed-workstation.json")
            baseline["metadata"]["id"] = "test.overlap"
            baseline["spec"]["controls"][0]["parameters"]["expected"] = False
            (selection / "baselines/overlap.json").write_text(json.dumps(baseline))
            assignments = [*self.assignments, {
                "id": "test-overlap", "target": {"group": "managed-workstations"},
                "baselines": ["test.overlap@1"],
            }]
            plan = render_plan(self.subject, self.groups, assignments, (
                PolicySource("control-library", self.root / "shared"),
                PolicySource("verification-policy", selection),
            ))
        self.assertEqual(plan["resolution"]["status"], "invalid")
        self.assertEqual(plan_disposition(plan), "invalid")
        self.assertIn("control-instance-conflict", {
            error["type"] for error in plan["resolution"]["errors"]
        })

    def test_active_subject_with_policy_is_assessable(self):
        plan = render_plan(
            self.subject,
            self.groups,
            self.assignments,
            self.policy_sources,
        )

        self.assertEqual(plan_disposition(plan), "result_required")
        self.assertEqual(len(plan["controls"]), 3)
        self.assertEqual(len(plan["excluded_controls"]), 1)

    def test_assessment_plan_is_sufficient_external_adapter_handoff(self):
        plan = render_plan(
            self.subject,
            self.groups,
            self.assignments,
            self.policy_sources,
        )
        validate_assessment_plan(plan)

        active = next(
            control
            for control in plan["controls"]
            if control["implementation"] == "macos.packages.required"
        )
        excluded = next(
            control
            for control in plan["excluded_controls"]
            if control["implementation"] == "macos.packages.required"
        )
        self.assertNotEqual(active["instance_id"], excluded["instance_id"])
        self.assertNotEqual(active["parameters"], excluded["parameters"])
        self.assertEqual(active["disposition"], "evaluate")
        self.assertEqual(excluded["disposition"], "excluded")
        self.assertTrue(active["definition_fingerprint"].startswith("sha256:"))
        self.assertTrue(excluded["definition_fingerprint"].startswith("sha256:"))
        self.assertTrue(active["title"])
        self.assertTrue(active["purpose"])
        self.assertEqual(
            active["title"], active["policy_inputs"]["definition"]["spec"]["title"]
        )
        self.assertEqual(
            active["purpose"], active["policy_inputs"]["definition"]["spec"]["purpose"]
        )
        self.assertEqual(
            excluded["title"], excluded["policy_inputs"]["definition"]["spec"]["title"]
        )
        self.assertEqual(
            excluded["purpose"],
            excluded["policy_inputs"]["definition"]["spec"]["purpose"],
        )
        self.assertIn("derivations", active)
        self.assertIn("deviations", active)
        self.assertTrue(excluded["derivations"])
        self.assertTrue(excluded["deviations"])
        self.assertTrue(active["lineage"])
        self.assertTrue(excluded["lineage"])
        self.assertTrue(active["provenance"])
        self.assertTrue(excluded["provenance"])
        self.assertTrue(active["implementation_sources"])
        self.assertEqual(
            set(active["implementation_sources"][0]),
            {"policy_source", "path"},
        )
        self.assertTrue(plan["resolved_baselines"])
        self.assertTrue(all(item["title"] for item in plan["resolved_baselines"]))
        sources = plan['provenance']['planningComposition']['actual']['policySources']
        self.assertTrue(sources)
        self.assertTrue(all(source["name"] for source in sources))
        self.assertTrue(
            all(source["content"]["digest"].startswith("sha256:") for source in sources)
        )
        self.assertTrue(plan['provenance']['planningComposition']['compositionDigest'].startswith('sha256:'))
        self.assertTrue(plan["id"].startswith("sha256:"))
        self.assertEqual(plan["subject"]["id"], "workstation/tooling-macos-fixture")
        self.assertEqual(plan["subject"]["type"], "macos-workstation")

        with tempfile.TemporaryDirectory() as temporary:
            changed_selection = Path(temporary) / "selection"
            shutil.copytree(self.root / "selection", changed_selection)
            baseline_path = changed_selection / "baselines/developer.json"
            baseline = load_json(baseline_path)
            baseline["spec"]["controls"][0]["parameters"]["required"] = [
                "shellcheck",
                "shfmt",
            ]
            baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
            changed = render_plan(
                self.subject,
                self.groups,
                self.assignments,
                (
                    self.policy_sources[0],
                    PolicySource("verification-policy", changed_selection),
                ),
            )

        changed_active = next(
            control
            for control in changed["controls"]
            if control["instance_id"] == active["instance_id"]
        )
        self.assertEqual(changed_active["implementation"], active["implementation"])
        self.assertNotEqual(changed_active["parameters"], active["parameters"])
        self.assertNotEqual(
            changed_active["definition_fingerprint"],
            active["definition_fingerprint"],
        )
        self.assertNotEqual(changed['provenance']['planningComposition']['actual']['policySources'], sources)
        self.assertNotEqual(changed["id"], plan["id"])

        subject, groups, assignments = load_inventory_inputs(
            self.root / "iam/inventory",
            self.root / "iam/assignments",
            "host/restricted-linux-01",
            self.root / "schemas/inventory/resource.schema.json",
        )
        assurance_plan = render_plan(
            subject,
            groups,
            assignments,
            (
                PolicySource("control-library", self.root / "shared"),
                PolicySource("verification-policy", self.root / "selection"),
                PolicySource("environment-private", self.root / "iam/policy"),
            ),
        )
        validate_assessment_plan(assurance_plan)
        requirement = assurance_plan["requirements"][0]
        self.assertTrue(requirement["realization"]["reference"])
        self.assertTrue(requirement["realization"]["policy_sources"])
        realization_control = next(
            control
            for control in assurance_plan["controls"]
            if any("realization" in item for item in control["lineage"])
        )
        self.assertTrue(realization_control["provenance"])
        self.assertTrue(all(
            item["title"] for item in assurance_plan["resolved_requirement_baselines"]
        ))

    def test_plan_retains_authored_meaning_without_policy_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shared = root / "shared"
            selection = root / "selection"
            shutil.copytree(self.root / "shared", shared)
            shutil.copytree(self.root / "selection", selection)
            plan = render_plan(
                self.subject,
                self.groups,
                self.assignments,
                (
                    PolicySource("control-library", shared),
                    PolicySource("verification-policy", selection),
                ),
            )

        validate_assessment_plan(plan)
        self.assertTrue(all(item["title"] for item in plan["resolved_baselines"]))
        for control in [*plan["controls"], *plan["excluded_controls"]]:
            self.assertEqual(
                control["title"],
                control["policy_inputs"]["definition"]["spec"]["title"],
            )
            self.assertEqual(
                control["purpose"],
                control["policy_inputs"]["definition"]["spec"]["purpose"],
            )


    def test_active_subject_without_assignment_is_unassigned(self):
        plan = render_plan(
            self.subject,
            self.groups,
            [],
            self.policy_sources,
        )

        self.assertEqual(plan["resolution"]["status"], "valid")
        self.assertEqual(plan_disposition(plan), "unassigned")

    def test_retired_subject_is_inactive(self):
        retired = copy.deepcopy(self.subject)
        retired["status"] = "retired"

        plan = render_plan(
            retired,
            self.groups,
            self.assignments,
            self.policy_sources,
        )

        self.assertEqual(plan_disposition(plan), "inactive")

    def test_unknown_lifecycle_makes_plan_invalid(self):
        unknown = copy.deepcopy(self.subject)
        unknown["status"] = "unknown"

        plan = render_plan(
            unknown,
            self.groups,
            self.assignments,
            self.policy_sources,
        )

        self.assertEqual(plan_disposition(plan), "invalid")
        self.assertEqual(plan["resolution"]["errors"][0]["type"], "subject-lifecycle-unknown")


if __name__ == "__main__":
    unittest.main()
