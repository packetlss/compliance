import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from assessment_fixture import assessment_plan, refresh_operation
from contract_fixtures import fixture_root

from tools.artifact_validation import (
    ArtifactValidationError,
    result_outcome,
    validate_assessment_plan,
    validate_assessment_results,
)
from tools.assessment_provenance import artifact_digest, validate_result_against_plan
from tools.assessment import load_result_reports
from tools.evaluate_plan import evaluate_plan_document
from tools.policy_sources import PolicySource
from tools.render_plan import (
    content_digest,
    load_inventory_inputs,
    render_plan,
)


class AssessmentArtifactValidationTests(unittest.TestCase):
    def test_public_semantic_identifiers_are_not_normalized_in_frozen_plans(self):
        plan = assessment_plan(
            [{"name": "test", "digest": "sha256:" + "1" * 64}],
            with_requirement=True,
        )
        mutations = (
            lambda item: item["controls"][0].update(
                implementation="test.control_legacy"
            ),
            lambda item: item["controls"][0].update(
                instance_id="test.check_legacy"
            ),
            lambda item: item["assignments"][0]["baselines"].__setitem__(
                0, "test_baseline@1"
            ),
            lambda item: item["requirements"][0].update(
                reference="test_requirement@1"
            ),
        )
        for mutate in mutations:
            changed = copy.deepcopy(plan)
            mutate(changed)
            with self.subTest(mutation=mutate), self.assertRaises(
                ArtifactValidationError
            ):
                validate_assessment_plan(changed)

    @staticmethod
    def parameterized_plan(schema_host="compliance.example"):
        """Build one self-contained valid plan with a frozen freshness binding."""
        from tools import policy_parameters as parameters

        schema_origin = f"https://{schema_host}"
        policy_sources = [{"name": "test", "digest": "sha256:" + "1" * 64}]
        plan = assessment_plan(policy_sources, with_requirement=True)
        requirement = plan["requirements"][0]
        control = plan["controls"][0]

        requirement_document = copy.deepcopy(requirement["parameter_facts"]["document"])
        value_schema = {
            "$id": (
                schema_origin
                + "/schemas/requirements/test.requirement/parameters/age/v1.schema.json"
            ),
            "type": "string",
            "pattern": "^[1-9][0-9]*[smhd]$",
        }
        declaration = {
            "required": True,
            "binding_mode": "open",
            "schema": value_schema,
            "schema_digest": parameters.digest(value_schema),
            "binding_scope": ["test.baseline"],
            "representation": "duration",
        }
        requirement_document["spec"]["parameters"] = {"age": declaration}
        requirement["digest"] = parameters.digest(requirement_document)
        initial = parameters.declarations(requirement_document)["age"]
        operation = {
            "id": "bind-age",
            "op": "bind",
            "target": copy.deepcopy(initial["pin"]),
            "expected_parent_fingerprint": parameters.fingerprint(initial),
            "to": "1d",
        }
        baseline_document = {
            "metadata": {"id": "test.baseline", "revision": 1},
            "spec": {
                "title": plan["resolved_requirement_baselines"][0]["title"],
                "requirements": [{
                    "requirement": requirement["reference"],
                    "digest": requirement["digest"],
                    "required": True,
                }],
                "parameter_operations": [operation],
            },
        }
        source = [{"policy_source": "test", "path": "requirement-baselines/test.json"}]
        states, ancestry = parameters.resolve(
            "test.baseline@1",
            {"test.baseline@1": {**baseline_document, "_sources": source}},
            {requirement["reference"]: requirement_document},
        )
        parameters.complete(states)

        control["alignment"] = "realization"
        definition = copy.deepcopy(control["policy_inputs"]["definition"])
        definition["spec"]["evidence"] = [{
            "id": "observation",
            "type": "test.evidence/v1",
        }]
        definition["_parameters_schema"] = copy.deepcopy(
            control["policy_inputs"]["parameters_schema"]
        )
        definition["_parameters_schema"]["$id"] = (
            schema_origin
            + "/schemas/controls/test.control/parameters/v1.schema.json"
        )
        if schema_host != "compliance.example":
            definition["spec"]["evidence"][0]["inputs_schema"] = {
                "$id": (
                    schema_origin
                    + "/schemas/controls/test.control/evidence/observation/"
                    "inputs/v1.schema.json"
                ),
                "type": "object",
                "additionalProperties": False,
            }
        definition["_implementation_modules"] = []
        instance = {
            "instance_id": control["instance_id"],
            "implementation": control["implementation"],
            "parameters": {},
            "evidence": {},
        }
        realization = copy.deepcopy(requirement["parameter_facts"]["realization"])
        realization["spec"]["requirement"] = {
            "requirement": requirement["reference"],
            "digest": requirement["digest"],
        }
        realization["spec"]["checks"] = [copy.deepcopy(instance)]
        realization["spec"]["parameter_links"] = [{
            "id": "freshness",
            "source": copy.deepcopy(initial["pin"]),
            "destination": {
                "instance_id": control["instance_id"],
                "implementation": parameters.implementation_pin(definition),
                "kind": "freshness",
                "dependency": "observation",
                "path": "/max_age",
            },
        }]
        checks, consumption = parameters.consume(
            realization,
            states[requirement["reference"]],
            {control["implementation"]: definition},
        )
        instance = checks[0]
        control["policy_inputs"] = {
            "instance": copy.deepcopy(instance),
            "definition": {
                key: copy.deepcopy(value)
                for key, value in definition.items()
                if not key.startswith("_")
            },
            "parameters_schema": copy.deepcopy(definition["_parameters_schema"]),
        }
        control["parameters"] = copy.deepcopy(instance["parameters"])
        control["evidence"] = parameters.evidence_for(instance, definition)
        control["definition_fingerprint"] = parameters.digest(instance)

        requirement["parameter_facts"] = {
            "document": requirement_document,
            "states": states[requirement["reference"]],
            "realization": realization,
            "consumption": consumption,
        }
        requirement["realization"]["digest"] = parameters.digest(realization)
        baseline = plan["resolved_requirement_baselines"][0]
        baseline["digest"] = parameters.digest(baseline_document)
        baseline["requirements"] = copy.deepcopy(
            baseline_document["spec"]["requirements"]
        )
        baseline["parameter_derivation"] = {
            "states": states,
            "ancestry": ancestry,
        }
        refresh_operation(plan)
        plan["id"] = artifact_digest(plan)
        validate_assessment_plan(plan)
        return plan

    def test_frozen_plan_preserves_and_accepts_adopter_schema_host(self):
        plan = self.parameterized_plan("schemas.adopter.example")
        requirement_schema_id = plan["requirements"][0]["parameter_facts"][
            "document"
        ]["spec"]["parameters"]["age"]["schema"]["$id"]
        control = plan["controls"][0]

        self.assertTrue(requirement_schema_id.startswith(
            "https://schemas.adopter.example/"
        ))
        self.assertTrue(control["policy_inputs"]["parameters_schema"]["$id"].startswith(
            "https://schemas.adopter.example/"
        ))
        self.assertTrue(control["policy_inputs"]["definition"]["spec"]["evidence"][0][
            "inputs_schema"
        ]["$id"].startswith("https://schemas.adopter.example/"))
        validate_assessment_plan(plan)

    def test_invalid_plan_still_rejects_retained_contract_tampering(self):
        from tools import policy_parameters as parameters

        cases = {
            "control parameter schema": lambda plan: plan["controls"][0][
                "policy_inputs"
            ]["parameters_schema"].update({"$id": "https://bad.example/wrong"}),
            "evidence input schema": lambda plan: plan["controls"][0][
                "policy_inputs"
            ]["definition"]["spec"]["evidence"][0]["inputs_schema"].update(
                {"$id": "https://bad.example/wrong"}
            ),
            "requirement parameter schema": lambda plan: plan["requirements"][0][
                "parameter_facts"
            ]["document"]["spec"]["parameters"]["age"].update({
                "schema": {
                    **plan["requirements"][0]["parameter_facts"]["document"][
                        "spec"
                    ]["parameters"]["age"]["schema"],
                    "$id": "https://bad.example/wrong",
                },
            }),
            "requirement schema digest": lambda plan: plan["requirements"][0][
                "parameter_facts"
            ]["document"]["spec"]["parameters"]["age"].update(
                schema_digest="sha256:" + "0" * 64
            ),
            "control version": lambda plan: plan["controls"][0]["policy_inputs"][
                "definition"
            ]["metadata"].update(version="bad__version"),
            "evidence type": lambda plan: plan["controls"][0]["policy_inputs"][
                "definition"
            ]["spec"]["evidence"][0].update(type="bad_type/v1"),
        }
        for case, mutate in cases.items():
            with self.subTest(case=case):
                plan = self.parameterized_plan("schemas.adopter.example")
                mutate(plan)
                if case == "requirement parameter schema":
                    declaration = plan["requirements"][0]["parameter_facts"][
                        "document"
                    ]["spec"]["parameters"]["age"]
                    declaration["schema_digest"] = parameters.digest(
                        declaration["schema"]
                    )
                plan["resolution"] = {
                    "status": "invalid",
                    "errors": [{"type": "synthetic"}],
                }
                refresh_operation(plan)
                plan["id"] = artifact_digest(plan)

                with self.assertRaises(ArtifactValidationError):
                    validate_assessment_plan(plan)

    @classmethod
    def additive_plan(cls):
        """Build a valid plan with one additive contribution and exact consumer."""
        from tools import policy_parameters as parameters

        plan = cls.parameterized_plan()
        requirement = plan["requirements"][0]
        control = plan["controls"][0]
        base_record = plan["resolved_requirement_baselines"][0]
        requirement_document = copy.deepcopy(requirement["parameter_facts"]["document"])
        value_schema = {
            "$id": "https://compliance.example/schemas/requirements/test.requirement/parameters/allowed/v1.schema.json",
            "type": "array",
            "items": {"type": "string"},
            "uniqueItems": True,
        }
        declaration = {
            "required": True,
            "binding_mode": "open",
            "schema": value_schema,
            "schema_digest": parameters.digest(value_schema),
            "binding_scope": ["test.baseline"],
            "composition": {"kind": "additive-set"},
        }
        requirement_document["spec"]["parameters"] = {"allowed": declaration}
        requirement["digest"] = parameters.digest(requirement_document)
        initial = parameters.declarations(requirement_document)["allowed"]
        requirement_pin = {
            "requirement": requirement["reference"],
            "digest": requirement["digest"],
            "required": True,
        }
        base_document = {
            "metadata": {"id": "test.baseline", "revision": 1},
            "spec": {
                "title": base_record["title"],
                "requirements": [requirement_pin],
                "parameter_operations": [{
                    "id": "bind-allowed",
                    "op": "bind",
                    "target": copy.deepcopy(initial["pin"]),
                    "expected_parent_fingerprint": parameters.fingerprint(initial),
                    "to": ["base"],
                }],
            },
        }
        contribution_document = {
            "metadata": {"id": "test.feature", "revision": 1},
            "spec": {
                "title": "Synthetic contribution",
                "parameter_contributions": [{
                    "id": "feature-members",
                    "target": {"requirement": "test.requirement", "slot": "allowed"},
                    "members": ["contributed"],
                }],
            },
        }
        base_source = base_record["policy_sources"]
        contribution_source = [{
            "policy_source": "test",
            "path": "requirement-baselines/feature.json",
        }]
        baselines = {
            "test.baseline@1": {**base_document, "_sources": base_source},
            "test.feature@1": {**contribution_document, "_sources": contribution_source},
        }
        base_states, base_ancestry = parameters.resolve(
            "test.baseline@1", baselines, {requirement["reference"]: requirement_document}
        )
        contribution_states, contribution_ancestry = parameters.resolve(
            "test.feature@1", baselines, {requirement["reference"]: requirement_document}
        )
        resolved = [
            {
                "reference": "test.baseline@1",
                "applicability": {
                    "group": "test-hosts",
                    "assignment": "test-policy",
                    "baseline": "test.baseline@1",
                },
                "states": base_states,
                "ancestry": base_ancestry,
            },
            {
                "reference": "test.feature@1",
                "applicability": {
                    "group": "test-hosts",
                    "assignment": "test-feature",
                    "baseline": "test.feature@1",
                },
                "states": contribution_states,
                "ancestry": contribution_ancestry,
            },
        ]
        parameters.compose_selected(resolved, baselines)

        definition = copy.deepcopy(control["policy_inputs"]["definition"])
        definition["spec"]["evidence"] = [{
            "id": "observation",
            "type": "test.evidence/v1",
        }]
        definition["_parameters_schema"] = {
            "$id": (
                "https://compliance.example/schemas/controls/"
                f"{control['implementation']}/parameters/v1.schema.json"
            ),
            "type": "object",
            "properties": {
                "allowed": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["allowed"],
            "additionalProperties": False,
        }
        definition["_implementation_modules"] = []
        instance = {
            "instance_id": control["instance_id"],
            "implementation": control["implementation"],
            "parameters": {},
            "evidence": {"observation": {"max_age": "1d"}},
        }
        realization = copy.deepcopy(requirement["parameter_facts"]["realization"])
        realization["spec"]["requirement"] = {
            "requirement": requirement["reference"],
            "digest": requirement["digest"],
        }
        realization["spec"]["checks"] = [copy.deepcopy(instance)]
        realization["spec"]["parameter_links"] = [{
            "id": "allowed",
            "source": copy.deepcopy(initial["pin"]),
            "destination": {
                "instance_id": control["instance_id"],
                "implementation": parameters.implementation_pin(definition),
                "kind": "parameters",
                "path": "/allowed",
            },
        }]
        checks, consumption = parameters.consume(
            realization,
            base_states[requirement["reference"]],
            {control["implementation"]: definition},
        )
        instance = checks[0]
        control["policy_inputs"] = {
            "instance": copy.deepcopy(instance),
            "definition": {
                key: copy.deepcopy(value)
                for key, value in definition.items()
                if not key.startswith("_")
            },
            "parameters_schema": copy.deepcopy(definition["_parameters_schema"]),
        }
        control["parameters"] = copy.deepcopy(instance["parameters"])
        control["evidence"] = parameters.evidence_for(instance, definition)
        control["definition_fingerprint"] = parameters.digest(instance)
        requirement["parameter_facts"] = {
            "document": requirement_document,
            "states": base_states[requirement["reference"]],
            "realization": realization,
            "consumption": consumption,
        }
        requirement["realization"]["digest"] = parameters.digest(realization)
        base_record["digest"] = parameters.digest(base_document)
        base_record["requirements"] = [requirement_pin]
        base_record["parameter_derivation"] = {
            "states": base_states,
            "ancestry": base_ancestry,
        }
        plan["assignments"].append({
            "id": "test-feature",
            "group": "test-hosts",
            "baselines": ["test.feature@1"],
        })
        plan["resolved_requirement_baselines"].append({
            "assignment": "test-feature",
            "group": "test-hosts",
            "baseline": "test.feature@1",
            "reference": "test.feature@1",
            "title": contribution_document["spec"]["title"],
            "digest": parameters.digest(contribution_document),
            "policy_sources": contribution_source,
            "requirements": [],
            "parameter_derivation": {
                "states": contribution_states,
                "ancestry": contribution_ancestry,
            },
        })
        refresh_operation(plan)
        plan["id"] = artifact_digest(plan)
        validate_assessment_plan(plan)
        return plan

    def test_parameterized_plan_rejects_tampered_frozen_values_and_consumption(self):
        plan = self.parameterized_plan()
        requirement = plan["requirements"][0]
        reference = requirement["reference"]
        cases = {
            "resolved state": (
                lambda document: document["requirements"][0]["parameter_facts"][
                    "states"
                ]["age"].update(value="7200s"),
                "frozen derivation inconsistent",
            ),
            "materialized freshness": (
                lambda document: document["controls"][0]["evidence"][0].update(
                    max_age="7200s"
                ),
                "frozen policy freshness mismatch",
            ),
            "derivation history": (
                lambda document: document["resolved_requirement_baselines"][0][
                    "parameter_derivation"
                ]["states"][reference]["age"]["history"][-1]["operation"].update(
                    {"from": "2h"}
                ),
                "frozen derivation inconsistent",
            ),
            "consumption destination": (
                lambda document: document["requirements"][0]["parameter_facts"][
                    "consumption"
                ][0]["link"]["destination"]["implementation"].update(version=99),
                "frozen consumption records mismatch",
            ),
        }
        for case, (mutate, expected) in cases.items():
            with self.subTest(case=case):
                tampered = copy.deepcopy(plan)
                mutate(tampered)
                # Re-sign only the outer plan commitment, matching an independently
                # authored but internally inconsistent frozen artifact.
                tampered["id"] = artifact_digest(tampered)
                with self.assertRaisesRegex(
                    ArtifactValidationError,
                    expected,
                ):
                    validate_assessment_plan(tampered)

    def test_parameterized_plan_rejects_noncanonical_frozen_binding_scope(self):
        from tools import policy_parameters as parameters

        tampered = copy.deepcopy(self.parameterized_plan())
        requirement = tampered["requirements"][0]
        requirement_document = requirement["parameter_facts"]["document"]
        requirement_document["spec"]["parameters"]["age"]["binding_scope"].append(
            "bad__scope"
        )
        requirement["digest"] = parameters.digest(requirement_document)
        realization = requirement["parameter_facts"]["realization"]
        realization["spec"]["requirement"]["digest"] = requirement["digest"]
        requirement["realization"]["digest"] = parameters.digest(realization)
        baseline = tampered["resolved_requirement_baselines"][0]
        baseline["requirements"][0]["digest"] = requirement["digest"]
        ancestor = baseline["parameter_derivation"]["ancestry"][-1]
        ancestor["document"]["spec"]["requirements"][0]["digest"] = requirement[
            "digest"
        ]
        ancestor["digest"] = parameters.digest(ancestor["document"])
        baseline["digest"] = ancestor["digest"]
        refresh_operation(tampered)
        tampered["id"] = artifact_digest(tampered)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "invalid requirement parameter binding scope",
        ):
            validate_assessment_plan(tampered)

    def test_plan_rejects_frozen_control_identity_contract_tampering(self):
        cases = {
            "active version": (
                lambda document: document["controls"][0]["policy_inputs"][
                    "definition"
                ]["metadata"].update(version="bad__version"),
                "invalid frozen Control version",
            ),
            "active evidence dependency": (
                lambda document: document["controls"][0]["policy_inputs"][
                    "definition"
                ]["spec"]["evidence"][0].update(id="bad__dependency"),
                "invalid frozen Control evidence dependency identity",
            ),
            "active evidence type": (
                lambda document: document["controls"][0]["policy_inputs"][
                    "definition"
                ]["spec"]["evidence"][0].update(type="bad_type/v1"),
                "invalid frozen Control evidence type",
            ),
            "excluded parameter schema owner": (
                lambda document: document["excluded_controls"][0]["policy_inputs"][
                    "parameters_schema"
                ].update(
                    {
                        "$id": (
                            "https://compliance.example/schemas/controls/other.control/"
                            "parameters/v1.schema.json"
                        )
                    }
                ),
                "parameter schema identity does not match its semantic owner",
            ),
            "malformed parameter schema URI": (
                lambda document: document["excluded_controls"][0]["policy_inputs"][
                    "parameters_schema"
                ].update({
                    "$id": (
                        "https://schemas.\nadopter.example/schemas/controls/"
                        "test.setting-equals/parameters/v1.schema.json"
                    )
                }),
                "parameter schema identity does not match its semantic owner",
            ),
            "empty query delimiter in parameter schema URI": (
                lambda document: document["excluded_controls"][0]["policy_inputs"][
                    "parameters_schema"
                ].update({
                    "$id": (
                        "https://schemas.adopter.example/schemas/controls/"
                        "test.setting-equals/parameters/v1.schema.json?"
                    )
                }),
                "parameter schema identity does not match its semantic owner",
            ),
        }
        for case, (mutate, expected) in cases.items():
            with self.subTest(case=case):
                tampered = copy.deepcopy(self.plan)
                mutate(tampered)
                refresh_operation(tampered)
                tampered["id"] = artifact_digest(tampered)
                with self.assertRaisesRegex(ArtifactValidationError, expected):
                    validate_assessment_plan(tampered)

    def test_plan_rejects_noncanonical_refs_in_opaque_frozen_policy(self):
        from tools import policy_parameters as parameters

        baseline_plan = copy.deepcopy(self.parameterized_plan())
        requirement = baseline_plan["requirements"][0]
        baseline = baseline_plan["resolved_requirement_baselines"][0]
        original_ancestor = baseline["parameter_derivation"]["ancestry"][-1]
        child_document = copy.deepcopy(original_ancestor["document"])
        parent_document = {
            "metadata": {"id": "test.parent", "revision": 1},
            "spec": {
                "title": "Synthetic parent requirement policy",
                "requirements": copy.deepcopy(child_document["spec"]["requirements"]),
            },
        }
        child_document["spec"]["extends"] = {
            "baseline": "test.parent@1",
            "digest": parameters.digest(parent_document),
        }
        sources = original_ancestor["policy_sources"]
        catalog = {
            "test.parent@1": {**parent_document, "_sources": sources},
            baseline["reference"]: {**child_document, "_sources": sources},
        }
        states, ancestry = parameters.resolve(
            baseline["reference"],
            catalog,
            {requirement["reference"]: requirement["parameter_facts"]["document"]},
        )
        parameters.complete(states)
        ancestry[0]["reference"] = "bad__parent@1"
        ancestry[0]["document"]["metadata"]["id"] = "bad__parent"
        ancestry[0]["digest"] = parameters.digest(ancestry[0]["document"])
        ancestry[1]["document"]["spec"]["extends"] = {
            "baseline": "bad__parent@1",
            "digest": ancestry[0]["digest"],
        }
        ancestry[1]["digest"] = parameters.digest(ancestry[1]["document"])
        baseline["parameter_derivation"] = {
            "states": states,
            "ancestry": ancestry,
        }
        baseline["digest"] = ancestry[-1]["digest"]
        requirement["parameter_facts"]["states"] = states[requirement["reference"]]
        refresh_operation(baseline_plan)
        baseline_plan["id"] = artifact_digest(baseline_plan)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "invalid frozen requirement baseline parent reference",
        ):
            validate_assessment_plan(baseline_plan)

        realization_plan = copy.deepcopy(self.iam_plan)
        realization_requirement = next(
            item
            for item in realization_plan["requirements"]
            if item.get("parameter_facts", {}).get("realization", {}).get("spec", {}).get(
                "based_on"
            )
        )
        realization = realization_requirement["parameter_facts"]["realization"]
        realization["spec"]["based_on"]["realization"] = "bad__base@1"
        realization_requirement["realization"]["digest"] = parameters.digest(realization)
        refresh_operation(realization_plan)
        realization_plan["id"] = artifact_digest(realization_plan)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "invalid frozen realization parent reference",
        ):
            validate_assessment_plan(realization_plan)

    def test_additive_plan_rejects_frozen_composition_and_consumer_tampering(self):
        plan = self.additive_plan()
        cases = {
            "declaration": lambda document: document["requirements"][0]["parameter_facts"]["states"]["allowed"]["declaration"]["composition"].update(kind="atomic"),
            "contribution": lambda document: document["requirements"][0]["parameter_facts"]["states"]["allowed"]["composition"]["contributions"][0].update(members=["changed"]),
            "attribution": lambda document: document["requirements"][0]["parameter_facts"]["states"]["allowed"]["composition"]["contributions"][0].update(applicability=[]),
            "effective value": lambda document: document["requirements"][0]["parameter_facts"]["states"]["allowed"].update(value=["base"]),
            "member origins": lambda document: document["requirements"][0]["parameter_facts"]["states"]["allowed"]["composition"].update(member_origins=[]),
            "consumer": lambda document: document["controls"][0]["parameters"].update(allowed=["base"]),
        }
        for case, mutate in cases.items():
            with self.subTest(case=case):
                tampered = copy.deepcopy(plan)
                mutate(tampered)
                tampered["id"] = artifact_digest(tampered)
                with self.assertRaisesRegex(
                    ArtifactValidationError,
                    "invalid frozen policy parameters|frozen technical value mismatch",
                ):
                    validate_assessment_plan(tampered)

    def test_additive_plan_binds_contribution_owner_reference_to_document(self):
        from tools import policy_parameters as parameters

        tampered = copy.deepcopy(self.additive_plan())
        contributor = next(
            item for item in tampered["resolved_requirement_baselines"]
            if item["reference"] == "test.feature@1"
        )
        ancestor = contributor["parameter_derivation"]["ancestry"][-1]
        ancestor["document"]["metadata"]["revision"] = 99
        ancestor["digest"] = parameters.digest(ancestor["document"])
        contributor["digest"] = ancestor["digest"]
        for baseline in tampered["resolved_requirement_baselines"]:
            for slots in baseline["parameter_derivation"]["states"].values():
                for state in slots.values():
                    for contribution in state.get("composition", {}).get("contributions", []):
                        contribution["owner"]["document"]["metadata"]["revision"] = 99
                        contribution["owner"]["digest"] = parameters.digest(
                            contribution["owner"]["document"]
                        )
        for requirement in tampered["requirements"]:
            for state in requirement["parameter_facts"]["states"].values():
                for contribution in state.get("composition", {}).get("contributions", []):
                    contribution["owner"]["document"]["metadata"]["revision"] = 99
                    contribution["owner"]["digest"] = parameters.digest(
                        contribution["owner"]["document"]
                    )
        refresh_operation(tampered)
        tampered["id"] = artifact_digest(tampered)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "frozen requirement baseline reference mismatch",
        ):
            validate_assessment_plan(tampered)

    def test_additive_plan_rejects_structurally_empty_frozen_baseline(self):
        from tools import policy_parameters as parameters

        tampered = copy.deepcopy(self.additive_plan())
        contributor = next(
            item for item in tampered["resolved_requirement_baselines"]
            if item["reference"] == "test.feature@1"
        )
        ancestor = contributor["parameter_derivation"]["ancestry"][-1]
        ancestor["document"]["spec"].pop("parameter_contributions")
        ancestor["digest"] = parameters.digest(ancestor["document"])
        contributor["digest"] = ancestor["digest"]
        refresh_operation(tampered)
        tampered["id"] = artifact_digest(tampered)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "requires a requirement or parameter contribution",
        ):
            validate_assessment_plan(tampered)

    def test_additive_plan_rejects_unsupported_and_empty_present_frozen_syntax(self):
        from tools import policy_parameters as parameters

        cases = {
            "unsupported priority": (
                lambda document: document["spec"]["parameter_contributions"][0].update(
                    priority=1
                ),
                "unsupported additive contribution syntax",
            ),
            "present empty requirements": (
                lambda document: document["spec"].update(requirements=[]),
                "requirements must be nonempty when present",
            ),
        }
        for case, (mutate, expected) in cases.items():
            with self.subTest(case=case):
                tampered = copy.deepcopy(self.additive_plan())
                contributor = next(
                    item for item in tampered["resolved_requirement_baselines"]
                    if item["reference"] == "test.feature@1"
                )
                ancestor = contributor["parameter_derivation"]["ancestry"][-1]
                mutate(ancestor["document"])
                ancestor["digest"] = parameters.digest(ancestor["document"])
                contributor["digest"] = ancestor["digest"]
                refresh_operation(tampered)
                tampered["id"] = artifact_digest(tampered)

                with self.assertRaisesRegex(ArtifactValidationError, expected):
                    validate_assessment_plan(tampered)

    def test_result_outcome_uses_fail_first_logical_precedence(self):
        self.assertEqual(result_outcome({
            "results": [{"status": "error"}, {"status": "fail"}],
            "requirement_assessments": [],
            "requirement_baseline_assessments": [],
        }), "fail")

    def test_unknown_results_require_complete_frozen_control_coverage(self):
        report = self.result_report()
        self.assertFalse(report['provenance']['selectedEvidence'])
        self.assertTrue(report['results'])
        changed = copy.deepcopy(report)
        changed['results'] = changed['results'][1:]
        changed['outcome'] = result_outcome(changed)
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(
            ValueError, 'dependency disposition control is absent from results'
        ):
            validate_assessment_results(changed)

    def test_matching_freshness_copies_cannot_bypass_instance_fingerprint(self):
        from tools.assessment_provenance import artifact_digest
        plan = copy.deepcopy(self.plan)
        control = next(c for c in plan['controls'] if not c['derivations'])
        dependency = control['evidence'][0]
        dependency['max_age'] = '999999999s'
        control['policy_inputs']['instance']['evidence'][dependency['id']]['max_age'] = '999999999s'
        plan['id'] = artifact_digest(plan)
        with self.assertRaisesRegex(ArtifactValidationError, 'instance fingerprint mismatch'):
            validate_assessment_plan(plan)

    def test_frozen_realization_cannot_lose_required_checks(self):
        from tools.assessment_provenance import artifact_digest
        plan = copy.deepcopy(self.iam_plan)
        requirement = plan['requirements'][0]
        self.assertGreater(len(requirement['technical_instance_ids']), 1)
        requirement['technical_instance_ids'] = requirement['technical_instance_ids'][:1]
        requirement['satisfaction']['allOf'] = requirement['technical_instance_ids'][:]
        plan['id'] = artifact_digest(plan)
        with self.assertRaisesRegex(ArtifactValidationError, 'frozen realization satisfaction'):
            validate_assessment_plan(plan)

    def test_plan_rejects_retired_realization_classification(self):
        plan = copy.deepcopy(self.iam_plan)
        plan["requirements"][0]["realization"]["classification"] = "restricted"
        plan["id"] = artifact_digest(plan)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"classification.*unexpected",
        ):
            validate_assessment_plan(plan)

    def test_frozen_derivation_records_cannot_be_omitted(self):
        from tools.assessment_provenance import artifact_digest
        plan = copy.deepcopy(self.iam_plan)
        plan['resolved_requirement_baselines'] = []
        plan['id'] = artifact_digest(plan)
        with self.assertRaisesRegex(ArtifactValidationError, 'derivation coverage'):
            validate_assessment_plan(plan)

    @classmethod
    def setUpClass(cls):
        cls.root = fixture_root(cls)
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            cls.root / "schemas/inventory/resource.schema.json",
        )
        cls.plan = render_plan(
            subject,
            groups,
            assignments,
            (
                PolicySource(
                    "control-library",
                    cls.root / "shared",
                ),
                PolicySource(
                    "verification-policy",
                    cls.root / "selection",
                ),
            ),
        )
        iam_subject, iam_groups, iam_assignments = load_inventory_inputs(
            cls.root / "iam/inventory",
            cls.root / "iam/assignments",
            "host/restricted-linux-01",
            cls.root / "schemas/inventory/resource.schema.json",
        )
        cls.iam_plan = render_plan(
            iam_subject,
            iam_groups,
            iam_assignments,
            (
                PolicySource(
                    "control-library",
                    cls.root / "shared",
                ),
                PolicySource(
                    "verification-policy",
                    cls.root / "selection",
                ),
                PolicySource(
                    "environment-private",
                    cls.root / "iam/policy",
                ),
            ),
        )

    @staticmethod
    def opa_result(_opa, _policies, assessment_input, _entrypoint):
        control = assessment_input["control"]
        assessment = assessment_input["assessment"]
        return {
            "control_id": control["implementation"],
            "instance_id": control["instance_id"],
            "subject_id": assessment_input["subject"]["id"],
            "plan_id": assessment["plan_id"],
            "status": "pass",
            "severity": control["severity"],
            "reason": "Synthetic unit-test pass.",
            "expected": {},
            "observed": {},
            "remediation": control["remediation"],
            "external_refs": control.get("external_refs", []),
            "alignment": control["alignment"],
        }

    def result_report(self, plan=None):
        plan = plan or self.plan
        with tempfile.TemporaryDirectory() as directory, patch(
            "tools.evaluate_plan.evaluate_control",
            side_effect=self.opa_result,
        ):
            return evaluate_plan_document(
                plan,
                Path(directory),
                (
                    (
                        PolicySource(
                            "control-library",
                            self.root / "shared",
                        ),
                        PolicySource(
                            "verification-policy",
                            self.root / "selection",
                        ),
                    )
                    if plan is self.plan
                    else (
                        PolicySource(
                            "control-library",
                            self.root / "shared",
                        ),
                        PolicySource(
                            "verification-policy",
                            self.root / "selection",
                        ),
                        PolicySource(
                            "environment-private",
                            self.root / "iam/policy",
                        ),
                    )
                ),
                evaluated_at=datetime(2026, 8, 28, 12, tzinfo=UTC),
            )

    def test_rendered_plan_and_generated_results_satisfy_contracts(self):
        validate_assessment_plan(self.plan)
        result = self.result_report()
        validate_assessment_results(result)
        for item in result["results"]:
            self.assertNotIn("title", item)
            self.assertNotIn("purpose", item)

    def test_unavailable_policy_source_refuses_without_invented_provenance(self):
        fixture = Path(__file__).resolve().parent / "fixtures/macos-project"
        subject, groups, assignments = load_inventory_inputs(
            fixture / "inventory",
            fixture / "assignments",
            "workstation/tooling-macos-fixture",
            self.root / "schemas/inventory/resource.schema.json",
        )
        with self.assertRaisesRegex(ValueError, "not a directory"):
            render_plan(subject, groups, assignments, self.root / "does-not-exist-policy")

    def test_plan_rejects_unknown_envelope_field(self):
        document = copy.deepcopy(self.plan)
        document["unexpected"] = True

        with self.assertRaisesRegex(ArtifactValidationError, "unexpected"):
            validate_assessment_plan(document)

    def test_plan_rejects_malformed_control_provenance(self):
        document = copy.deepcopy(self.plan)
        del document["controls"][0]["provenance"][0]["group"]
        document.pop("id")
        document["id"] = content_digest(document)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/controls/0/provenance/0.*group",
        ):
            validate_assessment_plan(document)

    def test_plan_rejects_missing_or_contradictory_frozen_meaning(self):
        missing = copy.deepcopy(self.plan)
        del missing["controls"][0]["title"]
        with self.assertRaisesRegex(ArtifactValidationError, r"/controls/0.*title"):
            validate_assessment_plan(missing)

        cases = (
            (
                lambda plan: plan["controls"][0].update(
                    title="Contradictory active check title"
                ),
                r"/controls/0/title: differs from frozen Control title",
            ),
            (
                lambda plan: plan["excluded_controls"][0].update(
                    purpose="Contradictory excluded check purpose"
                ),
                r"/excluded_controls/0/purpose: differs from frozen Control purpose",
            ),
        )
        for mutate, message in cases:
            with self.subTest(message=message):
                document = copy.deepcopy(self.plan)
                mutate(document)
                refresh_operation(document)
                document.pop("id", None)
                document["id"] = artifact_digest(document)
                with self.assertRaisesRegex(ArtifactValidationError, message):
                    validate_assessment_plan(document)

        requirement_plan = copy.deepcopy(self.iam_plan)
        requirement_plan["resolved_requirement_baselines"][0]["title"] = (
            "Contradictory objective policy title"
        )
        refresh_operation(requirement_plan)
        requirement_plan.pop("id", None)
        requirement_plan["id"] = artifact_digest(requirement_plan)
        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"resolved_requirement_baselines/0/title: differs from frozen",
        ):
            validate_assessment_plan(requirement_plan)

    def test_unconsumed_subject_label_is_not_identity_bearing(self):
        document = copy.deepcopy(self.plan)
        document["subject"]["labels"]["changed"] = "true"
        validate_assessment_plan(document)
        self.assertEqual(document['id'], self.plan['id'])

    def test_plan_rejects_stale_member_commitment(self):
        document = copy.deepcopy(self.plan)
        document['controls'][0]['remediation'] = 'tampered'

        with self.assertRaisesRegex(
            ArtifactValidationError,
            "subject plan differs from frozen operation",
        ):
            validate_assessment_plan(document)

    def test_plan_rejects_derivation_that_does_not_reach_effective_criteria(self):
        document = copy.deepcopy(self.plan)
        control = next(item for item in document["controls"] if item["derivations"])
        control["derivations"][-1]["after"]["parameters"] = {"tampered": True}
        document.pop("id")
        document["id"] = content_digest(document)

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"derivations.*at least one after state",
        ):
            validate_assessment_plan(document)

    def test_results_reject_deleted_predecessor_fields(self):
        document = self.result_report()
        for field, value in (
            ("assessment_id", "old"), ("summary", {}), ("waiver_revision", "sha256:" + "0" * 64),
            ("operation", copy.deepcopy(self.plan["operation"])), ("resolved_policy", {}),
        ):
            changed = copy.deepcopy(document)
            changed[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ArtifactValidationError, field):
                validate_assessment_results(changed)

    def test_results_reject_plan_owned_child_attribution(self):
        document = self.result_report()
        document["results"][0]["plan_id"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0.*plan_id",
        ):
            validate_assessment_results(document)

    def test_results_reject_child_waiver_revision(self):
        document = self.result_report()
        document["results"][0]["waiver_revision"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(
            ArtifactValidationError,
            r"/results/0.*waiver_revision",
        ):
            validate_assessment_results(document)

    def test_results_reject_inconsistent_objective_rollup(self):
        document = self.result_report(self.iam_plan)
        document["requirement_assessments"][0]["status"] = "fail"
        document["outcome"] = result_outcome(document)
        document["id"] = artifact_digest(document)
        validate_assessment_results(document)
        with self.assertRaisesRegex(ValueError, "requirement outcomes differ"):
            validate_result_against_plan(document, self.iam_plan)

    def test_result_loader_rejects_malformed_matching_schema_with_path(self):
        document = self.result_report()
        document["results"][0]["status"] = "success"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "malformed.json"
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(
                ArtifactValidationError,
                r"malformed\.json.*results/0/status",
            ):
                load_result_reports(Path(directory))


if __name__ == "__main__":
    unittest.main()
