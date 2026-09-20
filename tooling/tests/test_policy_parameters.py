"""ADR 0024 Tranche B vectors for explicit ParameterPolicy resolution."""
import copy
import unittest

from tools import policy_parameters as p


class PolicyParameterTests(unittest.TestCase):
    @staticmethod
    def policy(identifier, **spec):
        return {
            "apiVersion": "compliance.example/v1alpha1",
            "kind": "ParameterPolicy",
            "metadata": {"id": identifier, "revision": 1},
            "spec": spec,
            "_sources": [{"policy_source": "test", "path": identifier + ".json"}],
        }

    @staticmethod
    def operation(op, state, **values):
        return {
            "id": op + "-value", "op": op,
            "target": copy.deepcopy(state["pin"]),
            "expected_parent_fingerprint": p.fingerprint(state), **values,
        }

    def setUp(self):
        schema = {
            "$id": "https://compliance.example/schemas/parameter-policies/objective/parameters/age/v1.schema.json",
            "type": "string", "pattern": "^[1-9][0-9]*[smhd]$", "default": "30d",
        }
        self.root = self.policy("objective", parameters={"age": {
            "required": True, "binding_mode": "open",
            "binding_scope": ["company", "enclave"],
            "schema": schema, "schema_digest": p.digest(schema),
            "representation": "duration",
        }})
        self.initial = p.declarations(self.root)["age"]
        self.base = self.policy(
            "company",
            extends={"policy": "objective@1", "digest": p.resource_digest(self.root)},
            parameter_operations=[self.operation("bind", self.initial, to="30d")],
        )
        self.catalog = {"objective@1": self.root, "company@1": self.base}
        self.definition = {
            "metadata": {"id": "test.check", "version": 1},
            "spec": {"evidence": [{
                "id": "observation", "type": "test/v1",
                "inputs_schema": {
                    "$id": "https://compliance.example/schemas/controls/test.check/evidence/observation/inputs/v1.schema.json",
                    "type": "object", "properties": {"period": {"type": "string"}},
                    "required": ["period"], "additionalProperties": False,
                },
            }]},
            "_parameters_schema": {
                "$id": "https://compliance.example/schemas/controls/test.check/parameters/v1.schema.json",
                "type": "object", "properties": {"age": {"type": "string"}},
                "required": ["age"], "additionalProperties": False,
            },
        }
        self.controls = {"test.check": self.definition}
        self.links = []
        for kind, path in (("parameters", "/age"), ("evidence_inputs", "/period"),
                           ("freshness", "/max_age")):
            destination = {
                "instance_id": "check", "implementation": p.implementation_pin(self.definition),
                "kind": kind, "path": path,
            }
            if kind != "parameters":
                destination["dependency"] = "observation"
            self.links.append({"id": kind, "source": copy.deepcopy(self.initial["pin"]),
                               "destination": destination})

    def resolution(self, reference="company@1", assignment="base"):
        states, ancestry = p.resolve(reference, self.catalog)
        p.complete(states)
        return {
            "reference": reference,
            "applicability": {"group": assignment, "assignment": assignment,
                              "parameter_policy": reference},
            "states": states, "ancestry": ancestry,
        }

    def states(self, reference="company@1"):
        return self.resolution(reference)["states"]

    def tailor(self, value="15d"):
        state = self.states()["objective@1"]["age"]
        child = self.policy(
            "enclave", extends={"policy": "company@1", "digest": p.resource_digest(self.base)},
            parameter_operations=[self.operation("tailor", state, **{
                "from": "30d", "to": value,
                "deviation": {"id": "DEV-1", "classification": "specialization",
                              "rationale": "Synthetic enclave intent",
                              "approval_ref": "test/review", "review_after": "2027-01-01"},
            })],
        )
        self.catalog["enclave@1"] = child
        return child

    def additive(self):
        schema = {
            "$id": "https://compliance.example/schemas/parameter-policies/software/parameters/allowed/v1.schema.json",
            "type": "array", "items": {"type": "string"}, "uniqueItems": True,
        }
        root = self.policy("software", parameters={"allowed": {
            "required": True, "binding_mode": "open", "binding_scope": ["software-base"],
            "schema": schema, "schema_digest": p.digest(schema),
            "composition": {"kind": "additive-set"},
        }})
        initial = p.declarations(root)["allowed"]
        base = self.policy(
            "software-base", extends={"policy": "software@1", "digest": p.resource_digest(root)},
            parameter_operations=[self.operation(
                "bind", initial, to=["shared", "base", "shared"]
            )],
        )
        contributor = self.policy("database", parameter_contributions=[{
            "id": "packages", "target": {"policy": "software", "slot": "allowed"},
            "members": ["postgresql", "shared", "postgresql"],
        }])
        catalog = {"software@1": root, "software-base@1": base,
                   "database@1": contributor}
        resolutions = []
        for reference, assignment in (("software-base@1", "base"),
                                      ("database@1", "database")):
            states, ancestry = p.resolve(reference, catalog)
            p.complete(states)
            resolutions.append({
                "reference": reference,
                "applicability": {"group": assignment, "assignment": assignment,
                                  "parameter_policy": reference},
                "states": states, "ancestry": ancestry,
            })
        return catalog, resolutions

    def test_default_does_not_bind_and_missing_value_fails_closed(self):
        self.base["spec"].pop("parameter_operations")
        states, _ = p.resolve("company@1", self.catalog)
        with self.assertRaisesRegex(p.ParameterResolutionError, "unresolved"):
            p.complete(states)
        self.assertFalse(p.declarations(self.root)["age"]["bound"])

    def test_binding_and_tailoring_fan_out_without_consumer_edits(self):
        checks = [{"instance_id": "check", "implementation": "test.check", "parameters": {}}]
        first, records = p.consume_links(self.links, checks, self.states(), self.controls)
        original = copy.deepcopy(self.links)
        self.tailor()
        second, second_records = p.consume_links(
            self.links, checks, self.states("enclave@1"), self.controls
        )
        self.assertEqual(self.links, original)
        self.assertEqual(first[0]["parameters"]["age"], "2592000s")
        self.assertEqual(second[0]["parameters"]["age"], "1296000s")
        self.assertEqual(second[0]["evidence"]["observation"], {
            "inputs": {"period": "1296000s"}, "max_age": "1296000s",
        })
        self.assertEqual(records, second_records)
        self.assertNotIn("value", records[0])

    def test_stale_pins_parent_fingerprint_and_expectation_fail(self):
        child = self.tailor()
        mutations = (
            lambda item: item["spec"]["extends"].update(digest="sha256:" + "0" * 64),
            lambda item: item["spec"]["parameter_operations"][0].update(
                expected_parent_fingerprint="sha256:" + "0" * 64),
            lambda item: item["spec"]["parameter_operations"][0].update(**{"from": "29d"}),
            lambda item: item["spec"]["parameter_operations"][0].pop("deviation"),
        )
        for mutate in mutations:
            changed = copy.deepcopy(child)
            mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(p.ParameterResolutionError):
                p.resolve("enclave@1", {**self.catalog, "enclave@1": changed})

    def test_independent_ancestor_and_descendant_applicability_conflicts(self):
        self.tailor()
        selected = [self.resolution("company@1", "company"),
                    self.resolution("enclave@1", "enclave")]
        with self.assertRaisesRegex(p.ParameterResolutionError, "conflict"):
            p.compose_selected(selected, self.catalog)

    def test_additive_union_is_canonical_and_completely_attributed(self):
        catalog, resolutions = self.additive()
        p.compose_selected(resolutions, catalog)
        state = p.effective_states(resolutions)["software@1"]["allowed"]
        self.assertEqual(state["value"], ["base", "postgresql", "shared"])
        contribution, = state["composition"]["contributions"]
        self.assertEqual(contribution["identity"], {
            "policy": "database@1", "id": "packages",
            "target_policy": "software", "slot": "allowed",
        })
        self.assertEqual(contribution["members"], ["postgresql", "shared"])
        shared = next(item for item in state["composition"]["member_origins"]
                      if item["member"] == "shared")
        self.assertEqual({origin["kind"] for origin in shared["origins"]},
                         {"base", "contribution"})

    def test_contribution_does_not_activate_owner_and_order_is_nonsemantic(self):
        catalog, resolutions = self.additive()
        with self.assertRaisesRegex(p.ParameterResolutionError, "no applicable"):
            p.compose_selected([resolutions[1]], catalog)
        first, second = copy.deepcopy(resolutions), list(reversed(copy.deepcopy(resolutions)))
        p.compose_selected(first, catalog)
        p.compose_selected(second, catalog)
        self.assertEqual(p.effective_states(first), p.effective_states(second))

    def test_duration_has_no_expression_semantics(self):
        for value in ("1d", "24h", "1440m", "86400s"):
            self.assertEqual(p.duration(value), "86400s")
        for value in ("1.5h", "P1D", "0s", 3600, True, "${AGE}", "30d / 2"):
            with self.subTest(value=value), self.assertRaises(p.ParameterResolutionError):
                p.duration(value)

    def test_destination_and_source_links_are_exact(self):
        checks = [{"instance_id": "check", "implementation": "test.check", "parameters": {}}]
        mutations = (
            lambda links: links[0]["source"].update(digest="sha256:" + "0" * 64),
            lambda links: links[0]["destination"].update(path="/missing"),
            lambda links: links.append(copy.deepcopy(links[0])),
        )
        for mutate in mutations:
            links = copy.deepcopy(self.links[:1])
            mutate(links)
            with self.subTest(mutate=mutate), self.assertRaises((p.ParameterResolutionError, KeyError)):
                p.consume_links(links, checks, self.states(), self.controls)


if __name__ == "__main__":
    unittest.main()
