package compliance.controls.aws.account_number_at_least_test

import data.compliance.controls.aws.account_number_at_least
import rego.v1

assessment_input(observed) := {
	"assessment": {"plan_id": "plan", "policy_revision": "policy"},
	"subject": {"id": "cloud-account/test"},
	"control": {
		"instance_id": "test.minimum",
		"implementation": "aws.account.number_at_least",
		"severity": "medium",
		"remediation": "Fix it",
		"parameters": {"section": "cloudtrail", "setting": "retention_days", "minimum": 90},
	},
	"evidence": [{
		"id": "evidence-1",
		"type": "aws.account.configuration/v1",
		"payload": {"cloudtrail": {"retention_days": observed}},
	}],
}

test_pass if account_number_at_least.evaluate.status == "pass" with input as assessment_input(120)

test_fail if account_number_at_least.evaluate.status == "fail" with input as assessment_input(30)

test_missing if {
	actual := account_number_at_least.evaluate with input as object.union(assessment_input(120), {"evidence": []})
	actual.status == "unknown"
}

test_inconclusive if account_number_at_least.evaluate.status == "unknown" with input as assessment_input(null)
