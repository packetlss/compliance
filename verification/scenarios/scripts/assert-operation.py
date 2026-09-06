"""Canonical #78 acceptance through public CLI and isolated synthetic sources."""
import argparse
import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment_provenance import artifact_digest


def run(root, private_source):
    with tempfile.TemporaryDirectory(prefix='closed-world-conformance-') as temporary:
        work = Path(temporary)
        project = work/'project'
        shutil.copytree(root/'verification/scenarios/projects/closed-world', project)
        sources = []
        for name, source in [('control-library', root/'policy-sources/control-library/policies'),
                             ('verification-policy', root/'policy-sources/verification-policy/policies'),
                             ('environment-private', private_source)]:
            destination = work/name
            shutil.copytree(source, destination)
            sources.append({'name':name, 'path':str(destination)})
        path = project/'compliance.json'
        config = json.loads(path.read_text())
        config['policySources'] = sources
        path.write_text(json.dumps(config))
        command = ['compliance','--config',str(path)]
        instant = '2026-09-01T00:00:00Z'

        def cli(*args, success=True, historical=False):
            if args[:2] == ('assessment','run'):
                args = (*args, '--format', 'json')
            result = subprocess.run([*(['compliance','--no-config'] if historical else command),*args],
                                    capture_output=True, text=True)
            if success:
                assert result.returncode == 0, result.stderr
            else:
                assert result.returncode != 0, result.stdout
            return result.stdout

        evidence = project/'generated/evidence'
        evidence.mkdir(parents=True)
        for fixture in sorted((project/'fixtures').glob('*.json')):
            doc = json.loads(fixture.read_text())
            doc.update(schema='compliance.example/evidence/v1', id='synthetic:'+fixture.stem,
                       collected_at=instant, integrity={'digest':'sha256:'+'0'*64})
            (evidence/fixture.name).write_text(json.dumps(doc))
        original = {p.name:p.read_bytes() for p in evidence.iterdir()}
        selected = ['host/A','host/B','entity/A']
        account = json.loads(cli('assessment','run',*selected,'--at',instant))
        assert account['accounting_complete'] and account['all_passed'], account
        plans = project/'generated/plans'
        results = project/'generated/results'
        anchor = plans/'host__A.json'
        frozen = json.loads(anchor.read_text())
        assert len(frozen['operation']['members']) == 3
        assert len(next(m for m in frozen['operation']['members'] if m['subject_id']=='entity/A')['policy']['requirements']) == 3
        reports = {p.name:json.loads(p.read_text()) for p in results.glob('*.json')}
        for report in reports.values(): validate_assessment_results(report)
        omitted = copy.deepcopy(reports['entity__A.json'])
        omitted['requirement_assessments'].pop(1)
        omitted['requirement_summary']['pass'] -= 1
        omitted['id'] = artifact_digest(omitted)
        try: validate_assessment_results(omitted)
        except ValueError: pass
        else: raise AssertionError('O2 omitted despite frozen required company target')
        def history(command_name='status', *args):
            return json.loads(cli('assessment',command_name,*args,'--plan',str(anchor),'--results',str(results),
                                  '--at',instant,'--format','json',historical=True))
        assert history()['all_passed']
        (results/'copy.json').write_text(json.dumps(reports['host__A.json'],sort_keys=True))
        assert history()['all_passed']
        (results/'copy.json').unlink()
        (results/'host__B.json').unlink()
        missing = history()
        assert not missing['accounting_complete'] and not missing['all_passed']
        assert next(m for m in missing['members'] if m['subject_id']=='host/B')['state']=='missing'
        cli('assessment','run','host/B','--at',instant,'--plan-output',str(work/'singleton'))
        assert not history()['accounting_complete']  # wrong operation cannot fill B
        for name,report in reports.items(): (results/name).write_text(json.dumps(report))
        before = history()
        mappings = history('frameworks','--reference','synthetic-framework:Q')
        assert mappings['filtered'] and mappings['mappings']
        assert 'no external conformity' in mappings['claim']
        # Recomputing the outer digest does not repair an omitted required row.
        tampered = copy.deepcopy(frozen)
        tampered['operation']['members'].pop()
        tampered['id'] = artifact_digest(tampered)
        try: validate_assessment_plan(tampered)
        except ValueError: pass
        else: raise AssertionError('tampered operation membership accepted')

        def assess_entity(change=None, remove=False):
            for p in evidence.iterdir(): p.unlink()
            for name,content in original.items(): (evidence/name).write_bytes(content)
            doc_path = next(evidence.glob('entity-A-*'))
            doc = json.loads(doc_path.read_text())
            if change:
                change(doc)
                doc_path.write_text(json.dumps(doc))
            if remove: doc_path.unlink()
            cli('assessment','run','entity/A','--at',instant,'--plan-output',str(work/'entity-plans'),
                '--output',str(work/'entity-results'))
            report = json.loads((work/'entity-results/entity__A.json').read_text())
            return report

        assert assess_entity()['requirement_summary']['pass']==3
        assert assess_entity(lambda d:d['payload'].update(outcome='negative'))['requirement_summary']['fail']==3
        for change in [lambda d:d['payload'].update(beneficiary='entity/B'),
                       lambda d:d['payload'].update(outcome='inconclusive'),
                       lambda d:d['payload'].update(valid_until='2026-08-31T00:00:00Z'),
                       lambda d:d['payload'].update(outcome=123),
                       lambda d:d.update(collected_at='2020-01-01T00:00:00Z')]:
            assert assess_entity(change)['requirement_summary']['unknown']==3
        assert assess_entity(remove=True)['requirement_summary']['unknown']==3
        criterion = work/'control-library/controls/organization/assertion-required/policy.rego'
        criterion_bytes = criterion.read_bytes()
        criterion.write_text('package compliance.controls.organization_assertion_required\nimport rego.v1\nevaluate := null\n')
        assert assess_entity()['requirement_summary']['error']==3
        criterion.write_bytes(criterion_bytes)
        for name,content in original.items(): (evidence/name).write_bytes(content)
        invalid_routing = next(evidence.glob('entity-A-*'))
        doc=json.loads(invalid_routing.read_text());doc['subject']=None
        invalid_routing.write_text(json.dumps(doc))
        cli('assessment','run','entity/A','--at',instant,'--output',str(work/'refused-results'),
            '--plan-output',str(work/'refused-plans'),success=False)
        assert not (work/'refused-results/entity__A.json').exists()
        for name,content in original.items(): (evidence/name).write_bytes(content)
        relationship = next(evidence.glob('host-A-iam.integration*'))
        relationship.unlink()
        cli('assessment','run','host/A','--at',instant,'--plan-output',str(work/'iam-plans'),
            '--output',str(work/'iam-results'))
        assert json.loads((work/'iam-results/host__A.json').read_text())['requirement_summary']['unknown']==1
        all_rows = json.loads(cli('assessment','run','--all','--at',instant,
                                 '--plan-output',str(work/'all-plans'),'--output',str(work/'all-results')))
        assert all_rows['accounting_complete'] and not all_rows['all_passed']
        assert {m['state'] for m in all_rows['members']} >= {'inactive','unassigned'}
        system=json.loads((work/'all-results/system__S.json').read_text())
        assert system['requirement_summary']['fail']==1
        assert system['resolved_policy']['requirements'][0]['adoption']['status']=='not_implemented'
        no_assessment = json.loads(cli('assessment','run','entity/B','host/retired','--at',instant,
                                      '--plan-output',str(work/'no-assessment-plans'),
                                      '--output',str(work/'no-assessment-results')))
        assert no_assessment['accounting_complete'] and not no_assessment['all_passed']
        assert not (work/'no-assessment-results').exists()
        cli('plan','render',success=False)
        # Destroy mutable inputs. No-config historical reporting still needs only
        # the old anchor and exact result envelopes, including frozen mappings.
        shutil.rmtree(project/'inventory')
        shutil.rmtree(project/'assignments')
        shutil.rmtree(evidence)
        for source in sources: shutil.rmtree(source['path'])
        assert history()==before
        assert history('frameworks','--reference','synthetic-framework:Q')==mappings
    print('Closed-world operation and typed external assertion conformance passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--integration-root',type=Path,required=True)
    parser.add_argument('--private-source',type=Path)
    args=parser.parse_args()
    run(args.integration_root, args.private_source or args.integration_root/'external-sources/environment-private')
