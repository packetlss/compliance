package compliance.controls.aws.account_setting_equals_test

import data.compliance.controls.aws.account_setting_equals
import rego.v1

assessment_input(observed) := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "cloud-account/test"},
	"control": {
		"instance_id": "test.setting",
		"implementation": "aws.account.setting_equals",
		"severity": "high",
		"remediation": "Fix it",
		"parameters": {"section": "cloudtrail", "setting": "multi_region_enabled", "expected": true},
	},
	"evidence": [{
		"id": "evidence-1",
		"type": "aws.account.configuration/v1",
		"payload": {"cloudtrail": {"multi_region_enabled": observed}},
	}],
}

test_pass if account_setting_equals.evaluate.status == "pass" with input as assessment_input(true)

test_fail if account_setting_equals.evaluate.status == "fail" with input as assessment_input(false)

test_missing if {
	actual := account_setting_equals.evaluate with input as object.union(assessment_input(true), {"evidence": []})
	actual.status == "unknown"
}

test_inconclusive if account_setting_equals.evaluate.status == "unknown" with input as assessment_input(null)

test_missing_optional_security_contact_is_unknown if {
	actual := account_setting_equals.evaluate with input as {
		"assessment": {"plan_id": "plan"},
		"subject": {"id": "cloud-account/test"},
		"control": {
			"instance_id": "test.security-contact",
			"implementation": "aws.account.setting_equals",
			"severity": "high",
			"remediation": "Fix it",
			"parameters": {"section": "security_contact", "setting": "configured", "expected": true},
		},
		"evidence": [{
			"id": "evidence-1",
			"type": "aws.account.configuration/v1",
			"payload": {
				"account": {"id": "111122223333"},
				"root_user": {"mfa_enabled": true},
				"cloudtrail": {"multi_region_enabled": true, "retention_days": 90},
			},
		}],
	}
	actual.status == "unknown"
}
