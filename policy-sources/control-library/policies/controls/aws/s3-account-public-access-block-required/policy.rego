package compliance.controls.aws.s3_account_public_access_block_required

import data.compliance.lib.result
import rego.v1

setting_names := [
	"block_public_acls",
	"block_public_policy",
	"ignore_public_acls",
	"restrict_public_buckets",
]

public_access_evidence := [doc |
	some doc in input.evidence
	doc.type == "aws.s3.account-public-access-block/v1"
]

desired := {setting: input.control.parameters[setting] |
	some setting in setting_names
}

observed := {setting: object.get(public_access_evidence[0].payload, setting, null) |
	some setting in setting_names
}

missing := sort([setting |
	some setting in setting_names
	object.get(observed, setting, null) == null
])

mismatched := sort([setting |
	some setting in setting_names
	object.get(observed, setting, null) != null
	observed[setting] != desired[setting]
])

outcome := {
	"status": "unknown",
	"reason": "No fresh aws.s3.account-public-access-block/v1 evidence is available",
	"expected": desired,
	"observed": {},
} if {
	count(public_access_evidence) == 0
}

else := {
	"status": "unknown",
	"reason": sprintf("The AWS collector could not determine S3 Block Public Access settings: %s", [concat(", ", missing)]),
	"expected": desired,
	"observed": observed,
} if {
	count(missing) > 0
}

else := {
	"status": "fail",
	"reason": sprintf("Amazon S3 account-level Block Public Access settings differ: %s", [concat(", ", mismatched)]),
	"expected": desired,
	"observed": observed,
} if {
	count(mismatched) > 0
}

else := {
	"status": "pass",
	"reason": "Amazon S3 account-level Block Public Access settings match policy",
	"expected": desired,
	"observed": observed,
}

evaluate := result.make(input, outcome)
