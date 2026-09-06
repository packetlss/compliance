"""Closed-world accounting is independent of result discovery and current inputs."""
import copy
import json
import unittest
from datetime import timedelta
from unittest.mock import patch

from assessment_fixture import refresh_operation
import test_assessment_v4 as fixtures
from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment_provenance import artifact_digest
from tools.evaluate_plan import evaluate_plan_document, control_error_result
from tools.operation import (
    account_operation, freeze_operation, freeze_selection_witness, normalize_request,
    qualify_operation, plan_disposition, select_from_witness, select_subjects,
)
from tools.policy_diff import build_policy_diff
from tools.render_plan import resolve_groups


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AssessmentV4Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.instant = self.fixture.now.isoformat().replace('+00:00', 'Z')

    def plans(self, ids=('host/A', 'host/B'), *, non_assessable=None):
        plans = []
        for sid in ids:
            plan = copy.deepcopy(self.fixture.plan)
            plan['subject']['id'] = sid
            if non_assessable and sid == ids[-1]:
                plan['controls'] = []
                plan['resolved_baselines'] = []
                plan['assignments'] = []
                plan['resolved_groups'] = []
            refresh_operation(plan)
            plans.append(plan)
        groups = [{'id': 'test-hosts', 'parents': [],
                   'members': list(ids[:-1] if non_assessable else ids)}]
        assignments = [{'id': 'test-policy', 'target': {'group': 'test-hosts'},
                        'baselines': ['test.baseline@1']}]
        subjects = {p['subject']['id']: p['subject'] for p in plans}
        freeze_operation(plans, subjects, groups, assignments,
                         {'subjects': list(ids), 'groups': [], 'all': False})
        for plan in plans:
            validate_assessment_plan(plan)
        return plans

    def evaluate(self, plans, *, instant=None):
        documents = [self.fixture.document(id='evidence:'+p['subject']['id'],
                     subject={'id':p['subject']['id'], 'type':p['subject']['type']}) for p in plans]
        self.fixture.write(documents)
        def decide(opa, sources, data, entrypoint):
            result = control_error_result(data, 'Qualifying observation')
            result['status'] = 'pass'
            return result
        with patch('tools.evaluate_plan.evaluate_control', side_effect=decide):
            return [evaluate_plan_document(p, self.fixture.evidence, self.fixture.sources,
                    evaluated_at=instant or self.fixture.now) for p in plans
                    if plan_disposition(p) == 'result_required']

    @staticmethod
    def subject(subject_id, labels=None):
        return {'id': subject_id, 'type': 'linux-host', 'status': 'active',
                'labels': labels or {}}

    def test_explicit_selection_ignores_supplied_nonselected_candidate(self):
        plans = self.plans()
        groups = [{'id':'test-hosts','parents':[],'members':['host/A','host/B']}]
        assignments = [{'id':'test-policy','target':{'group':'test-hosts'},
                        'baselines':['test.baseline@1']}]
        subjects = {plan['subject']['id']: plan['subject'] for plan in plans}
        baseline = copy.deepcopy(plans)
        freeze_operation(baseline, subjects, groups, assignments,
                         {'all':False,'subjects':['host/B','host/A'],'groups':[]})
        expanded = copy.deepcopy(plans)
        freeze_operation(expanded, {**subjects, 'host/C': self.subject('host/C')},
                         groups, assignments,
                         {'all':False,'subjects':['host/A','host/B'],'groups':[]})
        self.assertEqual(baseline[0]['operation'], expanded[0]['operation'])
        self.assertEqual([plan['id'] for plan in baseline], [plan['id'] for plan in expanded])

    def test_selector_candidate_domain_and_matching_mutations(self):
        all_plans = self.plans(('host/A','host/B','host/C'))
        groups = [
            {'id':'test-hosts','parents':[],'members':['host/A','host/B','host/C']},
            {'id':'selected','parents':[],'selector':{'match_labels':{'env':'prod'}}},
        ]
        assignments = [{'id':'test-policy','target':{'group':'test-hosts'},
                        'baselines':['test.baseline@1']}]
        subjects = {
            'host/A': self.subject('host/A', {'env':'prod'}),
            'host/B': self.subject('host/B', {'env':'prod'}),
            'host/C': self.subject('host/C', {'env':'dev','unrelated':'ignored'}),
        }
        for plan in all_plans:
            plan['subject'] = copy.deepcopy(subjects[plan['subject']['id']])
            refresh_operation(plan)
        without_c = copy.deepcopy(all_plans[:2])
        freeze_operation(without_c, {key:subjects[key] for key in ('host/A','host/B')},
                         groups, assignments, {'all':False,'subjects':[],'groups':['selected']})
        nonmatching_c = copy.deepcopy(all_plans[:2])
        freeze_operation(nonmatching_c, subjects, groups, assignments,
                         {'all':False,'subjects':[],'groups':['selected']})
        self.assertEqual(
            [row['member_plan_digest'] for row in without_c[0]['operation']['members']],
            [row['member_plan_digest'] for row in nonmatching_c[0]['operation']['members']],
        )
        self.assertNotEqual(without_c[0]['operation']['operation_id'],
                            nonmatching_c[0]['operation']['operation_id'])
        self.assertNotEqual([p['id'] for p in without_c], [p['id'] for p in nonmatching_c])
        self.assertEqual(nonmatching_c[0]['operation']['selection_witness']['candidates'][-1],
                         {'subject_id':'host/C','labels':{'env':'dev'}})

        matching_subjects = copy.deepcopy(subjects)
        matching_subjects['host/C']['labels']['env'] = 'prod'
        matching = copy.deepcopy(all_plans)
        matching[-1]['subject'] = copy.deepcopy(matching_subjects['host/C'])
        refresh_operation(matching[-1])
        freeze_operation(matching, matching_subjects, groups, assignments,
                         {'all':False,'subjects':[],'groups':['selected']})
        self.assertEqual([row['subject_id'] for row in matching[0]['operation']['members']],
                         ['host/A','host/B','host/C'])
        self.assertNotEqual(nonmatching_c[0]['operation']['operation_id'],
                            matching[0]['operation']['operation_id'])
        self.assertNotEqual(nonmatching_c[0]['id'], matching[0]['id'])

    def test_selector_free_group_mixed_union_and_all_modes(self):
        subjects = {sid:self.subject(sid) for sid in ('host/A','host/B','host/C')}
        groups = [{'id':'selected','parents':[],'members':['host/A']}]
        group_request = normalize_request({'all':False,'subjects':[],'groups':['selected']})
        witness = freeze_selection_witness(subjects, groups, group_request)
        self.assertNotIn('candidates', witness)
        self.assertEqual(select_from_witness(group_request, witness), ['host/A'])
        mixed = normalize_request({'all':False,'subjects':['host/B'],'groups':['selected']})
        self.assertEqual(select_from_witness(mixed, freeze_selection_witness(subjects, groups, mixed)),
                         ['host/A','host/B'])
        all_request = normalize_request({'all':True,'subjects':[],'groups':[]})
        all_witness = freeze_selection_witness(subjects, groups, all_request)
        self.assertEqual(all_witness, {'mode':'all','subject_ids':['host/A','host/B','host/C']})
        self.assertEqual(select_from_witness(all_request, all_witness),
                         ['host/A','host/B','host/C'])

    def test_empty_valid_group_and_unmatched_descendant_are_frozen(self):
        subjects = {'host/A':self.subject('host/A', {'env':'prod'})}
        groups = [
            {'id':'requested','parents':[]},
            {'id':'empty-child','parents':['requested'],
             'selector':{'match_labels':{'env':'never'}}},
            {'id':'unrelated','parents':[],'members':['host/A']},
        ]
        request = normalize_request({'all':False,'subjects':[],'groups':['requested']})
        witness = freeze_selection_witness(subjects, groups, request)
        self.assertEqual([group['id'] for group in witness['groups']],
                         ['empty-child','requested'])
        self.assertEqual(select_from_witness(request, witness), [])
        with self.assertRaisesRegex(ValueError, 'unresolved operation selection'):
            select_subjects(subjects, groups, {'all':False,'subjects':[],'groups':['unknown']})

    def test_same_denominator_different_request_changes_only_bound_context(self):
        plan = self.plans(('host/A',))[0]
        subject = {'host/A': plan['subject']}
        assignment = [{'id':'test-policy','target':{'group':'test-hosts'},
                       'baselines':['test.baseline@1']}]
        groups = [{'id':'test-hosts','parents':[],'members':['host/A']}]
        explicit = copy.deepcopy(plan)
        freeze_operation([explicit], subject, groups, assignment,
                         {'all':False,'subjects':['host/A'],'groups':[]})
        grouped = copy.deepcopy(plan)
        freeze_operation([grouped], subject, groups, assignment,
                         {'all':False,'subjects':[],'groups':['test-hosts']})
        self.assertEqual(explicit['operation']['members'][0]['member_plan_digest'],
                         grouped['operation']['members'][0]['member_plan_digest'])
        self.assertNotEqual(explicit['operation']['operation_id'],
                            grouped['operation']['operation_id'])
        self.assertNotEqual(explicit['id'], grouped['id'])

    def test_unrelated_group_assignment_and_label_do_not_change_identity(self):
        baseline = self.plans(('host/A',))[0]
        subject = copy.deepcopy(baseline['subject'])
        groups = [{'id':'test-hosts','parents':[],'members':['host/A']}]
        assignments = [{'id':'test-policy','target':{'group':'test-hosts'},
                        'baselines':['test.baseline@1']}]
        first = copy.deepcopy(baseline)
        freeze_operation([first], {'host/A':subject}, groups, assignments,
                         {'all':False,'subjects':['host/A'],'groups':[]})
        changed_subject = copy.deepcopy(subject)
        changed_subject['labels']['unrelated'] = 'value'
        second = copy.deepcopy(baseline)
        second['subject'] = changed_subject
        freeze_operation([second], {'host/A':changed_subject},
                         [*groups, {'id':'unrelated','parents':[]}],
                         [*assignments, {'id':'unrelated-assignment',
                                        'target':{'group':'unrelated'},'baselines':['unused@1']}],
                         {'all':False,'subjects':['host/A'],'groups':[]})
        self.assertEqual(first['operation'], second['operation'])
        self.assertEqual(first['id'], second['id'])

    def test_selected_member_type_and_lifecycle_are_member_semantics(self):
        original = self.plans(('host/A',))[0]
        for field, value in (('type','other-host'), ('status','retired')):
            changed = copy.deepcopy(original)
            changed['subject'][field] = value
            refresh_operation(changed)
            self.assertNotEqual(
                original['operation']['members'][0]['member_plan_digest'],
                changed['operation']['members'][0]['member_plan_digest'],
            )
            self.assertNotEqual(original['operation']['operation_id'],
                                changed['operation']['operation_id'])

    def test_exact_success_copies_and_missing_member(self):
        plans = self.plans(('host/A', 'host/B', 'host/C'))
        reports = self.evaluate(plans)
        complete = account_operation(plans[0], reports+[copy.deepcopy(reports[0])], self.instant)
        self.assertTrue(complete['accounting_complete'])
        self.assertTrue(complete['all_passed'])
        missing = account_operation(plans[0], reports[:2], self.instant)
        self.assertFalse(missing['accounting_complete'])
        self.assertFalse(missing['all_passed'])
        self.assertEqual([r['state'] for r in missing['members']], ['pass','pass','missing'])
        for report in reports[:2]:
            validate_assessment_results(report)

    def test_other_operation_and_instant_cannot_fill_slot(self):
        plans = self.plans()
        reports = self.evaluate(plans)
        singleton = self.plans(('host/B',))
        wrong_operation = self.evaluate(singleton)[0]
        wrong_time = self.evaluate(plans, instant=self.fixture.now+timedelta(seconds=1))[1]
        for substitute in (wrong_operation, wrong_time, reports[0]):
            account = account_operation(plans[0], [reports[0], substitute], self.instant)
            self.assertFalse(account['accounting_complete'])

    def test_operation_context_changes_identity_without_effective_policy_change(self):
        multiple = self.plans()
        singleton = copy.deepcopy(multiple[0])
        freeze_operation([singleton], {singleton['subject']['id']:singleton['subject']},
                         [{'id':'test-hosts','parents':[],'members':['host/A']}],
                         [{'id':'test-policy','target':{'group':'test-hosts'},'baselines':['test.baseline@1']}],
                         {'subjects':[singleton['subject']['id']], 'groups':[], 'all':False})
        self.assertNotEqual(singleton['id'], multiple[0]['id'])
        diff = build_policy_diff(singleton, multiple[0])
        self.assertFalse(diff['summary']['changed'])
        self.assertIn('operation_id', diff['context']['changed_fields'])

    def test_unassigned_accounted_without_pass_and_empty_selection_rejected(self):
        plans = self.plans(non_assessable=True)
        result = account_operation(plans[0], self.evaluate(plans), self.instant)
        self.assertTrue(result['accounting_complete'])
        self.assertFalse(result['all_passed'])
        self.assertEqual(result['members'][1]['state'], 'unassigned')
        with self.assertRaisesRegex(ValueError, 'empty operation'):
            select_subjects({}, [], {'subjects':[], 'groups':[], 'all':True})

    def test_internal_membership_tampering_survives_no_outer_resigning(self):
        anchor = self.plans()[0]
        for change in (
            lambda p: p['operation']['members'].pop(),
            lambda p: p['operation']['members'][1]['resolved_groups'].clear(),
            lambda p: p['operation']['members'][1]['policy']['controls'].clear(),
            lambda p: p['operation']['members'][1].update(member_plan_digest='sha256:'+'0'*64),
        ):
            changed = copy.deepcopy(anchor)
            change(changed)
            changed['id'] = artifact_digest(changed)
            with self.assertRaises(ValueError):
                validate_assessment_plan(changed)

    def test_sibling_member_commitment_tampering_is_rejected(self):
        anchor = self.plans()[0]
        for mutation in ('omit-controls', 'replace-member-commitment'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(anchor)
                row = changed['operation']['members'][1]
                if mutation == 'replace-member-commitment':
                    row['member_plan_digest'] = 'sha256:' + '0' * 64
                else:
                    row['policy']['controls'].clear()
                changed['id'] = artifact_digest(changed)
                with self.assertRaises(ValueError):
                    validate_assessment_plan(changed)
                with self.assertRaises(ValueError):
                    account_operation(changed, [], self.instant)

    def test_historical_accounting_does_not_reopen_policy_or_evidence(self):
        plans = self.plans()
        reports = self.evaluate(plans)
        expected = account_operation(plans[0], reports, self.instant)
        self.fixture.write([])
        with patch('tools.render_plan.load_policy_catalogs', side_effect=AssertionError('mutable policy')):
            self.assertEqual(account_operation(plans[0], reports, self.instant), expected)

    def test_query_time_timeliness_is_independent_and_inclusive(self):
        plans = self.plans(('host/A',))
        report = self.evaluate(plans)[0]
        collected = report['provenance']['selectedEvidence'][0]['collected_at']
        from tools.waivers import parse_timestamp
        boundary = parse_timestamp(collected) + timedelta(hours=24)
        at_boundary = qualify_operation(
            account_operation(plans[0], [report], self.instant), [report], boundary
        )
        row = at_boundary['members'][0]
        self.assertEqual(row['historical_outcome'], 'pass')
        self.assertEqual(row['plan_alignment'], 'plan_alignment_unavailable')
        self.assertEqual(row['evidence_timeliness']['timely_selected_dependencies'], 1)
        later = qualify_operation(
            account_operation(plans[0], [report], self.instant), [report],
            boundary + timedelta(seconds=1), plans[0]
        )
        row = later['members'][0]
        self.assertEqual(row['historical_outcome'], 'pass')
        self.assertEqual(row['plan_alignment'], 'plan_aligned')
        self.assertEqual(row['evidence_timeliness']['stale_selected_dependencies'], 1)

    def test_future_selected_timestamp_retains_adr_0011_rule(self):
        plans = self.plans(('host/A',))
        report = self.evaluate(plans)[0]
        query = self.fixture.now - timedelta(days=30)
        qualified = qualify_operation(
            account_operation(plans[0], [report], self.instant), [report], query
        )
        dependency = qualified['members'][0]['evidence_timeliness']['dependencies'][0]
        self.assertEqual(dependency['qualification'], 'timely')

    def test_stale_and_unavailable_dependencies_coexist_per_control(self):
        from tools.operation import _evidence_timeliness
        plans = self.plans(('host/A',))
        report = self.evaluate(plans)[0]
        missing = copy.deepcopy(report['resolved_policy']['controls'][0]['evidence'][0])
        missing.update(id='missing-observation', type='missing.observation/v1')
        report['resolved_policy']['controls'][0]['evidence'].append(missing)
        timing = _evidence_timeliness(report, self.fixture.now + timedelta(days=2))
        self.assertEqual(timing['stale_selected_dependencies'], 1)
        self.assertEqual(timing['unavailable_required_dependencies'], 1)
        self.assertTrue(timing['controls'][0]['reassessment_due'])
        self.assertTrue(timing['controls'][0]['timeliness_unavailable'])

    def test_different_operation_plan_and_missing_result_qualify_without_rewriting(self):
        historical = self.plans(('host/A',))
        comparison = self.plans(('host/A', 'host/B'))
        account = qualify_operation(
            account_operation(historical[0], [], self.instant), [], self.fixture.now,
            comparison[0]
        )
        row = account['members'][0]
        self.assertEqual(row['state'], 'missing')
        self.assertEqual(row['historical_outcome'], 'no_assessment')
        self.assertEqual(row['plan_alignment'], 'different_plan')
        self.assertEqual(row['evidence_timeliness'], {'qualification': 'unavailable'})

    def test_recorded_waiver_window_qualifies_but_never_rewrites_waived(self):
        waivers = self.fixture.root/'waivers'
        waivers.mkdir()
        (waivers/'exception.yaml').write_text(fixtures.fixtures.EvidenceFreshnessTests.waiver_resource())
        report, _ = self.fixture.run_assessment(
            [self.fixture.document()], status='fail', waiver_path=waivers
        )
        for query, expected in (
            ('2026-07-31T23:59:59Z', 'not_yet_in_window'),
            ('2026-08-23T12:00:00Z', 'within_window'),
            ('2026-09-01T00:00:00Z', 'expired'),
        ):
            from tools.waivers import parse_timestamp
            qualified = qualify_operation(
                account_operation(self.fixture.plan, [report], self.instant),
                [report], parse_timestamp(query),
            )
            row = qualified['members'][0]
            self.assertEqual(row['historical_outcome'], 'waived')
            self.assertEqual(
                row['recorded_waiver_qualification']['waivers'][0]['qualification'], expected
            )

    def test_direct_and_inherited_sources_are_both_preserved(self):
        subject = {'id':'host/A', 'labels':{}}
        groups = {'parent':{'id':'parent','members':['host/A']},
                  'left':{'id':'left','members':['host/A'],'parents':['parent']},
                  'right':{'id':'right','members':['host/A'],'parents':['parent']}}
        expected = resolve_groups(groups, subject)
        self.assertEqual(expected, resolve_groups(dict(reversed(list(groups.items()))), subject))
        parent = next(g for g in expected if g['id'] == 'parent')
        self.assertEqual(parent['sources'], [{'membership':'explicit','source':'group.members'},
                                           {'membership':'inherited','via':['left','right']}])

    def test_dangling_explicit_subject_reference_fails_catalog_loading(self):
        from tools.render_plan import load_inventory_catalog
        from tools.compliance import default_schema_path
        inventory = self.fixture.root/'inventory'
        assignments = self.fixture.root/'assignments'
        inventory.mkdir(); assignments.mkdir()
        (inventory/'group.json').write_text(json.dumps({
            'apiVersion':'compliance.example/v1alpha1', 'kind':'InventoryGroup',
            'metadata':{'name':'supplied'}, 'spec':{'subjectRefs':[{'id':'host/missing'}]},
        }))
        (assignments/'assignment.json').write_text(json.dumps({
            'apiVersion':'compliance.example/v1alpha1', 'kind':'PolicyAssignment',
            'metadata':{'name':'assigned'}, 'spec':{'targetRef':{'kind':'InventoryGroup','name':'supplied'},
                'baselineRefs':[{'name':'test','revision':'1'}]},
        }))
        with self.assertRaisesRegex(ValueError, 'unknown subjects: host/missing'):
            load_inventory_catalog(inventory, assignments, default_schema_path())

    def test_nonempty_operation_without_assessable_members_has_no_pass_basis(self):
        plans = self.plans()
        for plan in plans:
            plan['controls'] = []
            plan['requirements'] = []
            refresh_operation(plan)
        groups=[{'id':'test-hosts','parents':[],'members':['host/A','host/B']}]
        freeze_operation(plans, {p['subject']['id']:p['subject'] for p in plans},
                         groups, [{'id':'test-policy','target':{'group':'test-hosts'},'baselines':['test.baseline@1']}],
                         {'subjects':['host/A','host/B'],'groups':[],'all':False})
        account=account_operation(plans[0], [], self.instant)
        self.assertTrue(account['accounting_complete'])
        self.assertFalse(account['all_passed'])
        self.assertEqual([r['state'] for r in account['members']], ['no_assessable_policy','no_assessable_policy'])

    def test_freeze_is_independent_of_subject_assignment_and_group_traversal(self):
        plans=self.plans()
        expected=[p['id'] for p in plans]
        subjects={p['subject']['id']:p['subject'] for p in plans}
        groups=[{'id':'test-hosts','parents':[],'members':['host/B','host/A']}]
        assignments=[{'id':'test-policy','target':{'group':'test-hosts'},'baselines':['test.baseline@1']}]
        freeze_operation(list(reversed(plans)), dict(reversed(list(subjects.items()))),
                         list(reversed(groups)), list(reversed(assignments)),
                         {'subjects':['host/B','host/A'],'groups':[],'all':False})
        self.assertEqual([p['id'] for p in plans], expected)

    def test_result_plan_or_subject_substitution_is_refused(self):
        plans=self.plans()
        reports=self.evaluate(plans)
        for field in ('subject_id','plan_id'):
            changed=copy.deepcopy(reports[0])
            changed[field]=reports[1][field]
            changed['id']=artifact_digest(changed)
            with self.assertRaises(ValueError): validate_assessment_results(changed)
