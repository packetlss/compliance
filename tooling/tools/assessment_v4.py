"""V4 planner integration for v1alpha3 projects; predecessor consumers migrate separately."""
from __future__ import annotations

from .assessment_provenance import PLAN_SCHEMA, PROVENANCE_SCHEMA, PLAN_DIGEST_ALGORITHM, artifact_digest, stage
from .artifact_validation import validate_assessment_plan
from .composition import require_composition
from .project_config import composition_validation


def render_plan_v4(base_render, *args, config=None, **kwargs):
    policies = args[3] if len(args) > 3 else kwargs['policy_sources']
    report = composition_validation(config, require=True) if config else require_composition(policies)
    plan = base_render(*args, **kwargs)
    plan['schema'] = PLAN_SCHEMA
    plan['digestAlgorithm'] = PLAN_DIGEST_ALGORITHM
    plan['provenance'] = {'schema': PROVENANCE_SCHEMA, 'planningComposition': stage(report)}
    plan['id'] = artifact_digest(plan)
    validate_assessment_plan(plan)
    return plan
