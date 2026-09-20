"""Experimental document-only producer CLI; no policy resolution or assessment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable

from ._canonical_json import canonical_json_bytes, unique_object
from .evidence_selection import prepare_schemas
from .evaluate_plan import EVIDENCE_FORMAT_CHECKER
from .policy_sources import normalize_policy_sources, parse_policy_source
from .render_plan import load_evidence_schema_catalog


def add_commands(commands: argparse._SubParsersAction) -> None:
    producer = commands.add_parser(
        "producer", help="experimental schema discovery and document-only validation"
    )
    operations = producer.add_subparsers(dest="producer_command", required=True)
    for operation, help_text in (
        ("list", "list available producer contracts"),
        ("schema", "write the selected canonical schema to stdout"),
        ("validate", "validate one JSON document, without assessment admission"),
    ):
        child = operations.add_parser(operation, help=help_text)
        child.add_argument("--kind", choices=("evidence", "subject"), default="evidence")
        child.add_argument("--policy-source", action="append", default=[], metavar="NAME=PATH",
                           help="explicit materialized policy root; repeat to compose")
        if operation != "list":
            child.add_argument("--type", help="exact Evidence type (required for Evidence)")
            child.add_argument("--schema-id", help="require this exact schema contract URI")
        if operation == "validate":
            child.add_argument("--input", required=True, help="one JSON file, or - for stdin")
        child.set_defaults(handler=run)


def _contracts(args):
    if args.kind == "subject":
        if args.policy_source or getattr(args, "type", None):
            raise ValueError("Subject uses the tooling-owned schema, without --policy-source or --type")
        # This resource is mirrored into site-packages by the existing wheel build.
        schema = json.loads((Path(__file__).resolve().parents[1]
                             / "schemas/inventory/resource.schema.json").read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=EVIDENCE_FORMAT_CHECKER, registry=Registry())
        return {"Subject": schema}, {"Subject": validator}
    if not args.policy_source:
        raise ValueError("Evidence schemas require explicit --policy-source NAME=PATH; tooling does not own them")
    sources = normalize_policy_sources(parse_policy_source(value) for value in args.policy_source)
    for source in sources:
        if not source.path.is_dir():
            raise ValueError(f"policy source is not an accessible directory: {source.path}")
    catalog, errors = load_evidence_schema_catalog(sources)
    if errors:
        raise ValueError("invalid Evidence schema catalog: " + json.dumps(errors, sort_keys=True))
    validators, _ = prepare_schemas(catalog, catalog)
    return {key: validator.schema for key, validator in validators.items()}, validators


def run(args) -> None:
    try:
        schemas, validators = _contracts(args)
        if args.producer_command == "list":
            print(json.dumps({"kind": args.kind, "contracts": [
                {"type": key, "schema_id": schema["$id"]}
                for key, schema in sorted(schemas.items())
            ]}, indent=2, sort_keys=True))
            return
        key = "Subject" if args.kind == "subject" else args.type
        if not key:
            raise ValueError("--type is required for Evidence schema selection")
        if key not in schemas:
            raise ValueError(f"unknown Evidence type: {key}")
        schema = schemas[key]
        if args.schema_id is not None and args.schema_id != schema["$id"]:
            raise ValueError("selected schema ID does not match the canonical contract")
        canonical_json_bytes(schema)
        if args.producer_command == "schema":
            print(json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False))
            return
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
        document = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(document, dict):
            raise ValueError("producer document must be an object")
        # Match supported complete-document representation, including extensions.
        canonical_json_bytes(document)
        if args.kind == "subject" and document.get("kind") != "Subject":
            raise ValueError("expected one normalized Subject resource")
        errors = sorted(validators[key].iter_errors(document),
                        key=lambda error: (tuple(str(p) for p in error.absolute_path), error.message))
        if errors:
            raise ValueError("document invalid: " + "; ".join(
                f"/{'/'.join(str(p) for p in error.absolute_path)}: {error.message}" for error in errors
            ))
        print(json.dumps({"document_valid": True, "kind": args.kind,
                          "type": key, "schema_id": schema["$id"],
                          "validation_scope": "document-only"}, sort_keys=True))
    except (SchemaError, Unresolvable) as error:
        raise ValueError(f"invalid or unresolvable producer schema: {error}") from error
