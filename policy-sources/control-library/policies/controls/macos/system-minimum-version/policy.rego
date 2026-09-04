package compliance.controls.macos.system_minimum_version

import data.compliance.lib.result
import rego.v1

system_evidence := [doc |
	some doc in input.evidence
	doc.type == "macos.system/v1"
]

minimum := input.control.parameters.minimum
observed := system_evidence[0].payload.product_version if count(system_evidence) > 0

versions_are_valid if {
	semver.is_valid(minimum)
	semver.is_valid(observed)
}

outcome := {
	"status": "unknown",
	"reason": "No fresh macos.system/v1 evidence is available",
	"expected": {"minimum_version": minimum},
	"observed": {},
} if {
	count(system_evidence) == 0
}

else := {
	"status": "error",
	"reason": "The expected or observed macOS version is not valid semantic version syntax",
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
} if {
	not versions_are_valid
}

else := {
	"status": "fail",
	"reason": sprintf("macOS %s is older than required version %s", [observed, minimum]),
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
} if {
	semver.compare(observed, minimum) < 0
}

else := {
	"status": "pass",
	"reason": sprintf("macOS %s meets minimum version %s", [observed, minimum]),
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
}

evaluate := result.make(input, outcome)
