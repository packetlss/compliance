package compliance.controls.organization_risk_assessment_current

import data.compliance.lib.result
import rego.v1

documents := [doc | some doc in input.evidence; doc.type == "organization.risk-assessment/v1"]
expected := [dependency.inputs | some dependency in input.control.evidence; dependency.id == "risk_assessment"][0]

matches_governed_scope(assessment) if {
	assessment.programme_id == expected.programme_id
	assessment.scope_id == expected.scope_id
}

completed_is_current(assessment) if {
	assessment.completion_status == "completed"
	completed_at := time.parse_rfc3339_ns(assessment.completed_at)
	evaluated_at := time.parse_rfc3339_ns(input.assessment.evaluated_at)
	completed_at <= evaluated_at
	evaluated_at - completed_at <= expected.maximum_assessment_age_seconds * 1000000000
}

completed_is_not_future(assessment) if {
	time.parse_rfc3339_ns(assessment.completed_at) <= time.parse_rfc3339_ns(input.assessment.evaluated_at)
}

qualifies if {
	count(documents) == 1
	matches_governed_scope(documents[0].payload)
}

default status := "unknown"

status := "fail" if {
	qualifies
	documents[0].payload.completion_status == "not_completed"
}

status := "fail" if {
	qualifies
	documents[0].payload.completion_status == "completed"
	completed_is_not_future(documents[0].payload)
	not completed_is_current(documents[0].payload)
}

status := "pass" if {
	qualifies
	completed_is_current(documents[0].payload)
}

evaluate := result.make(input, {
	"status": status,
	"reason": "Assess the supplied periodic risk-assessment occurrence and currentness for the exact governed programme and scope.",
	"expected": expected,
	"observed": {"assessments": [doc.payload | some doc in documents], "qualifies": qualifies_value},
})

default qualifies_value := false

qualifies_value if qualifies
