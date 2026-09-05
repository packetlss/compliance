"""ADR 0007 actual composition and separate, complete expected enforcement."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from ._canonical_json import canonical_json_bytes
from .policy_sources import PolicySource, normalize_policy_sources, source_tree_digest
from .tooling_identity import actual_tooling_identity

COMPOSITION_DIGEST_ALGORITHM = "compliance.example/composition-digest/v1alpha1"
COMPOSITION_LOCK_SCHEMA = "compliance.example/composition-lock/v1alpha1"
COMPOSITION_LOCK_DIGEST_ALGORITHM = "compliance.example/composition-lock-digest/v1alpha1"
POLICY_SOURCE_DIGEST_ALGORITHM = "compliance.example/policy-source-tree-digest/v1alpha1"
COMPOSITION_LOCK_FILENAME = "compliance.lock.yaml"


class CompositionError(ValueError):
    """Configuration/provenance failure, never an assessment outcome."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject ambiguous YAML maps instead of silently selecting the last value."""


def _unique_mapping(loader: UniqueKeyLoader, node: Any, deep: bool = False) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            if key in result:
                raise CompositionError(f"duplicate YAML key: {key!r}")
            result[key] = loader.construct_object(value_node, deep=deep)
        except TypeError as error:
            raise CompositionError("YAML mapping keys must be scalar") from error
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def validate_document(document: Any, filename: str) -> None:
    schema = json.loads((Path(__file__).parent / "schemas" / filename).read_text())
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda e: str(e.path))
    if errors:
        raise CompositionError("; ".join(f"{list(e.path)}: {e.message}" for e in errors))


def composition_projection(document: dict) -> dict:
    """Normalize name-keyed content and explicitly exclude all descriptive metadata."""
    tooling = document["tooling"]
    execution = {"kind": tooling["execution"]["kind"]}
    if execution["kind"] == "installed-wheel":
        execution["wheelSha256"] = tooling["execution"]["wheelSha256"]
    result = {
        "tooling": {
            "source": {key: tooling["source"][key] for key in ("digestAlgorithm", "digest")},
            "execution": execution,
        },
        "policySources": [
            {"name": item["name"], "content": {
                key: item["content"][key] for key in ("digestAlgorithm", "digest")
            }}
            for item in sorted(document["policySources"], key=lambda item: item["name"])
        ],
    }
    validate_document(result, "composition.schema.json")
    names = [item["name"] for item in result["policySources"]]
    if len(names) != len(set(names)):
        raise CompositionError("duplicate policy source names")
    return result


def _digest(document: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(document)).hexdigest()


def composition_digest(document: dict) -> str:
    return _digest(composition_projection(document))


@dataclass(frozen=True)
class CompositionLock:
    source: Path
    expected: dict

    def semantic_document(self) -> dict:
        return {"schema": COMPOSITION_LOCK_SCHEMA, "expected": composition_projection(self.expected)}

    def digest(self) -> str:
        return _digest(self.semantic_document())


def load_composition_lock(source: Path) -> CompositionLock:
    try:
        documents = list(yaml.load_all(source.read_text(), Loader=UniqueKeyLoader))
    except (OSError, yaml.YAMLError) as error:
        raise CompositionError(f"cannot read composition lock {source}: {error}") from error
    if len(documents) != 1:
        raise CompositionError("composition lock requires exactly one YAML document")
    document = documents[0]
    validate_document(document, "composition-lock-v1alpha1.schema.json")
    expected = document["expected"]
    normalized = composition_projection({
        "tooling": expected["tooling"],
        "policySources": [{"name": name, **value} for name, value in expected["policySources"].items()],
    })
    return CompositionLock(source.resolve(), normalized)


def observe_composition(sources: tuple[PolicySource, ...]) -> dict:
    """Reobserve every actual input on each call; never accept expected tooling."""
    try:
        tooling = actual_tooling_identity()
        policy = [{"name": source.name, "content": {
            "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
            "digest": source_tree_digest(source.path),
        }} for source in normalize_policy_sources(sources)]
        return composition_projection({"tooling": tooling, "policySources": policy})
    except (OSError, ValueError, RuntimeError) as error:
        raise CompositionError(f"actual composition unavailable: {error}") from error


def validate_composition(
    sources: tuple[PolicySource, ...],
    *,
    direct: dict[str, dict] | None = None,
    lock: CompositionLock | None = None,
) -> dict:
    """Observe first, then compare independent expectations; diagnostics do not persist artifacts."""
    actual = observe_composition(sources)
    direct = direct or {}
    actual_by_name = {item["name"]: item["content"] for item in actual["policySources"]}
    expected_by_name = {item["name"]: item["content"] for item in lock.expected["policySources"]} if lock else {}
    errors = []
    for name, content in sorted(direct.items()):
        if actual_by_name.get(name) != content:
            errors.append(f"direct expected content mismatch: {name}")
        if lock and expected_by_name.get(name) != content:
            errors.append(f"direct and composition-lock expectations disagree: {name}")
    if lock and actual != lock.expected:
        errors.append("composition-lock mismatch: exact tooling execution and named source content set required")
    return {
        "actual": actual,
        "compositionDigestAlgorithm": COMPOSITION_DIGEST_ALGORITHM,
        "compositionDigest": composition_digest(actual),
        "enforcement": {
            "directExpectedContent": direct,
            "compositionLock": ({
                "expected": lock.expected,
                "digestAlgorithm": COMPOSITION_LOCK_DIGEST_ALGORITHM,
                "digest": lock.digest(),
            } if lock else None),
        },
        "valid": not errors,
        "errors": errors,
    }


def require_composition(sources: tuple[PolicySource, ...], **kwargs: Any) -> dict:
    report = validate_composition(sources, **kwargs)
    if not report["valid"]:
        raise CompositionError("; ".join(report["errors"]))
    return report
