package compliance.controls.iam_integration_required_test

import data.compliance.controls.iam_integration_required as criterion
import rego.v1

case(consumer, integrated, locator) := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "application/A"},
	"control": {
		"instance_id": "required-service", "implementation": "iam.integration.required",
		"severity": "high", "remediation": "Obtain evidence",
		"evidence": [{"id": "service", "inputs": {"service": "service/S", "condition": "Q"}}],
	},
	"evidence": [
		{"id": "source", "type": "iam.service.observation/v1", "payload": {"consumer": "application/A", "source_assertion": {
			"subject_id": "service/S", "asserted_by": "synthetic-reviewer", "source_locator": "report:S#Q", "condition": "Q", "outcome": "positive",
		}}},
		{"id": "relationship", "type": "iam.integration.observation/v1", "payload": {"consumer": consumer, "service": "service/S", "asserted_by": "synthetic-observer", "source_assertion_locator": locator, "integrated": integrated}},
	],
}

test_positive if criterion.evaluate.status == "pass" with input as case("application/A", true, "report:S#Q")
test_negative if criterion.evaluate.status == "fail" with input as case("application/A", false, "report:S#Q")
test_inconclusive if criterion.evaluate.status == "unknown" with input as case("application/A", null, "report:S#Q")
test_wrong_consumer if criterion.evaluate.status == "unknown" with input as case("application/B", true, "report:S#Q")
test_wrong_source_correlation if criterion.evaluate.status == "unknown" with input as case("application/A", true, "report:other#Q")

test_missing_relationship if {
	original := case("application/A", true, "report:S#Q")
	criterion.evaluate.status == "unknown" with input as object.union(original, {"evidence": [original.evidence[0]]})
}
