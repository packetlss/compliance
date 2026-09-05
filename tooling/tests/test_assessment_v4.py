"""ADR 0007/0010/0011 conformance over exact historical evidence selection."""
import copy
import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import test_evaluate_plan as predecessor
from tools.assessment_provenance import (
    PLAN_SCHEMA, PROVENANCE_SCHEMA, PLAN_DIGEST_ALGORITHM, artifact_digest, stage,
    validate_selection_plan,
)
from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.composition import require_composition, CompositionLock
from tools.evaluator import EvaluatorIdentity
from tools.evidence_provenance import evidence_document_digest
from tools.evaluate_plan import evaluate_plan_document, control_error_result


class AssessmentV4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.plan = predecessor.EvidenceFreshnessTests().evidence_plan(self.root)
        self.sources = (self.source,)
        self.plan.update(schema=PLAN_SCHEMA, digestAlgorithm=PLAN_DIGEST_ALGORITHM,
                         provenance={'schema': PROVENANCE_SCHEMA, 'planningComposition': stage(require_composition(self.sources))})
        self.sign_plan()
        self.evidence = self.root / 'evidence'
        self.evidence.mkdir()
        self.now = datetime(2026, 8, 23, 12, tzinfo=UTC)
        self.evaluator = EvaluatorIdentity('opa', '1.18.2', 'sha256:'+'e'*64)
        self.identity = patch('tools.evaluator.resolve_opa_evaluator', return_value=(self.evaluator, '/resolved/opa')).start()
        self.addCleanup(patch.stopall)

    def sign_plan(self):
        from tools.policy_sources import policy_revision
        self.plan['policy_revision'] = policy_revision(self.plan['policy_sources'])
        self.plan['id'] = artifact_digest(self.plan)
        validate_assessment_plan(self.plan)

    def write(self, docs):
        for path in self.evidence.iterdir(): path.unlink()
        for index, doc in enumerate(docs):
            (self.evidence / f'{index}.json').write_text(json.dumps(doc))

    def document(self, **changes):
        return {**predecessor.EvidenceFreshnessTests.evidence_document(), **changes}

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
        validate_selection_plan(report, self.plan)
        return report, opa

    def test_selected_exact_document_and_temporal_facts_survive_mutable_sources(self):
        doc = self.document(collected_at='2026-08-23T11:00:00.123456Z')
        older = self.document(collected_at='2026-08-23T10:00:00Z')
        unused = self.document(id='unused', type='unused/v1')
        report, opa = self.run_assessment([older, doc, unused])
        self.assertEqual(opa.call_count, 1)
        use, = report['provenance']['selectedEvidence']
        self.assertEqual(use, {'instance_id':'test.check', 'requirement_index':0,
                              'requirement':self.plan['controls'][0]['evidence'][0],
                              'id':doc['id'], 'digest':evidence_document_digest(doc), 'collected_at':doc['collected_at']})
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
                self.assertEqual(report['summary']['pass'], 1)
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
                self.assertEqual(a['summary']['unknown'], 1)
                self.assertEqual(a['provenance']['selectedEvidence'], [])
                diagnostic, = a['results'][0]['observed']['evidence_selection_ambiguities']
                self.assertEqual(diagnostic['code'], 'evidence_selection_ambiguity')
                self.assertEqual(len(diagnostic['candidates']), 2)

    def test_all_matching_candidates_validated_before_selection(self):
        good = self.document()
        for collected in ('2026-08-23T11:30:00Z','2020-01-01T00:00:00Z'):
            bad = self.document(payload={'value':False}, collected_at=collected)
            a, opa = self.run_assessment([good,bad])
            b, _ = self.run_assessment([bad,good])
            self.assertEqual(a['id'], b['id'])
            self.assertEqual(a['summary']['unknown'], 1)
            self.assertEqual(opa.call_count, 0)
            self.assertEqual(a['provenance']['selectedEvidence'], [])
            diagnostic, = a['results'][0]['observed']['evidence_validation_errors']
            self.assertEqual(diagnostic['evidence_digest'], evidence_document_digest(bad))
            self.assertEqual(diagnostic['path'], '/payload/value')
            self.assertIn('schema_reference', diagnostic)

    def test_missing_and_all_stale_no_opa(self):
        for docs in ([], [self.document(collected_at='2020-01-01T00:00:00Z')]):
            report, opa = self.run_assessment(docs)
            self.assertEqual(report['summary']['unknown'], 1)
            self.assertEqual(opa.call_count, 0)

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
            self.assertEqual(report['summary']['error'], 1)
            self.assertEqual(len(report['provenance']['selectedEvidence']), 1)

    def test_mutated_provenance_identity_and_reference_validation(self):
        report, _ = self.run_assessment([self.document()])
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['collected_at'] = '2026-08-23T10:59:00Z'
        self.assertNotEqual(artifact_digest(changed), report['id'])
        with self.assertRaises(ValueError): validate_assessment_results(changed)
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['digest'] = 'sha256:'+'0'*64
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'absent from snapshot'): validate_assessment_results(changed)
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['requirement_index'] = 8
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError, 'assessed plan'): validate_selection_plan(changed, self.plan)

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

    def test_policy_drift_and_missing_schema_refuse(self):
        self.write([self.document()])
        (self.source.path/'drift').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'composition differs'):
            evaluate_plan_document(self.plan, self.evidence, self.sources, evaluated_at=self.now)

    def test_independent_controls_and_multiple_required_types(self):
        schema_path = self.source.path/'schemas/evidence/second.json'
        schema = predecessor.EvidenceFreshnessTests.evidence_schema()
        schema['properties']['type']['const'] = 'second/v1'
        schema_path.write_text(json.dumps(schema))
        independent = copy.deepcopy(self.plan['controls'][0])
        independent['instance_id'] = 'independent'
        independent['evidence'] = []
        self.plan['controls'].append(independent)
        self.plan['coverage']['active_control_count'] = 2
        self.plan['controls'][0]['evidence'].append({'type':'second/v1','required':True,'max_age':'24h'})
        actual = require_composition(self.sources)
        self.plan['policy_sources'] = [{'name':x['name'],'digest':x['content']['digest']} for x in actual['actual']['policySources']]
        self.plan['provenance']['planningComposition'] = stage(actual)
        self.sign_plan()
        good = self.document()
        second = self.document(type='second/v1')
        for docs in ([good], [good,{**second,'payload':{'value':False}}], [good,second,{**second,'id':'second'}]):
            report, opa = self.run_assessment(docs)
            self.assertEqual(report['summary']['unknown'], 1)
            self.assertEqual(report['summary']['pass'], 1)
            self.assertEqual(opa.call_count, 1)
            self.assertEqual(len(report['provenance']['selectedEvidence']), 1)

    def test_optional_absence_does_not_block_the_criterion(self):
        self.plan['controls'][0]['evidence'][0]['required'] = False
        self.sign_plan()
        report, opa = self.run_assessment([])
        self.assertEqual(opa.call_count, 1)
        self.assertEqual(report['summary']['pass'], 1)

    def test_waivers_bind_identity_and_only_underlying_fail_is_waivable(self):
        waivers = self.root/'waivers'
        waivers.mkdir()
        (waivers/'exception.yaml').write_text(predecessor.EvidenceFreshnessTests.waiver_resource())
        failed, _ = self.run_assessment([self.document()], status='fail')
        waived, _ = self.run_assessment([self.document()], status='fail', waiver_path=waivers)
        self.assertEqual(waived['summary']['waived'], 1)
        self.assertNotEqual(failed['id'], waived['id'])
        self.assertEqual(waived['results'][0]['waiver']['underlying_status'], 'fail')
        for docs in ([self.document(payload={'value':False})], [self.document(),self.document(id='other')], []):
            report, _ = self.run_assessment(docs, waiver_path=waivers)
            self.assertEqual(report['summary']['unknown'], 1)
            self.assertNotIn('waiver', report['results'][0])
        error, _ = self.run_assessment([self.document()], effect=RuntimeError('criterion'), waiver_path=waivers)
        self.assertNotIn('waiver', error['results'][0])

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
        self.assertNotEqual(first['id'],second['id'])
        rejected, _ = self.run_assessment([self.document(payload={'value':False})])
        changed, _ = self.run_assessment([self.document(payload={'value':False},extension=True)])
        self.assertNotEqual(rejected['id'],changed['id'])

    def test_path_materialization_and_source_order_do_not_change_identity(self):
        import shutil
        from tools.policy_sources import PolicySource
        other = self.root/'additional'
        other.mkdir()
        (other/'unrelated.txt').write_text('source content')
        self.sources = (self.source,PolicySource('additional',other))
        actual = require_composition(self.sources)
        self.plan['policy_sources'] = [{'name':x['name'],'digest':x['content']['digest']} for x in actual['actual']['policySources']]
        self.plan['provenance']['planningComposition'] = stage(actual)
        self.sign_plan()
        first, _ = self.run_assessment([self.document()])
        relocated = self.root/'relocated'
        shutil.copytree(self.source.path,relocated)
        self.sources = (PolicySource('additional',other),PolicySource(self.source.name,relocated))
        second, _ = self.run_assessment([self.document()])
        self.assertEqual(first['id'],second['id'])
        (self.evidence/'0.json').rename(self.evidence/'different-name.json')
        with patch('tools.evaluate_plan.evaluate_control', return_value=copy.deepcopy(first['results'][0])):
            third = evaluate_plan_document(self.plan,self.evidence,self.sources,evaluated_at=self.now)
        self.assertEqual(first['id'],third['id'])

    def test_enforcement_and_descriptive_metadata_are_validated_but_nonsemantic(self):
        report, _ = self.run_assessment([self.document()])
        changed = copy.deepcopy(report)
        changed['provenance']['planningComposition']['metadata'] = {'distribution':'description', 'version':'arbitrary'}
        self.assertEqual(artifact_digest(changed), report['id'])
        validate_assessment_results(changed)
        changed['provenance']['planningComposition']['enforcement']['directExpectedContent'] = {'missing':{'digestAlgorithm':'compliance.example/policy-source-tree-digest/v1alpha1','digest':'sha256:'+'0'*64}}
        with self.assertRaisesRegex(ValueError,'enforcement'): validate_assessment_results(changed)

    def test_selected_snapshot_and_diagnostic_tampering_is_refused(self):
        report, _ = self.run_assessment([self.document(),self.document(id='other')])
        for field,value in (('subject','different'),('evaluated_at','2026-08-23T12:01:00Z'),('evidence_type','different/v1')):
            changed = copy.deepcopy(report)
            changed['results'][0]['observed']['evidence_selection_ambiguities'][0][field] = value
            changed['id'] = artifact_digest(changed)
            with self.assertRaises(ValueError): validate_assessment_results(changed)
        changed = copy.deepcopy(report)
        changed['provenance']['evidence']['setDigest'] = 'sha256:'+'0'*64
        changed['id'] = artifact_digest(changed)
        with self.assertRaisesRegex(ValueError,'snapshot'): validate_assessment_results(changed)

    def test_requirement_rollups_keep_unknown_error_fail_and_waived_meaning(self):
        shell = predecessor.assessment_plan(self.plan['policy_sources'], with_requirement=True)
        for key in ('requirements','resolved_requirement_baselines'):
            self.plan[key] = shell[key]
        self.plan['coverage']['requirement_count'] = 1
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
        for field, value in (('id','different'),('digest','sha256:'+'0'*64),('collected_at','2026-08-23T10:00:00Z')):
            changed = copy.deepcopy(report)
            changed['provenance']['selectedEvidence'][0][field] = value
            self.assertNotEqual(artifact_digest(changed), report['id'])
            with self.assertRaisesRegex(ValueError, 'evaluated evidence snapshot'):
                validate_selection_snapshot(changed, [doc])
        changed = copy.deepcopy(report)
        changed['provenance']['selectedEvidence'][0]['requirement']['max_age'] = '12h'
        self.assertNotEqual(artifact_digest(changed), report['id'])
        with self.assertRaisesRegex(ValueError, 'assessed plan'):
            validate_selection_plan(changed, self.plan)


class V4JcsProjectionVectors(unittest.TestCase):
    def test_fixed_unicode_numeric_and_enforcement_projection_vectors(self):
        from tools.composition import composition_digest
        actual = {'tooling':{'source':{'digestAlgorithm':'compliance.example/tooling-source-tree-digest/v1alpha1','digest':'sha256:'+'1'*64},'execution':{'kind':'source'}},'policySources':[{'name':'source','content':{'digestAlgorithm':'compliance.example/policy-source-tree-digest/v1alpha1','digest':'sha256:'+'2'*64}}]}
        record = {'actual':actual,'compositionDigestAlgorithm':'compliance.example/composition-digest/v1alpha1','compositionDigest':composition_digest(actual),'enforcement':{'directExpectedContent':{},'compositionLock':None}}
        # Projection-layer vectors, independent of full domain envelope validation.
        for kind, expected in (
            ('plan','sha256:d992280bae05164423efe0bd99c2b020334b496b26a0b6772dbe9a0f9ba5ae01'),
            ('results','sha256:bbc52bac753f18c0cb328b8ea19cae5cdec347a75f5cd1f883463b53aa35382e'),
        ):
            document = {'schema':f'compliance.example/assessment-{kind}/v4','digestAlgorithm':f'compliance.example/assessment-{kind}-digest/v1alpha1','provenance':{'schema':PROVENANCE_SCHEMA,'planningComposition':copy.deepcopy(record)},'payload':{'😀':1e-7,'€':333333333.33333329,'value':-0.0}}
            self.assertEqual(artifact_digest(document),expected)
            document['id'] = 'ignored self reference'
            document['provenance']['planningComposition']['metadata'] = {'distribution':'descriptive','version':'99'}
            document['provenance']['planningComposition']['enforcement']['directExpectedContent'] = {'source':actual['policySources'][0]['content']}
            self.assertEqual(artifact_digest(document),expected)
