"""Trusted ADR 0010 routing, validation and selection over an in-memory snapshot."""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry

from .evidence_provenance import evidence_document_digest, evidence_set_provenance
from .evaluate_plan import EVIDENCE_FORMAT_CHECKER, _json_pointer, parse_duration


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('ambiguous duplicate JSON member')
        result[key] = value
    return result


def snapshot_evidence(path: Path, subject_id: str):
    if not path.is_dir():
        raise ValueError('evidence source is not an accessible directory')
    documents, locations = [], {}
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
        evidence_document_digest(document)  # reject non-JCS/unrepresentable documents before child results
        documents.append(document)
        locations[id(document)] = source.name
    return documents, locations, evidence_set_provenance(documents)


def prepare_schemas(schemas, required_types):
    validators, references = {}, {}
    for evidence_type in sorted(required_types):
        if evidence_type not in schemas:
            raise ValueError('required evidence schema is unavailable: ' + evidence_type)
        schema = {k: copy.deepcopy(v) for k,v in schemas[evidence_type].items() if not k.startswith('_')}
        Draft202012Validator.check_schema(schema)
        # Catalog contracts use document-local refs. Resolve every reference before
        # attribution, even for empty snapshots; never retrieve mutable remote schemas.
        validator = Draft202012Validator(schema, format_checker=EVIDENCE_FORMAT_CHECKER, registry=Registry())
        def check_refs(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key in ('$ref', '$dynamicRef'):
                        if not child.startswith('#'):
                            raise ValueError('unresolvable external required evidence schema reference')
                        validator._resolver.lookup(child)
                    else:
                        check_refs(child)
            elif isinstance(value, list):
                for child in value: check_refs(child)
        check_refs(schema)
        validators[evidence_type] = validator
        references[evidence_type] = {
            'type': evidence_type,
            'policy_sources': sorted(copy.deepcopy(schemas[evidence_type]['_sources']), key=lambda item: (item['policy_source'], item['path'])),
        }
    return validators, references


def select_evidence(documents, requirements, evaluated_at, subject_id, validators, schemas, locations):
    selected, uses, invalid, ambiguous, optional_invalid = [], [], [], [], []
    for index, requirement in enumerate(requirements):
        evidence_type = requirement['type']
        candidates = [doc for doc in documents if doc['type'] == evidence_type]
        errors = []
        for doc in candidates:
            for error in validators[evidence_type].iter_errors(doc):
                errors.append({
                    'type': 'evidence-schema-validation-failed',
                    'code': 'evidence_schema_invalid',
                    'evidence_type': evidence_type,
                    'required': requirement['required'], 'requirement_index': index,
                    'evidence_id': doc['id'], 'evidence_digest': evidence_document_digest(doc),
                    'schema_reference': schemas[evidence_type],
                    'path': _json_pointer(error.absolute_path),
                    'schema_path': _json_pointer(error.absolute_schema_path),
                    'keyword': error.validator, 'message': error.message,
                    'source': locations[id(doc)],
                })
        if errors:
            (invalid if requirement['required'] else optional_invalid).extend(errors)
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
            continue
        if not requirement['required']:
            # Optional evidence remains the predecessor contract. ADR 0010/0011
            # changes required selections only; do not invent optional semantics.
            selected.append(max(eligible, key=lambda candidate: candidate[0])[1])
            continue
        latest = max(instant for instant, _ in eligible)
        tied = {evidence_document_digest(doc): doc for instant, doc in eligible if instant == latest}
        if len(tied) > 1:
            ambiguous.append({
                'code': 'evidence_selection_ambiguity', 'subject': subject_id,
                'evidence_type': evidence_type, 'schema_reference': schemas[evidence_type],
                'requirement_index': index, 'freshness_requirement': copy.deepcopy(requirement),
                'evaluated_at': evaluated_at.isoformat().replace('+00:00', 'Z'),
                'collected_at': latest.isoformat().replace('+00:00', 'Z'),
                'candidates': sorted([{'id': doc['id'], 'digest': key} for key,doc in tied.items()], key=lambda x:(x['id'],x['digest'])),
            })
            continue
        document = next(iter(tied.values()))
        selected.append(document)
        uses.append({'requirement_index': index, 'requirement': copy.deepcopy(requirement),
                     'id': document['id'], 'digest': evidence_document_digest(document),
                     'collected_at': document['collected_at']})
    for errors in (invalid, optional_invalid):
        errors.sort(key=lambda x:(x['evidence_type'],x['requirement_index'],x['evidence_id'],x['evidence_digest'],x['path'],x['schema_path'],x['message']))
    ambiguous.sort(key=lambda x:(x['evidence_type'],x['requirement_index']))
    return selected, uses, invalid, ambiguous, optional_invalid
