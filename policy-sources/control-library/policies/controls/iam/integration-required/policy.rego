package compliance.controls.iam_integration_required

import data.compliance.lib.result
import rego.v1

sources := [doc | some doc in input.evidence; doc.type == "iam.service.observation/v1"]
relationships := [doc | some doc in input.evidence; doc.type == "iam.integration.observation/v1"]
required_service := [dependency.inputs | some dependency in input.control.evidence; dependency.id == "service"][0]

qualifies if {
	count(sources) == 1
	count(relationships) == 1
	sources[0].payload.consumer == input.subject.id
	assertion := sources[0].payload.source_assertion
	assertion.subject_id == required_service.service
	assertion.condition == required_service.condition
	relationship := relationships[0].payload
	relationship.consumer == input.subject.id
	relationship.service == assertion.subject_id
	relationship.source_assertion_locator == assertion.source_locator
}

default status := "unknown"

status := "fail" if {
	qualifies
	sources[0].payload.source_assertion.outcome == "negative"
}

status := "fail" if {
	qualifies
	relationships[0].payload.integrated == false
}

status := "pass" if {
	qualifies
	sources[0].payload.source_assertion.outcome == "positive"
	relationships[0].payload.integrated == true
}

default qualifies_value := false

qualifies_value if qualifies

evaluate := result.make(input, {
	"status": status,
	"reason": "Assess the named service condition and independently observed consumer relationship.",
	"expected": {"consumer": input.subject.id, "service": required_service.service, "condition": required_service.condition},
	"observed": {
		"source_observations": [doc.payload | some doc in sources],
		"relationships": [doc.payload | some doc in relationships],
		"qualifies": qualifies_value,
	},
})
