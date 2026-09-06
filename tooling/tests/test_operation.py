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
from tools.operation import account_operation, freeze_operation, select_subjects
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
                plan['coverage'].update(status='unassigned', assessable=False, reason='no-policy-assignment',
                                        assignment_count=0, active_control_count=0)
            refresh_operation(plan)
            plans.append(plan)
        groups = copy.deepcopy(plans[0]['operation']['groups'])
        for group in groups:
            if 'members' in group:
                group['members'] = list(ids[:-1] if non_assessable else ids)
        subjects = {p['subject']['id']: p['subject'] for p in plans}
        freeze_operation(plans, subjects, groups, plans[0]['operation']['assignments'],
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
                    evaluated_at=instant or self.fixture.now) for p in plans if p['coverage']['assessable']]

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
        projection = singleton['operation']
        freeze_operation([singleton], {singleton['subject']['id']:singleton['subject']},
                         projection['groups'], projection['assignments'],
                         {'subjects':[singleton['subject']['id']], 'groups':[], 'all':False})
        # Nonselected explicit references are removed from the supplied projection.
        for group in singleton['operation']['groups']:
            if 'members' in group: group['members'] = ['host/A']
        singleton['id'] = artifact_digest(singleton)
        self.assertNotEqual(singleton['id'], multiple[0]['id'])
        diff = build_policy_diff(singleton, multiple[0])
        self.assertFalse(diff['summary']['changed'])
        self.assertIn('operation_digest', diff['context']['changed_fields'])

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
            lambda p: p['operation']['members'][1]['coverage'].update(assessable=False),
        ):
            changed = copy.deepcopy(anchor)
            change(changed)
            changed['id'] = artifact_digest(changed)
            with self.assertRaises(ValueError):
                validate_assessment_plan(changed)

    def test_correlated_sibling_membership_changes_cannot_keep_plan_commitment(self):
        anchor = self.plans()[0]
        for mutation in ('omit-controls', 'exclude-controls', 'replace-body-commitment'):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(anchor)
                row = changed['operation']['members'][1]
                if mutation == 'replace-body-commitment':
                    row['plan_body_digest'] = 'sha256:' + '0' * 64
                else:
                    if mutation == 'omit-controls':
                        row['policy']['controls'].clear()
                        for baseline in row['policy']['baselines']:
                            baseline['control_ids'] = []
                    else:
                        for control in row['policy']['controls']:
                            control['disposition'] = 'excluded'
                        row['coverage']['excluded_control_count'] = len(row['policy']['controls'])
                    row['coverage'].update(assessable=False, active_control_count=0,
                                           reason='no-active-controls')
                changed['id'] = artifact_digest(changed)
                with self.assertRaisesRegex(ValueError, 'member facts differ from plan content commitment'):
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
            plan['coverage'].update(assessable=False, active_control_count=0, reason='no-active-controls')
            refresh_operation(plan)
        projection=plans[0]['operation']
        groups=copy.deepcopy(projection['groups'])
        for group in groups:
            if 'members' in group: group['members']=['host/A','host/B']
        freeze_operation(plans, {p['subject']['id']:p['subject'] for p in plans},
                         groups, projection['assignments'], {'subjects':['host/A','host/B'],'groups':[],'all':False})
        account=account_operation(plans[0], [], self.instant)
        self.assertTrue(account['accounting_complete'])
        self.assertFalse(account['all_passed'])
        self.assertEqual([r['state'] for r in account['members']], ['no_controls','no_controls'])

    def test_freeze_is_independent_of_subject_assignment_and_group_traversal(self):
        plans=self.plans()
        expected=[p['id'] for p in plans]
        projection=copy.deepcopy(plans[0]['operation'])
        freeze_operation(list(reversed(plans)), {s['id']:s for s in reversed(projection['subjects'])},
                         list(reversed(projection['groups'])), list(reversed(projection['assignments'])),
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
