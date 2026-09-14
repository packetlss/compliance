package compliance.controls.iam_integration_required_test

import data.compliance.controls.iam_integration_required as criterion
import rego.v1

case(service, integrated) := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "application/A"},
	"control": {
		"instance_id": "required-service", "implementation": "iam.integration.required",
		"severity": "high", "remediation": "Obtain evidence",
		"evidence": [{"id": "relationship", "inputs": {"service": "service/S"}}],
	},
	"evidence": [
		{"id": "relationship", "type": "iam.integration.observation/v1", "payload": {"service": service, "integrated": integrated}},
	],
}

test_positive if criterion.evaluate.status == "pass" with input as case("service/S", true)
test_negative if criterion.evaluate.status == "fail" with input as case("service/S", false)
test_inconclusive if criterion.evaluate.status == "unknown" with input as case("service/S", null)
test_wrong_service if criterion.evaluate.status == "unknown" with input as case("service/other", true)

test_missing_relationship if {
	original := case("service/S", true)
	criterion.evaluate.status == "unknown" with input as object.union(original, {"evidence": []})
}
