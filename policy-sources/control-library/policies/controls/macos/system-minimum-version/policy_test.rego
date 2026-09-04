package compliance.controls.macos.system_minimum_version_test

import data.compliance.controls.macos.system_minimum_version
import rego.v1

test_supported_version if {
	actual := system_minimum_version.evaluate with input as {
		"assessment": {"plan_id": "plan", "policy_revision": "policy"},
		"subject": {"id": "workstation/test"},
		"control": {
			"instance_id": "test.version",
			"implementation": "macos.system.minimum_version",
			"severity": "high",
			"remediation": "Upgrade",
			"parameters": {"minimum": "15.0.0"},
		},
		"evidence": [{
			"id": "evidence-1",
			"type": "macos.system/v1",
			"payload": {"product_version": "15.4.1"},
		}],
	}

	actual.status == "pass"
}
