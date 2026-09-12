"""Internal assessment-plan rendering implementation."""

from __future__ import annotations

from . import policy_parameters as pp

import copy
import hashlib
import json
import re
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from ._canonical_json import canonical_json_bytes
from .artifact_validation import validate_assessment_plan
from .identifiers import (
    EVIDENCE_TYPE,
    canonical_control_evidence_inputs_schema_id,
    canonical_control_parameter_schema_id,
    canonical_evidence_schema_id,
)
from .policy_sources import (
    PolicySource,
    PolicySources,
    normalize_policy_sources,
    rego_module_paths,
    source_pin_errors,
    source_tree_digest as _source_tree_digest,
)


JsonObject = dict[str, Any]
INVENTORY_API_VERSION = "compliance.example/v1alpha1"
RESOURCE_EXTENSIONS = {".json", ".yaml", ".yml"}
BASELINE_SCHEMA_FILES = {
    "Baseline": "baseline.schema.json",
    "BaselineOverlay": "baseline-overlay.schema.json",
}
REQUIREMENT_POLICY_KINDS = {
    "ControlRequirement": ("requirements", "control-requirement.schema.json"),
    "RequirementBaseline": ("requirement-baselines", "requirement-baseline.schema.json"),
    "ControlRealization": ("realizations", "control-realization.schema.json"),
}
EVIDENCE_ENVELOPE_FIELDS = (
    "schema",
    "id",
    "subject",
    "type",
    "collected_at",
    "collector",
    "payload",
)
EVIDENCE_ENVELOPE_SCHEMA = "compliance.example/evidence/v1"


class BaselineResolutionError(ValueError):
    """A baseline inheritance or overlay rule could not be resolved safely."""

    def __init__(self, error_type: str, **details: Any) -> None:
        self.details = {"type": error_type, **details}
        super().__init__(json.dumps(self.details, sort_keys=True))


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def load_resource_documents(path: Path) -> list[tuple[Path, JsonObject]]:
    """Load Kubernetes-shaped JSON or YAML resources from a file or directory."""
    if not path.exists():
        raise ValueError(f"resource path does not exist: {path}")

    paths = [path] if path.is_file() else [
        candidate
        for candidate in sorted(path.rglob("*"))
        if candidate.is_file() and candidate.suffix.lower() in RESOURCE_EXTENSIONS
    ]
    if not paths:
        raise ValueError(f"resource path contains no YAML or JSON documents: {path}")

    documents: list[tuple[Path, JsonObject]] = []
    for resource_path in paths:
        with resource_path.open(encoding="utf-8") as stream:
            if resource_path.suffix.lower() == ".json":
                loaded_documents = [json.load(stream)]
            else:
                loaded_documents = list(yaml.safe_load_all(stream))

        for document_index, document in enumerate(loaded_documents, start=1):
            if document is None:
                continue
            if not isinstance(document, dict):
                raise ValueError(
                    f"resource must be an object: {resource_path} document {document_index}"
                )
            documents.append((resource_path, document))
    return documents


def resource_validation_errors(document: JsonObject, schema: JsonObject) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    messages = []
    for error in sorted(
        validator.iter_errors(document),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    ):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return messages


def validate_resource(document: JsonObject, schema: JsonObject, source: Path) -> None:
    errors = resource_validation_errors(document, schema)
    if errors:
        rendered = "\n  - ".join(errors)
        raise ValueError(f"invalid {document.get('kind', 'resource')} in {source}:\n  - {rendered}")


def normalize_subject(document: JsonObject) -> JsonObject:
    metadata = document["metadata"]
    spec = document["spec"]
    source = spec["source"]
    normalized: JsonObject = {
        "schema": "compliance.example/inventory-subject/v1",
        "id": spec["id"],
        "type": spec["type"],
        "status": spec["lifecycle"],
        "labels": copy.deepcopy(metadata.get("labels", {})),
        "inventory": {
            "source": source["name"],
            "external_id": source["externalId"],
            "observed_at": source["observedAt"],
        },
    }
    if "revision" in source:
        normalized["inventory"]["revision"] = source["revision"]
    if "annotations" in metadata:
        normalized["annotations"] = copy.deepcopy(metadata["annotations"])
    if "attributes" in spec:
        normalized["attributes"] = copy.deepcopy(spec["attributes"])
    return normalized


def normalize_group(document: JsonObject) -> JsonObject:
    metadata = document["metadata"]
    spec = document["spec"]
    normalized: JsonObject = {
        "id": metadata["name"],
        "parents": [reference["name"] for reference in spec.get("parentRefs", [])],
    }
    match_labels = spec.get("selector", {}).get("matchLabels")
    if match_labels:
        normalized["selector"] = {"match_labels": copy.deepcopy(match_labels)}
    if "subjectRefs" in spec:
        normalized["members"] = [reference["id"] for reference in spec["subjectRefs"]]
    if "labels" in metadata or "annotations" in metadata:
        normalized["metadata"] = {
            key: copy.deepcopy(metadata[key])
            for key in ("labels", "annotations")
            if key in metadata
        }
    return normalized


def normalize_assignment(document: JsonObject) -> JsonObject:
    metadata = document["metadata"]
    spec = document["spec"]
    return {
        "id": metadata["name"],
        "target": {"group": spec["targetRef"]["name"]},
        "baselines": [
            f'{reference["name"]}@{reference["revision"]}'
            for reference in spec["baselineRefs"]
        ],
    }


def load_inventory_catalog(
    inventory_path: Path,
    assignments_path: Path,
    schema_path: Path,
) -> tuple[dict[str, JsonObject], list[JsonObject], list[JsonObject]]:
    """Validate and normalize a complete authored inventory resource set."""
    schema = load_json(schema_path)
    subject_documents: list[JsonObject] = []
    group_documents: list[JsonObject] = []
    assignment_documents: list[JsonObject] = []

    for source, document in load_resource_documents(inventory_path):
        validate_resource(document, schema, source)
        kind = document["kind"]
        if kind == "Subject":
            subject_documents.append(normalize_subject(document))
        elif kind == "InventoryGroup":
            group_documents.append(normalize_group(document))
        else:
            raise ValueError(f"{kind} resource does not belong in inventory path: {source}")

    for source, document in load_resource_documents(assignments_path):
        validate_resource(document, schema, source)
        if document["kind"] != "PolicyAssignment":
            raise ValueError(
                f"{document['kind']} resource does not belong in assignments path: {source}"
            )
        assignment_documents.append(normalize_assignment(document))

    subjects = {subject["id"]: subject for subject in subject_documents}
    if len(subjects) != len(subject_documents):
        raise ValueError("subject ids must be unique")

    group_ids = [group["id"] for group in group_documents]
    if len(set(group_ids)) != len(group_ids):
        raise ValueError("group ids must be unique")
    assignment_ids = [assignment["id"] for assignment in assignment_documents]
    if len(set(assignment_ids)) != len(assignment_ids):
        raise ValueError("assignment ids must be unique")
    unknown_targets = sorted({
        assignment["target"]["group"]
        for assignment in assignment_documents
        if assignment["target"]["group"] not in set(group_ids)
    })
    if unknown_targets:
        raise ValueError(f"assignments target unknown groups: {', '.join(unknown_targets)}")

    validate_group_dag({group["id"]: group for group in group_documents})
    unknown_members = sorted({
        member for group in group_documents for member in group.get("members", [])
        if member not in subjects
    })
    if unknown_members:
        raise ValueError("groups reference unknown subjects: " + ", ".join(unknown_members))
    return subjects, group_documents, assignment_documents


def load_inventory_inputs(
    inventory_path: Path,
    assignments_path: Path,
    subject_id: str,
    schema_path: Path,
) -> tuple[JsonObject, list[JsonObject], list[JsonObject]]:
    """Load the authored resource set and select one subject for assessment."""
    subjects, group_documents, assignment_documents = load_inventory_catalog(
        inventory_path,
        assignments_path,
        schema_path,
    )
    if subject_id not in subjects:
        raise ValueError(f"unknown subject id: {subject_id}")
    return subjects[subject_id], group_documents, assignment_documents


def content_digest(value: Any) -> str:
    encoded = canonical_json_bytes(value)
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def source_tree_digest(root: Path) -> str:
    """Backward-compatible single-source digest helper."""
    return _source_tree_digest(root)


def _source_locator(source: PolicySource, relative: str) -> JsonObject:
    return {"policy_source": source.name, "path": relative}


def _qualify_catalog(catalog: dict[str, JsonObject], source: PolicySource) -> None:
    for document in catalog.values():
        relative = document["_source"]
        document["_source"] = f"{source.name}:{relative}"
        document["_sources"] = [_source_locator(source, relative)]
        if "_parameters_schema_source" in document:
            document["_parameters_schema_source"] = (
                f"{source.name}:{document['_parameters_schema_source']}"
            )


def _semantic_resource_digest(document: JsonObject) -> str:
    public = {key: value for key, value in document.items() if not key.startswith("_")}
    if "_parameters_schema" in document:
        public["parameters_schema_document"] = document["_parameters_schema"]
        public["implementation_modules"] = document.get("_implementation_modules", [])
    return content_digest(public)


def _merge_policy_catalog(
    target: dict[str, JsonObject],
    incoming: dict[str, JsonObject],
    *,
    resource_kind: str,
    errors: list[JsonObject],
) -> None:
    for identity, document in sorted(incoming.items()):
        existing = target.get(identity)
        if existing is None:
            target[identity] = document
            continue
        if _semantic_resource_digest(existing) == _semantic_resource_digest(document):
            for locator in document.get("_sources", []):
                if locator not in existing.setdefault("_sources", []):
                    existing["_sources"].append(locator)
            existing["_sources"].sort(
                key=lambda locator: (locator["policy_source"], locator["path"])
            )
            continue
        errors.append({
            "type": "policy-resource-conflict",
            "kind": resource_kind,
            "identity": identity,
            "existing_sources": existing.get("_sources", []),
            "incoming_sources": document.get("_sources", []),
        })


def _effective_schema_path(
    sources: PolicySources,
    relative: Path,
) -> tuple[Path | None, list[JsonObject]]:
    candidates = [
        (source, source.path / relative)
        for source in normalize_policy_sources(sources)
        if (source.path / relative).is_file()
    ]
    if not candidates:
        return None, [{
            "type": "policy-schema-unavailable",
            "source": relative.as_posix(),
        }]
    documents: list[tuple[PolicySource, Path, Any]] = []
    errors: list[JsonObject] = []
    for source, path in candidates:
        try:
            documents.append((source, path, load_json(path)))
        except (OSError, json.JSONDecodeError) as error:
            errors.append({
                "type": "policy-schema-unreadable",
                "policy_source": source.name,
                "source": relative.as_posix(),
                "message": str(error),
            })
    if errors or not documents:
        return None, errors
    expected = content_digest(documents[0][2])
    if any(content_digest(document) != expected for _, _, document in documents[1:]):
        return None, [{
            "type": "policy-schema-conflict",
            "source": relative.as_posix(),
            "policy_sources": [source.name for source, _, _ in documents],
        }]
    return documents[0][1], []


def validate_group_dag(groups: dict[str, JsonObject]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(group_id: str, path: list[str]) -> None:
        if group_id in visiting:
            cycle = " -> ".join([*path, group_id])
            raise ValueError(f"group DAG contains a cycle: {cycle}")
        if group_id in visited:
            return
        if group_id not in groups:
            raise ValueError(f"unknown group referenced by DAG: {group_id}")

        visiting.add(group_id)
        for parent in groups[group_id].get("parents", []):
            if parent not in groups:
                raise ValueError(f"group {group_id} has unknown parent {parent}")
            visit(parent, [*path, group_id])
        visiting.remove(group_id)
        visited.add(group_id)

    for group_id in sorted(groups):
        visit(group_id, [])


def direct_membership_sources(group: JsonObject, subject: JsonObject) -> list[JsonObject]:
    sources: list[JsonObject] = []
    if subject["id"] in group.get("members", []):
        sources.append({"membership": "explicit", "source": "group.members"})

    selector = group.get("selector", {})
    match_labels = selector.get("match_labels")
    if match_labels and all(subject.get("labels", {}).get(key) == value for key, value in match_labels.items()):
        sources.append({"membership": "selector", "source": {"match_labels": match_labels}})
    return sources


def resolve_groups(groups: dict[str, JsonObject], subject: JsonObject) -> list[JsonObject]:
    direct: dict[str, list[JsonObject]] = {}
    for group_id, group in groups.items():
        sources = direct_membership_sources(group, subject)
        if sources:
            direct[group_id] = sources

    inherited_via: dict[str, set[str]] = defaultdict(set)
    queue: deque[str] = deque(sorted(direct))
    resolved = set(direct)
    while queue:
        child = queue.popleft()
        for parent in groups[child].get("parents", []):
            inherited_via[parent].add(child)
            if parent not in resolved:
                resolved.add(parent)
                queue.append(parent)

    rendered: list[JsonObject] = []
    for group_id in sorted(resolved):
        sources = list(direct.get(group_id, []))
        if inherited_via[group_id]:
            sources.append({"membership": "inherited", "via": sorted(inherited_via[group_id])})
        rendered.append({"id": group_id, "sources": sources})
    return rendered


def load_control_catalog(
    controls_root: Path,
    schema_path: Path | None = None,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    """Load control manifests and their local parameter schemas safely."""
    schema_path = schema_path or controls_root.parent / "schemas/policy/control.schema.json"
    catalog: dict[str, JsonObject] = {}
    errors: list[JsonObject] = []
    try:
        manifest_schema = load_json(schema_path)
    except (OSError, json.JSONDecodeError) as error:
        try:
            source = schema_path.relative_to(controls_root.parent).as_posix()
        except ValueError:
            source = schema_path.as_posix()
        return catalog, [{
            "type": "control-schema-unavailable",
            "source": source,
            "message": str(error),
        }]
    try:
        Draft202012Validator.check_schema(manifest_schema)
    except SchemaError as error:
        try:
            source = schema_path.relative_to(controls_root.parent).as_posix()
        except ValueError:
            source = schema_path.as_posix()
        return catalog, [{
            "type": "control-schema-invalid",
            "source": source,
            "path": _json_pointer(error.absolute_path),
            "message": error.message,
        }]

    for path in sorted(controls_root.rglob("control.json")):
        source = path.relative_to(controls_root.parent).as_posix()
        try:
            control = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append({
                "type": "control-document-unreadable",
                "source": source,
                "message": str(error),
            })
            continue

        control_id = (
            control.get("metadata", {}).get("id")
            if isinstance(control, dict)
            else None
        )
        validation_errors = sorted(
            Draft202012Validator(
                manifest_schema,
                format_checker=FormatChecker(),
            ).iter_errors(control),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )
        if validation_errors:
            for error in validation_errors:
                errors.append({
                    "type": "control-manifest-schema-invalid",
                    "source": source,
                    "schema": manifest_schema.get("$id"),
                    "path": _json_pointer(error.absolute_path),
                    "message": error.message,
                    **({"control": control_id} if isinstance(control_id, str) else {}),
                })
            continue

        assert isinstance(control_id, str)
        if control_id in catalog:
            errors.append({
                "type": "duplicate-control-id",
                "control": control_id,
                "source": source,
                "existing_source": catalog[control_id]["_source"],
            })
            continue

        parameters_reference = Path(control["spec"]["parameters_schema"])
        control_directory = path.parent.resolve()
        parameters_path = (path.parent / parameters_reference).resolve()
        if parameters_reference.is_absolute() or not parameters_path.is_relative_to(control_directory):
            errors.append({
                "type": "control-parameters-schema-path-invalid",
                "control": control_id,
                "source": source,
                "parameters_schema": control["spec"]["parameters_schema"],
                "message": "parameters_schema must resolve within the control directory",
            })
            continue

        try:
            parameters_schema = load_json(parameters_path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append({
                "type": "control-parameters-schema-unavailable",
                "control": control_id,
                "source": source,
                "parameters_schema": control["spec"]["parameters_schema"],
                "message": str(error),
            })
            continue

        try:
            Draft202012Validator.check_schema(parameters_schema)
        except SchemaError as error:
            errors.append({
                "type": "control-parameters-schema-invalid",
                "control": control_id,
                "source": source,
                "parameters_schema": control["spec"]["parameters_schema"],
                "path": _json_pointer(error.absolute_path),
                "message": error.message,
            })
            continue

        parameters_schema_id = parameters_schema.get("$id")
        if not isinstance(parameters_schema_id, str) or not canonical_control_parameter_schema_id(
            control_id
        ).fullmatch(parameters_schema_id):
            errors.append({
                "type": "control-parameters-schema-identity-invalid",
                "control": control_id,
                "source": source,
                "parameters_schema": control["spec"]["parameters_schema"],
                "schema_id": parameters_schema_id,
            })
            continue

        invalid_inputs_schema = False
        for dependency in control["spec"].get("evidence", []):
            inputs_schema = dependency.get("inputs_schema")
            if inputs_schema is None:
                continue
            try:
                Draft202012Validator.check_schema(inputs_schema)
            except SchemaError as error:
                errors.append({
                    "type": "control-evidence-inputs-schema-invalid",
                    "control": control_id,
                    "dependency": dependency["id"],
                    "source": source,
                    "path": _json_pointer(error.absolute_path),
                    "message": error.message,
                })
                invalid_inputs_schema = True
                continue
            inputs_schema_id = inputs_schema.get("$id")
            if not isinstance(inputs_schema_id, str) or not canonical_control_evidence_inputs_schema_id(
                control_id,
                dependency["id"],
            ).fullmatch(inputs_schema_id):
                errors.append({
                    "type": "control-evidence-inputs-schema-identity-invalid",
                    "control": control_id,
                    "dependency": dependency["id"],
                    "source": source,
                    "schema_id": inputs_schema_id,
                })
                invalid_inputs_schema = True
        if invalid_inputs_schema:
            continue

        control["_implementation_modules"] = sorted(content_digest(module.read_text(encoding="utf-8")) for module in path.parent.rglob("*.rego") if not module.name.endswith("_test.rego"))
        control["_source"] = source
        control["_parameters_schema"] = parameters_schema
        control["_parameters_schema_source"] = parameters_path.relative_to(
            controls_root.parent.resolve(),
        ).as_posix()
        catalog[control_id] = control
    return catalog, errors


def _load_evidence_schema_catalog_root(
    policies_root: Path,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    """Index valid evidence schemas by their declared evidence type."""
    schemas_root = policies_root / "schemas/evidence"
    catalog: dict[str, JsonObject] = {}
    errors: list[JsonObject] = []
    if not schemas_root.is_dir():
        return catalog, [{
            "type": "evidence-schema-directory-unavailable",
            "source": schemas_root.relative_to(policies_root).as_posix(),
        }]

    for path in sorted(schemas_root.glob("*.json")):
        source = path.relative_to(policies_root).as_posix()
        try:
            schema = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append({
                "type": "evidence-schema-unreadable",
                "source": source,
                "message": str(error),
            })
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            errors.append({
                "type": "evidence-schema-invalid",
                "source": source,
                "path": _json_pointer(error.absolute_path),
                "message": error.message,
            })
            continue

        envelope_errors = _evidence_schema_envelope_errors(schema, source)
        if envelope_errors:
            errors.extend(envelope_errors)
            continue

        evidence_type = (
            schema.get("properties", {}).get("type", {}).get("const")
            if isinstance(schema, dict)
            else None
        )
        if not isinstance(evidence_type, str) or not evidence_type:
            errors.append({
                "type": "evidence-schema-type-missing",
                "source": source,
                "message": "properties.type.const must declare the evidence type",
            })
            continue
        expected_schema_id = canonical_evidence_schema_id(evidence_type)
        if expected_schema_id is None:
            errors.append({
                "type": "evidence-schema-type-invalid",
                "source": source,
                "evidence_type": evidence_type,
            })
            continue
        if schema.get("$id") != expected_schema_id:
            errors.append({
                "type": "evidence-schema-identity-invalid",
                "source": source,
                "evidence_type": evidence_type,
                "schema_id": schema.get("$id"),
                "expected_schema_id": expected_schema_id,
            })
            continue
        if evidence_type in catalog:
            errors.append({
                "type": "duplicate-evidence-schema-type",
                "evidence_type": evidence_type,
                "source": source,
                "existing_source": catalog[evidence_type]["_source"],
            })
            continue
        schema["_source"] = source
        catalog[evidence_type] = schema
    return catalog, errors


def _evidence_schema_envelope_errors(
    schema: Any,
    source: str,
) -> list[JsonObject]:
    """Require the common producer envelope without a shared runtime schema."""
    if not isinstance(schema, dict):
        return [{
            "type": "evidence-schema-envelope-invalid",
            "source": source,
            "path": "",
            "message": "must be an object schema defining the evidence envelope",
        }]
    errors: list[JsonObject] = []

    def require(condition: bool, path: str, message: str) -> None:
        if not condition:
            errors.append({
                "type": "evidence-schema-envelope-invalid",
                "source": source,
                "path": path,
                "message": message,
            })

    required = schema.get("required")
    properties = schema.get("properties")
    require(schema.get("type") == "object", "/type", "must be object")
    require(
        schema.get("additionalProperties") is True,
        "/additionalProperties",
        "must be true so opaque envelope extensions remain preserved",
    )
    require(
        isinstance(required, list)
        and len(required) == len(EVIDENCE_ENVELOPE_FIELDS)
        and set(required) == set(EVIDENCE_ENVELOPE_FIELDS),
        "/required",
        "must contain exactly the seven common evidence envelope fields",
    )
    require(
        isinstance(properties, dict)
        and set(properties) == set(EVIDENCE_ENVELOPE_FIELDS),
        "/properties",
        "must declare exactly the seven common evidence envelope fields",
    )
    if not isinstance(properties, dict):
        return errors

    schema_field = properties.get("schema")
    require(
        isinstance(schema_field, dict)
        and schema_field.get("const") == EVIDENCE_ENVELOPE_SCHEMA,
        "/properties/schema/const",
        f"must be {EVIDENCE_ENVELOPE_SCHEMA}",
    )

    id_field = properties.get("id")
    require(
        isinstance(id_field, dict)
        and id_field.get("type") == "string"
        and id_field.get("minLength") == 1,
        "/properties/id",
        "must be a non-empty string",
    )

    subject = properties.get("subject")
    require(
        isinstance(subject, dict) and subject.get("type") == "object",
        "/properties/subject/type",
        "must be object",
    )
    if isinstance(subject, dict):
        subject_required = subject.get("required")
        subject_properties = subject.get("properties")
        require(
            isinstance(subject_required, list)
            and len(subject_required) == 2
            and set(subject_required) == {"id", "type"},
            "/properties/subject/required",
            "must contain exactly id and type",
        )
        require(
            subject.get("additionalProperties") is True,
            "/properties/subject/additionalProperties",
            "must be true so subject attribution extensions remain preserved",
        )
        require(
            isinstance(subject_properties, dict)
            and set(subject_properties) == {"id", "type"},
            "/properties/subject/properties",
            "must declare exactly id and type",
        )
        if isinstance(subject_properties, dict):
            subject_id = subject_properties.get("id")
            subject_type = subject_properties.get("type")
            require(
                isinstance(subject_id, dict)
                and subject_id.get("type") == "string"
                and subject_id.get("minLength") == 1,
                "/properties/subject/properties/id",
                "must be a non-empty string",
            )
            require(
                isinstance(subject_type, dict)
                and isinstance(subject_type.get("const"), str)
                and bool(subject_type["const"]),
                "/properties/subject/properties/type/const",
                "must declare one non-empty subject type",
            )

    type_field = properties.get("type")
    require(
        isinstance(type_field, dict)
        and isinstance(type_field.get("const"), str)
        and re.fullmatch(EVIDENCE_TYPE, type_field["const"]) is not None,
        "/properties/type/const",
        "must declare one canonical evidence type",
    )

    collected_at = properties.get("collected_at")
    require(
        isinstance(collected_at, dict)
        and collected_at.get("type") == "string"
        and collected_at.get("format") == "date-time",
        "/properties/collected_at",
        "must be a date-time string",
    )

    collector = properties.get("collector")
    require(
        isinstance(collector, dict) and collector.get("type") == "object",
        "/properties/collector/type",
        "must be object",
    )
    if isinstance(collector, dict):
        collector_required = collector.get("required")
        collector_properties = collector.get("properties")
        require(
            isinstance(collector_required, list)
            and len(collector_required) == 2
            and set(collector_required) == {"id", "version"},
            "/properties/collector/required",
            "must contain exactly id and version",
        )
        require(
            collector.get("additionalProperties") is True,
            "/properties/collector/additionalProperties",
            "must be true so collector attribution extensions remain preserved",
        )
        require(
            isinstance(collector_properties, dict)
            and set(collector_properties) == {"id", "version"},
            "/properties/collector/properties",
            "must declare exactly id and version",
        )
        if isinstance(collector_properties, dict):
            for name in ("id", "version"):
                field = collector_properties.get(name)
                require(
                    isinstance(field, dict)
                    and field.get("type") == "string"
                    and field.get("minLength") == 1,
                    f"/properties/collector/properties/{name}",
                    "must be a non-empty string",
                )

    require(
        isinstance(properties.get("payload"), dict),
        "/properties/payload",
        "must define the typed observation payload",
    )
    return errors


def load_evidence_schema_catalog(
    policy_sources: PolicySources,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    """Assemble evidence schemas from partial named policy trees."""
    catalog: dict[str, JsonObject] = {}
    errors: list[JsonObject] = []
    found_directory = False
    for source in normalize_policy_sources(policy_sources):
        if not (source.path / "schemas/evidence").is_dir():
            continue
        found_directory = True
        incoming, incoming_errors = _load_evidence_schema_catalog_root(source.path)
        _qualify_catalog(incoming, source)
        errors.extend(incoming_errors)
        _merge_policy_catalog(
            catalog,
            incoming,
            resource_kind="EvidenceSchema",
            errors=errors,
        )
    if not found_directory:
        errors.append({
            "type": "evidence-schema-directory-unavailable",
            "source": "schemas/evidence",
        })
    return catalog, errors


def validate_control_evidence_contracts(
    policy_sources: PolicySources,
    controls: dict[str, JsonObject],
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    """Require every declared evidence type to have one compatible schema."""
    if not any(
        control["spec"].get("evidence", [])
        for control in controls.values()
    ):
        return {}, []
    schemas, errors = load_evidence_schema_catalog(policy_sources)
    for control_id, control in sorted(controls.items()):
        for requirement in control["spec"].get("evidence", []):
            evidence_type = requirement["type"]
            schema = schemas.get(evidence_type)
            if schema is None:
                errors.append({
                    "type": "control-evidence-schema-missing",
                    "control": control_id,
                    "source": control["_source"],
                    "evidence_type": evidence_type,
                })
                continue
            schema_subject_type = (
                schema.get("properties", {})
                .get("subject", {})
                .get("properties", {})
                .get("type", {})
                .get("const")
            )
            if not isinstance(schema_subject_type, str):
                errors.append({
                    "type": "evidence-schema-subject-type-missing",
                    "control": control_id,
                    "source": schema["_source"],
                    "evidence_type": evidence_type,
                })
                continue
            unsupported = sorted(
                set(control["spec"].get("applies_to", [])) - {schema_subject_type}
            )
            if unsupported:
                errors.append({
                    "type": "control-evidence-schema-incompatible",
                    "control": control_id,
                    "source": control["_source"],
                    "evidence_schema": schema["_source"],
                    "evidence_type": evidence_type,
                    "unsupported_subject_types": unsupported,
                })
    return schemas, errors


def validate_rego_entrypoints(
    policy_sources: PolicySources,
    controls: dict[str, JsonObject],
    *,
    opa: str = "opa",
) -> list[JsonObject]:
    """Compile Rego and prove that every manifest entrypoint names a rule."""
    sources = normalize_policy_sources(policy_sources)
    modules = rego_module_paths(sources, include_tests=True)
    if not modules:
        return [{"type": "rego-source-unavailable", "source": "controls"}]
    try:
        checked = subprocess.run(
            [opa, "check", "--strict", *(str(path) for path in modules)],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return [{
            "type": "opa-unavailable",
            "opa": opa,
            "message": str(error),
        }]
    if checked.returncode != 0:
        return [{
            "type": "rego-compilation-failed",
            "sources": [str(path) for path in modules],
            "message": checked.stderr.strip() or checked.stdout.strip(),
        }]

    entrypoints: set[str] = set()
    module_sources = {
        path: source
        for source in sources
        for path in (source.path / "controls").rglob("*.rego")
        if (source.path / "controls").is_dir()
    }
    for path in rego_module_paths(sources, include_tests=False):
        source = module_sources[path]
        parsed = subprocess.run(
            [opa, "parse", "--format=json", str(path)],
            text=True,
            capture_output=True,
            check=False,
        )
        relative = path.relative_to(source.path).as_posix()
        qualified = f"{source.name}:{relative}"
        if parsed.returncode != 0:
            return [{
                "type": "rego-parse-failed",
                "source": qualified,
                "message": parsed.stderr.strip() or parsed.stdout.strip(),
            }]
        try:
            module = json.loads(parsed.stdout)
        except json.JSONDecodeError as error:
            return [{
                "type": "rego-parse-output-invalid",
                "source": qualified,
                "message": str(error),
            }]
        package = [part.get("value") for part in module.get("package", {}).get("path", [])]
        if not package or package[0] != "data" or not all(
            isinstance(part, str) for part in package
        ):
            continue
        for rule in module.get("rules", []):
            name = rule.get("head", {}).get("name")
            if isinstance(name, str):
                entrypoints.add(".".join([*package, name]))

    return [{
        "type": "control-entrypoint-missing",
        "control": control_id,
        "source": control["_source"],
        "entrypoint": control["spec"]["entrypoint"],
    } for control_id, control in sorted(controls.items())
    if control["spec"]["entrypoint"] not in entrypoints]


def _json_pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else "/"


def _baseline_reference(document: Any) -> str | None:
    if not isinstance(document, dict) or not isinstance(document.get("metadata"), dict):
        return None
    metadata = document["metadata"]
    identifier = metadata.get("id")
    revision = metadata.get("revision", metadata.get("version"))
    if not isinstance(identifier, str) or revision is None:
        return None
    return f"{identifier}@{revision}"


def load_baseline_catalog(
    baselines_root: Path,
    schemas_root: Path | dict[str, Path] | None = None,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    """Load and schema-validate all baseline policy documents."""
    schemas_root = schemas_root or baselines_root.parent / "schemas/policy"
    schemas: dict[str, JsonObject] = {}
    errors: list[JsonObject] = []
    for kind, filename in BASELINE_SCHEMA_FILES.items():
        schema_path = (
            schemas_root[kind]
            if isinstance(schemas_root, dict)
            else schemas_root / filename
        )
        try:
            schemas[kind] = load_json(schema_path)
        except (OSError, json.JSONDecodeError) as error:
            try:
                schema_source = schema_path.relative_to(baselines_root.parent).as_posix()
            except ValueError:
                schema_source = schema_path.as_posix()
            errors.append({
                "type": "policy-schema-unavailable",
                "kind": kind,
                "source": schema_source,
                "message": str(error),
            })

    catalog: dict[str, JsonObject] = {}
    for path in sorted(baselines_root.rglob("*.json")):
        source = path.relative_to(baselines_root.parent).as_posix()
        try:
            baseline = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append({
                "type": "policy-document-unreadable",
                "source": source,
                "message": str(error),
            })
            continue

        kind = baseline.get("kind") if isinstance(baseline, dict) else None
        schema = schemas.get(kind)
        reference = _baseline_reference(baseline)
        if schema is None:
            errors.append({
                "type": "unsupported-baseline-kind",
                "source": source,
                "kind": kind,
                **({"baseline": reference} if reference else {}),
            })
            continue

        validation_errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(baseline),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )
        if validation_errors:
            for error in validation_errors:
                errors.append({
                    "type": "baseline-schema-invalid",
                    "source": source,
                    "kind": kind,
                    "schema": schema.get("$id"),
                    "path": _json_pointer(error.absolute_path),
                    "message": error.message,
                    **({"baseline": reference} if reference else {}),
                })
            continue

        assert reference is not None
        if reference in catalog:
            errors.append({
                "type": "duplicate-baseline-reference",
                "baseline": reference,
                "source": source,
                "existing_source": catalog[reference]["_source"],
            })
            continue
        baseline["_digest"] = content_digest(baseline)
        baseline["_source"] = source
        catalog[reference] = baseline
    return catalog, errors


def _load_control_catalogs(
    policy_sources: PolicySources,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    sources = normalize_policy_sources(policy_sources)
    schema_path, errors = _effective_schema_path(
        sources,
        Path("schemas/policy/control.schema.json"),
    )
    catalog: dict[str, JsonObject] = {}
    if schema_path is None:
        return catalog, errors
    for source in sources:
        controls_root = source.path / "controls"
        if not controls_root.is_dir():
            continue
        incoming, incoming_errors = load_control_catalog(controls_root, schema_path)
        _qualify_catalog(incoming, source)
        errors.extend(incoming_errors)
        _merge_policy_catalog(
            catalog,
            incoming,
            resource_kind="Control",
            errors=errors,
        )
    return catalog, errors


def _load_baseline_catalogs(
    policy_sources: PolicySources,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    sources = normalize_policy_sources(policy_sources)
    schema_paths: dict[str, Path] = {}
    errors: list[JsonObject] = []
    for kind, filename in BASELINE_SCHEMA_FILES.items():
        schema_path, schema_errors = _effective_schema_path(
            sources,
            Path("schemas/policy") / filename,
        )
        errors.extend(schema_errors)
        if schema_path is not None:
            schema_paths[kind] = schema_path
    if len(schema_paths) != len(BASELINE_SCHEMA_FILES):
        return {}, errors

    catalog: dict[str, JsonObject] = {}
    for source in sources:
        baselines_root = source.path / "baselines"
        if not baselines_root.is_dir():
            continue
        incoming, incoming_errors = load_baseline_catalog(baselines_root, schema_paths)
        _qualify_catalog(incoming, source)
        errors.extend(incoming_errors)
        _merge_policy_catalog(
            catalog,
            incoming,
            resource_kind="Baseline",
            errors=errors,
        )
    return catalog, errors


def load_policy_catalogs(
    policy_sources: PolicySources,
) -> tuple[dict[str, JsonObject], dict[str, JsonObject], list[JsonObject]]:
    """Validate manifests, baselines, inheritance, and effective parameters."""
    controls, control_errors = _load_control_catalogs(policy_sources)
    catalog, baseline_errors = _load_baseline_catalogs(policy_sources)
    _, evidence_errors = validate_control_evidence_contracts(policy_sources, controls)
    _, requirement_baselines, _, requirement_errors = load_requirement_catalogs(
        policy_sources,
        controls,
    )
    assignment_reference_collisions = sorted(set(catalog) & set(requirement_baselines))
    collision_errors = [
        {
            "type": "assignment-reference-kind-collision",
            "reference": reference,
            "technical_sources": catalog[reference].get("_sources", []),
            "requirement_sources": requirement_baselines[reference].get("_sources", []),
        }
        for reference in assignment_reference_collisions
    ]
    errors = [
        *source_pin_errors(policy_sources),
        *control_errors,
        *baseline_errors,
        *evidence_errors,
        *requirement_errors,
        *collision_errors,
    ]
    if errors:
        return controls, catalog, errors

    cache: dict[str, JsonObject] = {}
    for reference in sorted(catalog):
        try:
            baseline = resolve_baseline(reference, catalog, cache=cache)
        except BaselineResolutionError as error:
            errors.append({
                **error.details,
                "source": catalog[reference]["_source"],
            })
            continue

        for instance_id, instance in sorted(baseline["controls"].items()):
            implementation = instance["implementation"]
            definition = controls.get(implementation)
            if definition is None:
                errors.append({
                    "type": "unknown-control",
                    "source": catalog[reference]["_source"],
                    "baseline": reference,
                    "instance_id": instance_id,
                    "implementation": implementation,
                })
                continue

            try:
                pp.evidence_for(instance, definition)
            except (ValueError, KeyError) as error:
                errors.append({"type": "policy-freshness-invalid", "baseline": reference, "instance_id": instance_id, "message": str(error)})
            validation_errors = sorted(
                Draft202012Validator(
                    definition["_parameters_schema"],
                    format_checker=FormatChecker(),
                ).iter_errors(instance.get("parameters", {})),
                key=lambda error: (
                    tuple(str(part) for part in error.absolute_path),
                    error.message,
                ),
            )
            for error in validation_errors:
                errors.append({
                    "type": "control-parameters-invalid",
                    "source": catalog[reference]["_source"],
                    "baseline": reference,
                    "instance_id": instance_id,
                    "implementation": implementation,
                    "parameters_schema": definition["_parameters_schema_source"],
                    "path": _json_pointer(error.absolute_path),
                    "message": error.message,
                })
    return controls, catalog, errors


def _load_requirement_policy_kind(
    policies_root: Path,
    kind: str,
    directory_name: str,
    schema_filename: str,
    schema_path: Path | None = None,
    requirements: dict[str, JsonObject] | None = None,
) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    root = policies_root / directory_name
    if not root.exists():
        return {}, []
    schema_path = schema_path or policies_root / "schemas/policy" / schema_filename
    try:
        schema = load_json(schema_path)
    except (OSError, json.JSONDecodeError) as error:
        return {}, [{
            "type": "requirement-policy-schema-unavailable",
            "kind": kind,
            "source": schema_path.relative_to(policies_root).as_posix(),
            "message": str(error),
        }]

    catalog: dict[str, JsonObject] = {}
    errors: list[JsonObject] = []
    for path in sorted(root.rglob("*.json")):
        source = path.relative_to(policies_root).as_posix()
        try:
            document = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            errors.append({
                "type": "requirement-policy-document-unreadable",
                "kind": kind,
                "source": source,
                "message": str(error),
            })
            continue
        reference = _baseline_reference(document)
        validation_errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )
        if validation_errors:
            for error in validation_errors:
                errors.append({
                    "type": "requirement-policy-schema-invalid",
                    "kind": kind,
                    "source": source,
                    "schema": schema.get("$id"),
                    "path": _json_pointer(error.absolute_path),
                    "message": error.message,
                    **({"reference": reference} if reference else {}),
                })
            continue
        assert reference is not None
        document = pp.normalized_resource_document(document, requirements)
        if reference in catalog:
            errors.append({
                "type": "duplicate-requirement-policy-reference",
                "kind": kind,
                "reference": reference,
                "source": source,
                "existing_source": catalog[reference]["_source"],
            })
            continue
        document["_digest"] = content_digest(document)
        document["_source"] = source
        catalog[reference] = document
    return catalog, errors


def load_requirement_catalogs(
    policy_sources: PolicySources,
    controls: dict[str, JsonObject] | None = None,
) -> tuple[
    dict[str, JsonObject],
    dict[str, JsonObject],
    dict[str, JsonObject],
    list[JsonObject],
]:
    """Load and semantically validate requirements, baselines, and realizations."""
    sources = normalize_policy_sources(policy_sources)
    loaded: dict[str, tuple[dict[str, JsonObject], list[JsonObject]]] = {}
    for kind, (directory, schema_filename) in REQUIREMENT_POLICY_KINDS.items():
        has_documents = any((source.path / directory).is_dir() for source in sources)
        if not has_documents:
            loaded[kind] = ({}, [])
            continue
        schema_path, kind_errors = _effective_schema_path(
            sources,
            Path("schemas/policy") / schema_filename,
        )
        catalog: dict[str, JsonObject] = {}
        if schema_path is not None:
            for source in sources:
                if not (source.path / directory).is_dir():
                    continue
                incoming, incoming_errors = _load_requirement_policy_kind(
                    source.path,
                    kind,
                    directory,
                    schema_filename,
                    schema_path,
                    loaded.get("ControlRequirement", ({}, []))[0],
                )
                _qualify_catalog(incoming, source)
                kind_errors.extend(incoming_errors)
                _merge_policy_catalog(
                    catalog,
                    incoming,
                    resource_kind=kind,
                    errors=kind_errors,
                )
        loaded[kind] = (catalog, kind_errors)
    requirements, requirement_errors = loaded["ControlRequirement"]
    requirement_baselines, baseline_errors = loaded["RequirementBaseline"]
    realizations, realization_errors = loaded["ControlRealization"]
    errors = [*requirement_errors, *baseline_errors, *realization_errors]
    if errors:
        return requirements, requirement_baselines, realizations, errors

    for reference, requirement in sorted(requirements.items()):
        try:
            pp.declarations(requirement)
        except (ValueError, KeyError) as error:
            errors.append({"type": "parameter-declaration-invalid", "requirement": reference, "message": str(error)})
    for baseline_reference, baseline in sorted(requirement_baselines.items()):
        seen = set()
        for pin in baseline["spec"].get("requirements", []):
            reference = pin["requirement"]
            if reference in seen:
                errors.append({
                    "type": "duplicate-requirement-pin",
                    "source": baseline["_source"],
                    "baseline": baseline_reference,
                    "requirement": reference,
                })
                continue
            seen.add(reference)
            requirement = requirements.get(reference)
            if requirement is None:
                errors.append({
                    "type": "unknown-requirement",
                    "source": baseline["_source"],
                    "baseline": baseline_reference,
                    "requirement": reference,
                })
            elif requirement["_digest"] != pin["digest"]:
                errors.append({
                    "type": "requirement-digest-mismatch",
                    "source": baseline["_source"],
                    "baseline": baseline_reference,
                    "requirement": reference,
                    "expected": pin["digest"],
                    "actual": requirement["_digest"],
                })

    for realization_reference, realization in sorted(realizations.items()):
        spec = realization["spec"]
        requirement_pin = spec["requirement"]
        requirement = requirements.get(requirement_pin["requirement"])
        if requirement is None:
            errors.append({
                "type": "unknown-requirement",
                "source": realization["_source"],
                "realization": realization_reference,
                "requirement": requirement_pin["requirement"],
            })
        elif requirement["_digest"] != requirement_pin["digest"]:
            errors.append({
                "type": "requirement-digest-mismatch",
                "source": realization["_source"],
                "realization": realization_reference,
                "requirement": requirement_pin["requirement"],
                "expected": requirement_pin["digest"],
                "actual": requirement["_digest"],
            })

        based_on = spec.get("based_on")
        if based_on:
            base = realizations.get(based_on["realization"])
            if base is None:
                errors.append({
                    "type": "unknown-base-realization",
                    "source": realization["_source"],
                    "realization": realization_reference,
                    "based_on": based_on["realization"],
                })
            elif base["_digest"] != based_on["digest"]:
                errors.append({
                    "type": "base-realization-digest-mismatch",
                    "source": realization["_source"],
                    "realization": realization_reference,
                    "based_on": based_on["realization"],
                    "expected": based_on["digest"],
                    "actual": base["_digest"],
                })

        checks = spec.get("checks", [])
        check_ids = [check["instance_id"] for check in checks]
        duplicates = sorted(
            identifier for identifier in set(check_ids) if check_ids.count(identifier) > 1
        )
        if duplicates:
            errors.append({
                "type": "duplicate-realization-check",
                "source": realization["_source"],
                "realization": realization_reference,
                "instance_ids": duplicates,
            })
        required_ids = spec.get("satisfaction", {}).get("allOf", [])
        if set(check_ids) != set(required_ids):
            errors.append({
                "type": "incomplete-realization-satisfaction",
                "source": realization["_source"],
                "realization": realization_reference,
                "undefined": sorted(set(required_ids) - set(check_ids)),
                "unreferenced": sorted(set(check_ids) - set(required_ids)),
            })

        for index, instance in enumerate(checks):
            implementation = instance["implementation"]
            definition = (controls or {}).get(implementation)
            if definition is None:
                errors.append({
                    "type": "unknown-control",
                    "source": realization["_source"],
                    "realization": realization_reference,
                    "instance_id": instance["instance_id"],
                    "implementation": implementation,
                })
                continue
            unsupported_types = sorted(
                set(spec["applies_to"]["subject_types"])
                - set(definition["spec"].get("applies_to", []))
            )
            if unsupported_types:
                errors.append({
                    "type": "realization-control-inapplicable",
                    "source": realization["_source"],
                    "realization": realization_reference,
                    "instance_id": instance["instance_id"],
                    "subject_types": unsupported_types,
                })
            linked_paths = {link["destination"]["path"] for link in spec.get("parameter_links", []) if link["destination"]["instance_id"] == instance["instance_id"] and link["destination"]["kind"] == "parameters"}
            try:
                parameter_schema = pp.partial_parameter_schema(definition["_parameters_schema"], linked_paths)
            except ValueError as error:
                errors.append({"type": "parameter-destination-invalid", "realization": realization_reference, "message": str(error)})
                continue
            parameter_errors = sorted(
                Draft202012Validator(
                    parameter_schema,
                    format_checker=FormatChecker(),
                ).iter_errors(instance.get("parameters", {})),
                key=lambda error: tuple(str(part) for part in error.absolute_path),
            )
            for error in parameter_errors:
                errors.append({
                    "type": "control-parameters-invalid",
                    "source": realization["_source"],
                    "realization": realization_reference,
                    "instance_id": instance["instance_id"],
                    "implementation": implementation,
                    "parameters_schema": definition["_parameters_schema_source"],
                    "path": _json_pointer(error.absolute_path),
                    "message": error.message,
                })
    return requirements, requirement_baselines, realizations, errors


def validate_policy_catalog(policy_sources: PolicySources) -> tuple[dict[str, JsonObject], list[JsonObject]]:
    _, catalog, errors = load_policy_catalogs(policy_sources)
    return catalog, errors


def control_definition_fingerprint(control: JsonObject) -> str:
    ignored = {
        "alignment",
        "definition_fingerprint",
        "derivations",
        "deviations",
        "disposition",
        "lineage",
        "overlay_policy",
    }
    return content_digest({key: value for key, value in control.items() if key not in ignored})


def control_criteria_snapshot(control: JsonObject) -> JsonObject:
    """Freeze the normative state on either side of an overlay operation."""
    return {
        "evidence": copy.deepcopy(control.get("evidence", {})),
        "implementation": control["implementation"],
        "parameters": copy.deepcopy(control.get("parameters", {})),
        "disposition": control.get("disposition", "evaluate"),
    }


def require_deviation(operation: JsonObject, baseline_reference: str) -> JsonObject:
    deviation = operation.get("deviation")
    required = {"id", "classification", "rationale", "approval_ref", "review_after"}
    missing = sorted(required - set(deviation or {}))
    if missing:
        raise BaselineResolutionError(
            "incomplete-deviation",
            baseline=baseline_reference,
            operation=operation.get("op"),
            target=operation.get("target"),
            missing=missing,
        )
    return copy.deepcopy(deviation)


def resolve_baseline(
    reference: str,
    catalog: dict[str, JsonObject],
    stack: tuple[str, ...] = (),
    cache: dict[str, JsonObject] | None = None,
) -> JsonObject:
    cache = cache if cache is not None else {}
    if reference in cache:
        return copy.deepcopy(cache[reference])
    if reference in stack:
        raise BaselineResolutionError(
            "baseline-cycle",
            cycle=[*stack, reference],
        )

    document = catalog.get(reference)
    if document is None:
        raise BaselineResolutionError("unknown-baseline", baseline=reference)

    if document["kind"] == "Baseline":
        controls: dict[str, JsonObject] = {}
        for source_control in document["spec"].get("controls", []):
            instance_id = source_control["instance_id"]
            if instance_id in controls:
                raise BaselineResolutionError(
                    "duplicate-control-instance",
                    baseline=reference,
                    instance_id=instance_id,
                )
            control = copy.deepcopy(source_control)
            control.update({
                "alignment": "unaltered",
                "derivations": [],
                "deviations": [],
                "disposition": "evaluate",
                "lineage": [{"baseline": reference, "operation": "defined"}],
            })
            control["definition_fingerprint"] = control_definition_fingerprint(control)
            controls[instance_id] = control

        resolved = {
            "reference": reference,
            "title": document["spec"]["title"],
            "digest": document["_digest"],
            "lineage": [{"reference": reference, "digest": document["_digest"]}],
            "controls": controls,
            "deviations": [],
        }
        cache[reference] = copy.deepcopy(resolved)
        return resolved

    if document["kind"] != "BaselineOverlay":
        raise BaselineResolutionError(
            "unsupported-baseline-kind",
            baseline=reference,
            kind=document["kind"],
        )

    controls: dict[str, JsonObject] = {}
    baseline_lineage: list[JsonObject] = []
    deviations: list[JsonObject] = []
    next_stack = (*stack, reference)
    parents = document["spec"].get("extends", [])
    if not parents:
        raise BaselineResolutionError("overlay-without-parent", baseline=reference)

    for parent_pin in parents:
        parent_reference = parent_pin["baseline"]
        parent_document = catalog.get(parent_reference)
        if parent_document is None:
            raise BaselineResolutionError(
                "unknown-baseline",
                baseline=parent_reference,
                referenced_by=reference,
            )
        if parent_document["_digest"] != parent_pin["digest"]:
            raise BaselineResolutionError(
                "parent-digest-mismatch",
                baseline=reference,
                parent=parent_reference,
                expected=parent_pin["digest"],
                actual=parent_document["_digest"],
            )

        parent = resolve_baseline(parent_reference, catalog, next_stack, cache)
        for lineage_item in parent["lineage"]:
            if lineage_item not in baseline_lineage:
                baseline_lineage.append(copy.deepcopy(lineage_item))
        deviations.extend(copy.deepcopy(parent["deviations"]))

        for instance_id, inherited in parent["controls"].items():
            existing = controls.get(instance_id)
            if existing is None:
                controls[instance_id] = copy.deepcopy(inherited)
            elif existing["definition_fingerprint"] == inherited["definition_fingerprint"]:
                for lineage_item in inherited["lineage"]:
                    if lineage_item not in existing["lineage"]:
                        existing["lineage"].append(copy.deepcopy(lineage_item))
                for derivation in inherited["derivations"]:
                    if derivation not in existing["derivations"]:
                        existing["derivations"].append(copy.deepcopy(derivation))
                for deviation in inherited["deviations"]:
                    if deviation not in existing["deviations"]:
                        existing["deviations"].append(copy.deepcopy(deviation))
            else:
                raise BaselineResolutionError(
                    "inherited-control-conflict",
                    baseline=reference,
                    instance_id=instance_id,
                    parents=[parent["reference"]],
                )

    seen_operations: set[tuple[str, str]] = set()
    for operation in document["spec"].get("operations", []):
        operation_name = operation["op"]
        target = operation.get("target", "")
        operation_key = (operation_name, target)
        if operation_key in seen_operations:
            raise BaselineResolutionError(
                "duplicate-overlay-operation",
                baseline=reference,
                operation=operation_name,
                target=target,
            )
        seen_operations.add(operation_key)

        if operation_name == "add":
            added = copy.deepcopy(operation["control"])
            instance_id = added["instance_id"]
            if instance_id in controls:
                raise BaselineResolutionError(
                    "added-control-conflict",
                    baseline=reference,
                    instance_id=instance_id,
                )
            added.update({
                "alignment": "additional",
                "derivations": [],
                "deviations": [],
                "disposition": "evaluate",
                "lineage": [{"baseline": reference, "operation": "add"}],
            })
            added["definition_fingerprint"] = control_definition_fingerprint(added)
            controls[instance_id] = added
            continue

        control = controls.get(target)
        if control is None:
            raise BaselineResolutionError(
                "overlay-target-missing",
                baseline=reference,
                operation=operation_name,
                target=target,
            )

        blocked = control.get("overlay_policy", {}).get("blocked_operations", [])
        if operation_name in blocked:
            raise BaselineResolutionError(
                "sealed-control",
                baseline=reference,
                operation=operation_name,
                target=target,
                sealed_by=control["overlay_policy"]["sealed_by"],
            )

        expected_fingerprint = operation.get("expected_parent_fingerprint")
        if expected_fingerprint != control["definition_fingerprint"]:
            raise BaselineResolutionError(
                "parent-control-fingerprint-mismatch",
                baseline=reference,
                operation=operation_name,
                target=target,
                expected=expected_fingerprint,
                actual=control["definition_fingerprint"],
            )

        records_derivation = operation_name in {"tailor", "exclude", "substitute"}
        before = control_criteria_snapshot(control) if records_derivation else None
        inherited_lineage = (
            copy.deepcopy(control["lineage"]) if records_derivation else None
        )
        derivation_deviation = None
        if operation_name == "tailor":
            deviation = require_deviation(operation, reference)
            control["parameters"] = copy.deepcopy(operation["parameters"])
            if "evidence" in operation:
                control["evidence"] = copy.deepcopy(operation["evidence"])
            control["alignment"] = "tailored"
            control["deviations"].append(deviation)
            deviations.append(deviation)
            derivation_deviation = deviation
        elif operation_name == "exclude":
            deviation = require_deviation(operation, reference)
            control["disposition"] = "excluded"
            control["alignment"] = "deviated"
            control["deviations"].append(deviation)
            deviations.append(deviation)
            derivation_deviation = deviation
        elif operation_name == "substitute":
            if not operation.get("equivalence_ref"):
                raise BaselineResolutionError(
                    "missing-equivalence-reference",
                    baseline=reference,
                    target=target,
                )
            control["implementation"] = operation["implementation"]
            if "evidence" in operation:
                control["evidence"] = copy.deepcopy(operation["evidence"])
            if "parameters" in operation:
                control["parameters"] = copy.deepcopy(operation["parameters"])
            if "evidence" in operation:
                control["evidence"] = copy.deepcopy(operation["evidence"])
            control["alignment"] = "substituted"
            control["equivalence_ref"] = operation["equivalence_ref"]
        elif operation_name == "annotate":
            annotations = operation.get("annotations", {})
            allowed = {"severity", "remediation", "external_refs"}
            unexpected = sorted(set(annotations) - allowed)
            if unexpected:
                raise BaselineResolutionError(
                    "unsupported-annotation",
                    baseline=reference,
                    target=target,
                    fields=unexpected,
                )
            control.update(copy.deepcopy(annotations))
            if control["alignment"] == "unaltered":
                control["alignment"] = "annotated"
        elif operation_name == "seal":
            blocked_operations = operation.get(
                "blocked_operations",
                ["tailor", "exclude", "substitute"],
            )
            control["overlay_policy"] = {
                "blocked_operations": sorted(set(blocked_operations)),
                "reason": operation["reason"],
                "sealed_by": reference,
            }
        else:
            raise BaselineResolutionError(
                "unsupported-overlay-operation",
                baseline=reference,
                operation=operation_name,
            )

        if records_derivation:
            assert before is not None
            assert inherited_lineage is not None
            derivation = {
                "operation": operation_name,
                "overlay": reference,
                "parent_fingerprint": expected_fingerprint,
                "inherited_lineage": inherited_lineage,
                "before": before,
                "after": control_criteria_snapshot(control),
            }
            if derivation_deviation is not None:
                derivation["deviation"] = copy.deepcopy(derivation_deviation)
            if operation_name == "substitute":
                derivation["equivalence_ref"] = operation["equivalence_ref"]
            control["derivations"].append(derivation)

        control["lineage"].append({"baseline": reference, "operation": operation_name})
        control["definition_fingerprint"] = control_definition_fingerprint(control)

    baseline_lineage.append({"reference": reference, "digest": document["_digest"]})
    resolved = {
        "reference": reference,
        "title": document["spec"]["title"],
        "digest": document["_digest"],
        "lineage": baseline_lineage,
        "controls": controls,
        "deviations": deviations,
    }
    cache[reference] = copy.deepcopy(resolved)
    return resolved


def render_plan(
    subject: JsonObject,
    groups_document: list[JsonObject],
    assignments: list[JsonObject],
    policy_sources: PolicySources,
    *,
    config=None,
) -> JsonObject:
    from .assessment_provenance import PLAN_SCHEMA, PROVENANCE_SCHEMA, PLAN_DIGEST_ALGORITHM, artifact_digest, stage
    from .composition import require_composition
    from .project_config import composition_validation
    report = composition_validation(config, require=True) if config and config.source else require_composition(policy_sources)
    normalized_policy_sources = normalize_policy_sources(policy_sources)
    canonical_groups = []
    for source_group in sorted(groups_document, key=lambda group: group["id"]):
        group = copy.deepcopy(source_group)
        group["parents"] = sorted(group.get("parents", []))
        if "members" in group:
            group["members"] = sorted(group["members"])
        canonical_groups.append(group)

    canonical_assignments = []
    for source_assignment in sorted(assignments, key=lambda assignment: assignment["id"]):
        assignment = copy.deepcopy(source_assignment)
        assignment["baselines"] = sorted(assignment.get("baselines", []))
        canonical_assignments.append(assignment)

    assignments = canonical_assignments

    groups = {group["id"]: group for group in groups_document}
    if len(groups) != len(groups_document):
        raise ValueError("group ids must be unique")
    validate_group_dag(groups)

    resolved_groups = resolve_groups(groups, subject)
    resolved_group_ids = {group["id"] for group in resolved_groups}
    applicable_assignments = sorted(
        [assignment for assignment in assignments if assignment["target"].get("group") in resolved_group_ids],
        key=lambda assignment: assignment["id"],
    )

    controls, baselines, policy_errors = load_policy_catalogs(normalized_policy_sources)
    requirements, requirement_baselines, realizations, _ = load_requirement_catalogs(
        normalized_policy_sources,
        controls,
    )
    rendered_controls: dict[str, JsonObject] = {}
    excluded_controls: dict[str, JsonObject] = {}
    rendered_requirements: dict[str, JsonObject] = {}
    resolved_baselines: list[JsonObject] = []
    resolved_requirement_baselines: list[JsonObject] = []
    resolution_errors: list[JsonObject] = copy.deepcopy(policy_errors)
    baseline_cache: dict[str, JsonObject] = {}
    parameter_resolutions: dict[tuple[str, str, str], JsonObject] = {}

    if subject["status"] == "unknown":
        resolution_errors.append({
            "type": "subject-lifecycle-unknown",
            "subject_id": subject["id"],
        })

    parameter_resolution_failed = False
    if not policy_errors:
        for assignment in applicable_assignments:
            group_id = assignment["target"]["group"]
            for baseline_reference in assignment["baselines"]:
                if baseline_reference not in requirement_baselines:
                    continue
                baseline_provenance = {
                    "group": group_id,
                    "assignment": assignment["id"],
                    "baseline": baseline_reference,
                }
                try:
                    parameter_states, parameter_ancestry = pp.resolve(
                        baseline_reference,
                        requirement_baselines,
                        requirements,
                    )
                    pp.complete(parameter_states)
                except (ValueError, KeyError) as error:
                    parameter_resolution_failed = True
                    resolution_errors.append({
                        "type": "parameter-resolution-failed",
                        "message": str(error),
                        **baseline_provenance,
                    })
                    continue
                parameter_resolutions[(assignment["id"], group_id, baseline_reference)] = {
                    "reference": baseline_reference,
                    "applicability": baseline_provenance,
                    "states": parameter_states,
                    "ancestry": parameter_ancestry,
                }
        if not parameter_resolution_failed:
            try:
                pp.compose_selected(
                    list(parameter_resolutions.values()),
                    requirement_baselines,
                    requirements,
                )
            except (ValueError, KeyError) as error:
                resolution_errors.append({
                    "type": "parameter-resolution-failed",
                    "message": str(error),
                })
                parameter_resolutions.clear()

    for assignment in (applicable_assignments if not policy_errors else []):
        group_id = assignment["target"]["group"]
        for baseline_reference in assignment["baselines"]:
            requirement_baseline = requirement_baselines.get(baseline_reference)
            if requirement_baseline is not None:
                baseline_provenance = {
                    "group": group_id,
                    "assignment": assignment["id"],
                    "baseline": baseline_reference,
                }
                parameter_resolution = parameter_resolutions.get(
                    (assignment["id"], group_id, baseline_reference)
                )
                if parameter_resolution is None:
                    continue
                parameter_states = parameter_resolution["states"]
                parameter_ancestry = parameter_resolution["ancestry"]
                resolved_requirement_baselines.append({
                    **baseline_provenance,
                    "reference": baseline_reference,
                    "title": requirement_baseline["spec"]["title"],
                    "digest": requirement_baseline["_digest"],
                    "policy_sources": requirement_baseline.get("_sources", []),
                    "parameter_derivation": {"ancestry": parameter_ancestry, "states": parameter_states},
                    "requirements": [
                        copy.deepcopy(pin)
                        for pin in requirement_baseline["spec"].get("requirements", [])
                    ],
                })
                for pin in requirement_baseline["spec"].get("requirements", []):
                    requirement_reference = pin["requirement"]
                    requirement = requirements[requirement_reference]
                    matching_realizations = [
                        (reference, realization)
                        for reference, realization in realizations.items()
                        if realization["spec"]["requirement"]["requirement"]
                        == requirement_reference
                        and subject["type"]
                        in realization["spec"]["applies_to"]["subject_types"]
                        and all(
                            subject.get("labels", {}).get(key) == value
                            for key, value in realization["spec"]["applies_to"]
                            .get("match_labels", {})
                            .items()
                        )
                    ]
                    if len(matching_realizations) > 1:
                        resolution_errors.append({
                            "type": "multiple-control-realizations",
                            "requirement": requirement_reference,
                            "subject_id": subject["id"],
                            "realizations": sorted(
                                reference for reference, _ in matching_realizations
                            ),
                            **baseline_provenance,
                        })
                        continue

                    realization_reference = None
                    realization = None
                    if matching_realizations:
                        realization_reference, realization = matching_realizations[0]
                        adoption = copy.deepcopy(realization["spec"]["adoption"])
                        satisfaction = copy.deepcopy(
                            realization["spec"].get("satisfaction", {"allOf": []})
                        )
                    else:
                        adoption = {
                            "status": "not_implemented",
                            "method": "none",
                            "owner": "unassigned",
                        }
                        satisfaction = {"allOf": []}

                    requirement_candidate: JsonObject = {
                        "reference": requirement_reference,
                        "digest": requirement["_digest"],
                        "title": requirement["spec"]["title"],
                        "statement": requirement["spec"]["statement"],
                        "external_refs": requirement["spec"].get("external_refs", []),
                        "policy_sources": requirement.get("_sources", []),
                        "required": pin["required"],
                        "adoption": adoption,
                        "satisfaction": satisfaction,
                        "technical_instance_ids": satisfaction["allOf"],
                        "provenance": [baseline_provenance],
                        "parameter_facts": {"document": pp.document(requirement), "states": parameter_states[requirement_reference]},
                    }
                    if realization is not None and realization_reference is not None:
                        requirement_candidate["realization"] = {
                            "reference": realization_reference,
                            "digest": realization["_digest"],
                            "policy_sources": realization.get("_sources", []),
                            **(
                                {"based_on": copy.deepcopy(realization["spec"]["based_on"])}
                                if "based_on" in realization["spec"]
                                else {}
                            ),
                        }

                    resolved_checks = []
                    if realization is not None:
                        try:
                            resolved_checks, consumed = pp.consume(realization, parameter_states[requirement_reference], controls)
                        except (ValueError, KeyError) as error:
                            resolution_errors.append({"type": "parameter-consumption-failed", "message": str(error), **baseline_provenance})
                            continue
                        requirement_candidate["parameter_facts"]["realization"] = pp.document(realization)
                        requirement_candidate["parameter_facts"]["consumption"] = consumed
                    existing_requirement = rendered_requirements.get(requirement_reference)
                    if existing_requirement is None:
                        rendered_requirements[requirement_reference] = requirement_candidate
                    else:
                        comparable = (
                            "digest",
                            "required",
                            "adoption",
                            "satisfaction",
                            "technical_instance_ids",
                            "realization",
                            "parameter_facts",
                        )
                        if all(
                            existing_requirement.get(key) == requirement_candidate.get(key)
                            for key in comparable
                        ):
                            existing_requirement["provenance"].append(baseline_provenance)
                        else:
                            resolution_errors.append({
                                "type": "control-realization-conflict",
                                "requirement": requirement_reference,
                                **baseline_provenance,
                            })
                            continue

                    if realization is None:
                        continue
                    for source_instance in resolved_checks:
                        instance = copy.deepcopy(source_instance)
                        implementation = instance["implementation"]
                        definition = controls[implementation]
                        spec = definition["spec"]
                        instance_fingerprint = content_digest(instance)
                        realization_provenance = {
                            **baseline_provenance,
                            "requirement": requirement_reference,
                            "realization": realization_reference,
                        }
                        defaults = spec.get("defaults", {})
                        candidate = {
                            "instance_id": instance["instance_id"],
                            "implementation": implementation,
                            "title": spec["title"],
                            "purpose": spec["purpose"],
                            "entrypoint": spec["entrypoint"],
                            "parameters": instance.get("parameters", {}),
                            "severity": instance.get(
                                "severity",
                                defaults.get("severity", "medium"),
                            ),
                            "remediation": instance.get(
                                "remediation",
                                defaults.get("remediation", ""),
                            ),
                            "evidence": pp.evidence_for(instance, definition),
                            "policy_inputs": {"instance": copy.deepcopy(instance), "definition": pp.document(definition), "parameters_schema": definition["_parameters_schema"], "implementation_modules": definition.get("_implementation_modules", [])},
                            "disposition": "evaluate",
                            "alignment": "realization",
                            "definition_fingerprint": instance_fingerprint,
                            "derivations": [],
                            "deviations": [],
                            "lineage": [{
                                "realization": realization_reference,
                                "operation": "defined",
                            }],
                            "provenance": [realization_provenance],
                            "implementation_sources": definition.get("_sources", []),
                        }
                        instance_id = candidate["instance_id"]
                        existing = rendered_controls.get(instance_id)
                        if existing is None:
                            rendered_controls[instance_id] = candidate
                        else:
                            comparable_keys = (
                                "implementation",
                                "title",
                                "purpose",
                                "parameters",
                                "severity",
                                "remediation",
                                "evidence",
                                "alignment",
                                "definition_fingerprint",
                            )
                            if all(
                                existing.get(key) == candidate.get(key)
                                for key in comparable_keys
                            ):
                                existing["provenance"].append(realization_provenance)
                            else:
                                resolution_errors.append({
                                    "type": "control-instance-conflict",
                                    "instance_id": instance_id,
                                    "incoming_provenance": [realization_provenance],
                                })
                continue

            try:
                baseline = resolve_baseline(baseline_reference, baselines, cache=baseline_cache)
            except BaselineResolutionError as error:
                resolution_errors.append({
                    **error.details,
                    "assignment": assignment["id"],
                    "group": group_id,
                })
                continue

            resolved_baselines.append({
                "assignment": assignment["id"],
                "group": group_id,
                "reference": baseline_reference,
                "title": baseline["title"],
                "digest": baseline["digest"],
                "policy_sources": baselines[baseline_reference].get("_sources", []),
                "lineage": baseline["lineage"],
                "deviations": baseline["deviations"],
            })

            for instance in baseline["controls"].values():
                baseline_provenance = {
                    "group": group_id,
                    "assignment": assignment["id"],
                    "baseline": baseline_reference,
                }

                implementation = instance["implementation"]
                definition = controls.get(implementation)
                if definition is None:
                    resolution_errors.append({
                        "type": "unknown-control",
                        "baseline": baseline_reference,
                        "instance_id": instance["instance_id"],
                        "implementation": implementation,
                    })
                    continue
                spec = definition["spec"]

                if instance["disposition"] == "excluded":
                    excluded_candidate = {
                        "instance_id": instance["instance_id"],
                        "implementation": implementation,
                        "title": spec["title"],
                        "purpose": spec["purpose"],
                        "parameters": instance.get("parameters", {}),
                        "disposition": "excluded",
                        "policy_inputs": {
                            "instance": copy.deepcopy(instance),
                            "definition": pp.document(definition),
                            "parameters_schema": definition["_parameters_schema"],
                            "implementation_modules": definition.get(
                                "_implementation_modules", []
                            ),
                        },
                        "alignment": instance["alignment"],
                        "definition_fingerprint": instance["definition_fingerprint"],
                        "derivations": instance["derivations"],
                        "deviations": instance["deviations"],
                        "lineage": instance["lineage"],
                        "provenance": [baseline_provenance],
                        "implementation_sources": definition.get("_sources", []),
                    }
                    if "overlay_policy" in instance:
                        excluded_candidate["overlay_policy"] = instance["overlay_policy"]

                    existing_excluded = excluded_controls.get(instance["instance_id"])
                    if existing_excluded is None:
                        excluded_controls[instance["instance_id"]] = excluded_candidate
                    elif all(
                        existing_excluded[field] == excluded_candidate[field]
                        for field in (
                            "implementation",
                            "title",
                            "purpose",
                            "definition_fingerprint",
                        )
                    ):
                        existing_excluded["provenance"].extend(excluded_candidate["provenance"])
                        for field in ("lineage", "derivations", "deviations"):
                            for item in excluded_candidate[field]:
                                if item not in existing_excluded[field]:
                                    existing_excluded[field].append(copy.deepcopy(item))
                    else:
                        resolution_errors.append({
                            "type": "excluded-control-instance-conflict",
                            "instance_id": instance["instance_id"],
                        })
                    continue

                if subject["type"] not in spec.get("applies_to", []):
                    resolution_errors.append({
                        "type": "inapplicable-control",
                        "instance_id": instance["instance_id"],
                        "subject_type": subject["type"],
                    })
                    continue

                defaults = spec.get("defaults", {})
                candidate = {
                    "instance_id": instance["instance_id"],
                    "implementation": implementation,
                    "title": spec["title"],
                    "purpose": spec["purpose"],
                    "entrypoint": spec["entrypoint"],
                    "parameters": instance.get("parameters", {}),
                    "severity": instance.get("severity", defaults.get("severity", "medium")),
                    "remediation": instance.get("remediation", defaults.get("remediation", "")),
                    "evidence": pp.evidence_for(instance, definition),
                            "policy_inputs": {"instance": copy.deepcopy(instance), "definition": pp.document(definition), "parameters_schema": definition["_parameters_schema"], "implementation_modules": definition.get("_implementation_modules", [])},
                    "disposition": "evaluate",
                    "alignment": instance["alignment"],
                    "definition_fingerprint": instance["definition_fingerprint"],
                    "derivations": instance["derivations"],
                    "deviations": instance["deviations"],
                    "lineage": instance["lineage"],
                    "provenance": [baseline_provenance],
                    "implementation_sources": definition.get("_sources", []),
                }
                if "overlay_policy" in instance:
                    candidate["overlay_policy"] = instance["overlay_policy"]
                if "external_refs" in instance:
                    candidate["external_refs"] = instance["external_refs"]
                if "equivalence_ref" in instance:
                    candidate["equivalence_ref"] = instance["equivalence_ref"]

                instance_id = candidate["instance_id"]
                existing = rendered_controls.get(instance_id)
                if existing is None:
                    rendered_controls[instance_id] = candidate
                    continue

                comparable_keys = (
                    "implementation",
                    "title",
                    "purpose",
                    "parameters",
                    "severity",
                    "remediation",
                    "evidence",
                    "alignment",
                    "definition_fingerprint",
                )
                if all(
                    existing.get(key) == candidate.get(key)
                    for key in comparable_keys
                ):
                    existing["provenance"].extend(candidate["provenance"])
                    for field in ("lineage", "derivations", "deviations"):
                        for item in candidate[field]:
                            if item not in existing[field]:
                                existing[field].append(copy.deepcopy(item))
                else:
                    resolution_errors.append({
                        "type": "control-instance-conflict",
                        "instance_id": instance_id,
                        "existing": {key: existing.get(key) for key in comparable_keys},
                        "incoming": {key: candidate.get(key) for key in comparable_keys},
                        "incoming_provenance": candidate["provenance"],
                    })

    plan: JsonObject = {
        "schema": PLAN_SCHEMA,
        "digestAlgorithm": PLAN_DIGEST_ALGORITHM,
        "provenance": {"schema": PROVENANCE_SCHEMA, "planningComposition": stage(report)},
        "subject": subject,
        "resolved_groups": resolved_groups,
        "assignments": [{
            "id": assignment["id"],
            "group": assignment["target"]["group"],
            "baselines": assignment["baselines"],
        } for assignment in applicable_assignments],
        "resolved_baselines": sorted(
            resolved_baselines,
            key=lambda baseline: (baseline["assignment"], baseline["reference"]),
        ),
        "resolved_requirement_baselines": sorted(
            resolved_requirement_baselines,
            key=lambda baseline: (baseline["assignment"], baseline["reference"]),
        ),
        "requirements": sorted(
            rendered_requirements.values(),
            key=lambda requirement: requirement["reference"],
        ),
        "controls": sorted(rendered_controls.values(), key=lambda control: control["instance_id"]),
        "excluded_controls": sorted(excluded_controls.values(), key=lambda control: control["instance_id"]),
        "resolution": {
            "status": "valid" if not resolution_errors else "invalid",
            "errors": resolution_errors,
        },
    }
    from .operation import freeze_operation
    # A direct subject plan is an explicit singleton operation. Only this
    # subject's membership facts are needed; the catalog loader has already
    # checked supplied references before any subset is selected.
    projected_groups = copy.deepcopy(canonical_groups)
    for group in projected_groups:
        if 'members' in group:
            group['members'] = [s for s in group['members'] if s == subject['id']]
    freeze_operation([plan], {subject['id']: subject}, projected_groups,
                     canonical_assignments, {'subjects': [subject['id']], 'groups': [], 'all': False})
    validate_assessment_plan(plan)
    return plan
