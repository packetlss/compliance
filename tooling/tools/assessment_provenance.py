"""V4 historical assessment identity; expected enforcement is not actual identity."""
from __future__ import annotations

import copy
import hashlib
from importlib import metadata
from pathlib import PurePosixPath
from typing import Any

from ._canonical_json import canonical_json_bytes
from .composition import (
    COMPOSITION_DIGEST_ALGORITHM, COMPOSITION_LOCK_DIGEST_ALGORITHM,
    COMPOSITION_LOCK_SCHEMA, composition_digest, composition_projection, validate_document,
)

PLAN_SCHEMA = 'compliance.example/assessment-plan/v4'
RESULTS_SCHEMA = 'compliance.example/assessment-results/v4'
PROVENANCE_SCHEMA = 'compliance.example/assessment-provenance/v1alpha1'
PLAN_DIGEST_ALGORITHM = 'compliance.example/assessment-plan-digest/v1alpha1'
RESULTS_DIGEST_ALGORITHM = 'compliance.example/assessment-results-digest/v1alpha1'


def digest(value: Any) -> str:
    return 'sha256:' + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def stage(report: dict) -> dict:
    record = {key: copy.deepcopy(report[key]) for key in (
        'actual', 'compositionDigestAlgorithm', 'compositionDigest', 'enforcement')}
    try:
        record['metadata'] = {'distribution': 'compliance-tooling', 'version': metadata.version('compliance-tooling')}
    except metadata.PackageNotFoundError:
        pass
    return record


def _semantic(value: Any) -> Any:
    """Remove only known diagnostic locations, never arbitrary observed payload fields."""
    result = copy.deepcopy(value)
    for child in result.get('results', []):
        observed = child.get('observed', {})
        for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
            for diagnostic in observed.get(field, []):
                diagnostic.pop('source', None)
                diagnostic.pop('schema_source', None)
    return result


def artifact_digest(document: dict) -> str:
    projected = _semantic(document)
    projected.pop('id', None)
    provenance = projected['provenance']
    for name in ('planningComposition', 'evaluationComposition'):
        if name in provenance:
            record = provenance[name]
            provenance[name] = {
                'actual': composition_projection(record['actual']),
                'compositionDigestAlgorithm': record['compositionDigestAlgorithm'],
                'compositionDigest': record['compositionDigest'],
            }
    return digest(projected)


def validate_stage(record: dict) -> None:
    actual = record['actual']
    validate_document(actual, 'composition.schema.json')
    if record['compositionDigestAlgorithm'] != COMPOSITION_DIGEST_ALGORITHM:
        raise ValueError('invalid composition digest algorithm')
    if record['compositionDigest'] != composition_digest(actual):
        raise ValueError('composition digest mismatch')
    normalized = composition_projection(actual)
    if actual != normalized:
        raise ValueError('composition must use normalized source order')
    enforcement = record['enforcement']
    by_name = {item['name']: item['content'] for item in actual['policySources']}
    for name, content in enforcement['directExpectedContent'].items():
        if by_name.get(name) != content:
            raise ValueError('recorded direct enforcement does not match actual composition')
    lock = enforcement['compositionLock']
    if lock is not None:
        expected = composition_projection(lock['expected'])
        if lock['expected'] != expected or expected != actual:
            raise ValueError('recorded lock enforcement does not match actual composition')
        if lock['digestAlgorithm'] != COMPOSITION_LOCK_DIGEST_ALGORITHM or lock['digest'] != digest({
            'schema': COMPOSITION_LOCK_SCHEMA, 'expected': expected,
        }):
            raise ValueError('recorded composition lock digest mismatch')


def validate_provenance(document: dict, *, plan: bool) -> None:
    provenance = document['provenance']
    validate_stage(provenance['planningComposition'])
    if document['id'] != artifact_digest(document):
        raise ValueError('assessment v4 semantic digest mismatch')
    planning = provenance['planningComposition']['actual']['policySources']
    from .policy_sources import policy_revision
    revisions = [{'name': item['name'], 'digest': item['content']['digest']} for item in planning]
    if document['policy_revision'] != policy_revision(revisions):
        raise ValueError('policy revision differs from actual planning source composition')
    if plan:
        if document['policy_sources'] != [{'name': item['name'], 'digest': item['content']['digest']} for item in planning]:
            raise ValueError('plan policy sources do not match planning composition')
        return
    from .policy_parameters import validate_frozen
    if document['resolved_policy']['resolution'] != {'status': 'valid', 'errors': []}:
        raise ValueError('results require valid error-free frozen policy resolution')
    validate_frozen(document['resolved_policy'])
    frozen_controls = {item['instance_id']: item for item in document['resolved_policy']['controls']}
    for use in provenance['selectedEvidence']:
        control = frozen_controls.get(use['instance_id'])
        if control is None or use['requirement_index'] >= len(control['evidence']) or use['requirement'] != control['evidence'][use['requirement_index']]:
            raise ValueError('selected evidence differs from frozen policy dependency')
    from .control_realization import roll_up_plan_requirements
    requirements, baselines = roll_up_plan_requirements(document['resolved_policy'], document['results'])
    if requirements != document['requirement_assessments'] or baselines != document['requirement_baseline_assessments']:
        raise ValueError('result rollup differs from frozen policy satisfaction')
    validate_stage(provenance['evaluationComposition'])
    if planning != provenance['evaluationComposition']['actual']['policySources']:
        raise ValueError('evaluation policy composition differs from planning composition')
    snapshot = provenance['evidence']
    entries = snapshot['documents']
    if entries != sorted(entries, key=lambda item: (item['id'], item['digest'])) or snapshot['setDigest'] != digest(entries):
        raise ValueError('invalid evidence snapshot set digest/order')
    references = {(item['id'], item['digest']) for item in entries}
    uses = provenance['selectedEvidence']
    if uses != sorted(uses, key=lambda item: (item['instance_id'], item['requirement_index'])):
        raise ValueError('selected evidence must be ordered by control and requirement')
    keys = [(item['instance_id'], item['requirement_index']) for item in uses]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate selected evidence requirement')
    results = {item['instance_id']: item for item in document['results']}
    for use in uses:
        if (use['id'], use['digest']) not in references:
            raise ValueError('selected evidence reference is absent from snapshot')
        if use['instance_id'] not in results:
            raise ValueError('selected evidence control is absent from results')
    for result in results.values():
        observed = result.get('observed', {})
        for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
            for diagnostic in observed.get(field, []):
                schema = diagnostic['schema_reference']
                source_names = {item['name'] for item in planning}
                if schema['type'] != diagnostic['evidence_type'] or not {item['policy_source'] for item in schema['policy_sources']} <= source_names:
                    raise ValueError('diagnostic schema reference does not resolve into planning composition')
                for locator in schema['policy_sources']:
                    path = PurePosixPath(locator['path'])
                    if path.is_absolute() or '..' in path.parts or path.as_posix() != locator['path'] or '\\' in locator['path']:
                        raise ValueError('unsafe schema reference path')
                if field.endswith('ambiguities'):
                    if diagnostic['subject'] != document['subject_id'] or diagnostic['evaluated_at'] != document['evaluated_at'] or diagnostic['freshness_requirement']['type'] != diagnostic['evidence_type']:
                        raise ValueError('ambiguity attribution differs from assessed subject/time/requirement')
                    if diagnostic['candidates'] != sorted(diagnostic['candidates'], key=lambda x:(x['id'],x['digest'])):
                        raise ValueError('ambiguity candidate ordering is invalid')
                pairs = diagnostic.get('candidates', []) if field.endswith('ambiguities') else [
                    {'id': diagnostic['evidence_id'], 'digest': diagnostic['evidence_digest']}]
                if any((item['id'], item['digest']) not in references for item in pairs):
                    raise ValueError('evidence diagnostic reference is absent from snapshot')
                required = field.endswith('ambiguities') or diagnostic['required']
                if required and result['status'] != 'unknown':
                    raise ValueError('rejected/ambiguous required evidence must be unknown')
                if not required and result['status'] not in {'error', 'unknown'}:
                    raise ValueError('invalid optional evidence must prevent criterion execution')
                if any(use['instance_id'] == result['instance_id'] and use['requirement_index'] == diagnostic['requirement_index'] for use in uses):
                    raise ValueError('rejected/ambiguous requirement mislabeled as selected')


def validate_selection_plan(report: dict, plan: dict) -> None:
    """Check references against the exact assessed plan while it is available."""
    if report['plan_id'] != plan['id'] or report['provenance']['planningComposition'] != plan['provenance']['planningComposition']:
        raise ValueError('result does not reference the assessed plan')
    controls = {control['instance_id']: control for control in plan['controls']}
    if set(controls) != {item['instance_id'] for item in report['results']}:
        raise ValueError('result controls do not match assessed plan')
    for result in report['results']:
        requirements = controls[result['instance_id']]['evidence']
        for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
            for diagnostic in result.get('observed', {}).get(field, []):
                index = diagnostic['requirement_index']
                if index >= len(requirements) or requirements[index]['type'] != diagnostic['evidence_type']:
                    raise ValueError('evidence diagnostic requirement does not resolve into assessed plan')
                if field.endswith('ambiguities'):
                    if diagnostic['freshness_requirement'] != requirements[index]:
                        raise ValueError('ambiguity freshness requirement differs from assessed plan')
                elif diagnostic['required'] != requirements[index]['required']:
                    raise ValueError('diagnostic required flag differs from assessed plan')
    for use in report['provenance']['selectedEvidence']:
        control = controls.get(use['instance_id'])
        if control is None or use['requirement_index'] >= len(control['evidence']) or control['evidence'][use['requirement_index']] != use['requirement']:
            raise ValueError('selected evidence requirement does not resolve into assessed plan')


def validate_selection_snapshot(report: dict, documents: list[dict]) -> None:
    """Bind recorded factual selections to the exact in-memory evaluation inputs."""
    from .evidence_provenance import evidence_document_digest
    by_reference = {(doc['id'], evidence_document_digest(doc)): doc for doc in documents}
    for use in report['provenance']['selectedEvidence']:
        document = by_reference.get((use['id'], use['digest']))
        if document is None or document['collected_at'] != use['collected_at'] or document['type'] != use['requirement']['type']:
            raise ValueError('selected facts differ from the evaluated evidence snapshot')
