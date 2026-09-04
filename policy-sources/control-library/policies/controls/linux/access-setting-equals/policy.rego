package compliance.controls.linux.access_setting_equals

import data.compliance.lib.result
import rego.v1

configuration := [doc |
	some doc in input.evidence
	doc.type == "linux.access.configuration/v1"
]

section := input.control.parameters.section
setting := input.control.parameters.setting
expected := input.control.parameters.expected

observed := object.get(object.get(configuration[0].payload, section, {}), setting, null) if count(configuration) > 0

outcome := {
	"status": "unknown",
	"reason": "No fresh linux.access.configuration/v1 evidence is available",
	"expected": {section: {setting: expected}},
	"observed": {},
} if {
	count(configuration) == 0
}

else := {
	"status": "unknown",
	"reason": sprintf("The Linux collector could not determine %s.%s", [section, setting]),
	"expected": {section: {setting: expected}},
	"observed": {section: {setting: observed}},
} if {
	observed == null
}

else := {
	"status": "fail",
	"reason": sprintf("Linux setting %s.%s is %v; expected %v", [section, setting, observed, expected]),
	"expected": {section: {setting: expected}},
	"observed": {section: {setting: observed}},
} if {
	observed != expected
}

else := {
	"status": "pass",
	"reason": sprintf("Linux setting %s.%s has the approved value", [section, setting]),
	"expected": {section: {setting: expected}},
	"observed": {section: {setting: observed}},
}

evaluate := result.make(input, outcome)
