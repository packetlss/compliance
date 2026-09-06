"""Embedded frozen operation facts inside assessment plans and results.

This is a projection of supplied planning facts, not another inventory or run
artifact. Sibling policy bodies are committed by digest, never embedded as plans.
"""
from __future__ import annotations

import copy

from .assessment_provenance import digest


class InvalidOperationResolution(ValueError):
    """Supplied policy resolved to an invalid selected member, refusing assessment."""


def policy_membership(plan):
    """Keep the denominator and mapping facts, without evaluator/parameter bodies."""
    controls = []
    for field in ('controls', 'excluded_controls'):
        for control in plan.get(field, []):
            controls.append({
                'instance_id': control['instance_id'],
                'implementation': control['implementation'],
                'disposition': control['disposition'],
                'digest': digest(control),
                'external_refs': copy.deepcopy(control.get('external_refs', [])),
                'provenance': copy.deepcopy(control['provenance']),
            })
    requirements = [{key: copy.deepcopy(r[key]) for key in (
        'reference', 'digest', 'required', 'external_refs', 'technical_instance_ids',
        'adoption', 'satisfaction', 'provenance')}
        for r in plan['requirements']]
    baselines = []
    for field in ('resolved_baselines', 'resolved_requirement_baselines'):
        for baseline in plan[field]:
            record = {key: copy.deepcopy(baseline[key]) for key in (
                'reference', 'digest', 'assignment', 'group')}
            if field == 'resolved_requirement_baselines':
                record['requirements'] = copy.deepcopy(baseline['requirements'])
            else:
                record['control_ids'] = sorted(c['instance_id'] for c in controls
                    if any(p['assignment'] == record['assignment'] and
                           p['baseline'] == record['reference'] for p in c['provenance']))
            baselines.append(record)
    return {'baselines': sorted(baselines, key=lambda b: (b['assignment'], b['reference'])),
            'requirements': sorted(requirements, key=lambda r: r['reference']),
            'controls': sorted(controls, key=lambda c: c['instance_id'])}


def select_subjects(subjects, groups, selection):
    from .render_plan import resolve_groups, validate_group_dag
    catalog = {g['id']: g for g in groups}
    if len(catalog) != len(groups):
        raise ValueError('duplicate frozen group identity')
    validate_group_dag(catalog)
    if set(selection['subjects']) - subjects.keys() or set(selection['groups']) - catalog.keys():
        raise ValueError('unresolved operation selection')
    selected = set(subjects) if selection['all'] else set(selection['subjects'])
    for sid, subject in subjects.items():
        if set(selection['groups']) & {g['id'] for g in resolve_groups(catalog, subject)}:
            selected.add(sid)
    if not selected:
        raise ValueError('empty operation selection')
    return sorted(selected)


def freeze_operation(plans, subjects, groups, assignments, selection):
    """Freeze all rows before evaluation; mutate only the generated subject plans."""
    from .assessment_provenance import artifact_digest, plan_content_digest
    canonical_groups = copy.deepcopy(sorted(groups, key=lambda g: g['id']))
    for group in canonical_groups:
        group['parents'] = sorted(group.get('parents', []))
        if 'members' in group:
            group['members'] = sorted(group['members'])
    canonical_assignments = copy.deepcopy(sorted(assignments, key=lambda a: a['id']))
    for assignment in canonical_assignments:
        assignment['baselines'] = sorted(assignment['baselines'])
    projection = {
        'planning_composition': {k: copy.deepcopy(plans[0]['provenance']['planningComposition'][k])
                                 for k in ('actual', 'compositionDigestAlgorithm', 'compositionDigest')},
        'selection': {**selection, 'subjects': sorted(set(selection['subjects'])),
                      'groups': sorted(set(selection['groups']))},
        'subjects': [copy.deepcopy(subjects[s]) for s in sorted(subjects)],
        'groups': canonical_groups, 'assignments': canonical_assignments,
        'members': [{
            'subject_id': plan['subject']['id'],
            'plan_content_digest': plan_content_digest(plan),
            'inventory_revision': plan['inventory_revision'],
            'assignment_revision': plan['assignment_revision'],
            'resolved_groups': copy.deepcopy(sorted(plan['resolved_groups'], key=lambda g: g['id'])),
            'assignments': copy.deepcopy(plan['assignments']),
            'coverage': copy.deepcopy(plan['coverage']),
            'policy': policy_membership(plan),
        } for plan in sorted(plans, key=lambda p: p['subject']['id'])],
    }
    for plan in plans:
        plan['operation'] = copy.deepcopy(projection)
        plan['id'] = artifact_digest(plan)
    return plans


def render_operation(subjects, groups, assignments, policy_sources, selection, *, config=None):
    from .render_plan import render_plan
    from .artifact_validation import validate_assessment_plan
    ids = select_subjects(subjects, groups, selection)
    plans = [render_plan(subjects[s], groups, assignments, policy_sources, config=config)
             for s in ids]
    if any(p['resolution']['status'] != 'valid' for p in plans):
        raise InvalidOperationResolution('operation planning failed: ' + str([{'subject': p['subject']['id'], 'errors': p['resolution']['errors']} for p in plans if p['resolution']['status'] != 'valid']))
    if not selection['groups'] and not selection['all']:
        subjects = {s: subjects[s] for s in ids}
        groups = copy.deepcopy(groups)
        for group in groups:
            if 'members' in group:
                group['members'] = [s for s in group['members'] if s in subjects]
    freeze_operation(plans, subjects, groups, assignments, selection)
    for plan in plans:
        validate_assessment_plan(plan)
    return plans


def validate_operation(document, *, plan):
    from .render_plan import resolve_groups
    from .assessment_provenance import plan_content_digest, operation_plan_id
    projection = document['operation']
    stage = document['provenance']['planningComposition']
    if projection['planning_composition'] != {k: stage[k] for k in projection['planning_composition']}:
        raise ValueError('artifact planning composition differs from frozen operation')
    subjects = {s['id']: s for s in projection['subjects']}
    if len(subjects) != len(projection['subjects']):
        raise ValueError('duplicate frozen subject identity')
    if any(s not in subjects for g in projection['groups'] for s in g.get('members', [])):
        raise ValueError('unresolved frozen subject reference')
    expected = select_subjects(subjects, projection['groups'], projection['selection'])
    if [m['subject_id'] for m in projection['members']] != expected:
        raise ValueError('frozen operation membership differs from selection')
    groups = {g['id']: g for g in projection['groups']}
    assignments = projection['assignments']
    if (projection['subjects'] != sorted(projection['subjects'], key=lambda s:s['id']) or
            projection['groups'] != sorted(projection['groups'], key=lambda g:g['id']) or
            assignments != sorted(assignments, key=lambda a:a['id'])):
        raise ValueError('frozen operation facts must use canonical identity order')
    if len({a['id'] for a in assignments}) != len(assignments):
        raise ValueError('duplicate frozen assignment identity')
    if any(a['target']['group'] not in groups for a in assignments):
        raise ValueError('unresolved frozen assignment target')
    for row in projection['members']:
        sid = row['subject_id']
        resolved = resolve_groups(groups, subjects[sid])
        applicable = [{'id': a['id'], 'group': a['target']['group'], 'baselines': a['baselines']}
                      for a in assignments if a['target']['group'] in {g['id'] for g in resolved}]
        if row['resolved_groups'] != resolved or row['assignments'] != applicable:
            raise ValueError('frozen membership/assignment attribution differs from supplied facts')
        policy = row['policy']
        selections = {(a['id'], a['group'], b) for a in applicable for b in a['baselines']}
        actual = [(b['assignment'], b['group'], b['reference']) for b in policy['baselines']]
        # Invalid diagnostic subject plans remain non-assessable. Operations reject
        # them before publication; no result may use such a row.
        if row['coverage']['status'] == 'invalid':
            if not (plan and document['resolution']['status'] == 'invalid' and len(projection['members']) == 1):
                raise ValueError('invalid member prevents operation planning')
            continue
        if set(actual) != selections or len(actual) != len(set(actual)):
            raise ValueError('frozen operation baseline membership differs from assignments')
        pins = {p['requirement']: p for b in policy['baselines'] for p in b.get('requirements', [])}
        if any(p != pins[p['requirement']] for b in policy['baselines'] for p in b.get('requirements', [])):
            raise ValueError('divergent frozen operation requirement pins')
        for field, identity in (('requirements','reference'), ('controls','instance_id')):
            values = [item[identity] for item in policy[field]]
            if values != sorted(set(values)):
                raise ValueError('duplicate or unordered frozen operation policy instances')
        if set(pins) != {r['reference'] for r in policy['requirements']}:
            raise ValueError('frozen operation required instance membership is incomplete')
        for requirement in policy['requirements']:
            pin = pins[requirement['reference']]
            if pin['digest'] != requirement['digest'] or pin['required'] != requirement['required']:
                raise ValueError('frozen operation requirement pin mismatch')
        expected_controls = {c for b in policy['baselines'] for c in b.get('control_ids', [])}
        expected_controls.update(c for r in policy['requirements'] for c in r['technical_instance_ids'])
        if expected_controls != {c['instance_id'] for c in policy['controls']}:
            raise ValueError('frozen operation check membership is incomplete')
        active = [c for c in policy['controls'] if c['disposition'] != 'excluded']
        status = ('inactive' if subjects[sid]['status'] == 'retired' else
                  'unassigned' if not applicable else 'assigned')
        coverage = {
            'status': status, 'assessable': status == 'assigned' and bool(active or pins),
            'reason': ('subject-retired' if status == 'inactive' else
                       'no-policy-assignment' if status == 'unassigned' else
                       'policy-assigned' if active or pins else 'no-active-controls'),
            'assignment_count': len(applicable), 'active_control_count': len(active),
            'excluded_control_count': len(policy['controls']) - len(active),
            'requirement_count': len(pins),
        }
        if row['coverage'] != coverage or subjects[sid]['status'] == 'unknown':
            raise ValueError('frozen operation coverage differs from resolved facts')
    sid = document['subject']['id'] if plan else document['subject_id']
    rows = {m['subject_id']: m for m in projection['members']}
    if sid not in rows:
        raise ValueError('artifact subject is absent from frozen operation')
    row = rows[sid]
    if plan:
        if (document['subject'] != subjects[sid] or document['coverage'] != row['coverage'] or
                plan_content_digest(document) != row['plan_content_digest']):
            raise ValueError('subject plan differs from frozen operation')
    else:
        if not row['coverage']['assessable']:
            raise ValueError('result supplied for non-assessable operation member')
        if document['plan_id'] != operation_plan_id(row['plan_content_digest'], projection):
            raise ValueError('result plan differs from frozen operation')
    if policy_membership(document if plan else document['resolved_policy']) != row['policy']:
        raise ValueError('artifact policy differs from frozen policy membership in operation')
    for key in ('inventory_revision', 'assignment_revision'):
        if document[key] != row[key]:
            raise ValueError('artifact attribution differs from frozen operation')


def account_operation(anchor, reports, evaluated_at):
    """Exact-set historical accounting; result discovery never supplies the scope."""
    from .artifact_validation import validate_assessment_plan, validate_assessment_results
    from .assessment_provenance import operation_plan_id
    from .assessment import result_state
    validate_assessment_plan(anchor)
    projection = anchor['operation']
    if any(m['coverage']['status'] == 'invalid' for m in projection['members']):
        raise ValueError('invalid operation resolution')
    for report in reports:
        validate_assessment_results(report)
    rows = []
    for member in projection['members']:
        plan_id = operation_plan_id(member['plan_content_digest'], projection)
        candidates = [r for r in reports if r['subject_id'] == member['subject_id'] and
                      r['plan_id'] == plan_id and r['operation'] == projection and
                      r['evaluated_at'] == evaluated_at and r['policy_revision'] == anchor['policy_revision']]
        # Complete-document copies only. Equal semantic IDs with different
        # descriptive/enforcement bytes do not invent result-selection precedence.
        unique = {digest(r): r for r in candidates}
        if len(unique) > 1:
            raise ValueError('multiple distinct results for exact operation member and instant')
        result = next(iter(unique.values()), None)
        coverage = member['coverage']
        state = (result_state(result) if result else 'missing') if coverage['assessable'] else (
            coverage['status'] if coverage['status'] != 'assigned' else 'no_controls')
        rows.append({**copy.deepcopy(member), 'plan_id': plan_id, 'state': state,
                     'result_id': result['id'] if result else None})
    return {'operation': copy.deepcopy(projection), 'evaluated_at': evaluated_at,
            'policy_revision': anchor['policy_revision'], 'members': rows,
            'accounting_complete': all(r['state'] != 'missing' for r in rows),
            'all_passed': all(r['state'] == 'pass' for r in rows),
            'claim': 'Exact supplied company policy only; no external conformity or inventory exhaustiveness.'}
