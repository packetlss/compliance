package compliance.controls.aws.account_number_at_least

import data.compliance.lib.result
import rego.v1

configuration := [doc |
	some doc in input.evidence
	doc.type == "aws.account.configuration/v1"
]

section := input.control.parameters.section
setting := input.control.parameters.setting
minimum := input.control.parameters.minimum

observed := object.get(object.get(configuration[0].payload, section, {}), setting, null) if count(configuration) > 0

outcome := {
	"status": "unknown",
	"reason": "No fresh aws.account.configuration/v1 evidence is available",
	"expected": {section: {setting: {"minimum": minimum}}},
	"observed": {},
} if {
	count(configuration) == 0
}

else := {
	"status": "unknown",
	"reason": sprintf("The AWS collector could not determine %s.%s", [section, setting]),
	"expected": {section: {setting: {"minimum": minimum}}},
	"observed": {section: {setting: observed}},
} if {
	not is_number(observed)
}

else := {
	"status": "fail",
	"reason": sprintf("AWS setting %s.%s is %v; minimum is %v", [section, setting, observed, minimum]),
	"expected": {section: {setting: {"minimum": minimum}}},
	"observed": {section: {setting: observed}},
} if {
	observed < minimum
}

else := {
	"status": "pass",
	"reason": sprintf("AWS setting %s.%s is %v, meeting minimum %v", [section, setting, observed, minimum]),
	"expected": {section: {setting: {"minimum": minimum}}},
	"observed": {section: {setting: observed}},
}

evaluate := result.make(input, outcome)
