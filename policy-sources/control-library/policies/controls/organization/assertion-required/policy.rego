package compliance.controls.organization_assertion_required

import data.compliance.lib.result
import rego.v1

documents := [doc | some doc in input.evidence; doc.type == "organization.assertion/v1"]
required_scheme := [dependency.inputs.scheme | some dependency in input.control.evidence; dependency.id == "assertion"][0]

qualifies if {
	count(documents) == 1
	assertion := documents[0].payload
	assertion.beneficiary == input.subject.id
	assertion.scheme == required_scheme
	instant := time.parse_rfc3339_ns(input.assessment.evaluated_at)
	time.parse_rfc3339_ns(assertion.valid_from) <= instant
	instant <= time.parse_rfc3339_ns(assertion.valid_until)
}

default status := "unknown"

status := "fail" if {
	qualifies
	documents[0].payload.outcome == "negative"
}

status := "pass" if {
	qualifies
	documents[0].payload.outcome == "positive"
}

evaluate := result.make(input, {
	"status": status,
	"reason": "Assess the attributable assertion against the exact company requirement; no external conformity conclusion.",
	"expected": {"beneficiary": input.subject.id, "scheme": required_scheme, "outcome": "positive"},
	"observed": {"assertions": [doc.payload | some doc in documents], "qualifies": qualifies_value},
})

default qualifies_value := false

qualifies_value if qualifies
