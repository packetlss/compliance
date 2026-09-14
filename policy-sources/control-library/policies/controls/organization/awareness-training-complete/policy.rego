package compliance.controls.organization_awareness_training_complete

import data.compliance.lib.result
import rego.v1

documents := [doc | some doc in input.evidence; doc.type == "organization.awareness-training/v1"]
expected := [dependency.inputs | some dependency in input.control.evidence; dependency.id == "training_report"][0]

matches_programme_and_population(report) if {
	report.programme_id == expected.programme_id
	report.population.basis_id == expected.population_basis_id
}

report_is_current(report) if {
	as_of := time.parse_rfc3339_ns(report.as_of)
	evaluated_at := time.parse_rfc3339_ns(input.assessment.evaluated_at)
	as_of <= evaluated_at
	evaluated_at - as_of <= expected.maximum_report_age_seconds * 1000000000
}

counts_are_established(report) if {
	report.population.status == "established"
	report.completion.status == "established"
	report.population.required_count > 0
	report.completion.completed_count <= report.population.required_count
}

qualifies if {
	count(documents) == 1
	matches_programme_and_population(documents[0].payload)
	report_is_current(documents[0].payload)
	counts_are_established(documents[0].payload)
}

default status := "unknown"

status := "fail" if {
	qualifies
	documents[0].payload.completion.completed_count < documents[0].payload.population.required_count
}

status := "pass" if {
	qualifies
	documents[0].payload.completion.completed_count == documents[0].payload.population.required_count
}

evaluate := result.make(input, {
	"status": status,
	"reason": "Assess the supplied awareness-training report for the exact governed programme and required-population basis.",
	"expected": expected,
	"observed": {"reports": [doc.payload | some doc in documents], "qualifies": qualifies_value},
})

default qualifies_value := false

qualifies_value if qualifies
