package compliance.controls.linux.sysctl_required

import data.compliance.lib.result
import rego.v1

sysctl_evidence := [doc |
	some doc in input.evidence
	doc.type == "linux.sysctl/v1"
]

observed_keys := {setting.key |
	some doc in sysctl_evidence
	some setting in doc.payload.settings
}

observed_values := {key: values |
	some key in observed_keys
	values := {setting.value |
		some doc in sysctl_evidence
		some setting in doc.payload.settings
		setting.key == key
	}
}

observed_settings := {key: value |
	some key in observed_keys
	values := observed_values[key]
	count(values) == 1
	some value in values
}

conflicting := sort([key |
	some key in observed_keys
	count(observed_values[key]) > 1
])

required_settings := input.control.parameters.settings

has_conflicts if {
	count(conflicting) > 0
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
	"status": "unknown",
	"reason": sprintf("Selected linux.sysctl/v1 evidence contains conflicting values for: %s", [concat(", ", conflicting)]),
	"expected": {"settings": required_settings},
	"observed": {
		"settings": observed_settings,
		"conflicting": conflicting,
	},
} if {
	has_conflicts
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
