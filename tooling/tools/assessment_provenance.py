"""V4 plan and result identity plus exact-pair historical validation."""
from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta
from importlib import metadata
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
        'dependency_dispositions': copy.deepcopy(
            semantic['dependency_dispositions']
        ),
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
        'parameters': copy.deepcopy(document['parameters']),
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
    dispositions = document['dependency_dispositions']
    if dispositions != sorted(
        dispositions, key=lambda item: (item['instance_id'], item['dependency_id'])
    ):
        raise ValueError('dependency dispositions must be canonically ordered')
    disposition_keys = [
        (item['instance_id'], item['dependency_id']) for item in dispositions
    ]
    if len(disposition_keys) != len(set(disposition_keys)):
        raise ValueError('duplicate dependency disposition')
    overlap = set(keys) & set(disposition_keys)
    if overlap:
        raise ValueError('dependency cannot be both selected and unsuccessful')
    for disposition in dispositions:
        result = results.get(disposition['instance_id'])
        if result is None:
            raise ValueError('dependency disposition control is absent from results')
        if result['status'] != 'unknown':
            raise ValueError('unsuccessful required evidence must be unknown')
        nested_field = {
            'stale': 'latest_candidates',
            'invalid': 'diagnostics',
            'ambiguous': 'candidates',
        }.get(disposition['disposition'])
        if nested_field is None:
            continue
        nested = disposition[nested_field]
        if disposition['disposition'] == 'invalid':
            key_function = lambda item: (
                item['evidence_id'], item['evidence_digest'], item['schema_path'],
                item['keyword'], item['code'],
            )
        else:
            key_function = lambda item: (
                item['evidence_id'], item['evidence_digest']
            )
        nested_keys = [key_function(item) for item in nested]
        if nested_keys != sorted(nested_keys) or len(nested_keys) != len(set(nested_keys)):
            raise ValueError('dependency disposition facts are not unique and canonically ordered')
        for item in nested:
            if (item['evidence_id'], item['evidence_digest']) not in references:
                raise ValueError('dependency disposition reference is absent from snapshot')

    expected_errors = {
        'criterion_execution_failed': (
            'criterion_execution', 'Criterion execution failed.'
        ),
        'criterion_decision_invalid': (
            'criterion_decision', 'Criterion decision was unusable.'
        ),
        'criterion_reported_error': (
            'criterion_decision', 'Criterion reported an evaluation error.'
        ),
    }
    for result in results.values():
        evaluation_error = result.get('evaluation_error')
        if result['status'] == 'error':
            if evaluation_error is None:
                raise ValueError('technical error requires evaluation error attribution')
            expected_stage, expected_reason = expected_errors[evaluation_error['code']]
            if (
                evaluation_error['stage'] != expected_stage
                or result['reason'] != expected_reason
                or result['expected'] != {}
                or result['observed'] != {}
            ):
                raise ValueError('technical error facts are not canonical')
        elif evaluation_error is not None:
            raise ValueError('evaluation error attribution requires technical error status')


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
    uses_by_control: dict[str, set[str]] = {instance_id: set() for instance_id in controls}
    dispositions_by_control: dict[str, set[str]] = {
        instance_id: set() for instance_id in controls
    }
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
    for disposition in report['dependency_dispositions']:
        control = controls.get(disposition['instance_id'])
        dependencies = [] if control is None else [
            item for item in control['evidence']
            if item['id'] == disposition['dependency_id']
        ]
        if len(dependencies) != 1:
            raise ValueError('dependency disposition does not resolve into assessed plan')
        dependency = dependencies[0]
        dispositions_by_control[disposition['instance_id']].add(
            disposition['dependency_id']
        )
        amount, unit = int(dependency['max_age'][:-1]), dependency['max_age'][-1]
        maximum_age = timedelta(seconds=amount * {
            's': 1, 'm': 60, 'h': 3600, 'd': 86400,
        }[unit])
        candidates = disposition.get('latest_candidates', disposition.get('candidates', []))
        if candidates:
            instants = {
                datetime.fromisoformat(item['collected_at'].replace('Z', '+00:00'))
                for item in candidates
            }
            if len(instants) != 1:
                raise ValueError('dependency disposition candidates differ in collection instant')
            instant = next(iter(instants))
            if disposition['disposition'] == 'stale' and evaluated_at - instant <= maximum_age:
                raise ValueError('stale disposition candidate was eligible at the assessment instant')
            if disposition['disposition'] == 'ambiguous' and evaluated_at - instant > maximum_age:
                raise ValueError('ambiguous disposition candidate was stale at the assessment instant')
    for result in report['results']:
        required = {item['id'] for item in controls[result['instance_id']]['evidence']}
        actual = (
            uses_by_control[result['instance_id']]
            | dispositions_by_control[result['instance_id']]
        )
        if actual != required:
            raise ValueError('selected evidence and dispositions do not partition required plan dependencies')
        if result['status'] == 'error' and uses_by_control[result['instance_id']] != required:
            raise ValueError('technical error requires every required dependency selection')
    from .control_realization import compact_plan_outcomes
    requirements, baselines = compact_plan_outcomes(plan, report['results'])
    if requirements != report['requirement_assessments']:
        raise ValueError('requirement outcomes differ from assessed plan and technical outcomes')
    if baselines != report['requirement_baseline_assessments']:
        raise ValueError('requirement-baseline outcomes differ from assessed plan and technical outcomes')


def validate_selection_snapshot(
    report: dict,
    documents: list[dict],
    *,
    plan: dict | None = None,
    validators: dict | None = None,
    schema_references: dict | None = None,
) -> None:
    """Bind recorded factual selections to the exact in-memory evaluation inputs."""
    from .evidence_provenance import evidence_document_digest, evidence_set_provenance
    if report['provenance']['evidence'] != evidence_set_provenance(documents):
        raise ValueError('evidence descriptor differs from the evaluated snapshot')
    by_reference = {(doc['id'], evidence_document_digest(doc)): doc for doc in documents}
    for use in report['provenance']['selectedEvidence']:
        document = by_reference.get((use['evidence_id'], use['evidence_digest']))
        if document is None or document['collected_at'] != use['collected_at']:
            raise ValueError('selected facts differ from the evaluated evidence snapshot')
    for disposition in report['dependency_dispositions']:
        facts = disposition.get(
            'latest_candidates', disposition.get(
                'candidates', disposition.get('diagnostics', [])
            )
        )
        for fact in facts:
            document = by_reference.get(
                (fact['evidence_id'], fact['evidence_digest'])
            )
            if document is None:
                raise ValueError(
                    'dependency disposition differs from the evaluated evidence snapshot'
                )
            if (
                'collected_at' in fact
                and document['collected_at'] != fact['collected_at']
            ):
                raise ValueError(
                    'dependency disposition differs from the evaluated evidence snapshot'
                )
    if plan is None or validators is None:
        return
    from .evidence_selection import select_evidence
    evaluated_at = datetime.fromisoformat(
        report['evaluated_at'].replace('Z', '+00:00')
    )
    expected_uses = []
    expected_dispositions = []
    for control in plan['controls']:
        _, uses, dispositions = select_evidence(
            documents, control['evidence'], evaluated_at, report['subject_id'],
            validators, schema_references or {},
        )
        expected_uses.extend(
            {'instance_id': control['instance_id'], **item} for item in uses
        )
        expected_dispositions.extend(
            {'instance_id': control['instance_id'], **item}
            for item in dispositions
        )
    expected_uses.sort(key=lambda item: (item['instance_id'], item['dependency_id']))
    expected_dispositions.sort(
        key=lambda item: (item['instance_id'], item['dependency_id'])
    )
    if expected_uses != report['provenance']['selectedEvidence']:
        raise ValueError('selected facts differ from same-snapshot evidence selection')
    if expected_dispositions != report['dependency_dispositions']:
        raise ValueError('dependency dispositions differ from same-snapshot evidence selection')
