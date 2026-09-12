package compliance.controls.saas.tenant_number_at_least_test

import data.compliance.controls.saas.tenant_number_at_least
import rego.v1

assessment_input(observed) := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "saas/test"},
	"control": {
		"instance_id": "test.minimum",
		"implementation": "saas.tenant.number-at-least",
		"severity": "medium",
		"remediation": "Fix it",
		"parameters": {"section": "audit_log", "setting": "retention_days", "minimum": 90},
	},
	"evidence": [{
		"id": "evidence-1",
		"type": "saas.tenant.configuration/v1",
		"payload": {"audit_log": {"retention_days": observed}},
	}],
}

test_pass if tenant_number_at_least.evaluate.status == "pass" with input as assessment_input(180)

test_fail if tenant_number_at_least.evaluate.status == "fail" with input as assessment_input(30)

test_missing if {
	actual := tenant_number_at_least.evaluate with input as object.union(assessment_input(180), {"evidence": []})
	actual.status == "unknown"
}

test_inconclusive if tenant_number_at_least.evaluate.status == "unknown" with input as assessment_input(null)
