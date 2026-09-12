package compliance.controls.linux.packages_only_allowed_test

import data.compliance.controls.linux.packages_only_allowed
import rego.v1

base_input := {
	"subject": {"id": "host/demo", "type": "linux-host"},
	"assessment": {"plan_id": "sha256:plan"},
	"control": {
		"instance_id": "linux.packages.demo",
		"implementation": "linux.packages.only_allowed",
		"parameters": {"ecosystem": "linux-native", "allowed": ["git", "curl"]},
		"severity": "medium",
		"remediation": "Remove unexpected packages",
	},
}

observation(packages) := [{
	"type": "linux.packages/v1",
	"id": "evidence:packages",
	"payload": {"ecosystem": "linux-native", "packages": packages},
}]

test_strict_subset_pass if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([{"id": "curl"}])})
	actual.status == "pass"
	actual.expected.allowed == ["curl", "git"]
	actual.observed == {"installed": ["curl"], "unexpected": []}
}

test_equal_pass if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([{"id": "git"}, {"id": "curl"}])})
	actual.status == "pass"
	actual.observed.installed == ["curl", "git"]
}

test_unexpected_fail if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([{"id": "telnet"}, {"id": "curl"}])})
	actual.status == "fail"
	actual.observed == {"installed": ["curl", "telnet"], "unexpected": ["telnet"]}
	actual.reason == "Unexpected Linux packages are installed: telnet"
}

test_empty_allowed_fail if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([{"id": "curl"}])}) with input.control.parameters.allowed as []
	actual.status == "fail"
	actual.expected.allowed == []
	actual.observed.unexpected == ["curl"]
}

test_empty_installed_pass if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([])}) with input.control.parameters.allowed as []
	actual.status == "pass"
}

test_no_evidence_unknown if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": []})
	actual.status == "unknown"
	actual.observed == {}
}

test_wrong_ecosystem_unknown if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": [{"type": "linux.packages/v1", "payload": {"ecosystem": "other", "packages": []}}]})
	actual.status == "unknown"
}

test_wrong_type_unknown if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": [{"type": "other/v1", "payload": {"ecosystem": "linux-native", "packages": []}}]})
	actual.status == "unknown"
}

test_versions_do_not_affect_authorization if {
	every version in ["1.0", "99.2"] {
		actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([{"id": "curl", "version": version}])})
		actual.status == "pass"
	}
}

test_exact_ids_and_deterministic_details if {
	actual := packages_only_allowed.evaluate with input as object.union(base_input, {"evidence": observation([{"id": "telnet"}, {"id": "Git"}, {"id": "curl"}])})
	actual.status == "fail"
	actual.observed.installed == ["Git", "curl", "telnet"]
	actual.observed.unexpected == ["Git", "telnet"]
	actual.expected.allowed == ["curl", "git"]
}
