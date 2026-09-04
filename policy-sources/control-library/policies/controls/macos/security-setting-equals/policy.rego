package compliance.controls.macos.security_setting_equals

import data.compliance.lib.result
import rego.v1

security_evidence := [doc |
	some doc in input.evidence
	doc.type == "macos.security/v1"
]

setting := input.control.parameters.setting
expected := input.control.parameters.expected

observed := object.get(object.get(security_evidence[0].payload, setting, {}), "status", "unknown") if count(security_evidence) > 0

outcome := {
	"status": "unknown",
	"reason": "No fresh macos.security/v1 evidence is available",
	"expected": {setting: expected},
	"observed": {},
} if {
	count(security_evidence) == 0
}

else := {
	"status": "unknown",
	"reason": sprintf("The collector could not determine macOS setting %s", [setting]),
	"expected": {setting: expected},
	"observed": {setting: observed},
} if {
	observed == "unknown"
}

else := {
	"status": "fail",
	"reason": sprintf("macOS setting %s is %s; expected %s", [setting, observed, expected]),
	"expected": {setting: expected},
	"observed": {setting: observed},
} if {
	observed != expected
}

else := {
	"status": "pass",
	"reason": sprintf("macOS setting %s is %s", [setting, expected]),
	"expected": {setting: expected},
	"observed": {setting: observed},
}

evaluate := result.make(input, outcome)
