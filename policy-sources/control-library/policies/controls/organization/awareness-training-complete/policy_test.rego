package compliance.controls.organization_awareness_training_complete_test

import data.compliance.controls.organization_awareness_training_complete as criterion
import rego.v1

case(payload) := {
	"assessment": {"plan_id": "plan", "evaluated_at": "2026-09-01T00:00:00Z"},
	"subject": {"id": "entity/A"},
	"control": {"instance_id": "training", "implementation": "organization.awareness-training.complete", "severity": "high", "remediation": "Obtain evidence", "evidence": [{"id": "training_report", "inputs": {"programme_id": "annual-awareness", "population_basis_id": "people-2026", "maximum_report_age_seconds": 2592000}}]},
	"evidence": [{"id": "observation", "type": "organization.awareness-training/v1", "payload": payload}],
}

payload(population, completion, as_of) := {"programme_id": "annual-awareness", "report_id": "training-2026", "campaign_id": "annual-2026", "as_of": as_of, "reporting_source_id": "training-register", "source_locator": "report:training-2026", "population": population, "completion": completion}
established_population(count) := {"basis_id": "people-2026", "status": "established", "required_count": count}
established_completion(count) := {"status": "established", "completed_count": count}

test_full_completion if criterion.evaluate.status == "pass" with input as case(payload(established_population(10), established_completion(10), "2026-08-15T00:00:00Z"))
test_incomplete if criterion.evaluate.status == "fail" with input as case(payload(established_population(10), established_completion(9), "2026-08-15T00:00:00Z"))
test_population_unknown if criterion.evaluate.status == "unknown" with input as case(payload({"basis_id": "people-2026", "status": "not_established"}, established_completion(9), "2026-08-15T00:00:00Z"))
test_completion_unknown if criterion.evaluate.status == "unknown" with input as case(payload(established_population(10), {"status": "not_established"}, "2026-08-15T00:00:00Z"))
test_zero_population if criterion.evaluate.status == "unknown" with input as case(payload(established_population(0), established_completion(0), "2026-08-15T00:00:00Z"))
test_inconsistent_counts if criterion.evaluate.status == "unknown" with input as case(payload(established_population(10), established_completion(11), "2026-08-15T00:00:00Z"))
test_future_report if criterion.evaluate.status == "unknown" with input as case(payload(established_population(10), established_completion(10), "2026-09-02T00:00:00Z"))
test_old_report if criterion.evaluate.status == "unknown" with input as case(payload(established_population(10), established_completion(10), "2026-07-01T00:00:00Z"))
test_wrong_basis if criterion.evaluate.status == "unknown" with input as case(payload({"basis_id": "other", "status": "established", "required_count": 10}, established_completion(10), "2026-08-15T00:00:00Z"))
