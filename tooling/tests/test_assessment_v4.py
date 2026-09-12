"""ADR 0007/0010/0011 conformance over exact historical evidence selection."""
import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from assessment_fixture import (
    assessment_plan,
    evidence_document,
    evidence_plan,
    evidence_schema,
    freeze_policy_inputs,
    refresh_operation,
    waiver_resource,
)
from tools.assessment_provenance import (
    PLAN_SCHEMA, PROVENANCE_SCHEMA, PLAN_DIGEST_ALGORITHM, artifact_digest, stage,
    result_identity_projection, validate_result_against_plan,
)
from tools.artifact_validation import (
    result_outcome, validate_assessment_plan, validate_assessment_results,
)
from tools.composition import require_composition, CompositionLock
from tools.evaluator import EvaluatorIdentity
from tools.evidence_provenance import evidence_document_digest
from tools.evaluate_plan import evaluate_plan_document, control_error_result


class AssessmentV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.plan = evidence_plan(self.root)
        self.sources = (self.source,)
        self.sign_plan()
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.now = datetime(2026, 8, 23, 12, tzinfo=UTC)
        self.evaluator = EvaluatorIdentity('opa', '1.18.2', 'sha256:'+'e'*64)
        self.identity = patch('tools.evaluator.resolve_opa_evaluator', return_value=(self.evaluator, '/resolved/opa')).start()
        self.addCleanup(patch.stopall)

    def sign_plan(self):
        freeze_policy_inputs(self.plan)
        self.plan['id'] = artifact_digest(self.plan)
        validate_assessment_plan(self.plan)

    def write(self, docs):
        for path in self.evidence.iterdir(): path.unlink()
        for index, doc in enumerate(docs):
            (self.evidence / f'{index}.json').write_text(json.dumps(doc))

    def document(self, **changes):
        return {**evidence_document(), **changes}

    def run_assessment(self, docs, *, status='pass', effect=None, **kwargs):
        self.write(docs)
        def decide(opa, sources, data, entrypoint):
            self.assertEqual(opa, '/resolved/opa')
            result = control_error_result(data, 'Synthetic decision')
            result['status'] = status
            return result
        with patch('tools.evaluate_plan.evaluate_control', side_effect=effect or decide) as opa:
            report = evaluate_plan_document(self.plan, self.evidence, self.sources, evaluated_at=self.now, **kwargs)
        validate_assessment_results(report)
        validate_result_against_plan(report, self.plan)
        return report, opa

    def test_selected_exact_document_and_temporal_facts_survive_mutable_sources(self):
        doc = self.document(collected_at='2026-08-23T11:00:00.123456Z')
        older = self.document(collected_at='2026-08-23T10:00:00Z')
        unused = self.document(id='unused', type='unused/v1')
        report, opa = self.run_assessment([older, doc, unused])
        self.assertEqual(opa.call_count, 1)
        use, = report['provenance']['selectedEvidence']
        self.assertEqual(use, {
            'instance_id':'test.check', 'dependency_id':'observation',
            'evidence_id':doc['id'], 'evidence_digest':evidence_document_digest(doc),
            'collected_at':doc['collected_at'],
        })
        self.assertEqual(len(report['provenance']['evidence']['documents']), 3)
        before = json.dumps(report, sort_keys=True)
        self.write([self.document(payload={'value':'replacement'})])
        self.write([])
        self.evidence.rmdir()
        validate_assessment_results(report)
        self.assertEqual(before, json.dumps(report, sort_keys=True))
        for name in ('fresh','stale','current','reassessment_due','operational_status'):
            self.assertNotIn('"'+name+'":', before)

    def test_unique_latest_and_identical_duplicates_and_older_ties(self):
        old = self.document(collected_at='2026-08-23T09:00:00Z')
        old2 = {**old, 'id':'old2'}
        latest = self.document()
        for docs in ([old,old2,latest], [old,latest,copy.deepcopy(latest)]):
            with self.subTest(docs=docs):
                report, opa = self.run_assessment(docs)
                self.assertEqual(report['outcome'], 'pass')
                self.assertEqual(opa.call_count, 1)
                self.assertEqual(len(report['provenance']['selectedEvidence']), 1)
                self.assertEqual(len(report['provenance']['evidence']['documents']), len(docs))

    def test_distinct_latest_is_unknown_no_opa_and_order_independent(self):
        first = self.document()
        for changes in ({'id':'other'}, {'collector':{'id':'different','version':'1'}}, {'extension':True}, {'payload':{'value':'other'}}):
            second = {**first, **changes}
            with self.subTest(changes=changes):
                a, opa = self.run_assessment([first,second])
                b, reverse = self.run_assessment([second,first])
                self.assertEqual(opa.call_count, 0)
                self.assertEqual(reverse.call_count, 0)
                self.assertEqual(a['id'], b['id'])
                self.assertEqual(a['outcome'], 'unknown')
                self.assertEqual(a['provenance']['selectedEvidence'], [])
                disposition, = a['dependency_dispositions']
                self.assertEqual(disposition['disposition'], 'ambiguous')
                self.assertEqual(len(disposition['candidates']), 2)

    def test_all_matching_candidates_validated_before_selection(self):
        good = self.document()
        for collected in ('2026-08-23T11:30:00Z','2020-01-01T00:00:00Z'):
            bad = self.document(payload={'value':False}, collected_at=collected)
            a, opa = self.run_assessment([good,bad])
            b, _ = self.run_assessment([bad,good])
            self.assertEqual(a['id'], b['id'])
            self.assertEqual(a['outcome'], 'unknown')
            self.assertEqual(opa.call_count, 0)
            self.assertEqual(a['provenance']['selectedEvidence'], [])
            disposition, = a['dependency_dispositions']
            self.assertEqual(disposition['disposition'], 'invalid')
            diagnostic, = disposition['diagnostics']
            self.assertEqual(diagnostic['evidence_digest'], evidence_document_digest(bad))
            self.assertEqual(diagnostic['schema_path'], '/properties/payload/properties/value/type')
            self.assertEqual(diagnostic['keyword'], 'type')
            for retired in ('path', 'message', 'schema_reference', 'evidence_type'):
                self.assertNotIn(retired, diagnostic)

    def test_missing_and_all_stale_no_opa(self):
        for docs in ([], [self.document(collected_at='2020-01-01T00:00:00Z')]):
            report, opa = self.run_assessment(docs)
            self.assertEqual(report['outcome'], 'unknown')
            self.assertEqual(opa.call_count, 0)

    def test_absent_and_greatest_stale_facts_are_exact_and_minimal(self):
        absent, opa = self.run_assessment([])
        self.assertEqual(opa.call_count, 0)
        self.assertEqual(absent['dependency_dispositions'], [{
            'instance_id': 'test.check',
            'dependency_id': 'observation',
            'disposition': 'absent',
        }])

        latest_a = self.document(
            id='latest-a', collected_at='2026-08-22T11:00:00Z'
        )
        latest_b = self.document(
            id='latest-b', collected_at='2026-08-22T13:00:00+02:00'
        )
        older = self.document(id='older', collected_at='2026-08-22T10:00:00Z')
        stale, opa = self.run_assessment([older, latest_b, latest_a])
        self.assertEqual(opa.call_count, 0)
        disposition, = stale['dependency_dispositions']
        self.assertEqual(disposition['disposition'], 'stale')
        self.assertEqual(
            [item['evidence_id'] for item in disposition['latest_candidates']],
            ['latest-a', 'latest-b'],
        )
        self.assertEqual(
            [item['collected_at'] for item in disposition['latest_candidates']],
            ['2026-08-22T11:00:00Z', '2026-08-22T13:00:00+02:00'],
        )
        self.assertNotIn('older', json.dumps(disposition))
        self.assertNotIn('payload', json.dumps(stale))

    def test_multiple_invalid_documents_retain_only_stable_safe_facts(self):
        first = self.document(id='invalid-a', payload={'value': False})
        second = self.document(
            id='invalid-b', collected_at='invalid', payload={'value': False}
        )
        report, opa = self.run_assessment([second, first])
        self.assertEqual(opa.call_count, 0)
        disposition, = report['dependency_dispositions']
        self.assertEqual(disposition['disposition'], 'invalid')
        diagnostics = disposition['diagnostics']
        self.assertEqual(
            diagnostics,
            sorted(diagnostics, key=lambda item: (
                item['evidence_id'], item['evidence_digest'], item['schema_path'],
                item['keyword'], item['code'],
            )),
        )
        self.assertEqual({item['evidence_id'] for item in diagnostics}, {
            'invalid-a', 'invalid-b',
        })
        serialized = json.dumps(report)
        for forbidden in ('schema_reference', 'evidence_type', 'message', 'path'):
            self.assertNotIn(f'"{forbidden}"', serialized)

    def test_criterion_unknown_is_distinct_from_dependency_unknown(self):
        report, opa = self.run_assessment([self.document()], status='unknown')
        self.assertEqual(opa.call_count, 1)
        self.assertEqual(report['results'][0]['status'], 'unknown')
        self.assertEqual(report['dependency_dispositions'], [])
        self.assertEqual(len(report['provenance']['selectedEvidence']), 1)
        self.assertNotIn('evaluation_error', report['results'][0])

    def test_invalid_routing_and_snapshot_refuse_before_opa(self):
        for doc in ([], self.document(subject=None), self.document(subject={}), self.document(type=None), self.document(id=''), self.document(payload={'value':float('nan')})):
            with self.subTest(doc=doc), patch('tools.evaluate_plan.evaluate_control') as opa:
                self.write([doc])
                with self.assertRaises(ValueError):
                    evaluate_plan_document(self.plan, self.evidence, self.sources, evaluated_at=self.now)
                opa.assert_not_called()

    def test_unusable_decision_and_scoped_exception_are_errors(self):
        for effect in (lambda *a: [], lambda *a: {}, lambda *a: None, RuntimeError('scoped')):
            report, opa = self.run_assessment([self.document()], effect=effect)
            self.assertEqual(report['outcome'], 'error')
            self.assertEqual(len(report['provenance']['selectedEvidence']), 1)

    def test_closed_error_classes_use_safe_fixed_facts_and_distinct_identity(self):
        cases = (
            (
                RuntimeError('private backend message'),
                'criterion_execution',
                'criterion_execution_failed',
                'Criterion execution failed.',
            ),
            (
                lambda *args: {'unusable': 'private returned value'},
                'criterion_decision',
                'criterion_decision_invalid',
                'Criterion decision was unusable.',
            ),
            (
                None,
                'criterion_decision',
                'criterion_reported_error',
                'Criterion reported an evaluation error.',
            ),
        )
        reports = []
        for effect, stage_name, code, reason in cases:
            with self.subTest(code=code):
                kwargs = {'effect': effect} if effect is not None else {'status': 'error'}
                report, opa = self.run_assessment([self.document()], **kwargs)
                result, = report['results']
                self.assertEqual(opa.call_count, 1)
                self.assertEqual(result, {
                    'instance_id': 'test.check',
                    'status': 'error',
                    'reason': reason,
                    'expected': {},
                    'observed': {},
                    'evaluation_error': {'stage': stage_name, 'code': code},
                })
                serialized = json.dumps(report)
                self.assertNotIn('private backend message', serialized)
                self.assertNotIn('private returned value', serialized)
                reports.append(report)
        self.assertEqual(len({report['id'] for report in reports}), 3)

    def test_mutated_provenance_identity_and_reference_validation(self):
        report, _ = self.run_assessment([self.document()])
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['collected_at'] = '2026-08-23T10:59:00Z'
        self.assertNotEqual(artifact_digest(changed), report['id'])
        with self.assertRaises(ValueError): validate_assessment_results(changed)
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['evidence_digest'] = 'sha256:'+'0'*64
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'absent from snapshot'): validate_assessment_results(changed)
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['dependency_id'] = 'missing'
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'assessed plan'):
            validate_result_against_plan(changed, self.plan)

    def test_relational_validation_requires_complete_fresh_successful_selections(self):
        report, _ = self.run_assessment([self.document()])
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'] = []
        changed['id'] = artifact_digest(changed)
        validate_assessment_results(changed)
        with self.assertRaisesRegex(ValueError, 'partition required plan dependencies'):
            validate_result_against_plan(changed, self.plan)

        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['collected_at'] = '2020-01-01T00:00:00Z'
        changed['id'] = artifact_digest(changed)
        validate_assessment_results(changed)
        with self.assertRaisesRegex(ValueError, 'stale at the assessment instant'):
            validate_result_against_plan(changed, self.plan)

    def test_locked_unlocked_same_actual_identity(self):
        original, _ = self.run_assessment([self.document()])
        actual = self.plan['provenance']['planningComposition']['actual']
        lock = CompositionLock(self.root/'compliance.lock.yaml', actual)
        locked = require_composition(self.sources, lock=lock)
        self.plan['provenance']['planningComposition'] = stage(locked)
        prior_id = self.plan['id']
        self.sign_plan()
        self.assertEqual(prior_id, self.plan['id'])
        report, _ = self.run_assessment([self.document()], composition_report=locked)
        self.assertEqual(original['id'], report['id'])
        self.assertNotEqual(
            original['provenance']['evaluationComposition']['enforcement'],
            report['provenance']['evaluationComposition']['enforcement'],
        )

    def test_policy_drift_and_missing_schema_refuse(self):
        self.write([self.document()])
        (self.source.path/'drift').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'composition differs'):
            evaluate_plan_document(self.plan, self.evidence, self.sources, evaluated_at=self.now)

    def test_independent_controls_and_multiple_required_types(self):
        schema_path = self.source.path/'schemas/evidence/second.json'
        schema = evidence_schema()
        schema['properties']['type']['const'] = 'second/v1'
        schema['$id'] = 'https://compliance.example/schemas/evidence/second/v1.schema.json'
        schema_path.write_text(json.dumps(schema))
        independent = copy.deepcopy(self.plan['controls'][0])
        independent['instance_id'] = 'independent'
        independent['implementation'] = 'test.independent'
        independent['evidence'] = []
        self.plan['controls'].append(independent)
        self.plan['controls'][0]['evidence'].append({
            'id': 'second_observation',
            'type': 'second/v1',
            'max_age': '24h',
        })
        actual = require_composition(self.sources)
        self.plan['provenance']['planningComposition'] = stage(actual)
        self.sign_plan()
        good = self.document()
        second = self.document(type='second/v1')
        for docs in ([good], [good,{**second,'payload':{'value':False}}], [good,second,{**second,'id':'second'}]):
            report, opa = self.run_assessment(docs)
            self.assertEqual([item['status'] for item in report['results']], ['pass', 'unknown'])
            self.assertEqual(report['outcome'], 'unknown')
            self.assertEqual(opa.call_count, 1)
            self.assertEqual(len(report['provenance']['selectedEvidence']), 1)

    def test_evidence_required_discriminator_is_rejected(self):
        self.plan['controls'][0]['evidence'][0]['required'] = False
        with self.assertRaisesRegex(ValueError, 'required'):
            self.sign_plan()

    def test_waivers_bind_identity_and_only_underlying_fail_is_waivable(self):
        waivers = self.root/'waivers'
        waivers.mkdir()
        (waivers/'exception.yaml').write_text(waiver_resource())
        failed, _ = self.run_assessment([self.document()], status='fail')
        waived, _ = self.run_assessment([self.document()], status='fail', waiver_path=waivers)
        self.assertEqual(waived['outcome'], 'waived')
        self.assertNotEqual(failed['id'], waived['id'])
        self.assertEqual(waived['results'][0]['waiver']['underlying_status'], 'fail')
        for docs in ([self.document(payload={'value':False})], [self.document(),self.document(id='other')], []):
            report, _ = self.run_assessment(docs, waiver_path=waivers)
            self.assertEqual(report['outcome'], 'unknown')
            self.assertNotIn('waiver', report['results'][0])
        error, _ = self.run_assessment([self.document()], effect=RuntimeError('criterion'), waiver_path=waivers)
        self.assertNotIn('waiver', error['results'][0])

    def test_unrelated_waiver_catalog_is_nonsemantic_but_applied_snapshot_is_semantic(self):
        without, _ = self.run_assessment([self.document()], status='fail')
        waivers = self.root/'waivers'
        waivers.mkdir()
        unrelated = waiver_resource().replace(
            'name: test-control-rollout', 'name: unrelated').replace(
            'id: host/test', 'id: host/other')
        (waivers/'unrelated.yaml').write_text(unrelated)
        with_unrelated, _ = self.run_assessment(
            [self.document()], status='fail', waiver_path=waivers)
        self.assertEqual(without['id'], with_unrelated['id'])
        self.assertEqual(without, with_unrelated)

        (waivers/'unrelated.yaml').write_text(
            waiver_resource())
        first, _ = self.run_assessment([self.document()], status='fail', waiver_path=waivers)
        (waivers/'unrelated.yaml').write_text(
            waiver_resource().replace(
                'owner: test-owner', 'owner: successor-owner'))
        second, _ = self.run_assessment([self.document()], status='fail', waiver_path=waivers)
        self.assertNotEqual(first['results'][0]['waiver']['digest'],
                            second['results'][0]['waiver']['digest'])
        self.assertNotEqual(first['id'], second['id'])

    def test_evaluator_identity_is_resolved_once_and_identity_bearing(self):
        first, _ = self.run_assessment([self.document()])
        self.identity.assert_called_once_with('opa')
        changed = EvaluatorIdentity('opa', '1.18.2', 'sha256:'+'f'*64)
        self.identity.return_value = changed, '/resolved/opa'
        second, _ = self.run_assessment([self.document()])
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['plan_id'], second['plan_id'])

    def test_missing_evaluator_refuses_even_empty_snapshot(self):
        from tools.evaluator import EvaluatorIdentityError
        self.identity.side_effect = EvaluatorIdentityError('unavailable')
        with self.assertRaises(EvaluatorIdentityError), patch('tools.evaluate_plan.evaluate_control') as opa:
            self.run_assessment([])
        opa.assert_not_called()

    def test_schema_catalog_and_validator_failures_are_shared_refusals(self):
        from tools.render_plan import load_evidence_schema_catalog
        original, _ = load_evidence_schema_catalog(self.sources)
        for replacement in ({}, {'test.evidence/v1': {**original['test.evidence/v1'], '$ref':'#/missing'}}):
            with patch('tools.evaluate_plan.load_evidence_schema_catalog', return_value=(replacement, [])):
                with self.assertRaises(Exception): self.run_assessment([])
        with patch('tools.evidence_selection.Draft202012Validator.iter_errors', side_effect=RuntimeError('validator bug')):
            with self.assertRaisesRegex(RuntimeError, 'validator bug'): self.run_assessment([self.document()])

    def test_duplicate_json_and_unreadable_source_refuse(self):
        self.write([])
        (self.evidence/'duplicate.json').write_text('{"subject":{"id":"host/test"},"subject":{"id":"other"}}')
        with self.assertRaisesRegex(ValueError,'duplicate JSON'):
            evaluate_plan_document(self.plan,self.evidence,self.sources,evaluated_at=self.now)
        self.write([])
        self.evidence.rmdir()
        with self.assertRaises((ValueError,SystemExit)):
            evaluate_plan_document(self.plan,self.evidence,self.sources,evaluated_at=self.now)

    def test_unused_and_rejected_documents_change_complete_snapshot_identity(self):
        first, _ = self.run_assessment([self.document()])
        second, _ = self.run_assessment([self.document(),self.document(id='unused',type='unused/v1',payload={'bad':True})])
        self.assertEqual(first['provenance']['selectedEvidence'],second['provenance']['selectedEvidence'])
        self.assertEqual(first['outcome'], second['outcome'])
        self.assertNotEqual(first['id'],second['id'])
        rejected, _ = self.run_assessment([self.document(payload={'value':False})])
        changed, _ = self.run_assessment([self.document(payload={'value':False},extension=True)])
        self.assertNotEqual(rejected['id'],changed['id'])

    def test_complete_selected_document_and_evaluation_composition_are_semantic(self):
        first, _ = self.run_assessment([self.document()])
        changed_document, _ = self.run_assessment([self.document(extension=True)])
        self.assertEqual(
            first['provenance']['selectedEvidence'][0]['evidence_id'],
            changed_document['provenance']['selectedEvidence'][0]['evidence_id'],
        )
        self.assertNotEqual(first['id'], changed_document['id'])

        from tools.composition import composition_digest
        changed_composition = copy.deepcopy(first)
        actual = changed_composition['provenance']['evaluationComposition']['actual']
        actual['policySources'][0]['content']['digest'] = 'sha256:' + 'd' * 64
        changed_composition['provenance']['evaluationComposition'][
            'compositionDigest'
        ] = composition_digest(actual)
        changed_composition['id'] = artifact_digest(changed_composition)
        validate_assessment_results(changed_composition)
        self.assertNotEqual(first['id'], changed_composition['id'])
        with self.assertRaisesRegex(ValueError, 'planning composition'):
            validate_result_against_plan(changed_composition, self.plan)

    def test_result_identity_projection_is_explicit_and_owns_no_plan_copy(self):
        report, _ = self.run_assessment([self.document()])
        projection = result_identity_projection(report)
        self.assertEqual(set(projection), {
            'schema', 'digestAlgorithm', 'plan_id', 'subject_id', 'evaluated_at',
            'outcome', 'evaluationComposition', 'evaluator', 'evidence',
            'selectedEvidence', 'dependency_dispositions', 'results', 'requirement_assessments',
            'requirement_baseline_assessments',
        })
        for retired in ('assessment_id', 'operation', 'resolved_policy',
                        'planningComposition', 'summary', 'waiver_revision'):
            self.assertNotIn(retired, report)

    def test_path_materialization_and_source_order_do_not_change_identity(self):
        import shutil
        from tools.policy_sources import PolicySource
        base, _ = self.run_assessment([self.document()])
        base_plan_id = self.plan['id']
        other = self.root/'additional'
        other.mkdir()
        (other/'unrelated.txt').write_text('source content')
        self.sources = (self.source,PolicySource('additional',other))
        actual = require_composition(self.sources)
        self.plan['provenance']['planningComposition'] = stage(actual)
        self.sign_plan()
        first, _ = self.run_assessment([self.document()])
        self.assertNotEqual(base_plan_id, self.plan['id'])
        self.assertNotEqual(base['id'], first['id'])
        relocated = self.root/'relocated'
        shutil.copytree(self.source.path,relocated)
        self.sources = (PolicySource('additional',other),PolicySource(self.source.name,relocated))
        second, _ = self.run_assessment([self.document()])
        self.assertEqual(first['id'],second['id'])
        (self.evidence/'0.json').rename(self.evidence/'different-name.json')
        def same_decision(opa, sources, data, entrypoint):
            decision = control_error_result(data, first['results'][0]['reason'])
            decision.update({key: copy.deepcopy(first['results'][0][key])
                             for key in ('status', 'expected', 'observed')})
            return decision
        with patch('tools.evaluate_plan.evaluate_control', side_effect=same_decision):
            third = evaluate_plan_document(self.plan,self.evidence,self.sources,evaluated_at=self.now)
        self.assertEqual(first['id'],third['id'])

    def test_enforcement_and_descriptive_metadata_are_validated_but_nonsemantic(self):
        report, _ = self.run_assessment([self.document()])
        changed = copy.deepcopy(report)
        changed['provenance']['evaluationComposition']['metadata'] = {'distribution':'description', 'version':'arbitrary'}
        self.assertEqual(artifact_digest(changed), report['id'])
        validate_assessment_results(changed)
        changed['provenance']['evaluationComposition']['enforcement']['directExpectedContent'] = {'missing':{'digestAlgorithm':'compliance.example/policy-source-tree-digest/v1alpha1','digest':'sha256:'+'0'*64}}
        with self.assertRaisesRegex(ValueError,'enforcement'): validate_assessment_results(changed)

    def test_selected_snapshot_and_diagnostic_tampering_is_refused(self):
        report, _ = self.run_assessment([self.document(),self.document(id='other')])
        for field,value in (('evidence_id','different'),('collected_at','2026-08-23T12:01:00Z')):
            changed = copy.deepcopy(report)
            changed['dependency_dispositions'][0]['candidates'][0][field] = value
            changed['id'] = artifact_digest(changed)
            with self.assertRaises(ValueError):
                if field == 'evidence_id':
                    validate_assessment_results(changed)
                else:
                    validate_result_against_plan(changed, self.plan)
        changed = copy.deepcopy(report)
        changed['provenance']['evidence']['setDigest'] = 'sha256:'+'0'*64
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError,'snapshot'): validate_assessment_results(changed)

    def test_results_cannot_bypass_frozen_validation_with_invalid_resolution(self):
        report, _ = self.run_assessment([self.document()])
        for resolution in ({'status': 'invalid', 'errors': []},
                           {'status': 'valid', 'errors': [{'message': 'unresolved'}]}):
            changed_plan = copy.deepcopy(self.plan)
            changed_plan['resolution'] = resolution
            with self.assertRaises(ValueError):
                validate_result_against_plan(report, changed_plan)

    def test_relational_validation_rejects_non_result_required_plans(self):
        report, _ = self.run_assessment([self.document()])
        validate_result_against_plan(report, self.plan)

        variants = {}
        retired = copy.deepcopy(self.plan)
        retired['subject']['status'] = 'retired'
        variants['inactive'] = retired

        unassigned = copy.deepcopy(self.plan)
        unassigned['assignments'] = []
        unassigned['resolved_groups'] = []
        unassigned['resolved_baselines'] = []
        unassigned['resolved_requirement_baselines'] = []
        unassigned['requirements'] = []
        unassigned['controls'] = []
        unassigned['excluded_controls'] = []
        variants['unassigned'] = unassigned

        no_policy = copy.deepcopy(self.plan)
        no_policy['controls'] = []
        no_policy['requirements'] = []
        no_policy['resolved_requirement_baselines'] = []
        variants['no_assessable_policy'] = no_policy

        invalid = copy.deepcopy(self.plan)
        invalid['resolution'] = {
            'status': 'invalid',
            'errors': [{'type': 'synthetic-diagnostic-invalid'}],
        }
        variants['invalid'] = invalid

        from tools.operation import plan_disposition
        for expected, plan in variants.items():
            with self.subTest(disposition=expected):
                refresh_operation(plan)
                validate_assessment_plan(plan)
                self.assertEqual(plan_disposition(plan), expected)
                changed = copy.deepcopy(report)
                changed['plan_id'] = plan['id']
                if not plan['controls']:
                    changed['results'] = []
                    changed['requirement_assessments'] = []
                    changed['requirement_baseline_assessments'] = []
                    changed['provenance']['selectedEvidence'] = []
                changed['outcome'] = result_outcome(changed)
                changed['id'] = artifact_digest(changed)
                validate_assessment_results(changed)
                with self.assertRaisesRegex(ValueError, 'non-assessable plan'):
                    validate_result_against_plan(changed, plan)

    def test_requirement_rollups_keep_unknown_error_fail_and_waived_meaning(self):
        sources = [{'name': item['name'], 'digest': item['content']['digest']}
                   for item in self.plan['provenance']['planningComposition']['actual']['policySources']]
        shell = assessment_plan(sources, with_requirement=True)
        from tools import policy_parameters as parameters
        requirement_baseline = shell['resolved_requirement_baselines'][0]
        requirement_baseline['baseline'] = 'test.requirements@1'
        requirement_baseline['reference'] = 'test.requirements@1'
        selected = requirement_baseline['parameter_derivation']['ancestry'][-1]
        selected['reference'] = 'test.requirements@1'
        selected['document']['metadata']['id'] = 'test.requirements'
        selected['digest'] = parameters.digest(selected['document'])
        requirement_baseline['digest'] = selected['digest']
        shell['requirements'][0]['provenance'][0]['baseline'] = 'test.requirements@1'
        for key in ('requirements', 'resolved_requirement_baselines'):
            self.plan[key] = shell[key]
        self.plan['assignments'][0]['baselines'].append('test.requirements@1')
        self.sign_plan()
        for status in ('pass','fail','unknown','error'):
            report, _ = self.run_assessment([self.document()], status=status)
            self.assertEqual(report['requirement_assessments'][0]['status'], status)
            self.assertEqual(report['requirement_baseline_assessments'][0]['status'], status)
        invalid, _ = self.run_assessment([self.document(payload={'value':False})])
        self.assertEqual(invalid['requirement_assessments'][0]['status'], 'unknown')

    def test_same_snapshot_different_successful_selection_facts_change_result_identity(self):
        from tools.assessment_provenance import validate_selection_snapshot
        doc = self.document()
        report, _ = self.run_assessment([doc])
        for field, value in (('evidence_id','different'),('evidence_digest','sha256:'+'0'*64),('collected_at','2026-08-23T10:00:00Z')):
            changed = copy.deepcopy(report)
            changed['provenance']['selectedEvidence'][0][field] = value
            self.assertNotEqual(artifact_digest(changed), report['id'])
            with self.assertRaisesRegex(ValueError, 'evaluated evidence snapshot'):
                validate_selection_snapshot(changed, [doc])
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['dependency_id'] = 'different'
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'assessed plan'):
            validate_result_against_plan(changed, self.plan)

    def test_dispositions_are_identity_bearing_and_intrinsically_fail_closed(self):
        absent, _ = self.run_assessment([])
        stale, _ = self.run_assessment([
            self.document(collected_at='2020-01-01T00:00:00Z')
        ])
        invalid, _ = self.run_assessment([
            self.document(payload={'value': False})
        ])
        ambiguous, _ = self.run_assessment([
            self.document(), self.document(id='other')
        ])
        self.assertEqual(
            {item['dependency_dispositions'][0]['disposition'] for item in (
                absent, stale, invalid, ambiguous,
            )},
            {'absent', 'stale', 'invalid', 'ambiguous'},
        )
        self.assertEqual(len({item['id'] for item in (
            absent, stale, invalid, ambiguous,
        )}), 4)

        changed = copy.deepcopy(absent)
        changed['dependency_dispositions'].append(
            copy.deepcopy(changed['dependency_dispositions'][0])
        )
        changed['id'] = artifact_digest(changed)
        with self.assertRaises(ValueError):
            validate_assessment_results(changed)

        changed = copy.deepcopy(ambiguous)
        candidate = changed['dependency_dispositions'][0]['candidates'][0]
        changed['provenance']['selectedEvidence'] = [{
            'instance_id': 'test.check',
            'dependency_id': 'observation',
            **candidate,
        }]
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'both selected and unsuccessful'):
            validate_assessment_results(changed)

        changed = copy.deepcopy(absent)
        changed['results'][0]['status'] = 'pass'
        changed['outcome'] = result_outcome(changed)
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'must be unknown'):
            validate_assessment_results(changed)

    def test_relational_and_same_snapshot_disposition_tampering_is_refused(self):
        stale_doc = self.document(collected_at='2020-01-01T00:00:00Z')
        stale, _ = self.run_assessment([stale_doc])
        changed = copy.deepcopy(stale)
        changed['dependency_dispositions'][0]['latest_candidates'][0][
            'collected_at'
        ] = '2026-08-23T11:00:00Z'
        changed['id'] = artifact_digest(changed)
        validate_assessment_results(changed)
        with self.assertRaisesRegex(ValueError, 'stale disposition candidate was eligible'):
            validate_result_against_plan(changed, self.plan)

        invalid_doc = self.document(payload={'value': False})
        invalid, _ = self.run_assessment([invalid_doc])
        changed = copy.deepcopy(invalid)
        changed['dependency_dispositions'][0]['diagnostics'][0][
            'schema_path'
        ] = '/properties/payload/type'
        changed['id'] = artifact_digest(changed)
        validate_assessment_results(changed)
        from tools.assessment_provenance import validate_selection_snapshot
        from tools.evidence_selection import prepare_schemas
        from tools.render_plan import load_evidence_schema_catalog
        schemas, errors = load_evidence_schema_catalog(self.sources)
        self.assertEqual(errors, [])
        validators, references = prepare_schemas(
            schemas, {'test.evidence/v1'}
        )
        with self.assertRaisesRegex(ValueError, 'same-snapshot evidence selection'):
            validate_selection_snapshot(
                changed, [invalid_doc], plan=self.plan, validators=validators,
                schema_references=references,
            )

    def test_error_admission_rejects_missing_mismatched_and_legacy_details(self):
        report, _ = self.run_assessment(
            [self.document()], effect=RuntimeError('not retained')
        )
        mutations = (
            lambda item: item['results'][0].pop('evaluation_error'),
            lambda item: item['results'][0].update(reason='raw evaluator error'),
            lambda item: item['results'][0]['observed'].update(stderr='secret'),
            lambda item: item['results'][0]['evaluation_error'].update(
                stage='criterion_decision'
            ),
        )
        for mutate in mutations:
            changed = copy.deepcopy(report)
            mutate(changed)
            changed['id'] = artifact_digest(changed)
            with self.assertRaises(ValueError):
                validate_assessment_results(changed)

        unknown, _ = self.run_assessment([])
        unknown['results'][0]['observed']['evidence_validation_errors'] = [{}]
        unknown['id'] = artifact_digest(unknown)
        with self.assertRaises(ValueError):
            validate_assessment_results(unknown)


    def test_unrepresentable_criterion_decisions_are_attributable_errors(self):
        for value in (float('nan'),float('inf'),'\ud800'):
            def unusable(opa, sources, data, entrypoint):
                result = control_error_result(data, 'Criterion decision')
                result['status'] = 'pass'
                result['observed'] = {'value':value}
                return result
            report, opa = self.run_assessment([self.document()], effect=unusable)
            self.assertEqual(report['outcome'],'error')
            self.assertEqual(opa.call_count,1)
            self.assertEqual(len(report['provenance']['selectedEvidence']),1)

    def test_standalone_provenance_requires_complete_evaluation_record(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).parents[1]/'tools/schemas/assessment-provenance-v1alpha1.schema.json').read_text())
        validator = Draft202012Validator(schema)
        planning = self.plan['provenance']
        validator.validate(planning)
        report, _ = self.run_assessment([self.document()])
        validator.validate(report['provenance'])
        for field in ('evaluationComposition','evaluator','evidence','selectedEvidence'):
            incomplete = {**planning, field:report['provenance'][field]}
            self.assertTrue(list(validator.iter_errors(incomplete)),field)

    def test_naive_assessment_time_refuses_before_criterion_execution(self):
        self.plan['controls'][0]['evidence'] = []
        self.sign_plan()
        self.write([])
        with patch('tools.evaluate_plan.evaluate_control') as opa:
            with self.assertRaisesRegex(ValueError,'explicit timezone'):
                evaluate_plan_document(self.plan,self.evidence,self.sources,evaluated_at=self.now.replace(tzinfo=None))
            opa.assert_not_called()


    def test_canonical_identical_invalid_documents_have_identical_diagnostics(self):
        first = self.document(payload={'value':{'a':1,'b':2}})
        second = self.document(payload={'value':{'b':2,'a':1}})
        a, opa_a = self.run_assessment([first])
        b, opa_b = self.run_assessment([second])
        self.assertEqual(a['provenance']['evidence'],b['provenance']['evidence'])
        self.assertEqual(a['results'],b['results'])
        self.assertEqual(a['id'],b['id'])
        self.assertEqual(opa_a.call_count,0)
        self.assertEqual(opa_b.call_count,0)

    def test_same_document_selected_for_two_requirements_retains_attributable_error(self):
        requirement = copy.deepcopy(self.plan['controls'][0]['evidence'][0])
        requirement['max_age'] = '48h'
        requirement['id'] = 'second_observation'
        self.plan['controls'][0]['evidence'].append(requirement)
        self.sign_plan()
        for effect in (RuntimeError('scoped'), lambda *args: None):
            report, opa = self.run_assessment([self.document()],effect=effect)
            self.assertEqual(report['outcome'],'error')
            self.assertNotIn('evidence_ids', report['results'][0])
            self.assertEqual(
                [use['dependency_id'] for use in report['provenance']['selectedEvidence']],
                ['observation', 'second_observation'],
            )
            self.assertEqual(opa.call_count,1)


class V4JcsProjectionVectors(unittest.TestCase):
    def test_result_explanation_facts_vector(self):
        document = {
            'schema': 'compliance.example/assessment-results/v4',
            'digestAlgorithm': 'compliance.example/assessment-results-digest/v1alpha1',
            'plan_id': 'sha256:' + '1' * 64,
            'subject_id': 'host/vector',
            'evaluated_at': '2026-09-08T10:00:00Z',
            'outcome': 'error',
            'provenance': {
                'evaluationComposition': {
                    'compositionDigestAlgorithm': 'compliance.example/composition-digest/v1alpha1',
                    'compositionDigest': 'sha256:' + '2' * 64,
                },
                'evaluator': {
                    'name': 'opa', 'version': '1.18.2',
                    'executableSha256': 'sha256:' + '3' * 64,
                },
                'evidence': {
                    'setDigestAlgorithm': 'compliance.example/evidence-set-digest/v1alpha1',
                    'setDigest': 'sha256:' + '4' * 64,
                },
                'selectedEvidence': [],
            },
            'dependency_dispositions': [{
                'instance_id': 'control.unknown',
                'dependency_id': 'observation',
                'disposition': 'absent',
            }],
            'results': [
                {
                    'instance_id': 'control.error', 'status': 'error',
                    'reason': 'Criterion execution failed.',
                    'expected': {}, 'observed': {},
                    'evaluation_error': {
                        'stage': 'criterion_execution',
                        'code': 'criterion_execution_failed',
                    },
                },
                {
                    'instance_id': 'control.unknown', 'status': 'unknown',
                    'reason': 'Required evidence is absent.',
                    'expected': {}, 'observed': {},
                },
            ],
            'requirement_assessments': [],
            'requirement_baseline_assessments': [],
        }
        self.assertEqual(
            artifact_digest(document),
            'sha256:7e1851b5bb0dfb1b1556720984bf8fdb62d7b187aa1f7d39f6f1062724488293',
        )

    def test_operation_bound_plan_id_vector(self):
        from tools.assessment_provenance import operation_plan_id
        self.assertEqual(
            operation_plan_id('sha256:' + '1' * 64, 'host/😀'),
            'sha256:afa65ce31505eb476b07e08d9e9523dfbbd6ea7f93c32b1d41818705fc800f40',
        )
