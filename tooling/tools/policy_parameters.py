"""ADR 0012 direct parameter resolution over explicit, pinned JSON facts."""
from __future__ import annotations

import copy
import re

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from jsonschema.exceptions import FormatError
from referencing import Registry

from .assessment_provenance import digest
from ._canonical_json import canonical_json_bytes
from .identifiers import (
    EVIDENCE_TYPE,
    ID,
    REFERENCE,
    REVISION,
    SLOT,
    is_canonical_control_evidence_inputs_schema_id,
    is_canonical_control_parameter_schema_id,
    is_canonical_parameter_policy_schema_id,
)


class ParameterResolutionError(ValueError):
    """Policy cannot produce an assessable plan."""


def document(value):
    return {k: copy.deepcopy(v) for k, v in value.items() if not k.startswith('_')}


def authored_parameter_links(value):
    """Return links authored directly by one Check-owning policy document."""
    spec = value.get('spec', {})
    links = copy.deepcopy(spec.get('parameter_links', []))
    for operation in spec.get('operations', []):
        links.extend(copy.deepcopy(operation.get('parameter_links', [])))
    return sorted(links, key=lambda item: item['id'])


def validate_parameter_link_structure(link):
    """Validate the bounded symbolic link wire without a current policy schema."""
    require(isinstance(link, dict) and set(link) == {'id', 'source', 'destination'},
            'unsupported parameter link syntax')
    require(isinstance(link['id'], str) and bool(link['id']),
            'parameter link id must be nonempty')
    source = link['source']
    require(isinstance(source, dict) and set(source) == {
        'policy', 'digest', 'slot', 'declaration_digest', 'schema_digest',
    }, 'unsupported parameter link source syntax')
    require(isinstance(source['policy'], str) and bool(re.fullmatch(REFERENCE, source['policy']))
            and isinstance(source['slot'], str) and bool(re.fullmatch(SLOT, source['slot']))
            and all(valid_digest(source[field]) for field in (
                'digest', 'declaration_digest', 'schema_digest')),
            'invalid parameter link source')
    destination = link['destination']
    require(isinstance(destination, dict)
            and {'instance_id', 'implementation', 'kind', 'path'} <= set(destination)
            and set(destination).issubset({
                'instance_id', 'implementation', 'kind', 'dependency', 'path',
            }), 'unsupported parameter link destination syntax')
    require(isinstance(destination['instance_id'], str)
            and bool(re.fullmatch(ID, destination['instance_id'])),
            'invalid parameter link destination instance')
    validate_implementation_pin_identities(destination['implementation'])
    require(valid_digest(destination['implementation'].get('fingerprint')),
            'invalid frozen implementation fingerprint')
    require(destination['kind'] in {'parameters', 'evidence_inputs', 'freshness'}
            and isinstance(destination['path'], str)
            and bool(re.fullmatch(r'/[^/].*', destination['path'])),
            'invalid parameter link destination interface')
    if destination['kind'] == 'parameters':
        require('dependency' not in destination,
                'parameter destination cannot name an Evidence dependency')
    else:
        require(isinstance(destination.get('dependency'), str)
                and bool(re.fullmatch(SLOT, destination['dependency'])),
                'Evidence destination requires a dependency')
    if destination['kind'] == 'freshness':
        require(destination['path'] == '/max_age',
                'freshness destination must target /max_age')


def technical_document_reference(resource):
    metadata = resource.get('metadata', {})
    revision = metadata.get('revision', metadata.get('version'))
    return f"{metadata.get('id')}@{revision}"


def _validate_authored_evidence(evidence):
    require(isinstance(evidence, dict), 'technical Check evidence must be an object')
    for dependency, requirement in evidence.items():
        require(isinstance(dependency, str) and bool(re.fullmatch(SLOT, dependency))
                and isinstance(requirement, dict)
                and set(requirement).issubset({'max_age', 'inputs'}),
                'unsupported technical Check evidence syntax')
        if 'max_age' in requirement:
            require(isinstance(requirement['max_age'], str)
                    and bool(re.fullmatch(r'[1-9][0-9]*[smhd]', requirement['max_age'])),
                    'invalid technical Check evidence freshness')
        if 'inputs' in requirement:
            require(isinstance(requirement['inputs'], dict),
                    'technical Check Evidence inputs must be an object')


def _validate_authored_control(control, *, allow_external_refs=True):
    """Validate the exact bounded Check wire retained inside a technical owner."""
    allowed_fields = {
        'instance_id', 'implementation', 'parameters', 'severity',
        'remediation', 'evidence',
    }
    if allow_external_refs:
        allowed_fields.add('external_refs')
    require(isinstance(control, dict)
            and {'instance_id', 'implementation'} <= set(control)
            and set(control).issubset(allowed_fields),
            'unsupported frozen technical Check syntax')
    require(isinstance(control['instance_id'], str)
            and bool(re.fullmatch(ID, control['instance_id']))
            and isinstance(control['implementation'], str)
            and bool(re.fullmatch(ID, control['implementation'])),
            'invalid frozen technical Check identity')
    require('parameters' not in control or isinstance(control['parameters'], dict),
            'technical Check parameters must be an object')
    require('severity' not in control
            or control['severity'] in {'info', 'low', 'medium', 'high', 'critical'},
            'invalid technical Check severity')
    require('remediation' not in control or isinstance(control['remediation'], str),
            'invalid technical Check remediation')
    external_refs = control.get('external_refs', [])
    require(isinstance(external_refs, list)
            and len(external_refs) == len(set(external_refs))
            and all(isinstance(item, str) and bool(item) for item in external_refs),
            'invalid technical Check external references')
    _validate_authored_evidence(control.get('evidence', {}))


def _validate_deviation(deviation):
    require(isinstance(deviation, dict)
            and set(deviation) == {
                'id', 'classification', 'rationale', 'approval_ref', 'review_after',
            }
            and all(isinstance(deviation[field], str) and bool(deviation[field])
                    for field in deviation),
            'invalid frozen technical deviation')
    try:
        FormatChecker().check(deviation['review_after'], 'date')
    except FormatError as error:
        raise ParameterResolutionError('invalid frozen technical deviation date') from error


def _validate_annotations(annotations):
    require(isinstance(annotations, dict)
            and set(annotations).issubset({'severity', 'remediation', 'external_refs'}),
            'unsupported frozen technical annotations')
    if 'severity' in annotations:
        require(annotations['severity'] in {'info', 'low', 'medium', 'high', 'critical'},
                'invalid frozen technical annotation severity')
    if 'remediation' in annotations:
        require(isinstance(annotations['remediation'], str),
                'invalid frozen technical annotation remediation')
    if 'external_refs' in annotations:
        refs = annotations['external_refs']
        require(isinstance(refs, list) and len(refs) == len(set(refs))
                and all(isinstance(item, str) and bool(item) for item in refs),
                'invalid frozen technical annotation references')


def validate_technical_consumer_document(resource):
    """Validate frozen Check-owning technical policy syntax needed for replay."""
    require(isinstance(resource, dict)
            and set(resource) == {'apiVersion', 'kind', 'metadata', 'spec'}
            and resource.get('apiVersion') == 'compliance.example/v1',
            'unsupported frozen technical consumer document syntax')
    kind = resource.get('kind')
    require(kind in {'Baseline', 'BaselineOverlay'},
            'unsupported frozen technical consumer kind')
    metadata = resource.get('metadata')
    require(isinstance(metadata, dict), 'technical consumer metadata must be an object')
    require(isinstance(metadata.get('id'), str)
            and bool(re.fullmatch(ID, metadata['id'])),
            'invalid frozen technical consumer identity')
    if kind == 'Baseline':
        require(set(metadata).issubset({'id', 'version', 'revision', 'origin'})
                and (('version' in metadata) != ('revision' in metadata)),
                'unsupported frozen Baseline metadata syntax')
        revision = metadata.get('version', metadata.get('revision'))
        require(valid_revision(revision), 'invalid frozen Baseline revision')
        require('origin' not in metadata or (
                    isinstance(metadata['origin'], dict)
                    and {'type', 'name'} <= set(metadata['origin'])
                    and all(isinstance(metadata['origin'][field], str)
                            and bool(metadata['origin'][field])
                            for field in ('type', 'name'))
                ),
                'invalid frozen Baseline origin')
    else:
        require(set(metadata) == {'id', 'revision'}
                and valid_revision(metadata.get('revision')),
                'unsupported frozen BaselineOverlay metadata syntax')
    spec = resource.get('spec')
    require(isinstance(spec, dict), 'technical consumer spec must be an object')
    if kind == 'Baseline':
        require(set(spec).issubset({'title', 'controls', 'parameter_links'})
                and {'title', 'controls'} <= set(spec)
                and isinstance(spec['title'], str) and bool(spec['title'].strip())
                and isinstance(spec['controls'], list),
                'unsupported frozen Baseline spec syntax')
        for control in spec['controls']:
            _validate_authored_control(control)
    else:
        require(set(spec).issubset({'title', 'extends', 'operations', 'parameter_links'})
                and {'title', 'extends', 'operations'} <= set(spec)
                and isinstance(spec['title'], str) and bool(spec['title'].strip())
                and isinstance(spec['extends'], list) and bool(spec['extends'])
                and isinstance(spec['operations'], list),
                'unsupported frozen BaselineOverlay spec syntax')
        for parent in spec['extends']:
            require(isinstance(parent, dict) and set(parent) == {'baseline', 'digest'}
                    and isinstance(parent['baseline'], str)
                    and bool(re.fullmatch(REFERENCE, parent['baseline']))
                    and valid_digest(parent['digest']),
                    'invalid frozen technical parent pin')
        allowed_operation_fields = {
            'add': {'op', 'control'},
            'tailor': {'op', 'target', 'expected_parent_fingerprint', 'parameters',
                       'evidence', 'deviation'},
            'exclude': {'op', 'target', 'expected_parent_fingerprint', 'deviation'},
            'substitute': {'op', 'target', 'expected_parent_fingerprint', 'implementation',
                           'parameters', 'equivalence_ref', 'parameter_links', 'evidence'},
            'annotate': {'op', 'target', 'expected_parent_fingerprint', 'annotations'},
        }
        required_operation_fields = {
            'add': {'op', 'control'},
            'tailor': {'op', 'target', 'expected_parent_fingerprint', 'parameters', 'deviation'},
            'exclude': {'op', 'target', 'expected_parent_fingerprint', 'deviation'},
            'substitute': {
                'op', 'target', 'expected_parent_fingerprint', 'implementation', 'equivalence_ref',
            },
            'annotate': {'op', 'target', 'expected_parent_fingerprint', 'annotations'},
        }
        for operation in spec['operations']:
            require(isinstance(operation, dict)
                    and operation.get('op') in allowed_operation_fields
                    and required_operation_fields[operation['op']] <= set(operation)
                    and set(operation).issubset(allowed_operation_fields[operation['op']]),
                    'unsupported frozen technical operation syntax')
            if operation['op'] != 'add':
                require(isinstance(operation['target'], str)
                        and bool(re.fullmatch(ID, operation['target']))
                        and valid_digest(operation['expected_parent_fingerprint']),
                        'invalid frozen technical operation target')
            if operation['op'] == 'add':
                _validate_authored_control(operation['control'])
            elif operation['op'] == 'tailor':
                require(isinstance(operation['parameters'], dict),
                        'technical tailor parameters must be an object')
                _validate_authored_evidence(operation.get('evidence', {}))
                _validate_deviation(operation['deviation'])
            elif operation['op'] == 'exclude':
                _validate_deviation(operation['deviation'])
            elif operation['op'] == 'substitute':
                require(isinstance(operation['implementation'], str)
                        and bool(re.fullmatch(ID, operation['implementation']))
                        and isinstance(operation['equivalence_ref'], str)
                        and bool(operation['equivalence_ref']),
                        'invalid frozen technical substitution')
                require('parameters' not in operation
                        or isinstance(operation['parameters'], dict),
                        'technical substitution parameters must be an object')
                _validate_authored_evidence(operation.get('evidence', {}))
            elif operation['op'] == 'annotate':
                _validate_annotations(operation['annotations'])
            operation_links = operation.get('parameter_links', [])
            require(isinstance(operation_links, list),
                    'technical operation parameter links must be an array')
            for link in operation_links:
                validate_parameter_link_structure(link)
    links = spec.get('parameter_links', [])
    require(isinstance(links, list), 'technical parameter links must be an array')
    for link in links:
        validate_parameter_link_structure(link)


def _merge_technical_links(target, incoming):
    for link in incoming:
        existing = target.get(link['id'])
        require(existing is None or equal(existing, link),
                'inherited technical parameter link conflict')
        target[link['id']] = copy.deepcopy(link)


def frozen_technical_links(plan):
    """Reconstruct all effective direct technical links from frozen owner documents."""
    records = [
        item for item in plan.get('parameters', {}).get('consumers', [])
        if item.get('kind') in {'Baseline', 'BaselineOverlay'}
    ]
    catalog = {item['reference']: item for item in records}
    require(len(catalog) == len(records), 'duplicate frozen technical consumer document')
    from .render_plan import baseline_semantic_digest
    for item in records:
        require(set(item) == {
            'kind', 'reference', 'digest', 'policy_sources', 'document',
        }, 'invalid frozen technical parameter consumer')
        validate_technical_consumer_document(item['document'])
        require(item['kind'] == item['document']['kind']
                and item['reference'] == technical_document_reference(item['document'])
                and item['digest'] == baseline_semantic_digest(item['document']),
                'frozen technical parameter consumer owner mismatch')
    technical_catalog = {
        item['reference']: {
            **copy.deepcopy(item['document']),
            '_digest': item['digest'],
            '_sources': copy.deepcopy(item['policy_sources']),
        }
        for item in records
    }
    combined = {}
    visited = set()
    from .render_plan import BaselineResolutionError, resolve_baseline
    for baseline in plan.get('resolved_baselines', []):
        if baseline['reference'] not in catalog:
            continue
        try:
            resolved = resolve_baseline(baseline['reference'], technical_catalog)
        except BaselineResolutionError as error:
            message = {
                'duplicate-parameter-link': 'duplicate technical parameter link',
                'unknown-baseline': 'missing frozen technical consumer ancestor document',
            }.get(error.details.get('type'), 'invalid frozen technical consumer replay')
            raise ParameterResolutionError(message) from error
        links = resolved['parameter_links']
        if not links:
            continue
        ancestry = [item['reference'] for item in resolved['lineage']]
        selected_lineage = [
            (item['reference'], item['digest']) for item in baseline['lineage']
        ]
        reconstructed_lineage = [
            (reference, catalog[reference]['digest']) for reference in ancestry
        ]
        require(selected_lineage == reconstructed_lineage,
                'frozen technical consumer ancestry differs from selected baseline')
        _merge_technical_links(combined, links)
        visited.update(ancestry)
    require(visited == set(catalog),
            'frozen technical consumer document is outside selected consuming ancestry')
    links = [combined[key] for key in sorted(combined)]
    destinations = [(
        link['destination']['instance_id'],
        link['destination']['kind'],
        link['destination'].get('dependency'),
        link['destination']['path'],
    ) for link in links]
    require(len(destinations) == len(set(destinations)),
            'ambiguous consumption destination')
    return links


def normalized_resource_document(value, policies=None):
    """Project parameter resources into their contract-defined semantic order."""
    clean = document(value)
    spec = clean.get('spec', {})
    for declaration in spec.get('parameters', {}).values():
        if declaration.get('composition') == {'kind': 'additive-set'} and 'value' in declaration:
            if isinstance(declaration['value'], list) and all(isinstance(item, str) for item in declaration['value']):
                declaration['value'] = canonical_additive_set(declaration['value'])
    if 'parameter_contributions' in spec:
        for contribution in spec['parameter_contributions']:
            contribution['members'] = canonical_additive_set(contribution['members'])
        spec['parameter_contributions'].sort(key=lambda item: canonical_json_bytes({
            'id': item['id'],
            'target': item['target'],
        }))
    if 'parameter_operations' in spec:
        policy_catalog = policies or {}
        for operation in spec['parameter_operations']:
            target = operation.get('target', {})
            policy = policy_catalog.get(target.get('policy'))
            declaration = (policy or {}).get('spec', {}).get('parameters', {}).get(target.get('slot'))
            if declaration and declaration.get('composition') == {'kind': 'additive-set'}:
                for field in ('from', 'to'):
                    if field in operation:
                        authored = operation[field]
                        if isinstance(authored, list) and all(isinstance(item, str) for item in authored):
                            operation[field] = canonical_additive_set(authored)
        spec['parameter_operations'].sort(key=lambda item: item['id'])
    return clean


def resource_digest(value, policies=None):
    return digest(normalized_resource_document(value, policies))


def validate_parameter_policy_structure(value):
    """Re-enforce the bounded ParameterPolicy wire used by frozen resolution."""
    clean = document(value)
    require(set(clean) == {'apiVersion', 'kind', 'metadata', 'spec'},
            'unsupported parameter policy document syntax')
    require(clean.get('apiVersion') == 'compliance.example/v1alpha1',
            'frozen parameter policy apiVersion mismatch')
    metadata = clean.get('metadata')
    require(clean.get('kind') == 'ParameterPolicy', 'frozen parameter policy kind mismatch')
    require(isinstance(metadata, dict), 'parameter policy metadata must be an object')
    require({'id', 'revision'} <= set(metadata)
            and set(metadata).issubset({'id', 'revision', 'origin'}),
            'unsupported parameter policy metadata syntax')
    require(
        isinstance(metadata.get('id'), str) and bool(re.fullmatch(ID, metadata['id'])),
        'invalid frozen parameter policy identity',
    )
    require(
        valid_revision(metadata.get('revision')),
        'invalid frozen parameter policy revision',
    )
    require('origin' not in metadata or isinstance(metadata['origin'], dict),
            'parameter policy origin must be an object')
    spec = clean.get('spec')
    require(isinstance(spec, dict), 'parameter policy spec must be an object')
    require(set(spec).issubset({
        'parameters', 'extends', 'parameter_operations', 'parameter_contributions',
    }), 'unsupported parameter policy syntax')
    if 'parameters' in spec:
        require(isinstance(spec['parameters'], dict) and bool(spec['parameters']),
                'parameter policy declarations must be nonempty when present')
        for slot, declaration in spec['parameters'].items():
            require(isinstance(slot, str) and bool(re.fullmatch(SLOT, slot)),
                    'invalid ParameterPolicy slot')
            require(isinstance(declaration, dict)
                    and {'required', 'binding_mode', 'schema', 'schema_digest'} <= set(declaration)
                    and set(declaration).issubset({
                        'required', 'binding_mode', 'schema', 'schema_digest',
                        'composition', 'binding_scope', 'value', 'representation',
                    }), 'unsupported parameter declaration syntax')
            require(isinstance(declaration['required'], bool),
                    'parameter declaration required must be boolean')
            require(declaration['binding_mode'] in {'open', 'fixed'},
                    'invalid parameter binding mode')
            require(isinstance(declaration['schema'], dict)
                    and valid_digest(declaration['schema_digest']),
                    'invalid parameter schema contract')
            if 'composition' in declaration:
                require(declaration['composition'] == {'kind': 'additive-set'}
                        and 'representation' not in declaration,
                        'unsupported parameter composition')
            if 'binding_scope' in declaration:
                scope = declaration['binding_scope']
                require(isinstance(scope, list) and bool(scope)
                        and len(scope) == len(set(scope))
                        and all(isinstance(item, str) and bool(re.fullmatch(ID, item))
                                for item in scope),
                        'invalid ParameterPolicy binding scope')
            if declaration['binding_mode'] == 'fixed':
                require('value' in declaration, 'fixed declaration requires a value')
            else:
                require('binding_scope' in declaration and 'value' not in declaration,
                        'open declaration requires scope and cannot own a value')
            require('representation' not in declaration
                    or declaration['representation'] == 'duration',
                    'unsupported parameter representation')
    if 'extends' in spec:
        parent = spec['extends']
        require(
            isinstance(parent, dict)
            and set(parent) == {'policy', 'digest'}
            and isinstance(parent.get('policy'), str)
            and bool(re.fullmatch(REFERENCE, parent['policy']))
            and valid_digest(parent.get('digest')),
            'invalid frozen parameter policy parent reference',
        )
    if 'parameter_operations' in spec:
        operations = spec['parameter_operations']
        require(isinstance(operations, list) and bool(operations),
                'parameter operations must be nonempty when present')
        for operation in operations:
            require(isinstance(operation, dict)
                    and set(operation).issubset({
                        'id', 'op', 'target', 'expected_parent_fingerprint',
                        'from', 'to', 'deviation',
                    })
                    and {'id', 'op', 'target', 'expected_parent_fingerprint'} <= set(operation),
                    'unsupported parameter operation syntax')
            require(isinstance(operation['id'], str) and bool(operation['id'])
                    and operation['op'] in {'bind', 'tailor'}
                    and valid_digest(operation['expected_parent_fingerprint']),
                    'invalid parameter operation')
            target = operation['target']
            require(isinstance(target, dict)
                    and set(target) == {
                        'policy', 'digest', 'slot', 'declaration_digest', 'schema_digest',
                    }
                    and isinstance(target.get('policy'), str)
                    and bool(re.fullmatch(REFERENCE, target['policy']))
                    and isinstance(target.get('slot'), str)
                    and bool(re.fullmatch(SLOT, target['slot']))
                    and all(valid_digest(target.get(field)) for field in (
                        'digest', 'declaration_digest', 'schema_digest')),
                    'invalid parameter operation target')
            if operation['op'] == 'bind':
                require('to' in operation and 'from' not in operation
                        and 'deviation' not in operation,
                        'bind operation requires only a destination value')
            else:
                require({'from', 'to', 'deviation'} <= set(operation),
                        'tailor operation requires from, to, and deviation')
                deviation = operation['deviation']
                require(isinstance(deviation, dict)
                        and set(deviation) == {
                            'id', 'classification', 'rationale', 'approval_ref', 'review_after',
                        }
                        and all(isinstance(deviation[field], str) and bool(deviation[field])
                                for field in deviation),
                        'invalid parameter deviation')
                try:
                    FormatChecker().check(deviation['review_after'], 'date')
                except FormatError as error:
                    raise ParameterResolutionError(
                        'invalid parameter deviation date'
                    ) from error
    if 'parameter_contributions' in spec:
        items = spec['parameter_contributions']
        require(isinstance(items, list) and bool(items),
                'parameter contributions must be nonempty when present')
        for contribution in items:
            require(isinstance(contribution, dict)
                    and set(contribution) == {'id', 'target', 'members'},
                    'unsupported additive contribution syntax')
            target = contribution.get('target')
            require(isinstance(contribution.get('id'), str) and bool(contribution['id']),
                    'additive contribution id must be nonempty')
            require(isinstance(target, dict) and set(target) == {'policy', 'slot'},
                    'unsupported additive contribution target syntax')
            require(isinstance(target.get('policy'), str)
                    and bool(re.fullmatch(ID, target['policy'])),
                    'invalid additive contribution policy target')
            require(isinstance(target.get('slot'), str)
                    and bool(re.fullmatch(SLOT, target['slot'])),
                    'invalid additive contribution slot target')
            members = contribution.get('members')
            require(isinstance(members, list) and all(isinstance(member, str) for member in members),
                    'additive contribution members must be JSON strings')
    require(bool(spec.get('parameters')) or bool(spec.get('extends'))
            or bool(spec.get('parameter_contributions')),
            'parameter policy requires declarations, ancestry, or a contribution')


def require(condition, message):
    if not condition:
        raise ParameterResolutionError(message)


def equal(left, right):
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def valid_revision(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 1
    ) or (
        isinstance(value, str)
        and bool(re.fullmatch(REVISION, value))
    )


def valid_digest(value):
    return isinstance(value, str) and bool(re.fullmatch(r'sha256:[0-9a-f]{64}', value))


def duration(value):
    require(isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*[smhd]', value),
            'duration must be positive integral fixed s/m/h/d')
    seconds = int(value[:-1]) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[value[-1]]
    return f'{seconds}s'


def validate_schema(schema, *, identity_validator=None):
    require(isinstance(schema, dict) and isinstance(schema.get('$id'), str),
            'parameter schema requires explicit identity')
    if identity_validator is not None:
        require(bool(identity_validator(schema['$id'])),
                'parameter schema identity does not match its semantic owner')
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


def validate_composition(declaration):
    composition = declaration.get('composition')
    if composition is None:
        return None
    require(composition == {'kind': 'additive-set'}, 'unsupported parameter composition')
    schema = declaration.get('schema', {})
    require(schema.get('type') == 'array'
            and isinstance(schema.get('items'), dict)
            and schema['items'].get('type') == 'string',
            'additive-set requires a direct string-array parameter schema')
    require('representation' not in declaration,
            'additive-set does not support a transformed representation')
    return composition['kind']


def canonical_additive_set(value):
    require(isinstance(value, list) and all(isinstance(member, str) for member in value),
            'additive-set values contain JSON strings only')
    return sorted(set(value), key=lambda member: member.encode('utf-8'))


def value_for(declaration, value):
    validator = validate_schema(declaration['schema'])
    canonical_json_bytes(value)  # Reject non-JSON numbers and ambiguous numeric identity.
    if validate_composition(declaration) == 'additive-set':
        canonical = canonical_additive_set(value)
        try:
            validator.validate(canonical)
        except ValidationError as error:
            raise ParameterResolutionError(
                f'additive-set value violates the current declaration schema: {error.message}'
            ) from error
        return canonical
    validator.validate(value)
    return duration(value) if declaration.get('representation') == 'duration' else copy.deepcopy(value)


def declarations(policy):
    clean = normalized_resource_document(policy)
    reference = f"{clean['metadata']['id']}@{clean['metadata']['revision']}"
    states = {}
    for name, declaration in sorted(clean['spec'].get('parameters', {}).items()):
        require(
            isinstance(name, str) and bool(re.fullmatch(SLOT, name)),
            'invalid ParameterPolicy slot',
        )
        require(declaration['schema_digest'] == digest(declaration['schema']), 'stale parameter schema digest')
        validate_schema(
            declaration['schema'],
            identity_validator=lambda schema_id: (
                is_canonical_parameter_policy_schema_id(
                    schema_id,
                    clean['metadata']['id'],
                    name,
                )
            ),
        )
        validate_composition(declaration)
        fixed = declaration['binding_mode'] == 'fixed'
        require(fixed == ('value' in declaration), 'only fixed declarations contain values')
        binding_scope = declaration.get('binding_scope')
        if binding_scope is not None:
            require(
                isinstance(binding_scope, list)
                and bool(binding_scope)
                and all(
                    isinstance(item, str) and bool(re.fullmatch(ID, item))
                    for item in binding_scope
                ),
                'invalid ParameterPolicy binding scope',
            )
            require(
                len(binding_scope) == len(set(binding_scope)),
                'invalid ParameterPolicy binding scope',
            )
        require(fixed or binding_scope is not None, 'open declaration requires structural binding scope')
        pin = {'policy': reference, 'digest': digest(clean), 'slot': name,
               'declaration_digest': digest(declaration), 'schema_digest': declaration['schema_digest']}
        state = {'identity': {'policy': clean['metadata']['id'], 'slot': name},
                 'pin': pin, 'declaration': copy.deepcopy(declaration),
                 'bound': fixed, 'history': []}
        if fixed:
            state['value'] = value_for(declaration, declaration['value'])
        states[name] = state
    return states


def fingerprint(state):
    return digest({k: v for k, v in state.items() if k != 'history'})


def resolve(reference, policies, stack=()):
    require(reference not in stack, 'parameter derivation cycle')
    require(reference in policies, 'missing ParameterPolicy')
    policy = policies[reference]
    validate_parameter_policy_structure(policy)
    clean_policy = normalized_resource_document(policy, policies)
    spec = clean_policy['spec']
    states, ancestry = {}, []
    if 'extends' in spec:
        parent_pin = spec['extends']
        parent = policies.get(parent_pin['policy'])
        require(parent is not None and resource_digest(parent, policies) == parent_pin['digest'],
                'stale parent policy pin')
        require(not spec.get('parameters'),
                'descendant ParameterPolicy cannot redeclare inherited slots')
        states, ancestry = resolve(parent_pin['policy'], policies, (*stack, reference))
    else:
        slots = declarations(policy)
        if slots:
            states[reference] = slots
    seen_ids, seen_targets = set(), set()
    for operation in sorted(spec.get('parameter_operations', []), key=lambda op: op['id']):
        target = operation['target']
        key = (target['policy'], target['slot'])
        require(operation['id'] not in seen_ids and key not in seen_targets, 'duplicate or ambiguous parameter operation')
        seen_ids.add(operation['id'])
        seen_targets.add(key)
        state = states.get(key[0], {}).get(key[1])
        require(state is not None, 'missing parameter target')
        require(equal(target, state['pin']), 'stale declaration/schema pin')
        require(operation['expected_parent_fingerprint'] == fingerprint(state), 'stale parameter parent fingerprint')
        require(
            state['declaration'].get('binding_scope') is not None
            and clean_policy['metadata']['id'] in state['declaration']['binding_scope'],
            'parameter operation outside structural scope',
        )
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
        else:
            raise ParameterResolutionError('unsupported parameter operation')
        state['history'].append({'policy': reference, 'operation': copy.deepcopy(operation),
                                 'before_fingerprint': before, 'after_fingerprint': fingerprint(state)})
    ancestry.append({'reference': reference, 'digest': digest(clean_policy),
                     'document': clean_policy, 'policy_sources': copy.deepcopy(policy.get('_sources', []))})
    return states, ancestry


def complete(states):
    for slots in states.values():
        for state in slots.values():
            require(state['bound'] or not state['declaration']['required'], 'required policy parameter unresolved')


def reconcile_selected_slots(states, selected, *, selection):
    """Independently selected exact pins cannot split one semantic slot identity."""
    candidate = dict(selected)
    for slots in states.values():
        for state in slots.values():
            identity = (state['identity']['policy'], state['identity']['slot'])
            value = digest({'selection': selection, 'state': state})
            require(identity not in candidate or candidate[identity] == value,
                    'independently selected stable parameter identity conflict')
            candidate[identity] = value
    selected.update(candidate)


def compose_selected(resolutions, policies):
    """Apply independently applicable additive contributions to resolved base states."""
    ordered = sorted(
        resolutions,
        key=lambda item: canonical_json_bytes({
            'reference': item['reference'],
            'applicability': item['applicability'],
        }),
    )
    selected = {}
    occurrences = {}
    for resolved in ordered:
        reconcile_selected_slots(
            resolved['states'], selected, selection=resolved['reference'],
        )
        for slots in resolved['states'].values():
            for state in slots.values():
                identity = (state['identity']['policy'], state['identity']['slot'])
                occurrences.setdefault(identity, []).append((resolved, state))

    contributions = {}
    for resolved in ordered:
        reference = resolved['reference']
        policy = policies[reference]
        clean = normalized_resource_document(policy, policies)
        owner = {
            'reference': reference,
            'digest': digest(clean),
            'document': clean,
            'policy_sources': copy.deepcopy(policy.get('_sources', [])),
        }
        seen = set()
        for contribution in policy['spec'].get('parameter_contributions', []):
            target = contribution['target']
            identity = {
                'policy': clean['metadata']['id'],
                'id': contribution['id'],
                'target_policy': target['policy'],
                'slot': target['slot'],
            }
            key = tuple(identity.values())
            require(key not in seen, 'duplicate additive contribution identity')
            seen.add(key)
            record = contributions.get(key)
            canonical_members = canonical_additive_set(contribution['members'])
            if record is None:
                record = {
                    'identity': identity,
                    'members': canonical_members,
                    'origins': [],
                    'applicability': [],
                }
                contributions[key] = record
            else:
                require(equal(record['members'], canonical_members),
                        'divergent additive contribution identity')
            path = copy.deepcopy(resolved['applicability'])
            origin = {'owner': copy.deepcopy(owner), 'applicability': path}
            if origin not in record['origins']:
                record['origins'].append(origin)
            if path not in record['applicability']:
                record['applicability'].append(path)

    contributions_by_slot = {}
    for record in contributions.values():
        identity = (record['identity']['target_policy'], record['identity']['slot'])
        require(identity in occurrences, 'additive contribution has no applicable declaration or base')
        representative = occurrences[identity][0][1]
        require(validate_composition(representative['declaration']) == 'additive-set',
                'additive contribution targets an atomic or incompatible slot')
        require(representative['bound'], 'additive contribution has no applicable declaration or base')
        record['origins'].sort(key=canonical_json_bytes)
        record['applicability'].sort(key=canonical_json_bytes)
        contributions_by_slot.setdefault(identity, []).append(record)

    for identity, slot_occurrences in occurrences.items():
        representative = slot_occurrences[0][1]
        if validate_composition(representative['declaration']) != 'additive-set':
            continue
        require(representative['bound'], 'additive-set requires an applicable base value')
        base_value = canonical_additive_set(representative['value'])
        base_origins = []
        for resolved, _ in slot_occurrences:
            ancestry = next(
                item for item in reversed(resolved['ancestry'])
                if item['reference'] == resolved['reference']
            )
            origin = {
                'policy': resolved['reference'],
                'digest': ancestry['digest'],
                'applicability': copy.deepcopy(resolved['applicability']),
            }
            if origin not in base_origins:
                base_origins.append(origin)
        base_origins.sort(key=canonical_json_bytes)
        slot_contributions = sorted(
            contributions_by_slot.get(identity, []),
            key=lambda item: canonical_json_bytes(item['identity']),
        )
        effective = canonical_additive_set([
            *base_value,
            *(member for item in slot_contributions for member in item['members']),
        ])
        effective = value_for(representative['declaration'], effective)
        member_origins = []
        for member in effective:
            origins = [
                {'kind': 'base', **copy.deepcopy(origin)}
                for origin in base_origins
                if member in base_value
            ]
            origins.extend(
                {
                    'kind': 'contribution',
                    'identity': copy.deepcopy(item['identity']),
                }
                for item in slot_contributions
                if member in item['members']
            )
            member_origins.append({
                'member': member,
                'origins': sorted(origins, key=canonical_json_bytes),
            })
        composition = {
            'kind': 'additive-set',
            'base_value': base_value,
            'base_origins': base_origins,
            'contributions': copy.deepcopy(slot_contributions),
            'member_origins': member_origins,
        }
        for _, state in slot_occurrences:
            state['value'] = copy.deepcopy(effective)
            state['composition'] = copy.deepcopy(composition)


def effective_states(resolutions):
    """Return one exact resolved state per declaration reference and slot."""
    result = {}
    for resolved in resolutions:
        for reference, slots in resolved['states'].items():
            target = result.setdefault(reference, {})
            for slot, state in slots.items():
                previous = target.get(slot)
                require(previous is None or equal(previous, state),
                        'independently selected stable parameter identity conflict')
                target[slot] = copy.deepcopy(state)
    return result


def implementation_pin(definition):
    validate_schema(
        definition['_parameters_schema'],
        identity_validator=lambda schema_id: (
            is_canonical_control_parameter_schema_id(
                schema_id,
                definition['metadata']['id'],
            )
        ),
    )
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


def remove_path(target, path):
    """Remove one symbolic destination and prune containers created for it."""
    parts = [part.replace('~1', '/').replace('~0', '~') for part in path[1:].split('/')]
    current = target
    parents = []
    for part in parts[:-1]:
        require(isinstance(current, dict) and part in current,
                'materialized destination path is absent')
        parents.append((current, part))
        current = current[part]
    require(isinstance(current, dict) and parts[-1] in current,
            'materialized destination path is absent')
    del current[parts[-1]]
    for parent, part in reversed(parents):
        if parent[part] == {}:
            del parent[part]
        else:
            break


def dematerialize_links(checks, links):
    """Reconstruct authored Check inputs from exact links and execution inputs."""
    result = copy.deepcopy(checks)
    by_id = {check['instance_id']: check for check in result}
    for link in sorted(links, key=lambda item: item['id'], reverse=True):
        target = link['destination']
        check = by_id[target['instance_id']]
        if target['kind'] == 'parameters':
            container = check['parameters']
        else:
            container = check['evidence'][target['dependency']]
            if target['kind'] == 'evidence_inputs':
                container = container['inputs']
        remove_path(container, target['path'])
        if check.get('evidence') == {}:
            check.pop('evidence')
    return result


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
            validate_schema(
                input_schema,
                identity_validator=lambda schema_id: (
                    is_canonical_control_evidence_inputs_schema_id(
                        schema_id,
                        definition['metadata']['id'],
                        contract['id'],
                    )
                ),
            ).validate(inputs)
        result.append({'id': contract['id'], 'type': contract['type'],
                       'max_age': age, **({'inputs': copy.deepcopy(inputs)} if input_schema is not None else {})})
    return result


def validate_control_contract_identity(definition):
    """Re-enforce the frozen Control identity contract without source schemas."""
    metadata = definition.get('metadata')
    spec = definition.get('spec')
    require(isinstance(metadata, dict), 'frozen Control metadata must be an object')
    require(isinstance(spec, dict), 'frozen Control spec must be an object')
    control_id = metadata.get('id')
    require(
        isinstance(control_id, str) and bool(re.fullmatch(ID, control_id)),
        'invalid frozen Control identity',
    )
    version = metadata.get('version')
    require(valid_revision(version), 'invalid frozen Control version')
    validate_schema(
        definition.get('_parameters_schema'),
        identity_validator=lambda schema_id: (
            is_canonical_control_parameter_schema_id(schema_id, control_id)
        ),
    )
    dependencies = spec.get('evidence')
    require(isinstance(dependencies, list), 'frozen Control evidence must be an array')
    dependency_ids = []
    for dependency in dependencies:
        require(isinstance(dependency, dict), 'frozen Control evidence dependency must be an object')
        dependency_id = dependency.get('id')
        require(
            isinstance(dependency_id, str) and bool(re.fullmatch(SLOT, dependency_id)),
            'invalid frozen Control evidence dependency identity',
        )
        dependency_ids.append(dependency_id)
        require(
            isinstance(dependency.get('type'), str)
            and bool(re.fullmatch(EVIDENCE_TYPE, dependency['type'])),
            'invalid frozen Control evidence type',
        )
        inputs_schema = dependency.get('inputs_schema')
        if inputs_schema is not None:
            validate_schema(
                inputs_schema,
                identity_validator=lambda schema_id: (
                    is_canonical_control_evidence_inputs_schema_id(
                        schema_id,
                        control_id,
                        dependency_id,
                    )
                ),
            )
    require(
        len(dependency_ids) == len(set(dependency_ids)),
        'ambiguous evidence dependency identity',
    )


def consume_links(links, checks, states, controls):
    """Materialize exact ParameterPolicy values into one Check-owner interface."""
    checks = copy.deepcopy(checks)
    by_id = {check['instance_id']: check for check in checks}
    required_ids = [check['instance_id'] for check in checks]
    destinations, link_ids, records = set(), set(), []
    for link in sorted(links, key=lambda item: item['id']):
        require(link['id'] not in link_ids, 'duplicate consumption link identity')
        link_ids.add(link['id'])
        source = link['source']
        state = states.get(source['policy'], {}).get(source['slot'])
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
        records.append({'link': copy.deepcopy(link)})
    for check in checks:
        definition = controls[check['implementation']]
        Draft202012Validator(definition['_parameters_schema'], format_checker=FormatChecker()).validate(check.get('parameters', {}))
        evidence_for(check, definition)
    return checks, records


def consume(owner, states, controls):
    return consume_links(
        owner['spec'].get('parameter_links', []),
        owner['spec'].get('checks', []),
        states,
        controls,
    )


def validate_realization_reference_identity(realization):
    """Validate the bounded historical ControlRealization owner wire."""
    require(isinstance(realization, dict)
            and set(realization) == {'apiVersion', 'kind', 'metadata', 'spec'}
            and realization.get('apiVersion') == 'compliance.example/v1alpha1'
            and realization.get('kind') == 'ControlRealization',
            'unsupported frozen ControlRealization document syntax')
    metadata = realization.get('metadata')
    spec = realization.get('spec')
    require(isinstance(metadata, dict) and set(metadata) == {'id', 'revision'},
            'unsupported frozen ControlRealization metadata syntax')
    require(
        isinstance(metadata.get('id'), str) and bool(re.fullmatch(ID, metadata['id'])),
        'invalid frozen realization identity',
    )
    require(
        valid_revision(metadata.get('revision')),
        'invalid frozen realization revision',
    )
    require(isinstance(spec, dict)
            and {'requirement', 'applies_to', 'adoption'} <= set(spec)
            and set(spec).issubset({
                'requirement', 'based_on', 'applies_to', 'adoption', 'checks',
                'parameter_links',
            }), 'unsupported frozen ControlRealization spec syntax')
    requirement = spec['requirement']
    require(isinstance(requirement, dict)
            and set(requirement) == {'requirement', 'digest'}
            and isinstance(requirement['requirement'], str)
            and bool(re.fullmatch(REFERENCE, requirement['requirement']))
            and valid_digest(requirement['digest']),
            'invalid frozen ControlRealization Objective pin')
    based_on = spec.get('based_on')
    if based_on is not None:
        require(
            isinstance(based_on, dict)
            and set(based_on) == {'realization', 'digest'}
            and isinstance(based_on.get('realization'), str)
            and bool(re.fullmatch(REFERENCE, based_on['realization']))
            and valid_digest(based_on.get('digest')),
            'invalid frozen realization parent reference',
        )
    applies_to = spec['applies_to']
    require(isinstance(applies_to, dict)
            and {'subject_types'} <= set(applies_to)
            and set(applies_to).issubset({'subject_types', 'match_labels'}),
            'unsupported frozen ControlRealization applicability syntax')
    subject_types = applies_to['subject_types']
    require(isinstance(subject_types, list) and bool(subject_types)
            and len(subject_types) == len(set(subject_types))
            and all(isinstance(item, str) and bool(item) for item in subject_types),
            'invalid frozen ControlRealization subject types')
    if 'match_labels' in applies_to:
        labels = applies_to['match_labels']
        require(isinstance(labels, dict) and bool(labels)
                and all(isinstance(key, str) and bool(key)
                        and isinstance(value, str)
                        for key, value in labels.items()),
                'invalid frozen ControlRealization labels')
    adoption = spec['adoption']
    require(isinstance(adoption, dict)
            and {'status', 'method', 'owner'} <= set(adoption)
            and set(adoption).issubset({
                'status', 'method', 'owner', 'implementation_ref', 'determination',
            })
            and adoption['status'] in {
                'implemented', 'not_implemented', 'not_applicable',
            }
            and adoption['method'] in {'automated', 'hybrid', 'manual', 'none'}
            and isinstance(adoption['owner'], str) and bool(adoption['owner']),
            'invalid frozen ControlRealization adoption')
    if 'implementation_ref' in adoption:
        require(isinstance(adoption['implementation_ref'], str)
                and bool(adoption['implementation_ref']),
                'invalid frozen ControlRealization implementation reference')
    if 'determination' in adoption:
        determination = adoption['determination']
        require(isinstance(determination, dict)
                and set(determination) == {
                    'rationale', 'approval_ref', 'review_after',
                }
                and all(isinstance(determination[field], str)
                        and bool(determination[field]) for field in determination),
                'invalid frozen ControlRealization determination')
        try:
            FormatChecker().check(determination['review_after'], 'date')
        except FormatError as error:
            raise ParameterResolutionError(
                'invalid frozen ControlRealization determination date'
            ) from error
    status = adoption['status']
    if status == 'implemented':
        require(adoption['method'] in {'automated', 'hybrid', 'manual'}
                and 'implementation_ref' in adoption,
                'implemented realization requires an implementation reference')
    else:
        require(adoption['method'] == 'none',
                'non-implemented realization adoption method must be none')
    if status == 'not_applicable':
        require('determination' in adoption,
                'not-applicable realization requires a determination')
    checks = spec.get('checks', [])
    require(isinstance(checks, list), 'realization Checks must be an array')
    require((status == 'implemented' and bool(checks))
            or (status != 'implemented' and not checks),
            'realization Check membership differs from adoption')
    for check in checks:
        _validate_authored_control(check, allow_external_refs=False)
    links = spec.get('parameter_links', [])
    require(isinstance(links, list), 'realization parameter links must be an array')
    for link in links:
        validate_parameter_link_structure(link)


def _validate_frozen_origin(metadata, resource_kind):
    origin = metadata.get('origin')
    if origin is None:
        return
    require(isinstance(origin, dict)
            and {'type', 'name'} <= set(origin)
            and all(isinstance(origin[field], str) and bool(origin[field])
                    for field in ('type', 'name')),
            f'invalid frozen {resource_kind} origin')


def validate_requirement_baseline_document(resource):
    """Validate the bounded historical RequirementBaseline source wire."""
    require(isinstance(resource, dict)
            and set(resource) == {'apiVersion', 'kind', 'metadata', 'spec'}
            and resource.get('apiVersion') == 'compliance.example/v1alpha1'
            and resource.get('kind') == 'RequirementBaseline',
            'unsupported frozen RequirementBaseline document syntax')
    metadata = resource.get('metadata')
    require(isinstance(metadata, dict)
            and {'id', 'revision'} <= set(metadata)
            and set(metadata).issubset({'id', 'revision', 'origin'})
            and isinstance(metadata['id'], str)
            and bool(re.fullmatch(ID, metadata['id']))
            and valid_revision(metadata['revision']),
            'unsupported frozen RequirementBaseline metadata syntax')
    _validate_frozen_origin(metadata, 'RequirementBaseline')
    spec = resource.get('spec')
    require(isinstance(spec, dict)
            and set(spec) == {'title', 'requirements'}
            and isinstance(spec['title'], str) and bool(spec['title'].strip())
            and isinstance(spec['requirements'], list) and bool(spec['requirements']),
            'unsupported frozen RequirementBaseline spec syntax')
    references = []
    for pin in spec['requirements']:
        require(isinstance(pin, dict) and set(pin) == {'requirement', 'digest'}
                and isinstance(pin['requirement'], str)
                and bool(re.fullmatch(REFERENCE, pin['requirement']))
                and valid_digest(pin['digest']),
                'invalid frozen RequirementBaseline Objective pin')
        references.append(pin['requirement'])
    require(len(references) == len(set(references)),
            'duplicate frozen RequirementBaseline Objective pin')


def validate_objective_document(resource):
    """Validate the bounded historical ControlRequirement source wire."""
    require(isinstance(resource, dict)
            and set(resource) == {'apiVersion', 'kind', 'metadata', 'spec'}
            and resource.get('apiVersion') == 'compliance.example/v1alpha1'
            and resource.get('kind') == 'ControlRequirement',
            'unsupported frozen Objective document syntax')
    metadata = resource.get('metadata')
    require(isinstance(metadata, dict)
            and {'id', 'revision'} <= set(metadata)
            and set(metadata).issubset({'id', 'revision', 'origin'})
            and isinstance(metadata['id'], str)
            and bool(re.fullmatch(ID, metadata['id']))
            and valid_revision(metadata['revision']),
            'unsupported frozen Objective metadata syntax')
    _validate_frozen_origin(metadata, 'Objective')
    spec = resource.get('spec')
    require(isinstance(spec, dict)
            and {'title', 'statement'} <= set(spec)
            and set(spec).issubset({'title', 'statement', 'rationale', 'external_refs'})
            and all(isinstance(spec[field], str) and bool(spec[field])
                    for field in ('title', 'statement')),
            'unsupported frozen Objective spec syntax')
    if 'rationale' in spec:
        require(isinstance(spec['rationale'], str) and bool(spec['rationale']),
                'invalid frozen Objective rationale')
    external_refs = spec.get('external_refs', [])
    require(isinstance(external_refs, list)
            and len(external_refs) == len(set(external_refs))
            and all(isinstance(item, str) and bool(item) for item in external_refs),
            'invalid frozen Objective external references')


def require_identity(value, grammar, message):
    require(
        isinstance(value, str) and bool(re.fullmatch(grammar, value)),
        message,
    )


def validate_implementation_pin_identities(pin):
    require(isinstance(pin, dict), 'frozen implementation pin must be an object')
    require_identity(
        pin.get('id'),
        ID,
        'invalid frozen implementation pin identity',
    )
    require(
        valid_revision(pin.get('version')),
        'invalid frozen implementation pin version',
    )


def validate_control_instance_identities(instance):
    require(isinstance(instance, dict), 'frozen Control instance must be an object')
    require_identity(
        instance.get('instance_id'),
        ID,
        'invalid frozen Control instance identity',
    )
    require_identity(
        instance.get('implementation'),
        ID,
        'invalid frozen Control implementation reference',
    )
    evidence = instance.get('evidence', {})
    require(isinstance(evidence, dict), 'frozen Control instance evidence must be an object')
    for dependency_id in evidence:
        require_identity(
            dependency_id,
            SLOT,
            'invalid frozen Control evidence dependency reference',
        )
    validate_control_lineage_identities(instance.get('lineage', []))
    validate_control_derivation_identities(instance.get('derivations', []))
    require('overlay_policy' not in instance, 'frozen Control contains removed overlay policy')


def validate_control_lineage_identities(lineage):
    require(isinstance(lineage, list), 'frozen Control lineage must be an array')
    for entry in lineage:
        require(
            isinstance(entry, dict),
            'frozen Control lineage entry must be an object',
        )
        reference_fields = [
            field for field in ('baseline', 'realization') if field in entry
        ]
        require(
            len(reference_fields) == 1,
            'frozen Control lineage entry must have one semantic reference',
        )
        require_identity(
            entry[reference_fields[0]],
            REFERENCE,
            'invalid frozen Control lineage reference',
        )


def validate_control_criteria_identities(criteria):
    require(
        isinstance(criteria, dict),
        'frozen Control criteria must be an object',
    )
    require_identity(
        criteria.get('implementation'),
        ID,
        'invalid frozen Control criteria implementation reference',
    )
    evidence = criteria.get('evidence', {})
    require(
        isinstance(evidence, dict),
        'frozen Control criteria evidence must be an object',
    )
    for dependency_id in evidence:
        require_identity(
            dependency_id,
            SLOT,
            'invalid frozen Control criteria evidence dependency reference',
        )


def validate_control_derivation_identities(derivations):
    require(
        isinstance(derivations, list),
        'frozen Control derivations must be an array',
    )
    for derivation in derivations:
        require(
            isinstance(derivation, dict),
            'frozen Control derivation must be an object',
        )
        require_identity(
            derivation.get('overlay'),
            REFERENCE,
            'invalid frozen Control derivation overlay reference',
        )
        validate_control_lineage_identities(
            derivation.get('inherited_lineage', []),
        )
        for snapshot_name in ('before', 'after'):
            validate_control_criteria_identities(derivation.get(snapshot_name))


def validate_frozen_contract_identities(plan):
    """Validate retained semantic/schema contracts independently of resolution."""
    technical_links = frozen_technical_links(plan)
    technical_selections = {}
    for baseline in plan['resolved_baselines']:
        reference = baseline.get('reference')
        require_identity(
            reference,
            REFERENCE,
            'invalid frozen technical baseline reference',
        )
        lineage = baseline.get('lineage')
        require(
            isinstance(lineage, list) and bool(lineage),
            'frozen technical baseline lineage must be a non-empty array',
        )
        for ancestor in lineage:
            require(
                isinstance(ancestor, dict),
                'frozen technical baseline ancestor must be an object',
            )
            require_identity(
                ancestor.get('reference'),
                REFERENCE,
                'invalid frozen technical baseline ancestor reference',
            )
        require(
            lineage[-1].get('reference') == reference,
            'frozen technical baseline terminal reference mismatch',
        )
        require(
            lineage[-1].get('digest') == baseline.get('digest'),
            'frozen technical baseline terminal digest mismatch',
        )
        require(
            equal(lineage[-1].get('policy_sources'), baseline.get('policy_sources')),
            'frozen technical baseline terminal source mismatch',
        )
        key = (baseline.get('assignment'), baseline.get('group'), reference)
        require(
            key not in technical_selections,
            'duplicate frozen technical baseline selection',
        )
        technical_selections[key] = baseline

    requirement_selections = {
        (baseline.get('assignment'), baseline.get('group'), baseline.get('reference')):
        baseline
        for baseline in plan['resolved_requirement_baselines']
    }
    requirement_records = {
        requirement.get('reference'): requirement
        for requirement in plan['requirements']
    }
    realization_memberships = set()
    for requirement in plan['requirements']:
        realization = requirement.get('realization', {}).get('document')
        if not isinstance(realization, dict):
            continue
        metadata = realization.get('metadata', {})
        realization_reference = (
            f"{metadata.get('id')}@{metadata.get('revision')}"
        )
        instance_ids = [check['instance_id'] for check in realization['spec'].get('checks', [])]
        if isinstance(instance_ids, list):
            realization_memberships.update(
                (requirement.get('reference'), realization_reference, instance_id)
                for instance_id in instance_ids
            )
    controls = {}
    for collection_name in ('controls', 'excluded_controls'):
        for control in plan[collection_name]:
            facts = control['policy_inputs']
            definition = copy.deepcopy(facts['definition'])
            definition['_parameters_schema'] = facts['parameters_schema']
            definition['_implementation_modules'] = facts.get(
                'implementation_modules',
                [],
            )
            validate_control_contract_identity(definition)
            validate_control_instance_identities(facts['instance'])
            require(
                definition['metadata']['id'] == control['implementation'],
                'frozen implementation definition identity mismatch',
            )
            require(
                facts['instance']['instance_id'] == control['instance_id']
                and facts['instance']['implementation'] == control['implementation'],
                'frozen technical input identity mismatch',
            )
            from .render_plan import control_definition_fingerprint
            instance = facts['instance']
            fingerprint_instance = instance
            instance_links = [
                link for link in technical_links
                if link['destination']['instance_id'] == control['instance_id']
            ]
            if instance_links:
                fingerprint_instance = dematerialize_links(
                    [instance], instance_links
                )[0]
            instance_fingerprint = (
                digest(instance)
                if control['alignment'] == 'realization'
                else control_definition_fingerprint(fingerprint_instance)
            )
            require(
                instance_fingerprint == control['definition_fingerprint'],
                'frozen policy instance fingerprint mismatch',
            )
            require(
                equal(instance.get('parameters', {}), control['parameters']),
                'frozen technical value mismatch',
            )
            resolved_evidence = evidence_for(instance, definition)
            if collection_name == 'controls':
                require(
                    equal(resolved_evidence, control['evidence']),
                    'frozen policy freshness mismatch',
                )
                require(
                    definition['spec']['entrypoint'] == control['entrypoint'],
                    'frozen implementation entrypoint mismatch',
                )
            previous = controls.get(control['implementation'])
            require(
                previous is None or equal(previous, definition),
                'divergent frozen implementation definitions',
            )
            controls[control['implementation']] = definition
            validate_control_lineage_identities(control.get('lineage', []))
            validate_control_derivation_identities(control.get('derivations', []))
            require('overlay_policy' not in control, 'frozen Control contains removed overlay policy')
            if control['alignment'] == 'realization':
                require(
                    all(
                        field not in instance
                        for field in (
                            'alignment',
                            'definition_fingerprint',
                            'derivations',
                            'deviations',
                            'disposition',
                            'lineage',
                        )
                    ),
                    'frozen realization check contains technical derivation facts',
                )
            else:
                for field in ('alignment', 'definition_fingerprint', 'disposition'):
                    if field in instance:
                        require(
                            equal(instance[field], control.get(field)),
                            f'frozen technical {field} differs from retained instance',
                        )
                require(
                    all(
                        item in control.get('lineage', [])
                        for item in instance.get('lineage', [])
                    ),
                    'frozen technical lineage differs from retained instance',
                )
                require(
                    all(
                        item in control.get('derivations', [])
                        for item in instance.get('derivations', [])
                    ),
                    'frozen technical derivations differ from retained instance',
                )
                require(
                    all(
                        item in control.get('deviations', [])
                        for item in instance.get('deviations', [])
                    ),
                    'frozen technical deviations differ from retained instance',
                )
                require('overlay_policy' not in instance,
                        'frozen technical instance contains removed overlay policy')

            technical_lineage = set()
            realization_lineage = set()
            technical_deviations = []
            provenance_records = control.get('provenance', [])
            require(
                all(
                    ('requirement' in provenance)
                    == ('realization' in provenance)
                    for provenance in provenance_records
                ),
                'frozen Control provenance kind is incomplete',
            )
            require(
                all(
                    ('requirement' in provenance)
                    == (control['alignment'] == 'realization')
                    for provenance in provenance_records
                ),
                'frozen Control provenance kind differs from alignment',
            )
            for provenance in provenance_records:
                if 'requirement' in provenance:
                    key = (
                        provenance.get('assignment'),
                        provenance.get('group'),
                        provenance.get('baseline'),
                    )
                    require(
                        key in requirement_selections,
                        'frozen realization provenance has no selected baseline',
                    )
                    requirement_record = requirement_records.get(
                        provenance.get('requirement')
                    )
                    require(
                        requirement_record is not None
                        and any(
                            pin.get('requirement')
                            == provenance.get('requirement')
                            and pin.get('digest') == requirement_record.get('digest')
                            for pin in requirement_selections[key].get(
                                'requirements',
                                [],
                            )
                        ),
                        'frozen realization provenance has no matching baseline membership',
                    )
                    require(
                        (
                            provenance.get('requirement'),
                            provenance.get('realization'),
                            control['instance_id'],
                        ) in realization_memberships,
                        'frozen realization provenance differs from requirement coverage',
                    )
                    realization_lineage.add(provenance.get('realization'))
                else:
                    key = (
                        provenance.get('assignment'),
                        provenance.get('group'),
                        provenance.get('baseline'),
                    )
                    selected = technical_selections.get(key)
                    require(
                        selected is not None,
                        'frozen technical Control provenance has no selected technical baseline',
                    )
                    technical_lineage.update(
                        ancestor['reference']
                        for ancestor in selected['lineage']
                    )
                    for deviation in selected.get('deviations', []):
                        if deviation not in technical_deviations:
                            technical_deviations.append(deviation)
            for lineage_entry in control.get('lineage', []):
                if 'baseline' in lineage_entry:
                    require(
                        lineage_entry['baseline'] in technical_lineage,
                        'frozen Control lineage has no selected baseline ancestry',
                    )
                else:
                    require(
                        lineage_entry['realization'] in realization_lineage,
                        'frozen Control lineage has no selected realization',
                    )
            for derivation in control.get('derivations', []):
                require(
                    derivation['overlay'] in technical_lineage,
                    'frozen Control derivation has no selected baseline ancestry',
                )
                for lineage_entry in derivation['inherited_lineage']:
                    if 'baseline' in lineage_entry:
                        require(
                            lineage_entry['baseline'] in technical_lineage,
                            'frozen inherited lineage has no selected baseline ancestry',
                        )
            require(
                all(
                    deviation in technical_deviations
                    for deviation in control.get('deviations', [])
                ),
                'frozen Control deviation has no selected baseline attribution',
            )

    return
def validate_frozen_parameter_inputs(plan):
    """Validate retained ParameterPolicy documents and explicit applicability."""
    frozen = plan.get('parameters')
    require(isinstance(frozen, dict), 'frozen ParameterPolicy facts must be an object')
    require(set(frozen) == {'documents', 'applicability', 'consumers'},
            'unsupported frozen ParameterPolicy representation')
    documents = frozen['documents']
    require(isinstance(documents, list), 'frozen ParameterPolicy documents must be an array')
    references = [item.get('reference') for item in documents]
    require(references == sorted(set(references)),
            'frozen ParameterPolicy documents must use unique canonical order')
    catalog = {}
    actual_policy_sources = {
        item['name']
        for item in plan['provenance']['planningComposition']['actual']['policySources']
    }
    for item in documents:
        require(isinstance(item, dict)
                and set(item) == {'reference', 'digest', 'document', 'policy_sources'},
                'invalid frozen ParameterPolicy document record')
        resource = item['document']
        validate_parameter_policy_structure(resource)
        reference = f"{resource['metadata']['id']}@{resource['metadata']['revision']}"
        require(reference == item['reference'], 'frozen ParameterPolicy reference mismatch')
        require(isinstance(item['policy_sources'], list) and bool(item['policy_sources']),
                'frozen ParameterPolicy source attribution is required')
        require(all(locator.get('policy_source') in actual_policy_sources
                    for locator in item['policy_sources']),
                'frozen ParameterPolicy source is absent from planning composition')
        catalog[reference] = {**copy.deepcopy(resource), '_sources': copy.deepcopy(item['policy_sources'])}
    for item in documents:
        require(resource_digest(item['document'], catalog) == item['digest'],
                'frozen ParameterPolicy content pin mismatch')

    applicability = frozen['applicability']
    require(isinstance(applicability, list), 'frozen ParameterPolicy applicability must be an array')
    require(applicability == sorted(applicability, key=canonical_json_bytes)
            and len({canonical_json_bytes(item) for item in applicability}) == len(applicability),
            'frozen ParameterPolicy applicability must be unique and canonical')
    expected = sorted([
        {
            'group': assignment['group'],
            'assignment': assignment['id'],
            'parameter_policy': reference,
        }
        for assignment in plan['assignments']
        for reference in assignment.get('parameter_policies', [])
    ], key=canonical_json_bytes)
    require(equal(applicability, expected),
            'frozen ParameterPolicy applicability differs from assignments')
    return frozen, catalog, applicability


def reconstruct_frozen_parameters(plan):
    """Reconstruct effective parameter state from retained historical source facts."""
    _, catalog, applicability = validate_frozen_parameter_inputs(plan)

    resolutions = []
    visited = set()
    for path in applicability:
        reference = path['parameter_policy']
        states, ancestry = resolve(reference, catalog)
        complete(states)
        resolutions.append({
            'reference': reference,
            'applicability': copy.deepcopy(path),
            'states': states,
            'ancestry': ancestry,
        })
        visited.update(item['reference'] for item in ancestry)
    require(visited == set(catalog),
            'frozen ParameterPolicy table contains unselected source documents')
    compose_selected(resolutions, catalog)
    return effective_states(resolutions), resolutions, catalog


def _validate_requirement_facts(plan, controls, states):
    actual_policy_sources = {
        item['name']
        for item in plan['provenance']['planningComposition']['actual']['policySources']
    }

    def validate_sources(record, resource_kind):
        sources = record.get('policy_sources')
        require(isinstance(sources, list) and bool(sources)
                and all(locator.get('policy_source') in actual_policy_sources
                        for locator in sources),
                f'frozen {resource_kind} source is absent from planning composition')

    for baseline in plan['resolved_requirement_baselines']:
        validate_sources(baseline, 'RequirementBaseline')
        resource = baseline.get('document')
        validate_requirement_baseline_document(resource)
        reference = f"{resource['metadata']['id']}@{resource['metadata']['revision']}"
        require(reference == baseline['reference'] == baseline['baseline']
                and digest(resource) == baseline['digest'],
                'frozen RequirementBaseline content pin mismatch')
        require(resource['spec'].get('title') == baseline['title']
                and equal(resource['spec'].get('requirements', []), baseline['requirements']),
                'frozen RequirementBaseline projection mismatch')
        require(not ({'parameters', 'parameter_operations', 'parameter_contributions'}
                     & set(resource['spec'])),
                'RequirementBaseline cannot own parameter state')
    memberships = {
        (pin['requirement'], pin['digest'])
        for baseline in plan['resolved_requirement_baselines']
        for pin in baseline['requirements']
    }
    requirement_memberships = [
        (requirement['reference'], requirement['digest'])
        for requirement in plan['requirements']
    ]
    if plan['resolution']['status'] == 'valid':
        require(len(requirement_memberships) == len(set(requirement_memberships))
                and set(requirement_memberships) == memberships,
                'frozen Objective membership differs from selected baselines')
    planned = {item['instance_id']: item for item in plan['controls']}
    realization_consumers = {
        item['reference']: item
        for item in plan['parameters']['consumers']
        if item['kind'] == 'ControlRealization'
    }
    for requirement in plan['requirements']:
        validate_sources(requirement, 'Objective')
        resource = requirement.get('document')
        validate_objective_document(resource)
        reference = f"{resource['metadata']['id']}@{resource['metadata']['revision']}"
        require(reference == requirement['reference']
                and digest(resource) == requirement['digest'],
                'frozen Objective content pin mismatch')
        for field in ('title', 'statement', 'external_refs'):
            require(equal(requirement.get(field), resource['spec'].get(field, [])),
                    'frozen Objective explanation mismatch')
        expected_provenance = [{
            'group': baseline['group'],
            'assignment': baseline['assignment'],
            'baseline': baseline['reference'],
        } for baseline in plan['resolved_requirement_baselines']
          if any(pin['requirement'] == reference and pin['digest'] == requirement['digest']
                 for pin in baseline['requirements'])]
        require(equal(sorted(requirement['provenance'], key=canonical_json_bytes),
                      sorted(expected_provenance, key=canonical_json_bytes)),
                'frozen Objective assignment attribution mismatch')
        realization_record = requirement.get('realization')
        if realization_record is None:
            require('adoption' not in requirement
                    and requirement['implementation_state'] == 'no_realization'
                    and requirement['technical_instance_ids'] == [],
                    'missing-realization record differs from frozen coverage')
            continue
        validate_sources(realization_record, 'ControlRealization')
        realization = realization_record.get('document')
        validate_realization_reference_identity(realization)
        realization_reference = f"{realization['metadata']['id']}@{realization['metadata']['revision']}"
        require(realization_reference == realization_record['reference']
                and digest(realization) == realization_record['digest'],
                'frozen realization content pin mismatch')
        require(realization['spec']['requirement'] == {
            'requirement': reference,
            'digest': requirement['digest'],
        }, 'frozen realization Objective pin mismatch')
        checks = realization['spec'].get('checks', [])
        require(equal(requirement['technical_instance_ids'],
                      [check['instance_id'] for check in checks])
                and equal(requirement.get('adoption'), realization['spec']['adoption'])
                and requirement['implementation_state'] == realization['spec']['adoption']['status'],
                'frozen realization membership or adoption mismatch')
        materialized, records = consume(realization, states, controls)
        has_links = bool(realization['spec'].get('parameter_links', []))
        require(has_links == (realization_reference in realization_consumers),
                'frozen realization consumer attribution mismatch')
        if has_links:
            consumer = realization_consumers[realization_reference]
            require(set(consumer) == {'kind', 'reference', 'digest', 'policy_sources'},
                    'realization consumer duplicates authored links')
            require(consumer['digest'] == realization_record['digest']
                    and equal(consumer['policy_sources'], realization_record['policy_sources']),
                    'frozen realization consumer owner mismatch')
        for check in materialized:
            require(check['instance_id'] in planned
                    and equal(check, planned[check['instance_id']]['policy_inputs']['instance']),
                    'frozen realization materialized destination mismatch')


def _validate_technical_consumers(plan, controls, states):
    planned = {}
    for item in [*plan['controls'], *plan['excluded_controls']]:
        require(item['instance_id'] not in planned,
                'duplicate active/excluded technical Check identity')
        planned[item['instance_id']] = item
    links = frozen_technical_links(plan)
    source_checks = dematerialize_links(
        [copy.deepcopy(item['policy_inputs']['instance']) for item in planned.values()],
        links,
    )
    source_by_id = {item['instance_id']: item for item in source_checks}
    materialized, _ = consume_links(links, source_checks, states, controls)
    for check in materialized:
        require(equal(check, planned[check['instance_id']]['policy_inputs']['instance']),
                'frozen technical materialized destination mismatch')
    technical_records = {
        consumer['reference']: consumer
        for consumer in plan['parameters']['consumers']
        if consumer['kind'] in {'Baseline', 'BaselineOverlay'}
    }
    technical_catalog = {
        reference: {
            **copy.deepcopy(record['document']),
            '_digest': record['digest'],
            '_sources': copy.deepcopy(record['policy_sources']),
        }
        for reference, record in technical_records.items()
    }
    from .render_plan import resolve_baseline
    for baseline in plan['resolved_baselines']:
        if baseline['reference'] not in technical_catalog:
            continue
        resolved = resolve_baseline(baseline['reference'], technical_catalog)
        if not resolved['parameter_links']:
            continue
        provenance = {
            'group': baseline['group'],
            'assignment': baseline['assignment'],
            'baseline': baseline['reference'],
        }
        planned_ids = {
            instance_id for instance_id, item in planned.items()
            if provenance in item['provenance']
        }
        require(planned_ids == set(resolved['controls']),
                'frozen technical consumer Check membership differs from retained owner')
        for instance_id, expected in resolved['controls'].items():
            require(instance_id in source_by_id
                    and equal(expected, source_by_id[instance_id]),
                    'frozen technical consumer Check differs from retained owner')
    for consumer in plan['parameters']['consumers']:
        if consumer['kind'] == 'ControlRealization':
            continue
        require(consumer['kind'] in {'Baseline', 'BaselineOverlay'},
                'unsupported frozen parameter consumer kind')
        require(set(consumer) == {
            'kind', 'reference', 'digest', 'policy_sources', 'document'
        }, 'invalid frozen technical parameter consumer')
        document = consumer['document']
        validate_technical_consumer_document(document)
        require(document.get('kind') == consumer['kind'],
                'frozen technical parameter consumer kind mismatch')
        reference = technical_document_reference(document)
        from .render_plan import baseline_semantic_digest
        require(reference == consumer['reference']
                and baseline_semantic_digest(document) == consumer['digest'],
                'frozen technical parameter consumer owner mismatch')
        matching_lineage = [
            ancestor
            for baseline in plan['resolved_baselines']
            for ancestor in baseline['lineage']
            if ancestor['reference'] == reference
            and ancestor['digest'] == consumer['digest']
        ]
        require(matching_lineage
                and all(equal(item['policy_sources'], consumer['policy_sources'])
                        for item in matching_lineage),
                'frozen technical parameter consumer source mismatch')
        actual_policy_sources = {
            item['name']
            for item in plan['provenance']['planningComposition']['actual']['policySources']
        }
        require(all(locator.get('policy_source') in actual_policy_sources
                    for locator in consumer['policy_sources']),
                'frozen technical consumer source is absent from planning composition')


def validate_frozen(plan):
    """Validate the ADR 0024 source-fact representation without current inputs."""
    require('parameter_facts' not in canonical_json_bytes(plan).decode('utf-8')
            and 'parameter_derivation' not in canonical_json_bytes(plan).decode('utf-8'),
            'superseded frozen parameter summaries are not accepted')
    validate_frozen_contract_identities(plan)
    assignments = {item['id']: item for item in plan['assignments']}
    expected_baselines = {
        (assignment['id'], assignment['group'], reference)
        for assignment in assignments.values()
        for reference in assignment['baselines']
    }
    actual_baselines = {
        (item['assignment'], item['group'], item['reference'])
        for item in [*plan['resolved_baselines'], *plan['resolved_requirement_baselines']]
    }
    if plan['resolution']['status'] == 'valid':
        require(expected_baselines == actual_baselines,
                'frozen baseline coverage differs from selected assignments')
    else:
        require(actual_baselines.issubset(expected_baselines),
                'frozen baseline coverage exceeds selected assignments')

    consumers = plan['parameters']['consumers']
    require(consumers == sorted(consumers, key=lambda item: (item['kind'], item['reference']))
            and len({(item['kind'], item['reference']) for item in consumers}) == len(consumers),
            'frozen parameter consumers must use unique canonical order')
    technical_links = frozen_technical_links(plan)
    controls = {}
    for collection_name in ('controls', 'excluded_controls'):
        for control in plan[collection_name]:
            facts = control['policy_inputs']
            definition = copy.deepcopy(facts['definition'])
            definition['_parameters_schema'] = facts['parameters_schema']
            definition['_implementation_modules'] = facts.get('implementation_modules', [])
            validate_control_contract_identity(definition)
            instance = facts['instance']
            from .render_plan import control_definition_fingerprint
            source_instance = instance
            instance_links = [
                link for link in technical_links
                if link['destination']['instance_id'] == control['instance_id']
            ]
            if instance_links:
                source_instance = dematerialize_links([instance], instance_links)[0]
            expected_fingerprint = (
                digest(instance)
                if control['alignment'] == 'realization'
                else control_definition_fingerprint(source_instance)
            )
            require(expected_fingerprint == control['definition_fingerprint'],
                    'frozen policy instance fingerprint mismatch')
            require(instance['instance_id'] == control['instance_id']
                    and instance['implementation'] == control['implementation'],
                    'frozen technical input identity mismatch')
            require(equal(instance.get('parameters', {}), control['parameters']),
                    'frozen technical value mismatch')
            resolved_evidence = evidence_for(instance, definition)
            if collection_name == 'controls':
                require(equal(resolved_evidence, control['evidence']),
                        'frozen policy freshness mismatch')
                require(definition['spec']['entrypoint'] == control['entrypoint'],
                        'frozen implementation entrypoint mismatch')
            previous = controls.get(control['implementation'])
            require(previous is None or equal(previous, definition),
                    'divergent frozen implementation definitions')
            controls[control['implementation']] = definition

    try:
        states, _, _ = reconstruct_frozen_parameters(plan)
    except ParameterResolutionError as error:
        parameter_failure = any(
            error.get('type') in {
                'parameter-resolution-failed',
                'parameter-document-conflict',
                'parameter-consumption-failed',
                'parameter-consumer-conflict',
                'parameter-policy-invalid',
            }
            for error in plan['resolution']['errors']
        )
        require(plan['resolution']['status'] == 'invalid' and parameter_failure,
                'frozen ParameterPolicy reconstruction failed '
                f'({error}) without a retained planning refusal')
        validate_frozen_parameter_inputs(plan)
        require(not consumers,
                'unresolved ParameterPolicy cannot retain materialized consumers')
        _validate_requirement_facts(plan, controls, {})
        _validate_technical_consumers(plan, controls, {})
        return
    _validate_requirement_facts(plan, controls, states)
    _validate_technical_consumers(plan, controls, states)
