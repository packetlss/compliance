"""V4 plan and result identity plus exact-pair historical validation."""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta
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
MEMBER_PLAN_DOMAIN = 'compliance.example/member-plan/v1alpha1'
OPERATION_PLAN_DOMAIN = 'compliance.example/operation-bound-plan/v1alpha1'


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


def result_identity_projection(document: dict) -> dict:
    """Project independently meaningful result-domain identity facts."""
    semantic = copy.deepcopy(document)
    provenance = semantic['provenance']
    evaluation = provenance['evaluationComposition']
    evidence = provenance['evidence']
    return {
        'schema': semantic['schema'],
        'digestAlgorithm': semantic['digestAlgorithm'],
        'plan_id': semantic['plan_id'],
        'subject_id': semantic['subject_id'],
        'evaluated_at': semantic['evaluated_at'],
        'outcome': semantic['outcome'],
        'evaluationComposition': {
            'compositionDigestAlgorithm': evaluation['compositionDigestAlgorithm'],
            'compositionDigest': evaluation['compositionDigest'],
        },
        'evaluator': copy.deepcopy(provenance['evaluator']),
        'evidence': {
            'setDigestAlgorithm': evidence['setDigestAlgorithm'],
            'setDigest': evidence['setDigest'],
        },
        'selectedEvidence': copy.deepcopy(provenance['selectedEvidence']),
        'results': copy.deepcopy(semantic['results']),
        'requirement_assessments': copy.deepcopy(semantic['requirement_assessments']),
        'requirement_baseline_assessments': copy.deepcopy(
            semantic['requirement_baseline_assessments']
        ),
    }


def member_plan_projection(document: dict) -> dict:
    """Project complete resolved member intent without operation context."""
    from .operation import _member_resolved_groups, _member_subject
    subject = _member_subject(document)
    return {
        'domain': MEMBER_PLAN_DOMAIN,
        'subject': copy.deepcopy(subject),
        'resolved_groups': _member_resolved_groups(document),
        'assignments': copy.deepcopy(document['assignments']),
        'resolved_baselines': copy.deepcopy(document['resolved_baselines']),
        'resolved_requirement_baselines': copy.deepcopy(document['resolved_requirement_baselines']),
        'requirements': copy.deepcopy(document['requirements']),
        'controls': copy.deepcopy(document['controls']),
        'excluded_controls': copy.deepcopy(document['excluded_controls']),
        'resolution': copy.deepcopy(document['resolution']),
    }


def member_plan_digest(document: dict) -> str:
    return digest(member_plan_projection(document))


def operation_plan_id(operation_id: str, subject_id: str) -> str:
    return digest({
        'domain': OPERATION_PLAN_DOMAIN,
        'operation_id': operation_id,
        'subject_id': subject_id,
    })


def artifact_digest(document: dict) -> str:
    if document['schema'] == PLAN_SCHEMA:
        return operation_plan_id(document['operation']['operation_id'], document['subject']['id'])
    if document['schema'] == RESULTS_SCHEMA:
        return digest(result_identity_projection(document))
    raise ValueError('unsupported assessment artifact schema')


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


def validate_plan_provenance(document: dict) -> None:
    provenance = document['provenance']
    validate_stage(provenance['planningComposition'])
    if document['id'] != artifact_digest(document):
        raise ValueError('assessment v4 semantic digest mismatch')
    from .operation import validate_operation
    validate_operation(document)


def validate_result_provenance(document: dict) -> None:
    """Validate result-owned provenance without interpreting an assessed plan."""
    provenance = document['provenance']
    validate_stage(provenance['evaluationComposition'])
    if document['id'] != artifact_digest(document):
        raise ValueError('assessment v4 semantic digest mismatch')
    snapshot = provenance['evidence']
    entries = snapshot['documents']
    if entries != sorted(entries, key=lambda item: (item['id'], item['digest'])) or snapshot['setDigest'] != digest(entries):
        raise ValueError('invalid evidence snapshot set digest/order')
    references = {(item['id'], item['digest']) for item in entries}
    uses = provenance['selectedEvidence']
    if uses != sorted(uses, key=lambda item: (item['instance_id'], item['dependency_id'])):
        raise ValueError('selected evidence must be ordered by control and dependency')
    keys = [(item['instance_id'], item['dependency_id']) for item in uses]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate selected evidence dependency')
    results = {item['instance_id']: item for item in document['results']}
    for use in uses:
        if (use['evidence_id'], use['evidence_digest']) not in references:
            raise ValueError('selected evidence reference is absent from snapshot')
        if use['instance_id'] not in results:
            raise ValueError('selected evidence control is absent from results')
    policy_sources = {
        item['name']
        for item in provenance['evaluationComposition']['actual']['policySources']
    }
    for result in results.values():
        observed = result.get('observed', {})
        for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
            diagnostics = observed.get(field, [])
            if field == 'evidence_validation_errors':
                ordered = sorted(diagnostics, key=lambda item: (
                    item['dependency_id'], item['evidence_type'], item['evidence_id'],
                    item['evidence_digest'], item['path'], item['schema_path'], item['message'],
                ))
            else:
                ordered = sorted(diagnostics, key=lambda item: (
                    item['dependency_id'], item['evidence_type'],
                ))
            if diagnostics != ordered:
                raise ValueError('evidence diagnostics are not canonically ordered')
            for diagnostic in diagnostics:
                schema = diagnostic['schema_reference']
                if schema['type'] != diagnostic['evidence_type'] or not {
                        item['policy_source'] for item in schema['policy_sources']
                } <= policy_sources:
                    raise ValueError('diagnostic schema reference does not resolve into evaluation composition')
                if schema['policy_sources'] != sorted(
                        schema['policy_sources'], key=lambda item: (
                            item['policy_source'], item['path'])):
                    raise ValueError('diagnostic schema reference is not canonically ordered')
                for locator in schema['policy_sources']:
                    path = PurePosixPath(locator['path'])
                    if path.is_absolute() or '..' in path.parts or path.as_posix() != locator['path'] or '\\' in locator['path']:
                        raise ValueError('unsafe schema reference path')
                if field.endswith('ambiguities'):
                    if diagnostic['subject'] != document['subject_id'] or diagnostic['evaluated_at'] != document['evaluated_at']:
                        raise ValueError('ambiguity attribution differs from assessed subject/time')
                    if diagnostic['candidates'] != sorted(diagnostic['candidates'], key=lambda x:(x['id'],x['digest'])):
                        raise ValueError('ambiguity candidate ordering is invalid')
                pairs = diagnostic.get('candidates', []) if field.endswith('ambiguities') else [
                    {'id': diagnostic['evidence_id'], 'digest': diagnostic['evidence_digest']}]
                if any((item['id'], item['digest']) not in references for item in pairs):
                    raise ValueError('evidence diagnostic reference is absent from snapshot')
                if result['status'] != 'unknown':
                    raise ValueError('rejected/ambiguous required evidence must be unknown')
                if any(use['instance_id'] == result['instance_id'] and
                       use['dependency_id'] == diagnostic['dependency_id'] for use in uses):
                    raise ValueError('rejected/ambiguous dependency mislabeled as selected')


def validate_result_against_plan(report: dict, plan: dict) -> None:
    """Establish the mandatory exact plan/result historical relationship."""
    from .artifact_validation import validate_assessment_plan, validate_assessment_results
    validate_assessment_plan(plan)
    validate_assessment_results(report)
    if report['plan_id'] != plan['id']:
        raise ValueError('result does not reference the exact assessed plan')
    if report['subject_id'] != plan['subject']['id']:
        raise ValueError('result subject differs from assessed plan')
    from .operation import plan_disposition
    if plan_disposition(plan) != 'result_required':
        raise ValueError('result supplied for non-assessable plan')
    planning_sources = plan['provenance']['planningComposition']['actual']['policySources']
    evaluation_sources = report['provenance']['evaluationComposition']['actual']['policySources']
    if evaluation_sources != planning_sources:
        raise ValueError('evaluation policy composition differs from planning composition')
    controls = {control['instance_id']: control for control in plan['controls']}
    if set(controls) != {item['instance_id'] for item in report['results']}:
        raise ValueError('result controls do not match assessed plan')
    for result in report['results']:
        requirements = controls[result['instance_id']]['evidence']
        for field in ('evidence_validation_errors', 'evidence_selection_ambiguities'):
            for diagnostic in result.get('observed', {}).get(field, []):
                dependencies = [item for item in requirements
                                if item['id'] == diagnostic['dependency_id']]
                if len(dependencies) != 1 or dependencies[0]['type'] != diagnostic['evidence_type']:
                    raise ValueError('evidence diagnostic dependency does not resolve into assessed plan')
    uses_by_control: dict[str, set[str]] = {instance_id: set() for instance_id in controls}
    evaluated_at = datetime.fromisoformat(report['evaluated_at'].replace('Z', '+00:00'))
    for use in report['provenance']['selectedEvidence']:
        control = controls.get(use['instance_id'])
        dependencies = [] if control is None else [item for item in control['evidence']
                                                   if item['id'] == use['dependency_id']]
        if len(dependencies) != 1:
            raise ValueError('selected evidence dependency does not resolve into assessed plan')
        uses_by_control[use['instance_id']].add(use['dependency_id'])
        dependency = dependencies[0]
        collected_at = datetime.fromisoformat(use['collected_at'].replace('Z', '+00:00'))
        amount, unit = int(dependency['max_age'][:-1]), dependency['max_age'][-1]
        maximum_age = timedelta(seconds=amount * {
            's': 1, 'm': 60, 'h': 3600, 'd': 86400,
        }[unit])
        if evaluated_at - collected_at > maximum_age:
            raise ValueError('selected evidence was stale at the assessment instant')
    for result in report['results']:
        if result['status'] != 'unknown':
            required = {item['id'] for item in controls[result['instance_id']]['evidence']}
            if uses_by_control[result['instance_id']] != required:
                raise ValueError('successful evidence selections do not cover required plan dependencies')
    from .control_realization import compact_plan_outcomes
    requirements, baselines = compact_plan_outcomes(plan, report['results'])
    if requirements != report['requirement_assessments']:
        raise ValueError('requirement outcomes differ from assessed plan and technical outcomes')
    if baselines != report['requirement_baseline_assessments']:
        raise ValueError('requirement-baseline outcomes differ from assessed plan and technical outcomes')


def validate_selection_snapshot(report: dict, documents: list[dict]) -> None:
    """Bind recorded factual selections to the exact in-memory evaluation inputs."""
    from .evidence_provenance import evidence_document_digest
    by_reference = {(doc['id'], evidence_document_digest(doc)): doc for doc in documents}
    for use in report['provenance']['selectedEvidence']:
        document = by_reference.get((use['evidence_id'], use['evidence_digest']))
        if document is None or document['collected_at'] != use['collected_at']:
            raise ValueError('selected facts differ from the evaluated evidence snapshot')
