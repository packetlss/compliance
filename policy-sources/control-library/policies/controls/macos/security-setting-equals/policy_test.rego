package compliance.controls.macos.security_setting_equals_test

import data.compliance.controls.macos.security_setting_equals
import rego.v1

test_setting_matches if {
	actual := security_setting_equals.evaluate with input as {
		"assessment": {"plan_id": "plan"},
		"subject": {"id": "workstation/test"},
		"control": {
			"instance_id": "test.gatekeeper",
			"implementation": "macos.security.setting_equals",
			"severity": "high",
			"remediation": "Enable it",
			"parameters": {"setting": "gatekeeper", "expected": "enabled"},
		},
		"evidence": [{
			"id": "evidence-1",
			"type": "macos.security/v1",
			"payload": {"gatekeeper": {"status": "enabled"}},
		}],
	}

	actual.status == "pass"
}
