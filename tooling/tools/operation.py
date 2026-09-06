"""Embedded frozen operation facts inside assessment plans and results.

This is a projection of supplied planning facts, not another inventory or run
artifact. Sibling policy bodies are committed by digest, never embedded as plans.
"""
from __future__ import annotations

import copy
from collections import Counter
from datetime import datetime

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
    for requirement, original in zip(requirements, plan['requirements']):
        if 'realization' in original:
            requirement['realization'] = copy.deepcopy(original['realization'])
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


def member_facts(plan):
    """Bind exposed sibling accounting facts to a compact full-body commitment."""
    from .assessment_provenance import plan_body_digest
    return {
        'subject_id': plan['subject']['id'],
        'plan_body_digest': plan_body_digest(plan),
        'inventory_revision': plan['inventory_revision'],
        'assignment_revision': plan['assignment_revision'],
        'resolved_groups': copy.deepcopy(sorted(plan['resolved_groups'], key=lambda g: g['id'])),
        'assignments': copy.deepcopy(plan['assignments']),
        'coverage': copy.deepcopy(plan['coverage']),
        'policy': policy_membership(plan),
    }


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
        'members': [{**member_facts(plan), 'plan_content_digest': plan_content_digest(plan)}
                    for plan in sorted(plans, key=lambda p: p['subject']['id'])],
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
        if digest({k: v for k, v in row.items() if k != 'plan_content_digest'}) != row['plan_content_digest']:
            raise ValueError('frozen member facts differ from plan content commitment')
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


def _evidence_timeliness(report, query_instant):
    """Derive age qualifications solely from frozen dependency/selection facts."""
    from .evaluate_plan import parse_duration
    from .waivers import parse_timestamp

    selected = {
        (item['instance_id'], item['requirement_index']): item
        for item in report['provenance']['selectedEvidence']
    }
    results = {item['instance_id']: item for item in report['results']}
    dependencies = []
    controls = []
    for control in report['resolved_policy']['controls']:
        required = [
            (index, requirement)
            for index, requirement in enumerate(control['evidence'])
            if requirement['required']
        ]
        if not required:
            continue
        stale = False
        unavailable = False
        for index, requirement in required:
            use = selected.get((control['instance_id'], index))
            if use is None:
                unavailable = True
                result = results[control['instance_id']]
                dependencies.append({
                    'instance_id': control['instance_id'],
                    'requirement_index': index,
                    'requirement': copy.deepcopy(requirement),
                    'qualification': 'unavailable',
                    'historical_result': {
                        'status': result['status'],
                        'reason': result.get('reason'),
                        'observed': copy.deepcopy(result.get('observed', {})),
                    },
                })
                continue
            collected = parse_timestamp(use['collected_at'], field='selected collected_at')
            qualification = (
                'timely'
                if query_instant - collected <= parse_duration(requirement['max_age'])
                else 'stale'
            )
            stale = stale or qualification == 'stale'
            dependencies.append({
                'instance_id': control['instance_id'],
                'requirement_index': index,
                'requirement': copy.deepcopy(requirement),
                'evidence_id': use['id'],
                'evidence_digest': use['digest'],
                'collected_at': use['collected_at'],
                'recorded_max_age': requirement['max_age'],
                'qualification': qualification,
            })
        controls.append({
            'instance_id': control['instance_id'],
            'within_recorded_age_limits': not stale and not unavailable,
            'reassessment_due': stale,
            'timeliness_unavailable': unavailable,
        })
    counts = Counter(item['qualification'] for item in dependencies)
    return {
        'dependencies': dependencies,
        'controls': controls,
        'timely_selected_dependencies': counts['timely'],
        'stale_selected_dependencies': counts['stale'],
        'unavailable_required_dependencies': counts['unavailable'],
        'controls_within_recorded_age_limits': sum(c['within_recorded_age_limits'] for c in controls),
        'controls_needing_reassessment': sum(c['reassessment_due'] for c in controls),
        'controls_with_unavailable_timeliness': sum(c['timeliness_unavailable'] for c in controls),
    }


def _recorded_waiver_qualification(report, query_instant):
    from .waivers import parse_timestamp

    waivers = []
    for result in report['results']:
        waiver = result.get('waiver')
        if waiver is None:
            continue
        valid_from = parse_timestamp(waiver['valid_from'], field='recorded waiver valid_from')
        expires_at = parse_timestamp(waiver['expires_at'], field='recorded waiver expires_at')
        qualification = ('not_yet_in_window' if query_instant < valid_from else
                         'within_window' if query_instant < expires_at else 'expired')
        waivers.append({
            'instance_id': result['instance_id'],
            'waiver_id': waiver['id'],
            'valid_from': waiver['valid_from'],
            'expires_at': waiver['expires_at'],
            'qualification': qualification,
        })
    counts = Counter(item['qualification'] for item in waivers)
    return {'waivers': waivers, 'counts': {key: counts[key] for key in
            ('within_window', 'expired', 'not_yet_in_window')}}


def qualify_operation(account, reports, query_instant: datetime, comparison_anchor=None):
    """Add independent query-time dimensions without changing frozen accounting."""
    from .artifact_validation import validate_assessment_plan
    from .assessment_provenance import operation_plan_id

    comparison_members = {}
    if comparison_anchor is not None:
        validate_assessment_plan(comparison_anchor)
        comparison_members = {
            row['subject_id']: operation_plan_id(
                row['plan_content_digest'], comparison_anchor['operation']
            )
            for row in comparison_anchor['operation']['members']
        }
    reports_by_id = {report['id']: report for report in reports}
    for row in account['members']:
        comparison_plan_id = comparison_members.get(row['subject_id'])
        alignment = ('plan_alignment_unavailable' if comparison_anchor is None or comparison_plan_id is None
                     else 'plan_aligned' if comparison_plan_id == row['plan_id'] else 'different_plan')
        row['plan_alignment'] = alignment
        row['historical_outcome'] = row['state'] if row['result_id'] else 'no_assessment'
        report = reports_by_id.get(row['result_id'])
        if report is None:
            row['evidence_timeliness'] = {'qualification': 'unavailable'}
            row['recorded_waiver_qualification'] = {'waivers': [], 'counts': {
                'within_window': 0, 'expired': 0, 'not_yet_in_window': 0}}
            continue
        timeliness = _evidence_timeliness(report, query_instant)
        row['evidence_timeliness'] = timeliness
        row['recorded_waiver_qualification'] = _recorded_waiver_qualification(report, query_instant)
    account['query_instant'] = query_instant.isoformat().replace('+00:00', 'Z')
    account['qualification_summary'] = summarize_qualifications(account['members'])
    account['all_passed_meaning'] = (
        'all frozen historical member outcomes passed at the selected assessment instant'
    )
    return account


def summarize_qualifications(rows):
    """Aggregate each operational dimension without imposing precedence."""
    totals = Counter()
    for row in rows:
        totals['historical_outcomes.' + row['historical_outcome']] += 1
        totals['plan_alignment.' + row['plan_alignment']] += 1
        totals['coverage.' + row['coverage']['status']] += 1
        timing = row['evidence_timeliness']
        if timing.get('qualification') == 'unavailable':
            totals['subjects.evidence_timeliness_unavailable'] += 1
        else:
            if timing['controls_needing_reassessment']:
                totals['subjects.needing_reassessment'] += 1
            if timing['controls_with_unavailable_timeliness']:
                totals['subjects.evidence_timeliness_unavailable'] += 1
            if timing['controls'] and all(c['within_recorded_age_limits'] for c in timing['controls']):
                totals['subjects.within_recorded_age_limits'] += 1
            for key in ('timely_selected_dependencies', 'stale_selected_dependencies',
                        'unavailable_required_dependencies', 'controls_within_recorded_age_limits',
                        'controls_needing_reassessment', 'controls_with_unavailable_timeliness'):
                totals['evidence_timeliness.' + key] += timing[key]
        for key, value in row['recorded_waiver_qualification']['counts'].items():
            totals['recorded_waivers.' + key] += value
    return dict(sorted(totals.items()))
