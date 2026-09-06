"""Embedded frozen operation facts inside assessment plans and results.

This is a projection of supplied planning facts, not another inventory or run
artifact. Sibling policy bodies are committed by digest, never embedded as plans.
"""
from __future__ import annotations

import copy
from collections import Counter
from datetime import datetime

from .assessment_provenance import digest


OPERATION_DOMAIN = 'compliance.example/frozen-operation/v1alpha1'


class InvalidOperationResolution(ValueError):
    """Supplied policy resolved to an invalid selected member, refusing assessment."""


def policy_membership(plan):
    """Retain only exact historical result slots and reporting mappings."""
    source = plan.get('resolved_policy', plan)
    controls = [{
        'instance_id': control['instance_id'],
        'disposition': control['disposition'],
        'external_refs': copy.deepcopy(control.get('external_refs', [])),
    } for field in ('controls', 'excluded_controls') for control in source.get(field, [])]
    requirements = [{
        'reference': requirement['reference'],
        'required': requirement['required'],
        'external_refs': copy.deepcopy(requirement.get('external_refs', [])),
    } for requirement in source['requirements']]
    return {
        'requirements': sorted(requirements, key=lambda item: item['reference']),
        'controls': sorted(controls, key=lambda item: item['instance_id']),
    }


def normalize_request(selection):
    request = {
        'all': bool(selection.get('all', False)),
        'subjects': sorted(set(selection.get('subjects', []))),
        'groups': sorted(set(selection.get('groups', []))),
    }
    if request['all'] and (request['subjects'] or request['groups']):
        raise ValueError('--all is exclusive of explicit subjects and groups')
    if not request['all'] and not (request['subjects'] or request['groups']):
        raise ValueError('empty operation selection')
    return request


def _relevant_group_ids(groups, requested):
    """Return requested groups and every descendant that can feed them."""
    relevant = set(requested)
    changed = True
    while changed:
        changed = False
        for group in groups:
            if group['id'] not in relevant and relevant.intersection(group.get('parents', [])):
                relevant.add(group['id'])
                changed = True
    return relevant


def freeze_selection_witness(subjects, groups, request):
    if not request['groups']:
        return ({'mode': 'all', 'subject_ids': sorted(subjects)}
                if request['all'] else {'mode': 'explicit'})
    relevant = _relevant_group_ids(groups, request['groups'])
    witness_groups = []
    selector_keys = set()
    for source in sorted((g for g in groups if g['id'] in relevant), key=lambda g: g['id']):
        group = {'id': source['id'],
                 'parents': sorted(parent for parent in source.get('parents', []) if parent in relevant)}
        members = sorted(member for member in source.get('members', []) if member in subjects)
        if members:
            group['members'] = members
        if 'selector' in source:
            group['selector'] = copy.deepcopy(source['selector'])
            selector_keys.update(source['selector'].get('match_labels', {}))
        witness_groups.append(group)
    witness = {'mode': 'groups', 'groups': witness_groups}
    if selector_keys:
        witness['candidates'] = [{
            'subject_id': subject_id,
            'labels': {key: subjects[subject_id].get('labels', {})[key]
                       for key in sorted(selector_keys)
                       if key in subjects[subject_id].get('labels', {})},
        } for subject_id in sorted(subjects)]
    return witness


def select_subjects(subjects, groups, selection):
    from .render_plan import resolve_groups, validate_group_dag
    selection = normalize_request(selection)
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


def select_from_witness(request, witness):
    """Rederive the exact denominator without mutable inventory."""
    request = normalize_request(request)
    if request['all']:
        if witness.get('mode') != 'all':
            raise ValueError('frozen selection witness mode differs from request')
        if witness['subject_ids'] != sorted(set(witness['subject_ids'])):
            raise ValueError('all-selection domain must use canonical subject order')
        return sorted(witness['subject_ids'])
    selected = set(request['subjects'])
    if not request['groups']:
        if witness != {'mode': 'explicit'}:
            raise ValueError('explicit selection has extraneous frozen witness facts')
        return sorted(selected)
    if witness.get('mode') != 'groups':
        raise ValueError('frozen selection witness mode differs from request')
    groups = witness['groups']
    group_ids = [group['id'] for group in groups]
    if group_ids != sorted(set(group_ids)):
        raise ValueError('frozen selection groups must use canonical identity order')
    known_groups = set(group_ids)
    for group in groups:
        for field in ('parents', 'members'):
            values = group.get(field, [])
            if values != sorted(set(values)):
                raise ValueError(f'frozen group {field} must use canonical identity order')
        if set(group.get('parents', [])) - known_groups:
            raise ValueError('frozen group parent is absent from relevant closure')
    selector_keys = {key for group in groups
                     for key in group.get('selector', {}).get('match_labels', {})}
    if selector_keys:
        candidates = witness.get('candidates')
        if candidates is None:
            raise ValueError('selector witness is missing its candidate domain')
        subject_rows = {row['subject_id']: {'id': row['subject_id'], 'labels': row['labels']}
                        for row in candidates}
        if len(subject_rows) != len(candidates):
            raise ValueError('duplicate selector candidate identity')
        if [row['subject_id'] for row in candidates] != sorted(subject_rows):
            raise ValueError('selector candidates must use canonical subject order')
        explicit_members = {member for group in groups
                            for member in group.get('members', [])}
        if explicit_members - subject_rows.keys():
            raise ValueError('explicit group member is absent from selector candidate domain')
        for row in candidates:
            if set(row['labels']) - selector_keys:
                raise ValueError('selector candidate contains an unconsulted label')
    else:
        if 'candidates' in witness:
            raise ValueError('selector-free witness has an unnecessary candidate domain')
        subject_rows = {member: {'id': member, 'labels': {}}
                        for group in groups for member in group.get('members', [])}
    from .render_plan import resolve_groups, validate_group_dag
    catalog = {group['id']: group for group in groups}
    if len(catalog) != len(groups):
        raise ValueError('duplicate frozen group identity')
    validate_group_dag(catalog)
    if set(request['groups']) - catalog.keys():
        raise ValueError('requested group is absent from frozen witness')
    if _relevant_group_ids(groups, request['groups']) != set(catalog):
        raise ValueError('frozen group witness contains an unrelated group')
    for subject_id, subject in subject_rows.items():
        if set(request['groups']) & {group['id'] for group in resolve_groups(catalog, subject)}:
            selected.add(subject_id)
    return sorted(selected)


def _member_resolved_groups(plan):
    """Keep only membership attribution needed to derive applicable assignments."""
    source = plan.get('resolved_policy', plan)
    by_id = {group['id']: group for group in source['resolved_groups']}
    needed = {assignment['group'] for assignment in source['assignments']}
    pending = list(needed)
    while pending:
        group = by_id.get(pending.pop())
        if group is None:
            continue
        for membership in group['sources']:
            for child in membership.get('via', []):
                if child not in needed:
                    needed.add(child)
                    pending.append(child)
    return copy.deepcopy(sorted((by_id[group_id] for group_id in needed),
                                key=lambda group: group['id']))


def _member_subject(plan):
    source = plan.get('resolved_policy', plan)
    subject = source.get('subject', plan.get('subject'))
    label_keys = set()
    for group in _member_resolved_groups(plan):
        for membership in group['sources']:
            selector = membership.get('source')
            if isinstance(selector, dict):
                label_keys.update(selector.get('match_labels', {}))
    for requirement in source['requirements']:
        realization = requirement.get('parameter_facts', {}).get('realization', {})
        label_keys.update(realization.get('spec', {}).get('applies_to', {}).get('match_labels', {}))
    return {
        'id': subject['id'], 'type': subject['type'], 'status': subject['status'],
        'labels': {key: subject.get('labels', {})[key] for key in sorted(label_keys)
                   if key in subject.get('labels', {})},
    }


def member_facts(plan):
    """Bind compact attribution and slots to complete resolved member intent."""
    from .assessment_provenance import member_plan_digest
    subject = _member_subject(plan)
    subject_id = subject.pop('id')
    return {
        'subject_id': subject_id,
        'subject': subject,
        'member_plan_digest': member_plan_digest(plan),
        'resolved_groups': _member_resolved_groups(plan),
        'policy': policy_membership(plan),
    }


def member_disposition(member, assignments):
    if member['subject']['status'] == 'retired':
        return 'inactive'
    groups = {group['id'] for group in member['resolved_groups']}
    applicable = [assignment for assignment in assignments if assignment['target_group'] in groups]
    if not applicable:
        return 'unassigned'
    active_controls = [control for control in member['policy']['controls']
                       if control['disposition'] == 'evaluate']
    if not active_controls and not member['policy']['requirements']:
        return 'no_assessable_policy'
    return 'result_required'


def plan_disposition(plan):
    if plan['resolution']['status'] != 'valid':
        return 'invalid'
    if plan['subject']['status'] == 'retired':
        return 'inactive'
    if not plan['assignments']:
        return 'unassigned'
    if not plan['controls'] and not plan['requirements']:
        return 'no_assessable_policy'
    return 'result_required'


def plan_coverage(plan):
    """Derive the legacy presentation dimensions; they are not frozen facts."""
    disposition = plan_disposition(plan)
    status = ('assigned' if disposition in ('result_required', 'no_assessable_policy')
              else disposition)
    reason = {
        'invalid': 'resolution-errors', 'inactive': 'subject-retired',
        'unassigned': 'no-policy-assignment', 'no_assessable_policy': 'no-active-controls',
        'result_required': 'policy-assigned',
    }[disposition]
    return {
        'status': status,
        'assessable': disposition == 'result_required',
        'reason': reason,
        'assignment_count': len(plan['assignments']),
        'active_control_count': len(plan['controls']),
        'excluded_control_count': len(plan['excluded_controls']),
        'requirement_count': len(plan['requirements']),
    }


def freeze_operation(plans, subjects, groups, assignments, selection):
    """Freeze all rows before evaluation; mutate only the generated subject plans."""
    from .assessment_provenance import artifact_digest
    request = normalize_request(selection)
    witness = freeze_selection_witness(subjects, groups, request)
    selected_groups = {g['id'] for plan in plans for g in plan['resolved_groups']}
    canonical_assignments = [{
        'id': assignment['id'],
        'target_group': assignment['target']['group'],
        'baselines': sorted(assignment['baselines']),
    } for assignment in sorted(assignments, key=lambda item: item['id'])
        if assignment['target']['group'] in selected_groups]
    projection = {
        'domain': OPERATION_DOMAIN,
        'request': request,
        'selection_witness': witness,
        'planning_composition': {k: copy.deepcopy(plans[0]['provenance']['planningComposition'][k])
                                 for k in ('compositionDigestAlgorithm', 'compositionDigest')},
        'assignments': canonical_assignments,
        'members': [member_facts(plan) for plan in sorted(plans, key=lambda p: p['subject']['id'])],
    }
    projection['operation_id'] = digest(projection)
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
    freeze_operation(plans, subjects, groups, assignments, selection)
    for plan in plans:
        validate_assessment_plan(plan)
    return plans


def validate_operation(document, *, plan):
    from .assessment_provenance import member_plan_digest, operation_plan_id
    projection = document['operation']
    stage = document['provenance']['planningComposition']
    if projection['domain'] != OPERATION_DOMAIN:
        raise ValueError('invalid frozen operation domain')
    semantic = {key: copy.deepcopy(value) for key, value in projection.items()
                if key != 'operation_id'}
    if projection['operation_id'] != digest(semantic):
        raise ValueError('frozen operation identity mismatch')
    if projection['planning_composition'] != {
            k: stage[k] for k in ('compositionDigestAlgorithm', 'compositionDigest')}:
        raise ValueError('artifact planning composition differs from frozen operation')
    request = normalize_request(projection['request'])
    if request != projection['request']:
        raise ValueError('operation request is not normalized')
    expected = select_from_witness(request, projection['selection_witness'])
    members = projection['members']
    if [member['subject_id'] for member in members] != expected:
        raise ValueError('frozen operation membership differs from selection')
    assignments = projection['assignments']
    if assignments != sorted(assignments, key=lambda item: item['id']):
        raise ValueError('frozen operation facts must use canonical identity order')
    if len({a['id'] for a in assignments}) != len(assignments):
        raise ValueError('duplicate frozen assignment identity')
    for assignment in assignments:
        if assignment['baselines'] != sorted(set(assignment['baselines'])):
            raise ValueError('frozen assignment baselines must use canonical identity order')
        if not any(assignment['target_group'] in {g['id'] for g in row['resolved_groups']}
                   for row in members):
            raise ValueError('frozen operation contains an unrelated assignment')
    for row in members:
        sid = row['subject_id']
        if row['resolved_groups'] != sorted(row['resolved_groups'], key=lambda item: item['id']):
            raise ValueError('frozen resolved groups must use canonical identity order')
        policy = row['policy']
        for field, identity in (('requirements','reference'), ('controls','instance_id')):
            values = [item[identity] for item in policy[field]]
            if values != sorted(set(values)):
                raise ValueError('duplicate or unordered frozen operation policy instances')
        if (row['subject']['status'] == 'unknown' and not
                (plan and document['resolution']['status'] == 'invalid' and len(members) == 1)):
            raise ValueError('unknown lifecycle prevents operation planning')
        if not any(assignment['target_group'] in {g['id'] for g in row['resolved_groups']}
                   for assignment in assignments) and policy['controls'] + policy['requirements']:
            raise ValueError('unassigned member has frozen expected policy')
    sid = document['subject']['id'] if plan else document['subject_id']
    rows = {m['subject_id']: m for m in members}
    if sid not in rows:
        raise ValueError('artifact subject is absent from frozen operation')
    row = rows[sid]
    source = document if plan else document['resolved_policy']
    artifact_assignments = sorted(({
        'id': assignment['id'],
        'target_group': assignment['group'],
        'baselines': sorted(assignment['baselines']),
    } for assignment in source['assignments']), key=lambda item: item['id'])
    row_groups = {group['id'] for group in row['resolved_groups']}
    expected_assignments = [assignment for assignment in assignments
                            if assignment['target_group'] in row_groups]
    if artifact_assignments != expected_assignments:
        raise ValueError('artifact assignments differ from frozen operation attribution')
    if plan:
        if member_facts(document) != row or member_plan_digest(document) != row['member_plan_digest']:
            raise ValueError('subject plan differs from frozen operation')
    else:
        if member_disposition(row, assignments) != 'result_required':
            raise ValueError('result supplied for non-assessable operation member')
        if (document['plan_id'] != operation_plan_id(projection['operation_id'], sid) or
                member_plan_digest(document) != row['member_plan_digest']):
            raise ValueError('result plan differs from frozen operation')
    if policy_membership(document if plan else document['resolved_policy']) != row['policy']:
        raise ValueError('artifact policy differs from frozen policy membership in operation')


def account_operation(anchor, reports, evaluated_at):
    """Exact-set historical accounting; result discovery never supplies the scope."""
    from .artifact_validation import validate_assessment_plan, validate_assessment_results
    from .assessment_provenance import operation_plan_id
    from .assessment import result_state
    validate_assessment_plan(anchor)
    projection = anchor['operation']
    for report in reports:
        validate_assessment_results(report)
    rows = []
    for member in projection['members']:
        sid = member['subject_id']
        plan_id = operation_plan_id(projection['operation_id'], sid)
        candidates = [r for r in reports if r['subject_id'] == sid and
                      r['plan_id'] == plan_id and r['operation'] == projection and
                      r['evaluated_at'] == evaluated_at]
        # Complete-document copies only. Equal semantic IDs with different
        # descriptive/enforcement bytes do not invent result-selection precedence.
        unique = {digest(r): r for r in candidates}
        if len(unique) > 1:
            raise ValueError('multiple distinct results for exact operation member and instant')
        result = next(iter(unique.values()), None)
        disposition = member_disposition(member, projection['assignments'])
        state = ((result_state(result) if result else 'missing')
                 if disposition == 'result_required' else disposition)
        rows.append({**copy.deepcopy(member), 'plan_id': plan_id, 'state': state,
                     'accounting_disposition': disposition,
                     'result_id': result['id'] if result else None})
    return {'operation': copy.deepcopy(projection), 'evaluated_at': evaluated_at,
            'members': rows,
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
        required = list(enumerate(control['evidence']))
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
                comparison_anchor['operation']['operation_id'], row['subject_id']
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
        totals['coverage.' + row['accounting_disposition']] += 1
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
