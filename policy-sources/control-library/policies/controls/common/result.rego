package compliance.lib.result

import rego.v1

make(assessment_input, outcome) := object.union(
	{
		"control_id": assessment_input.control.implementation,
		"instance_id": assessment_input.control.instance_id,
		"subject_id": assessment_input.subject.id,
		"plan_id": assessment_input.assessment.plan_id,
		"severity": assessment_input.control.severity,
		"remediation": assessment_input.control.remediation,
		"external_refs": object.get(assessment_input.control, "external_refs", []),
		"alignment": object.get(assessment_input.control, "alignment", "unmapped"),
		"evidence_ids": [doc.id | some doc in assessment_input.evidence],
	},
	outcome,
)
