package compliance.controls.linux.packages_required_test

import data.compliance.controls.linux.packages_required
import rego.v1

base_input := {
	"subject": {"id": "host/demo", "type": "linux-host"},
	"assessment": {"plan_id": "sha256:plan", "policy_revision": "sha256:policy"},
	"control": {
		"instance_id": "linux.packages.demo",
		"implementation": "linux.packages.required",
		"parameters": {
			"ecosystem": "linux-native",
			"required": [{"id": "curl"}, {"id": "git"}],
		},
		"severity": "medium",
		"remediation": "Install missing packages",
	},
}

test_pass if {
	actual := packages_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.packages/v1",
			"id": "evidence:packages",
			"payload": {
				"ecosystem": "linux-native",
				"packages": [{"id": "git"}, {"id": "curl"}],
			},
		}],
	})
	actual.status == "pass"
}

test_fail if {
	actual := packages_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.packages/v1",
			"id": "evidence:packages",
			"payload": {
				"ecosystem": "linux-native",
				"packages": [{"id": "curl"}],
			},
		}],
	})
	actual.status == "fail"
	actual.observed.missing == ["git"]
}

test_unknown if {
	actual := packages_required.evaluate with input as object.union(base_input, {"evidence": []})
	actual.status == "unknown"
}
