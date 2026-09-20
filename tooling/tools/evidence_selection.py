"""Trusted ADR 0010 routing, validation and selection over an in-memory snapshot."""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from ._canonical_json import canonical_json_bytes, unique_object as _unique_object
from .evidence_provenance import evidence_document_digest, evidence_set_provenance
from .evaluate_plan import EVIDENCE_FORMAT_CHECKER, _json_pointer, parse_duration


def snapshot_evidence(path: Path, subject_id: str):
    if not path.is_dir():
        raise ValueError('evidence source is not an accessible directory')
    documents = []
    # iterdir propagates access errors; an inaccessible source is never an empty set.
    for source in sorted(path.iterdir()):
        if source.suffix != '.json':
            continue
        document = json.loads(source.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
        if not isinstance(document, dict):
            raise ValueError('evidence document must be an object')
        subject = document.get('subject')
        if not isinstance(subject, dict) or not isinstance(subject.get('id'), str) or not subject['id'].strip():
            raise ValueError('evidence lacks unambiguous explicit subject routing')
        if subject['id'] != subject_id:
            continue
        if not isinstance(document.get('type'), str) or not document['type'].strip():
            raise ValueError('subject evidence lacks interpretable type routing')
        # Diagnose and consume the same canonical semantic document. JSON Schema
        # messages can embed object repr; insertion order must not change identity.
        document = json.loads(canonical_json_bytes(document))
        documents.append(document)
    return documents, evidence_set_provenance(documents)


def prepare_schemas(schemas, required_types):
    validators, references = {}, {}
    for evidence_type in sorted(required_types):
        if evidence_type not in schemas:
            raise ValueError('required evidence schema is unavailable: ' + evidence_type)
        schema = copy.deepcopy(schemas[evidence_type]['_schema_document'])
        Draft202012Validator.check_schema(schema)
        # Catalog contracts use document-local refs. Resolve every reference before
        # attribution, even for empty snapshots; never retrieve mutable remote schemas.
        validator = Draft202012Validator(schema, format_checker=EVIDENCE_FORMAT_CHECKER, registry=Registry())
        checked = set()
        def check_refs(resource, resolver):
            value = resource.contents
            location = (id(value), resolver._base_uri)
            if location in checked:
                return
            checked.add(location)
            if isinstance(value, dict):
                for key in ('$ref', '$dynamicRef'):
                    if key in value:
                        child = value[key]
                        if not child.startswith('#'):
                            raise ValueError('unresolvable external required evidence schema reference')
                        resolved = resolver.lookup(child)
                        # A reference can explicitly make an otherwise opaque
                        # location a schema. Follow it, without looping on cycles.
                        Draft202012Validator.check_schema(resolved.contents)
                        check_refs(Resource.from_contents(resolved.contents,
                                   default_specification=DRAFT202012), resolved.resolver)
            # The specification owns subschema locations. Annotation/default/const
            # values are ordinary JSON, even when they contain reference-like keys.
            for child in resource.subresources():
                check_refs(child, resolver.in_subresource(child))
        check_refs(DRAFT202012.create_resource(schema), validator._resolver)
        validators[evidence_type] = validator
        references[evidence_type] = {
            'type': evidence_type,
            'policy_sources': sorted(copy.deepcopy(schemas[evidence_type]['_sources']), key=lambda item: (item['policy_source'], item['path'])),
        }
    return validators, references


def _candidate_reference(document):
    return {
        'evidence_id': document['id'],
        'evidence_digest': evidence_document_digest(document),
        'collected_at': document['collected_at'],
    }


def select_evidence(documents, requirements, evaluated_at, subject_id, validators, schemas):
    """Select required evidence and retain canonical unsuccessful dispositions."""
    del subject_id, schemas
    selected, uses, dispositions = [], [], []
    for requirement in requirements:
        evidence_type = requirement['type']
        dependency_id = requirement['id']
        candidates = [doc for doc in documents if doc['type'] == evidence_type]
        diagnostics = []
        for doc in candidates:
            for error in validators[evidence_type].iter_errors(doc):
                diagnostics.append({
                    'code': 'evidence_schema_invalid',
                    'evidence_id': doc['id'], 'evidence_digest': evidence_document_digest(doc),
                    'schema_path': _json_pointer(error.absolute_schema_path),
                    'keyword': error.validator,
                })
        if diagnostics:
            unique = {
                (item['evidence_id'], item['evidence_digest'], item['schema_path'],
                 item['keyword'], item['code']): item
                for item in diagnostics
            }
            dispositions.append({
                'dependency_id': dependency_id,
                'disposition': 'invalid',
                'diagnostics': [unique[key] for key in sorted(unique)],
            })
            continue
        if not candidates:
            dispositions.append({
                'dependency_id': dependency_id,
                'disposition': 'absent',
            })
            continue
        maximum_age = parse_duration(requirement['max_age'])
        eligible = []
        for doc in candidates:
            instant = datetime.fromisoformat(doc['collected_at'].replace('Z', '+00:00'))
            if instant.utcoffset() is None:
                raise ValueError('validated evidence collection time is not attributable')
            if evaluated_at - instant <= maximum_age:
                eligible.append((instant, doc))
        if not eligible:
            latest = max(
                datetime.fromisoformat(doc['collected_at'].replace('Z', '+00:00'))
                for doc in candidates
            )
            latest_documents = {
                evidence_document_digest(doc): doc
                for doc in candidates
                if datetime.fromisoformat(
                    doc['collected_at'].replace('Z', '+00:00')
                ) == latest
            }
            latest_candidates = sorted(
                (_candidate_reference(doc) for doc in latest_documents.values()),
                key=lambda item: (item['evidence_id'], item['evidence_digest']),
            )
            dispositions.append({
                'dependency_id': dependency_id,
                'disposition': 'stale',
                'latest_candidates': latest_candidates,
            })
            continue
        latest = max(instant for instant, _ in eligible)
        tied = {evidence_document_digest(doc): doc for instant, doc in eligible if instant == latest}
        if len(tied) > 1:
            disposition_candidates = sorted(
                (_candidate_reference(doc) for doc in tied.values()),
                key=lambda item: (item['evidence_id'], item['evidence_digest']),
            )
            dispositions.append({
                'dependency_id': dependency_id,
                'disposition': 'ambiguous',
                'candidates': disposition_candidates,
            })
            continue
        document = next(iter(tied.values()))
        selected.append(document)
        uses.append({'dependency_id': dependency_id,
                     'evidence_id': document['id'],
                     'evidence_digest': evidence_document_digest(document),
                     'collected_at': document['collected_at']})
    dispositions.sort(key=lambda item: item['dependency_id'])
    return selected, uses, dispositions
