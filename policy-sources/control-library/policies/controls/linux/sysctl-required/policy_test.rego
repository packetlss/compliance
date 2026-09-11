package compliance.controls.linux.sysctl_required_test

import data.compliance.controls.linux.sysctl_required
import rego.v1

base_input := {
	"subject": {"id": "host/demo", "type": "linux-host"},
	"assessment": {"plan_id": "sha256:plan"},
	"control": {
		"instance_id": "linux.sysctl.demo",
		"implementation": "linux.sysctl.required",
		"parameters": {
			"settings": {
				"kernel.randomize_va_space": "2",
				"net.ipv4.ip_forward": "0",
			},
		},
		"severity": "high",
		"remediation": "Set the required kernel parameters",
	},
}

test_pass if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.sysctl/v1",
			"id": "evidence:sysctl",
			"payload": {"settings": [
				{"key": "net.ipv4.ip_forward", "value": "0"},
				{"key": "kernel.randomize_va_space", "value": "2"},
			]},
		}],
	})
	actual.status == "pass"
	actual.expected.settings == {
		"kernel.randomize_va_space": "2",
		"net.ipv4.ip_forward": "0",
	}
}

test_equal_duplicate_observations_coalesce if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.sysctl/v1",
			"id": "evidence:sysctl",
			"payload": {"settings": [
				{"key": "kernel.randomize_va_space", "value": "2"},
				{"key": "kernel.randomize_va_space", "value": "2"},
				{"key": "net.ipv4.ip_forward", "value": "0"},
			]},
		}],
	})
	actual.status == "pass"
	actual.observed.settings == {
		"kernel.randomize_va_space": "2",
		"net.ipv4.ip_forward": "0",
	}
}

test_divergent_duplicate_observations_are_unknown if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.sysctl/v1",
			"id": "evidence:sysctl",
			"payload": {"settings": [
				{"key": "kernel.randomize_va_space", "value": "2"},
				{"key": "net.ipv4.ip_forward", "value": "0"},
				{"key": "net.ipv4.ip_forward", "value": "1"},
			]},
		}],
	})
	actual.status == "unknown"
	actual.observed.conflicting == ["net.ipv4.ip_forward"]
	actual.observed.settings == {"kernel.randomize_va_space": "2"}
}

test_fail_reports_missing_and_mismatched if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.sysctl/v1",
			"id": "evidence:sysctl",
			"payload": {"settings": [
				{"key": "net.ipv4.ip_forward", "value": "1"},
			]},
		}],
	})
	actual.status == "fail"
	actual.observed.missing == ["kernel.randomize_va_space"]
	actual.observed.mismatched == ["net.ipv4.ip_forward"]
}

test_missing_required_key_is_fail if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.sysctl/v1",
			"id": "evidence:sysctl",
			"payload": {"settings": [
				{"key": "net.ipv4.ip_forward", "value": "0"},
			]},
		}],
	})
	actual.status == "fail"
	actual.observed.missing == ["kernel.randomize_va_space"]
	actual.observed.mismatched == []
}

test_mismatched_required_value_is_fail if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "linux.sysctl/v1",
			"id": "evidence:sysctl",
			"payload": {"settings": [
				{"key": "kernel.randomize_va_space", "value": "2"},
				{"key": "net.ipv4.ip_forward", "value": "1"},
			]},
		}],
	})
	actual.status == "fail"
	actual.observed.missing == []
	actual.observed.mismatched == ["net.ipv4.ip_forward"]
}

test_unknown_without_evidence if {
	actual := sysctl_required.evaluate with input as object.union(base_input, {"evidence": []})
	actual.status == "unknown"
}
