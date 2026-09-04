package compliance.controls.linux.packages_required

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

required := {pkg.id |
	some pkg in input.control.parameters.required
}

missing := sort([package_id |
	some package_id in required
	not package_id in installed
])

outcome := {
	"status": "unknown",
	"reason": "No fresh linux.packages/v1 evidence is available for the required ecosystem",
	"expected": {"ecosystem": input.control.parameters.ecosystem, "packages": sort([id | some id in required])},
	"observed": {},
} if {
	count(package_evidence) == 0
}

else := {
	"status": "fail",
	"reason": sprintf("Required Linux packages are missing: %s", [concat(", ", missing)]),
	"expected": {"ecosystem": input.control.parameters.ecosystem, "packages": sort([id | some id in required])},
	"observed": {"missing": missing},
} if {
	count(missing) > 0
}

else := {
	"status": "pass",
	"reason": "All required Linux packages are installed",
	"expected": {"ecosystem": input.control.parameters.ecosystem, "packages": sort([id | some id in required])},
	"observed": {"missing": []},
}

evaluate := result.make(input, outcome)
