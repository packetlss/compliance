"""Native v4 fixtures for synthetic in-memory domain tests."""
import json

from tools.assessment_provenance import PLAN_SCHEMA, PLAN_DIGEST_ALGORITHM, PROVENANCE_SCHEMA, artifact_digest
from tools.composition import COMPOSITION_DIGEST_ALGORITHM, composition_digest, POLICY_SOURCE_DIGEST_ALGORITHM
from tools.policy_sources import PolicySource, policy_source_revisions
from tools.tooling_identity import actual_tooling_identity


def assessment_plan(policy_sources, *, with_requirement=False):
    requirement_digest = "sha256:" + "5" * 64
    baseline_digest = "sha256:" + "6" * 64
    plan = {
        "subject": {
            "schema": "compliance.example/inventory-subject/v1",
            "id": "host/test",
            "type": "linux-host",
            "status": "active",
            "labels": {},
            "inventory": {
                "source": "unit-test",
                "external_id": "host/test",
                "observed_at": "2026-08-28T12:00:00Z",
            },
        },
        "resolved_groups": [{
            "id": "test-hosts",
            "sources": [{"membership": "explicit", "source": "group.members"}],
        }],
        "assignments": [{
            "id": "test-policy",
            "group": "test-hosts",
            "baselines": ["test.baseline@1"],
            "parameter_policies": [],
        }],
        "parameters": {"documents": [], "applicability": [], "consumers": []},
        "resolved_baselines": [],
        "resolved_requirement_baselines": [],
        "requirements": [],
        "controls": [{
            "instance_id": "test.check",
            "implementation": "test.control",
            "title": "Synthetic test check",
            "purpose": "Verify the structured synthetic test condition.",
            "entrypoint": "data.test.evaluate",
            "parameters": {},
            "severity": "medium",
            "remediation": "",
            "evidence": [],
            "disposition": "evaluate",
            "alignment": "unaltered",
            "definition_fingerprint": "sha256:" + "4" * 64,
            "derivations": [],
            "deviations": [],
            "lineage": [{"baseline": "test.baseline@1", "operation": "defined"}],
            "provenance": [{
                "group": "test-hosts",
                "assignment": "test-policy",
                "baseline": "test.baseline@1",
            }],
            "implementation_sources": [{
                "policy_source": policy_sources[0]["name"],
                "path": "controls/test/control.json",
            }],
        }],
        "excluded_controls": [],
        "resolution": {"status": "valid", "errors": []},
    }
    if with_requirement:
        locator = [{
            "policy_source": policy_sources[0]["name"],
            "path": "requirements/test.json",
        }]
        plan["requirements"] = [{
            "reference": "test.requirement@1",
            "digest": requirement_digest,
            "title": "Test requirement",
            "statement": "The test condition is satisfied.",
            "external_refs": [],
            "policy_sources": locator,
            "adoption": {
                "status": "implemented",
                "method": "automated",
                "owner": "test",
                "implementation_ref": "test/implementation",
            },
            "implementation_state": "implemented",
            "technical_instance_ids": ["test.check"],
            "realization": {
                "reference": "test.realization@1",
                "digest": "sha256:" + "8" * 64,
                "policy_sources": [{
                    "policy_source": policy_sources[0]["name"],
                    "path": "realizations/test.json",
                }],
            },
            "provenance": [{
                "group": "test-hosts",
                "assignment": "test-policy",
                "baseline": "test.baseline@1",
            }],
        }]
        plan["resolved_requirement_baselines"] = [{
            "assignment": "test-policy",
            "group": "test-hosts",
            "baseline": "test.baseline@1",
            "reference": "test.baseline@1",
            "title": "Synthetic requirement policy",
            "digest": baseline_digest,
            "policy_sources": [{
                "policy_source": policy_sources[0]["name"],
                "path": "requirement-baselines/test.json",
            }],
            "requirements": [{
                "requirement": "test.requirement@1",
                "digest": requirement_digest,
                }],
        }]
        plan["controls"][0].update({
            "alignment": "realization",
            "lineage": [{
                "realization": "test.realization@1",
                "operation": "defined",
            }],
            "provenance": [{
                "group": "test-hosts",
                "assignment": "test-policy",
                "baseline": "test.baseline@1",
                "requirement": "test.requirement@1",
                "realization": "test.realization@1",
            }],
        })
    plan.update(planning_fields(policy_sources))
    freeze_policy_inputs(plan)
    plan["id"] = artifact_digest(plan)
    return plan


def evidence_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://compliance.example/schemas/evidence/test.evidence/v1.schema.json",
        "type": "object",
        "required": [
            "schema", "id", "subject", "type", "collected_at",
            "collector", "payload",
        ],
        "additionalProperties": True,
        "properties": {
            "schema": {"const": "compliance.example/evidence/v1"},
            "id": {"type": "string", "minLength": 1},
            "subject": {
                "type": "object",
                "required": ["id", "type"],
                "additionalProperties": True,
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "type": {"const": "linux-host"},
                },
            },
            "type": {"const": "test.evidence/v1"},
            "collected_at": {"type": "string", "format": "date-time"},
            "collector": {
                "type": "object",
                "required": ["id", "version"],
                "additionalProperties": True,
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "version": {"type": "string", "minLength": 1},
                },
            },
            "payload": {
                "type": "object",
                "required": ["value"],
                "additionalProperties": True,
                "properties": {"value": {"type": "string"}},
            },
        },
    }


def evidence_document(*, subject_id="host/test", value="observed") -> dict:
    return {
        "schema": "compliance.example/evidence/v1",
        "id": "evidence:test",
        "subject": {"id": subject_id, "type": "linux-host"},
        "type": "test.evidence/v1",
        "collected_at": "2026-08-23T11:00:00Z",
        "collector": {"id": "test-collector", "version": "1"},
        "payload": {"value": value},
    }


def evidence_plan(root):
    source = PolicySource("shared", root / "policy")
    schemas = source.path / "schemas/evidence"
    schemas.mkdir(parents=True)
    (schemas / "test-evidence-v1.schema.json").write_text(
        json.dumps(evidence_schema()),
        encoding="utf-8",
    )
    plan = assessment_plan(policy_source_revisions((source,)))
    plan["controls"][0]["evidence"] = [{
        "id": "observation",
        "type": "test.evidence/v1",
        "max_age": "24h",
    }]
    plan.pop("id")
    freeze_policy_inputs(plan)
    plan["id"] = artifact_digest(plan)
    return source, plan


def waiver_resource() -> str:
    return """\
apiVersion: compliance.example/v1alpha1
kind: Waiver
metadata:
  name: test-control-rollout
spec:
  subjectRef:
    id: host/test
  controlRef:
    instanceId: test.check
  validFrom: "2026-08-01T00:00:00Z"
  expiresAt: "2026-09-01T00:00:00Z"
  rationale: Temporary rollout constraint.
  owner: test-owner
  approval:
    reference: risk/TEST-1
    approvedBy: risk-owner
    approvedAt: "2026-07-31T00:00:00Z"
"""


def control_result(plan, status):
    return {
        "control_id": "test.control",
        "instance_id": "test.check",
        "subject_id": "host/test",
        "plan_id": plan["id"],
        "status": status,
        "severity": "medium",
        "reason": "Synthetic control result.",
        "expected": {},
        "observed": {},
        "remediation": "",
        "external_refs": [],
        "alignment": plan["controls"][0]["alignment"],
    }


def freeze_policy_inputs(plan):
    """Author explicit synthetic input facts for hand-built evaluator fixtures."""
    import copy
    from tools import policy_parameters as pp
    policy_source_name = plan['provenance']['planningComposition']['actual']['policySources'][0]['name']
    for control in plan['controls']:
        for dependency in control['evidence']:
            if 'id' not in dependency:
                raise ValueError('synthetic evidence dependencies require an explicit stable id')
            dependency['max_age'] = pp.duration(dependency['max_age'])
        instance = {'instance_id': control['instance_id'], 'implementation': control['implementation'],
                    'parameters': copy.deepcopy(control['parameters']),
                    'evidence': {e['id']: {'max_age': e['max_age']} for e in control['evidence']}}
        definition = {'metadata': {'id': control['implementation'], 'version': 1},
                      'spec': {'title': control['title'], 'purpose': control['purpose'],
                               'entrypoint': control['entrypoint'],
                               'evidence': [{k: v for k, v in e.items() if k != 'max_age'} for e in control['evidence']]}}
        control['policy_inputs'] = {
            'instance': instance,
            'definition': definition,
            'parameters_schema': {
                '$id': (
                    'https://compliance.example/schemas/controls/'
                    f"{control['implementation']}/parameters/v1.schema.json"
                ),
                'type': 'object',
            },
        }
        from tools.render_plan import control_definition_fingerprint
        control['definition_fingerprint'] = pp.digest(instance) if control['alignment'] == 'realization' else control_definition_fingerprint(instance)
    if not plan['resolved_baselines'] and not plan['resolved_requirement_baselines']:
        for assignment in plan['assignments']:
            for reference in assignment['baselines']:
                identity = pp.digest({'reference': reference})
                policy_sources = [{
                    'policy_source': policy_source_name,
                    'path': 'baselines/test.json',
                }]
                plan['resolved_baselines'].append({'assignment': assignment['id'], 'group': assignment['group'],
                    'reference': reference, 'title': 'Synthetic technical policy',
                    'digest': identity, 'lineage': [{
                        'reference': reference,
                        'digest': identity,
                        'policy_sources': copy.deepcopy(policy_sources),
                    }],
                    'deviations': [], 'policy_sources': policy_sources})
    requirements = {}
    for record in plan['requirements']:
        identifier, revision = record['reference'].rsplit('@', 1)
        doc = {
            'apiVersion': 'compliance.example/v1alpha1',
            'kind': 'ControlRequirement',
            'metadata': {'id': identifier, 'revision': revision},
            'spec': {'title': record['title'], 'statement': record['statement'],
                     'external_refs': copy.deepcopy(record['external_refs'])},
        }
        record['digest'] = pp.digest(doc)
        record['document'] = copy.deepcopy(doc)
        requirements[record['reference']] = doc
        if 'realization' in record:
            rid, rev = record['realization']['reference'].rsplit('@', 1)
            realization = {'apiVersion': 'compliance.example/v1alpha1',
                           'kind': 'ControlRealization',
                           'metadata': {'id': rid, 'revision': rev}, 'spec': {
                'requirement': {'requirement': record['reference'], 'digest': record['digest']},
                'applies_to': {'subject_types': [plan['subject']['type']]},
                'adoption': copy.deepcopy(record['adoption']),
                'checks': [copy.deepcopy(c['policy_inputs']['instance']) for c in plan['controls'] if c['instance_id'] in record['technical_instance_ids']]}}
            if 'based_on' in record['realization']:
                realization['spec']['based_on'] = copy.deepcopy(
                    record['realization']['based_on']
                )
            record['realization']['digest'] = pp.digest(realization)
            record['realization']['document'] = realization
    for baseline in plan['resolved_requirement_baselines']:
        identifier, revision = baseline['reference'].rsplit('@', 1)
        for pin in baseline['requirements']:
            pin['digest'] = pp.digest(requirements[pin['requirement']])
        doc = {'metadata': {'id': identifier, 'revision': revision},
               'spec': {'title': baseline['title'],
                        'requirements': copy.deepcopy(baseline['requirements'])}}
        doc.update(apiVersion='compliance.example/v1alpha1', kind='RequirementBaseline')
        baseline['digest'] = pp.digest(doc)
        baseline['document'] = copy.deepcopy(doc)
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
    assignments = [{'id': a['id'], 'target': {'group': a['group']},
                    'baselines': a['baselines'],
                    'parameter_policies': a.get('parameter_policies', [])}
                   for a in plan['assignments']]
    freeze_operation([plan], {plan['subject']['id']: plan['subject']}, list(groups.values()), assignments,
                     {'subjects': [plan['subject']['id']], 'groups': [], 'all': False})


def planning_fields(sources):
    actual = {'tooling': actual_tooling_identity(), 'policySources': [
        {'name': item['name'], 'content': {'digest': item['digest'], 'digestAlgorithm': POLICY_SOURCE_DIGEST_ALGORITHM}}
        for item in sorted(sources, key=lambda item: item['name'])]}
    return {'schema': PLAN_SCHEMA, 'digestAlgorithm': PLAN_DIGEST_ALGORITHM,
            'provenance': {'schema': PROVENANCE_SCHEMA, 'planningComposition': {
                'actual': actual, 'compositionDigestAlgorithm': COMPOSITION_DIGEST_ALGORITHM,
                'compositionDigest': composition_digest(actual),
                'enforcement': {'directExpectedContent': {}, 'compositionLock': None}}}}
