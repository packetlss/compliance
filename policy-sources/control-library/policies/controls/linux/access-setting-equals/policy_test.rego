package compliance.controls.linux.access_setting_equals_test

import data.compliance.controls.linux.access_setting_equals
import rego.v1

assessment_input(observed) := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "host/test"},
	"control": {
		"instance_id": "test.setting",
		"implementation": "linux.access.setting_equals",
		"severity": "high",
		"remediation": "Fix it",
		"parameters": {"section": "ssh", "setting": "allowed_groups", "expected": ["operators"]},
	},
	"evidence": [{
		"id": "evidence-1",
		"type": "linux.access.configuration/v1",
		"payload": {"ssh": {"allowed_groups": observed}},
	}],
}

test_pass if access_setting_equals.evaluate.status == "pass" with input as assessment_input(["operators"])

test_fail if access_setting_equals.evaluate.status == "fail" with input as assessment_input(["local-operators"])

test_missing if {
	actual := access_setting_equals.evaluate with input as object.union(assessment_input(["operators"]), {"evidence": []})
	actual.status == "unknown"
}

test_inconclusive if access_setting_equals.evaluate.status == "unknown" with input as assessment_input(null)
