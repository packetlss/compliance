package compliance.controls.organization_assertion_required_test

import data.compliance.controls.organization_assertion_required as criterion
import rego.v1

case(beneficiary, outcome) := {
	"assessment": {"plan_id": "plan", "evaluated_at": "2026-09-01T00:00:00Z"},
	"subject": {"id": "entity/A"},
	"control": {
		"instance_id": "required-assertion", "implementation": "organization.assertion.required",
		"severity": "high", "remediation": "Obtain evidence",
		"evidence": [{"id": "assertion", "inputs": {"scheme": "CE+"}}],
	},
	"evidence": [{"id": "observation", "type": "organization.assertion/v1", "payload": {
		"beneficiary": beneficiary, "scheme": "CE+", "outcome": outcome,
		"asserted_by": "synthetic-assessor", "source_locator": "report:synthetic#assertion",
		"valid_from": "2026-08-01T00:00:00Z", "valid_until": "2026-10-01T00:00:00Z",
	}}],
}

test_positive if criterion.evaluate.status == "pass" with input as case("entity/A", "positive")
test_negative if criterion.evaluate.status == "fail" with input as case("entity/A", "negative")
test_inconclusive if criterion.evaluate.status == "unknown" with input as case("entity/A", "inconclusive")
test_other_beneficiary if criterion.evaluate.status == "unknown" with input as case("entity/B", "positive")
test_missing if criterion.evaluate.status == "unknown" with input as object.union(case("entity/A", "positive"), {"evidence": []})
