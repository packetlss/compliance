package compliance.lib.result

import rego.v1

make(assessment_input, outcome) := object.union(
	{
		"control_id": assessment_input.control.implementation,
		"instance_id": assessment_input.control.instance_id,
		"subject_id": assessment_input.subject.id,
		"plan_id": assessment_input.assessment.plan_id,
		"inventory_revision": object.get(assessment_input.assessment, "inventory_revision", "unknown"),
		"assignment_revision": object.get(assessment_input.assessment, "assignment_revision", "unknown"),
		"severity": assessment_input.control.severity,
		"remediation": assessment_input.control.remediation,
		"external_refs": object.get(assessment_input.control, "external_refs", []),
		"alignment": object.get(assessment_input.control, "alignment", "unmapped"),
		"policy_revision": assessment_input.assessment.policy_revision,
		"evidence_ids": [doc.id | some doc in assessment_input.evidence],
	},
	outcome,
)
