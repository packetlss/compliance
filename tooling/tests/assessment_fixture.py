"""Native v4 provenance for synthetic in-memory domain test plans."""
from tools.assessment_provenance import PLAN_SCHEMA, PLAN_DIGEST_ALGORITHM, PROVENANCE_SCHEMA, artifact_digest
from tools.composition import COMPOSITION_DIGEST_ALGORITHM, composition_digest, POLICY_SOURCE_DIGEST_ALGORITHM
from tools.tooling_identity import actual_tooling_identity
from tools.policy_sources import policy_revision


def freeze_policy_inputs(plan):
    """Author explicit synthetic input facts for hand-built evaluator fixtures."""
    import copy
    from tools import policy_parameters as pp
    for control in plan['controls']:
        for index, dependency in enumerate(control['evidence']):
            dependency.setdefault('id', f'observation-{index + 1}')
            dependency['max_age'] = pp.duration(dependency['max_age'])
        instance = {'instance_id': control['instance_id'], 'implementation': control['implementation'],
                    'parameters': copy.deepcopy(control['parameters']),
                    'evidence': {e['id']: {'max_age': e['max_age']} for e in control['evidence']}}
        definition = {'metadata': {'id': control['implementation'], 'version': 1},
                      'spec': {'entrypoint': control['entrypoint'],
                               'evidence': [{k: v for k, v in e.items() if k != 'max_age'} for e in control['evidence']]}}
        control['policy_inputs'] = {'instance': instance, 'definition': definition, 'parameters_schema': {'type': 'object'}}
        from tools.render_plan import control_definition_fingerprint
        control['definition_fingerprint'] = pp.digest(instance) if control['alignment'] == 'realization' else control_definition_fingerprint(instance)
    if not plan['resolved_baselines'] and not plan['resolved_requirement_baselines']:
        for assignment in plan['assignments']:
            for reference in assignment['baselines']:
                identity = pp.digest({'reference': reference})
                plan['resolved_baselines'].append({'assignment': assignment['id'], 'group': assignment['group'],
                    'reference': reference, 'digest': identity, 'lineage': [{'reference': reference, 'digest': identity}],
                    'deviations': [], 'policy_sources': [{'policy_source': plan['policy_sources'][0]['name'], 'path': 'baselines/test.json'}]})
    requirements = {}
    for record in plan['requirements']:
        identifier, revision = record['reference'].rsplit('@', 1)
        doc = {'metadata': {'id': identifier, 'revision': revision}, 'spec': {'title': record['title'], 'statement': record['statement'], 'external_refs': copy.deepcopy(record['external_refs'])}}
        record['digest'] = pp.digest(doc)
        requirements[record['reference']] = doc
        facts = {'document': doc, 'states': {}}
        if 'realization' in record:
            rid, rev = record['realization']['reference'].rsplit('@', 1)
            realization = {'metadata': {'id': rid, 'revision': rev}, 'spec': {
                'requirement': {'requirement': record['reference'], 'digest': record['digest']},
                'adoption': copy.deepcopy(record['adoption']), 'satisfaction': copy.deepcopy(record['satisfaction']),
                'checks': [copy.deepcopy(c['policy_inputs']['instance']) for c in plan['controls'] if c['instance_id'] in record['technical_instance_ids']]}}
            record['realization']['digest'] = pp.digest(realization)
            facts.update(realization=realization, consumption=[])
        record['parameter_facts'] = facts
    for baseline in plan['resolved_requirement_baselines']:
        identifier, revision = baseline['reference'].rsplit('@', 1)
        for pin in baseline['requirements']:
            pin['digest'] = pp.digest(requirements[pin['requirement']])
        doc = {'metadata': {'id': identifier, 'revision': revision}, 'spec': {'requirements': copy.deepcopy(baseline['requirements'])}}
        states, ancestry = pp.resolve(baseline['reference'], {baseline['reference']: {**doc, '_sources': baseline['policy_sources']}}, requirements)
        baseline['digest'] = pp.digest(doc)
        baseline['parameter_derivation'] = {'states': states, 'ancestry': ancestry}
    refresh_operation(plan)


def refresh_operation(plan):
    """Re-author singleton operation facts when a test intentionally edits policy."""
    from tools.operation import freeze_operation
    groups = {g['id']: {'id': g['id'], 'parents': []} for g in plan['resolved_groups']}
    for resolved in plan['resolved_groups']:
        group = groups[resolved['id']]
        for source in resolved['sources']:
            if source['membership'] == 'explicit':
                group['members'] = [plan['subject']['id']]
            elif source['membership'] == 'selector':
                group['selector'] = source['source']
            else:
                for child in source['via']:
                    groups[child]['parents'].append(resolved['id'])
    assignments = [{'id': a['id'], 'target': {'group': a['group']}, 'baselines': a['baselines']}
                   for a in plan['assignments']]
    freeze_operation([plan], {plan['subject']['id']: plan['subject']}, list(groups.values()), assignments,
                     {'subjects': [plan['subject']['id']], 'groups': [], 'all': False})


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
