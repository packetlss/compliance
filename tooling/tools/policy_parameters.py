"""ADR 0012 direct parameter resolution over explicit, pinned JSON facts."""
from __future__ import annotations

import copy
import re

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry

from .assessment_provenance import digest
from ._canonical_json import canonical_json_bytes


class ParameterResolutionError(ValueError):
    """Policy cannot produce an assessable plan."""


def document(value):
    return {k: copy.deepcopy(v) for k, v in value.items() if not k.startswith('_')}


def require(condition, message):
    if not condition:
        raise ParameterResolutionError(message)


def equal(left, right):
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def duration(value):
    require(isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*[smhd]', value),
            'duration must be positive integral fixed s/m/h/d')
    seconds = int(value[:-1]) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[value[-1]]
    return f'{seconds}s'


def validate_schema(schema):
    require(isinstance(schema, dict) and isinstance(schema.get('$id'), str),
            'parameter schema requires explicit identity')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker(), registry=Registry())

    def references(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in ('$ref', '$dynamicRef'):
                    require(child.startswith('#'), 'parameter schema references must be document-local')
                    validator._resolver.lookup(child)
                else:
                    references(child)
        elif isinstance(value, list):
            for child in value:
                references(child)
    references(schema)
    return validator


def value_for(declaration, value):
    validate_schema(declaration['schema']).validate(value)
    canonical_json_bytes(value)  # Reject non-JSON numbers and ambiguous numeric identity.
    return duration(value) if declaration.get('representation') == 'duration' else copy.deepcopy(value)


def declarations(requirement):
    clean = document(requirement)
    reference = f"{clean['metadata']['id']}@{clean['metadata']['revision']}"
    states = {}
    for name, declaration in sorted(clean['spec'].get('parameters', {}).items()):
        require(declaration['schema_digest'] == digest(declaration['schema']), 'stale parameter schema digest')
        validate_schema(declaration['schema'])
        fixed = declaration['binding_mode'] == 'fixed'
        require(fixed == ('value' in declaration), 'only fixed declarations contain values')
        require(fixed or bool(declaration.get('binding_scope')), 'open declaration requires structural binding scope')
        pin = {'requirement': reference, 'digest': digest(clean), 'slot': name,
               'declaration_digest': digest(declaration), 'schema_digest': declaration['schema_digest']}
        state = {'identity': {'requirement': clean['metadata']['id'], 'slot': name},
                 'pin': pin, 'declaration': copy.deepcopy(declaration),
                 'bound': fixed, 'sealed': fixed, 'history': []}
        if fixed:
            state['value'] = value_for(declaration, declaration['value'])
        states[name] = state
    return states


def fingerprint(state):
    return digest({k: v for k, v in state.items() if k != 'history'})


def resolve(reference, baselines, requirements, stack=()):
    require(reference not in stack, 'parameter derivation cycle')
    require(reference in baselines, 'missing parameter baseline')
    baseline = baselines[reference]
    spec = baseline['spec']
    states, ancestry = {}, []
    for pin in spec['requirements']:
        requirement = requirements.get(pin['requirement'])
        require(requirement is not None and digest(document(requirement)) == pin['digest'],
                'stale requirement pin')
        require(pin['requirement'] not in states, 'duplicate requirement membership')
        states[pin['requirement']] = declarations(requirement)
    if 'extends' in spec:
        parent_pin = spec['extends']
        parent = baselines.get(parent_pin['baseline'])
        require(parent is not None and digest(document(parent)) == parent_pin['digest'], 'stale parent policy pin')
        require(equal(sorted(spec['requirements'], key=lambda p: p['requirement']),
                      sorted(parent['spec']['requirements'], key=lambda p: p['requirement'])),
                'parameter derivation cannot change requirement membership')
        states, ancestry = resolve(parent_pin['baseline'], baselines, requirements, (*stack, reference))
    seen_ids, seen_targets = set(), set()
    for operation in sorted(spec.get('parameter_operations', []), key=lambda op: op['id']):
        target = operation['target']
        key = (target['requirement'], target['slot'])
        require(operation['id'] not in seen_ids and key not in seen_targets, 'duplicate or ambiguous parameter operation')
        seen_ids.add(operation['id'])
        seen_targets.add(key)
        state = states.get(key[0], {}).get(key[1])
        require(state is not None, 'missing parameter target')
        require(equal(target, state['pin']), 'stale declaration/schema pin')
        require(operation['expected_parent_fingerprint'] == fingerprint(state), 'stale parameter parent fingerprint')
        require(not state['sealed'], 'fixed or sealed parameter cannot change')
        require(baseline['metadata']['id'] in state['declaration']['binding_scope'], 'parameter operation outside structural scope')
        before = fingerprint(state)
        op = operation['op']
        if op == 'bind':
            require(not state['bound'], 'binding cannot replace inherited value')
            state['value'] = value_for(state['declaration'], operation['to'])
            state['bound'] = True
        elif op == 'tailor':
            require(state['bound'], 'tailoring requires bound parent state')
            require(equal(value_for(state['declaration'], operation['from']), state['value']), 'stale tailoring from value')
            deviation = operation.get('deviation', {})
            require(all(deviation.get(key) for key in ('id', 'classification', 'rationale', 'approval_ref', 'review_after')),
                    'tailoring requires complete deviation provenance')
            state['value'] = value_for(state['declaration'], operation['to'])
        elif op == 'seal':
            require(state['bound'], 'cannot seal an unresolved required value')
            state['sealed'] = True
        else:
            raise ParameterResolutionError('unsupported parameter operation')
        state['history'].append({'baseline': reference, 'operation': copy.deepcopy(operation),
                                 'before_fingerprint': before, 'after_fingerprint': fingerprint(state)})
    ancestry.append({'reference': reference, 'digest': digest(document(baseline)),
                     'document': document(baseline), 'policy_sources': copy.deepcopy(baseline.get('_sources', []))})
    return states, ancestry


def complete(states):
    for slots in states.values():
        for state in slots.values():
            require(state['bound'] or not state['declaration']['required'], 'required policy parameter unresolved')


def reconcile_selected_slots(states, selected):
    """Independently selected exact pins cannot split one semantic slot identity."""
    candidate = dict(selected)
    for slots in states.values():
        for state in slots.values():
            identity = (state['identity']['requirement'], state['identity']['slot'])
            value = fingerprint(state)
            require(identity not in candidate or candidate[identity] == value,
                    'independently selected stable parameter identity conflict')
            candidate[identity] = value
    selected.update(candidate)


def implementation_pin(definition):
    return {'id': definition['metadata']['id'], 'version': definition['metadata']['version'],
            'fingerprint': digest({'manifest': document(definition), 'parameters_schema': definition['_parameters_schema'], 'implementation_modules': definition.get('_implementation_modules', [])})}


def assign_path(target, path, value):
    require(isinstance(path, str) and path.startswith('/') and path != '/', 'destination requires an explicit object path')
    parts = [p.replace('~1', '/').replace('~0', '~') for p in path[1:].split('/')]
    current = target
    for part in parts[:-1]:
        require(isinstance(current, dict) and part in current, 'destination parent is absent or not an object')
        current = current[part]
    require(isinstance(current, dict), 'array values are atomic; destination cannot address an array element')
    require(parts[-1] not in current, 'literal value cannot replace or imitate symbolic consumption')
    current[parts[-1]] = copy.deepcopy(value)


def declared_path(schema, path):
    """Only explicitly named object inputs are initial typed destinations."""
    current = schema
    for part in path[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        require(part in current.get('properties', {}), 'destination input is absent from the pinned interface')
        current = current['properties'][part]


def partial_parameter_schema(schema, paths):
    """Leave symbolic leaf values open until full post-materialization validation."""
    result = copy.deepcopy(schema)
    for path in paths:
        declared_path(schema, path)
        parts = [p.replace('~1', '/').replace('~0', '~') for p in path[1:].split('/')]
        parent = result
        for part in parts[:-1]:
            parent = parent['properties'][part]
        parent['required'] = [name for name in parent.get('required', []) if name != parts[-1]]
        parent['properties'][parts[-1]] = {}
    return result


def evidence_for(instance, definition):
    contracts = definition['spec']['evidence']
    identifiers = [item['id'] for item in contracts]
    require(len(identifiers) == len(set(identifiers)), 'ambiguous evidence dependency identity')
    bindings = instance.get('evidence', {})
    require(set(bindings) == set(identifiers), 'explicit policy freshness required for every evidence dependency')
    result = []
    for contract in sorted(contracts, key=lambda item: item['id']):
        binding = bindings[contract['id']]
        age = duration(binding['max_age'])
        inputs = binding.get('inputs', {})
        input_schema = contract.get('inputs_schema')
        if input_schema is None:
            require(not inputs, 'evidence dependency has no declared input interface')
        else:
            validate_schema(input_schema).validate(inputs)
        result.append({'id': contract['id'], 'type': contract['type'],
                       'max_age': age, **({'inputs': copy.deepcopy(inputs)} if input_schema is not None else {})})
    return result


def consume(realization, slots, controls):
    checks = copy.deepcopy(realization['spec'].get('checks', []))
    by_id = {check['instance_id']: check for check in checks}
    required_ids = realization['spec'].get('satisfaction', {}).get('allOf', [])
    consumed, destinations, link_ids, records = set(), set(), set(), []
    for link in sorted(realization['spec'].get('parameter_links', []), key=lambda item: item['id']):
        require(link['id'] not in link_ids, 'duplicate consumption link identity')
        link_ids.add(link['id'])
        state = slots.get(link['source']['slot'])
        require(state is not None and equal(state['pin'], link['source']), 'stale consumption declaration pin')
        require(state['bound'], 'consumed slot is unresolved')
        target = link['destination']
        check = by_id.get(target['instance_id'])
        require(check is not None and target['instance_id'] in required_ids, 'consumption requires a defined required check')
        definition = controls[check['implementation']]
        require(equal(implementation_pin(definition), target['implementation']), 'stale post-substitution implementation destination')
        key = (target['instance_id'], target['kind'], target.get('dependency'), target['path'])
        require(key not in destinations, 'ambiguous consumption destination')
        destinations.add(key)
        if target['kind'] == 'parameters':
            declared_path(definition['_parameters_schema'], target['path'])
            assign_path(check.setdefault('parameters', {}), target['path'], state['value'])
        else:
            contracts = [d for d in definition['spec']['evidence'] if d['id'] == target['dependency']]
            require(len(contracts) == 1, 'consumption requires an unambiguous evidence dependency')
            binding = check.setdefault('evidence', {}).setdefault(target['dependency'], {})
            if target['kind'] == 'freshness':
                require(target['path'] == '/max_age' and state['declaration'].get('representation') == 'duration',
                        'freshness requires a direct duration slot')
                assign_path(binding, target['path'], state['value'])
            elif target['kind'] == 'evidence_inputs':
                declared_path(contracts[0].get('inputs_schema', {}), target['path'])
                assign_path(binding.setdefault('inputs', {}), target['path'], state['value'])
            else:
                raise ParameterResolutionError('unsupported consumption destination')
        consumed.add(link['source']['slot'])
        records.append({'link': copy.deepcopy(link), 'value': copy.deepcopy(state['value'])})
    if realization['spec']['adoption']['status'] == 'implemented':
        require(all(name in consumed for name, state in slots.items() if state['declaration']['required']),
                'required parameter has no required dependency consumption edge')
    for check in checks:
        definition = controls[check['implementation']]
        Draft202012Validator(definition['_parameters_schema'], format_checker=FormatChecker()).validate(check.get('parameters', {}))
        evidence_for(check, definition)
    return checks, records


def validate_frozen(plan):
    """Check stored derivations and destinations without reopening policy sources."""
    if plan['resolution']['status'] != 'valid':
        return
    assignments = {item['id']: item for item in plan['assignments']}
    expected_selections = {(a['id'], a['group'], reference) for a in assignments.values() for reference in a['baselines']}
    actual_selections = [(b['assignment'], b['group'], b['reference'])
                         for b in [*plan['resolved_baselines'], *plan['resolved_requirement_baselines']]]
    require(len(actual_selections) == len(set(actual_selections)) and set(actual_selections) == expected_selections,
            'frozen derivation coverage differs from selected assignments')
    expected_requirements = {pin['requirement'] for baseline in plan['resolved_requirement_baselines'] for pin in baseline['requirements']}
    require(expected_requirements == {r['reference'] for r in plan['requirements']}, 'frozen requirement membership coverage is incomplete')
    controls = {}
    for control in plan['controls']:
        facts = control['policy_inputs']
        definition = copy.deepcopy(facts['definition'])
        definition['_parameters_schema'] = facts['parameters_schema']
        definition['_implementation_modules'] = facts.get('implementation_modules', [])
        instance = facts['instance']
        from .render_plan import control_definition_fingerprint
        instance_fingerprint = digest(instance) if control['alignment'] == 'realization' else control_definition_fingerprint(instance)
        require(instance_fingerprint == control['definition_fingerprint'], 'frozen policy instance fingerprint mismatch')
        require(definition['metadata']['id'] == control['implementation'], 'frozen implementation definition identity mismatch')
        require(instance['instance_id'] == control['instance_id'] and instance['implementation'] == control['implementation'],
                'frozen technical input identity mismatch')
        require(equal(instance.get('parameters', {}), control['parameters']), 'frozen technical value mismatch')
        require(equal(evidence_for(instance, definition), control['evidence']), 'frozen policy freshness mismatch')
        require(definition['spec']['entrypoint'] == control['entrypoint'], 'frozen implementation entrypoint mismatch')
        Draft202012Validator(definition['_parameters_schema'], format_checker=FormatChecker()).validate(control['parameters'])
        previous = controls.get(control['implementation'])
        require(previous is None or equal(previous, definition), 'divergent frozen implementation definitions')
        controls[control['implementation']] = definition
    requirements = {r['reference']: r['parameter_facts']['document'] for r in plan['requirements']}
    by_reference = {r['reference']: r for r in plan['requirements']}
    selected_slots = {}
    for baseline in plan['resolved_requirement_baselines']:
        facts = baseline['parameter_derivation']
        catalog = {}
        for ancestor in facts['ancestry']:
            require(ancestor['digest'] == digest(ancestor['document']), 'frozen parent document digest mismatch')
            require(ancestor['reference'] not in catalog, 'duplicate frozen derivation ancestor')
            catalog[ancestor['reference']] = {**ancestor['document'], '_sources': ancestor['policy_sources']}
        states, ancestry = resolve(baseline['reference'], catalog, requirements)
        complete(states)
        reconcile_selected_slots(states, selected_slots)
        require(equal(states, facts['states']) and equal(ancestry, facts['ancestry']), 'frozen derivation inconsistent')
        require(baseline['digest'] == ancestry[-1]['digest'], 'selected baseline digest mismatch')
        require(equal(baseline['requirements'], ancestry[-1]['document']['spec']['requirements']),
                'frozen baseline membership differs from selected policy')
        for reference, slots in states.items():
            record = by_reference[reference]
            frozen = record['parameter_facts']
            require(digest(frozen['document']) == record['digest'], 'frozen requirement digest mismatch')
            declaration_document = frozen['document']
            require(reference == f"{declaration_document['metadata']['id']}@{declaration_document['metadata']['revision']}",
                    'frozen requirement reference mismatch')
            for field in ('title', 'statement', 'external_refs'):
                require(equal(record[field], declaration_document['spec'].get(field, [])), 'frozen requirement explanation mismatch')
            require(equal(slots, frozen['states']), 'assigned parameter state conflict')
            if 'realization' not in frozen:
                require(record['adoption'] == {'status': 'not_implemented', 'method': 'none', 'owner': 'unassigned'}
                        and record['satisfaction'] == {'allOf': []} and record['technical_instance_ids'] == []
                        and 'realization' not in record, 'missing-realization record differs from frozen coverage')
                continue
            realization = frozen['realization']
            require(digest(realization) == record['realization']['digest'], 'frozen realization digest mismatch')
            require(record['realization']['reference'] == f"{realization['metadata']['id']}@{realization['metadata']['revision']}",
                    'frozen realization reference mismatch')
            require(realization['spec']['requirement'] == {'requirement': reference, 'digest': record['digest']},
                    'frozen realization requirement pin mismatch')
            require(equal(record['adoption'], realization['spec']['adoption'])
                    and equal(record['satisfaction'], realization['spec'].get('satisfaction', {'allOf': []}))
                    and equal(record['technical_instance_ids'], realization['spec'].get('satisfaction', {'allOf': []})['allOf']),
                    'evaluated requirement differs from frozen realization satisfaction')
            checks, records = consume(realization, slots, controls)
            require(equal(records, frozen['consumption']), 'frozen consumption records mismatch')
            planned = {control['instance_id']: control for control in plan['controls']}
            for check in checks:
                require(equal(check, planned[check['instance_id']]['policy_inputs']['instance']),
                        'frozen materialized destination mismatch')
    for record in plan['requirements']:
        expected = [{'group': b['group'], 'assignment': b['assignment'], 'baseline': b['reference']}
                    for b in plan['resolved_requirement_baselines']
                    if any(pin['requirement'] == record['reference'] and pin['digest'] == record['digest'] and pin['required']
                           for pin in b['requirements'])]
        require(equal(sorted(record['provenance'], key=canonical_json_bytes), sorted(expected, key=canonical_json_bytes)),
                'frozen requirement assignment attribution mismatch')
