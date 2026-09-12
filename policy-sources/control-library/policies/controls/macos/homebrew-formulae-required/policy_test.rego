package compliance.controls.macos.homebrew_formulae_required_test

import data.compliance.controls.macos.homebrew_formulae_required
import rego.v1

test_reports_missing_formula if {
	actual := homebrew_formulae_required.evaluate with input as {
		"assessment": {"plan_id": "plan"},
		"subject": {"id": "workstation/test"},
		"control": {
			"instance_id": "test.packages",
			"implementation": "macos.homebrew.formulae-required",
			"severity": "medium",
			"remediation": "Install it",
			"parameters": {"required": ["git", "shellcheck"]},
		},
		"evidence": [{
			"id": "evidence-1",
			"type": "macos.homebrew/v1",
			"payload": {"formulae": [{"name": "git", "version": "1.0"}]},
		}],
	}

	actual.status == "fail"
	actual.observed.missing == ["shellcheck"]
}

test_reports_unknown_without_evidence if {
	actual := homebrew_formulae_required.evaluate with input as {
		"assessment": {"plan_id": "plan"},
		"subject": {"id": "workstation/test"},
		"control": {
			"instance_id": "test.packages",
			"implementation": "macos.homebrew.formulae-required",
			"severity": "medium",
			"remediation": "Install it",
			"parameters": {"required": ["git"]},
		},
		"evidence": [],
	}

	actual.status == "unknown"
}
