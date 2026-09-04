package compliance.controls.aws.s3_account_public_access_block_required_test

import data.compliance.controls.aws.s3_account_public_access_block_required
import rego.v1

desired := {
	"block_public_acls": true,
	"block_public_policy": true,
	"ignore_public_acls": true,
	"restrict_public_buckets": true,
}

base_input := {
	"subject": {"id": "cloud-account/aws-111122223333", "type": "aws-account"},
	"assessment": {"plan_id": "sha256:plan", "policy_revision": "sha256:policy"},
	"control": {
		"instance_id": "company.aws.s3-account-public-access-block",
		"implementation": "aws.s3.account_public_access_block_required",
		"parameters": desired,
		"severity": "high",
		"remediation": "Enable all S3 account public-access blocks",
	},
}

test_pass if {
	actual := s3_account_public_access_block_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "aws.s3.account-public-access-block/v1",
			"id": "evidence:s3-public-access",
			"payload": desired,
		}],
	})
	actual.status == "pass"
}

test_fail_reports_mismatched_setting if {
	actual := s3_account_public_access_block_required.evaluate with input as object.union(base_input, {
		"evidence": [{
			"type": "aws.s3.account-public-access-block/v1",
			"id": "evidence:s3-public-access",
			"payload": object.union(desired, {"block_public_policy": false}),
		}],
	})
	actual.status == "fail"
	contains(actual.reason, "block_public_policy")
}

test_unknown_without_evidence if {
	actual := s3_account_public_access_block_required.evaluate with input as object.union(base_input, {"evidence": []})
	actual.status == "unknown"
}
