package compliance.controls.macos.system_minimum_version

import data.compliance.lib.result
import rego.v1

system_evidence := [doc |
	some doc in input.evidence
	doc.type == "macos.system/v1"
]

minimum := input.control.parameters.minimum
observed := system_evidence[0].payload.product_version if count(system_evidence) > 0

macos_numeric_component(value) := 0 if {
	trim_left(value, "0") == ""
}

else := to_number(trim_left(value, "0"))

macos_policy_version(value) := [
	macos_numeric_component(parts[0]),
	macos_numeric_component(parts[1]),
	macos_numeric_component(parts[2]),
] if {
	regex.match(`^[0-9]+\.[0-9]+\.[0-9]+$`, value)
	parts := split(value, ".")
}

macos_observed_version(value) := [
	macos_numeric_component(parts[0]),
	macos_numeric_component(parts[1]),
	0,
] if {
	regex.match(`^[0-9]+\.[0-9]+$`, value)
	parts := split(value, ".")
}

macos_observed_version(value) := [
	macos_numeric_component(parts[0]),
	macos_numeric_component(parts[1]),
	macos_numeric_component(parts[2]),
] if {
	regex.match(`^[0-9]+\.[0-9]+\.[0-9]+$`, value)
	parts := split(value, ".")
}

minimum_components := macos_policy_version(minimum)
observed_components := macos_observed_version(observed) if count(system_evidence) > 0

minimum_is_valid if {
	_ := minimum_components
}

observed_is_valid if {
	_ := observed_components
}

observed_is_older if {
	observed_components[0] < minimum_components[0]
}

observed_is_older if {
	observed_components[0] == minimum_components[0]
	observed_components[1] < minimum_components[1]
}

observed_is_older if {
	observed_components[0] == minimum_components[0]
	observed_components[1] == minimum_components[1]
	observed_components[2] < minimum_components[2]
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
	"reason": "The minimum macOS version is not valid numeric major.minor.patch syntax",
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
} if {
	not minimum_is_valid
}

else := {
	"status": "unknown",
	"reason": sprintf("Observed macOS product version %q is not numeric major.minor or major.minor.patch syntax", [observed]),
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
} if {
	not observed_is_valid
}

else := {
	"status": "fail",
	"reason": sprintf("macOS %s is older than required version %s", [observed, minimum]),
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
} if {
	observed_is_older
}

else := {
	"status": "pass",
	"reason": sprintf("macOS %s meets minimum version %s", [observed, minimum]),
	"expected": {"minimum_version": minimum},
	"observed": {"product_version": observed},
}

evaluate := result.make(input, outcome)
