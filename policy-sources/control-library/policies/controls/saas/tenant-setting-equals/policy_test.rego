package compliance.controls.saas.tenant_setting_equals_test

import data.compliance.controls.saas.tenant_setting_equals
import rego.v1

assessment_input(observed) := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "saas/test"},
	"control": {
		"instance_id": "test.setting",
		"implementation": "saas.tenant.setting-equals",
		"severity": "high",
		"remediation": "Fix it",
		"parameters": {"section": "authentication", "setting": "sso_enforced", "expected": true},
	},
	"evidence": [{
		"id": "evidence-1",
		"type": "saas.tenant.configuration/v1",
		"payload": {"authentication": {"sso_enforced": observed}},
	}],
}

test_pass if tenant_setting_equals.evaluate.status == "pass" with input as assessment_input(true)

test_fail if tenant_setting_equals.evaluate.status == "fail" with input as assessment_input(false)

test_missing if {
	actual := tenant_setting_equals.evaluate with input as object.union(assessment_input(true), {"evidence": []})
	actual.status == "unknown"
}

test_inconclusive if tenant_setting_equals.evaluate.status == "unknown" with input as assessment_input(null)

test_missing_optional_guest_access_is_unknown if {
	actual := tenant_setting_equals.evaluate with input as {
		"assessment": {"plan_id": "plan"},
		"subject": {"id": "saas/test"},
		"control": {
			"instance_id": "test.guest-access",
			"implementation": "saas.tenant.setting-equals",
			"severity": "high",
			"remediation": "Fix it",
			"parameters": {"section": "guest_access", "setting": "allowed", "expected": false},
		},
		"evidence": [{
			"id": "evidence-1",
			"type": "saas.tenant.configuration/v1",
			"payload": {
				"tenant": {"id": "test", "provider": "example"},
				"authentication": {"sso_enforced": true, "mfa_enforced": true},
				"audit_log": {"retention_days": 180},
			},
		}],
	}
	actual.status == "unknown"
}
