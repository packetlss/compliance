package compliance.controls.iam_integration_required

import data.compliance.lib.result
import rego.v1

relationships := [doc | some doc in input.evidence; doc.type == "iam.integration.observation/v1"]
required_service := [dependency.inputs.service | some dependency in input.control.evidence; dependency.id == "relationship"][0]

qualifies if {
	count(relationships) == 1
	relationship := relationships[0].payload
	relationship.service == required_service
}

default status := "unknown"

status := "fail" if {
	qualifies
	relationships[0].payload.integrated == false
}

status := "pass" if {
	qualifies
	relationships[0].payload.integrated == true
}

default qualifies_value := false

qualifies_value if qualifies

evaluate := result.make(input, {
	"status": status,
	"reason": "Assess the observed consumer-to-service relationship against the service designated by governed policy.",
	"expected": {"service": required_service},
	"observed": {
		"relationships": [doc.payload | some doc in relationships],
		"qualifies": qualifies_value,
	},
})
