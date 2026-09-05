"""Native v4 provenance for synthetic in-memory domain test plans."""
from tools.assessment_provenance import PLAN_SCHEMA, PLAN_DIGEST_ALGORITHM, PROVENANCE_SCHEMA, artifact_digest
from tools.composition import COMPOSITION_DIGEST_ALGORITHM, composition_digest, POLICY_SOURCE_DIGEST_ALGORITHM
from tools.tooling_identity import actual_tooling_identity
from tools.policy_sources import policy_revision


def planning_fields(sources):
    actual = {'tooling': actual_tooling_identity(), 'policySources': [
        {'name': item['name'], 'content': {'digest': item['digest'], 'digestAlgorithm': POLICY_SOURCE_DIGEST_ALGORITHM}}
        for item in sorted(sources, key=lambda item: item['name'])]}
    return {'schema': PLAN_SCHEMA, 'digestAlgorithm': PLAN_DIGEST_ALGORITHM,
            'policy_revision': policy_revision(sources),
            'provenance': {'schema': PROVENANCE_SCHEMA, 'planningComposition': {
                'actual': actual, 'compositionDigestAlgorithm': COMPOSITION_DIGEST_ALGORITHM,
                'compositionDigest': composition_digest(actual),
                'enforcement': {'directExpectedContent': {}, 'compositionLock': None}}}}
