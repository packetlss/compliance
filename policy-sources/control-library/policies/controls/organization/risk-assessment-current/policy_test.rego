package compliance.controls.organization_risk_assessment_current_test

import data.compliance.controls.organization_risk_assessment_current as criterion
import rego.v1

case(payload) := {
	"assessment": {"plan_id": "plan", "evaluated_at": "2026-09-01T00:00:00Z"},
	"subject": {"id": "entity/A"},
	"control": {"instance_id": "risk", "implementation": "organization.risk-assessment.current", "severity": "high", "remediation": "Obtain evidence", "evidence": [{"id": "risk_assessment", "inputs": {"programme_id": "annual-risk", "scope_id": "legal-entity", "maximum_assessment_age_seconds": 2592000}}]},
	"evidence": [{"id": "observation", "type": "organization.risk-assessment/v1", "payload": payload}],
}

payload(status, completed_at) := object.union({"programme_id": "annual-risk", "assessment_id": "risk-2026", "scope_id": "legal-entity", "assessor_id": "risk-register", "source_locator": "report:risk-2026", "completion_status": status}, {"completed_at": completed_at}) if status == "completed"
payload(status, _) := {"programme_id": "annual-risk", "assessment_id": "risk-2026", "scope_id": "legal-entity", "assessor_id": "risk-register", "source_locator": "report:risk-2026", "completion_status": status} if status != "completed"

test_completed_current if criterion.evaluate.status == "pass" with input as case(payload("completed", "2026-08-15T00:00:00Z"))
test_not_completed if criterion.evaluate.status == "fail" with input as case(payload("not_completed", ""))
test_old_completed if criterion.evaluate.status == "fail" with input as case(payload("completed", "2026-07-01T00:00:00Z"))
test_inconclusive if criterion.evaluate.status == "unknown" with input as case(payload("inconclusive", ""))
test_future_completed if criterion.evaluate.status == "unknown" with input as case(payload("completed", "2026-09-02T00:00:00Z"))
test_wrong_scope if criterion.evaluate.status == "unknown" with input as case(object.union(payload("completed", "2026-08-15T00:00:00Z"), {"scope_id": "other"}))
