package compliance.controls.linux.packages_only_allowed

import data.compliance.lib.result
import rego.v1

package_evidence := [doc |
	some doc in input.evidence
	doc.type == "linux.packages/v1"
	doc.payload.ecosystem == input.control.parameters.ecosystem
]

installed := {pkg.id |
	some doc in package_evidence
	some pkg in doc.payload.packages
}

allowed := {id | some id in input.control.parameters.allowed}
unexpected := sort(installed - allowed)
expected := {"ecosystem": input.control.parameters.ecosystem, "allowed": sort(allowed)}

outcome := {
	"status": "unknown",
	"reason": "No fresh linux.packages/v1 evidence is available for the required ecosystem",
	"expected": expected,
	"observed": {},
} if {
	count(package_evidence) == 0
} else := {
	"status": "fail",
	"reason": sprintf("Unexpected Linux packages are installed: %s", [concat(", ", unexpected)]),
	"expected": expected,
	"observed": {"installed": sort(installed), "unexpected": unexpected},
} if {
	count(unexpected) > 0
} else := {
	"status": "pass",
	"reason": "All installed Linux package IDs are authorized",
	"expected": expected,
	"observed": {"installed": sort(installed), "unexpected": []},
}

evaluate := result.make(input, outcome)
