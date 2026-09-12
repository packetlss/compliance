package compliance.controls.macos.system_minimum_version_test

import data.compliance.controls.macos.system_minimum_version
import rego.v1

base_input := {
	"assessment": {"plan_id": "plan"},
	"subject": {"id": "workstation/test"},
	"control": {
		"instance_id": "test.version",
		"implementation": "macos.system.minimum-version",
		"severity": "high",
		"remediation": "Upgrade",
		"parameters": {"minimum": "15.0.0"},
	},
}

input_with_version(observed, minimum) := object.union(base_input, {
	"control": object.union(base_input.control, {
		"parameters": {"minimum": minimum},
	}),
	"evidence": [{
		"id": "evidence-1",
		"type": "macos.system/v1",
		"payload": {"product_version": observed},
	}],
})

test_two_component_version_uses_zero_patch if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.0", "15.0.0")
	actual.status == "pass"
}

test_three_component_version_equal if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.0.0", "15.0.0")
	actual.status == "pass"
}

test_newer_two_component_version if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.1", "15.0.9")
	actual.status == "pass"
}

test_newer_three_component_version if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.0.1", "15.0.0")
	actual.status == "pass"
}

test_older_major_version if {
	actual := system_minimum_version.evaluate with input as input_with_version("14.7", "15.0.0")
	actual.status == "fail"
}

test_older_minor_version if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.8", "15.9.0")
	actual.status == "fail"
}

test_older_patch_version if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.9.6", "15.9.7")
	actual.status == "fail"
}

test_omitted_observed_patch_is_zero_when_older if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.0", "15.0.1")
	actual.status == "fail"
}

test_multi_digit_components_compare_numerically if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.10", "15.9.7")
	actual.status == "pass"
}

test_numeric_components_may_have_leading_zeroes if {
	actual := system_minimum_version.evaluate with input as input_with_version("015.000.001", "15.0.0")
	actual.status == "pass"
}

test_malformed_observed_version_is_unknown if {
	actual := system_minimum_version.evaluate with input as input_with_version("15.0-beta", "15.0.0")
	actual.status == "unknown"
	contains(actual.reason, "15.0-beta")
	actual.observed.product_version == "15.0-beta"
}

test_missing_evidence_is_unknown if {
	actual := system_minimum_version.evaluate with input as object.union(base_input, {
		"evidence": [],
	})
	actual.status == "unknown"
}
