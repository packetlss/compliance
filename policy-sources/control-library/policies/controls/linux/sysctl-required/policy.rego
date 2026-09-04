package compliance.controls.linux.sysctl_required

import data.compliance.lib.result
import rego.v1

sysctl_evidence := [doc |
	some doc in input.evidence
	doc.type == "linux.sysctl/v1"
]

observed_settings := {setting.key: setting.value |
	some doc in sysctl_evidence
	some setting in doc.payload.settings
}

required_settings := {setting.key: setting.value |
	some setting in input.control.parameters.settings
}

missing := sort([key |
	some key, _ in required_settings
	not observed_settings[key]
])

mismatched := sort([key |
	some key, expected in required_settings
	observed_settings[key]
	observed_settings[key] != expected
])

has_differences if count(missing) > 0

has_differences if count(mismatched) > 0

outcome := {
	"status": "unknown",
	"reason": "No fresh linux.sysctl/v1 evidence is available",
	"expected": {"settings": required_settings},
	"observed": {},
} if {
	count(sysctl_evidence) == 0
}

else := {
	"status": "fail",
	"reason": sprintf("Required kernel parameters differ; missing: %s; mismatched: %s", [concat(", ", missing), concat(", ", mismatched)]),
	"expected": {"settings": required_settings},
	"observed": {
		"settings": observed_settings,
		"missing": missing,
		"mismatched": mismatched,
	},
} if {
	has_differences
}

else := {
	"status": "pass",
	"reason": "All required kernel parameters have their expected values",
	"expected": {"settings": required_settings},
	"observed": {
		"settings": observed_settings,
		"missing": [],
		"mismatched": [],
	},
}

evaluate := result.make(input, outcome)
