package compliance.controls.macos.homebrew_formulae_required

import data.compliance.lib.result
import rego.v1

homebrew_evidence := [doc |
	some doc in input.evidence
	doc.type == "macos.homebrew/v1"
]

installed := {pkg.name |
	some doc in homebrew_evidence
	some pkg in doc.payload.formulae
}

required := object.get(input.control.parameters, "required", [])

missing := sort([name |
	some name in required
	not name in installed
])

outcome := {
	"status": "unknown",
	"reason": "No fresh macos.homebrew/v1 evidence is available",
	"expected": {"formulae": required},
	"observed": {},
} if {
	count(homebrew_evidence) == 0
}

else := {
	"status": "fail",
	"reason": sprintf("Required Homebrew formulae are missing: %s", [concat(", ", missing)]),
	"expected": {"formulae": required},
	"observed": {"missing": missing},
} if {
	count(missing) > 0
}

else := {
	"status": "pass",
	"reason": "All required Homebrew formulae are installed",
	"expected": {"formulae": required},
	"observed": {"missing": []},
}

evaluate := result.make(input, outcome)
