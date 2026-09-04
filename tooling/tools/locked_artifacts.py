"""Content-addressed generated-artifact runtime for locked downstream projects.

The planner and evaluator remain the v1 semantic implementation.
Content-addressed release-lock/v1alpha2 projects use v3 envelopes while projecting
through the unchanged closed v1 semantic contracts for validation and execution.
"""

from __future__ import annotations

import copy
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from jsonschema import Draft202012Validator

from .artifact_provenance import (
    ArtifactProvenanceError,
    ContentArtifactProvenance,
    locked_artifact_provenance,
    require_artifact_provenance,
)
from .evaluator import resolve_opa_evaluator
from .evidence_provenance import evidence_set_provenance
from .project_config import ProjectConfig
from .render_plan import content_digest, load_json


JsonObject = dict[str, Any]
ASSESSMENT_PLAN_V1 = "compliance.example/assessment-plan/v1"
ASSESSMENT_PLAN_V3 = "compliance.example/assessment-plan/v3"
ASSESSMENT_RESULTS_V1 = "compliance.example/assessment-results/v1"
ASSESSMENT_RESULTS_V3 = "compliance.example/assessment-results/v3"


def _schemas_root() -> Path:
    return Path(__file__).resolve().parent / "schemas"


def _validate_overlay(document: JsonObject, filename: str, label: str) -> None:
    schema = json.loads((_schemas_root() / filename).read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )
    if errors:
        rendered = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in errors
        )
        raise ValueError(f"{label} locked provenance validation failed: {rendered}")


def _without_provenance(document: JsonObject, schema: str) -> JsonObject:
    projected = copy.deepcopy(document)
    projected.pop("generator", None)
    projected.pop("release_lock_digest", None)
    projected.pop("evaluator", None)
    projected.pop("evidence", None)
    projected["schema"] = schema
    return projected


def _content_id(document: JsonObject) -> str:
    return content_digest({key: value for key, value in document.items() if key != "id"})


def _project_plan_v1(document: JsonObject) -> JsonObject:
    projected = _without_provenance(document, ASSESSMENT_PLAN_V1)
    projected["id"] = _content_id(projected)
    return projected


def _require_content_provenance(
    document: JsonObject,
    *,
    label: str,
) -> ContentArtifactProvenance:
    provenance = require_artifact_provenance(document, None, label=label)
    return provenance


def validate_assessment_plan_any(
    document: JsonObject,
    *,
    source: Path | None = None,
    base_validator: Callable[..., None] | None = None,
) -> None:
    from .artifact_validation import validate_assessment_plan as default_validator

    validator = base_validator or default_validator
    schema = document.get("schema")
    if schema == ASSESSMENT_PLAN_V1:
        validator(document, source=source)
        return
    if schema != ASSESSMENT_PLAN_V3:
        raise ValueError(f"unsupported assessment plan schema: {schema!r}")
    _require_content_provenance(document, label="assessment plan")
    validator(_project_plan_v1(document), source=source)
    _validate_overlay(document, "assessment-plan-v3.schema.json", "assessment plan")
    expected = _content_id(document)
    if document.get("id") != expected:
        raise ValueError(
            f"assessment plan v3 content digest is {expected}, got {document.get('id')}"
        )


def validate_assessment_results_any(
    document: JsonObject,
    *,
    source: Path | None = None,
    base_validator: Callable[..., None] | None = None,
) -> None:
    from .artifact_validation import validate_assessment_results as default_validator

    validator = base_validator or default_validator
    schema = document.get("schema")
    if schema == ASSESSMENT_RESULTS_V1:
        validator(document, source=source)
        return
    if schema != ASSESSMENT_RESULTS_V3:
        raise ValueError(f"unsupported assessment results schema: {schema!r}")
    _require_content_provenance(document, label="assessment results")
    validator(_without_provenance(document, ASSESSMENT_RESULTS_V1), source=source)
    _validate_overlay(document, "assessment-results-v3.schema.json", "assessment results")


def render_plan_locked(
    base_render: Callable[..., JsonObject],
    provenance: ContentArtifactProvenance,
    *args: Any,
    **kwargs: Any,
) -> JsonObject:
    plan = copy.deepcopy(base_render(*args, **kwargs))
    plan["schema"] = ASSESSMENT_PLAN_V3
    plan.update(provenance.fields())
    plan["id"] = _content_id(plan)
    validate_assessment_plan_any(plan)
    return plan


def render_plan_v3(
    base_render: Callable[..., JsonObject],
    provenance: ContentArtifactProvenance,
    *args: Any,
    **kwargs: Any,
) -> JsonObject:
    return render_plan_locked(base_render, provenance, *args, **kwargs)


def _rewrite_assessment_plan_identity(
    report: JsonObject,
    projected: JsonObject,
    plan: JsonObject,
) -> None:
    old_short = projected["id"].removeprefix("sha256:")[:16]
    new_short = plan["id"].removeprefix("sha256:")[:16]
    if isinstance(report.get("assessment_id"), str):
        report["assessment_id"] = report["assessment_id"].replace(old_short, new_short, 1)
    report["plan_id"] = plan["id"]
    for result in report.get("results", []):
        result["plan_id"] = plan["id"]


def _v3_evidence_snapshot(
    evidence_path: Path,
    subject_id: str,
) -> tuple[tempfile.TemporaryDirectory[str], Path, dict[str, Any]]:
    """Snapshot the exact evidence files that the v1 evaluator will read."""
    if not evidence_path.is_dir():
        raise SystemExit(f"evidence path is not a directory: {evidence_path}")
    temporary = tempfile.TemporaryDirectory(prefix="compliance-evidence-snapshot-")
    snapshot = Path(temporary.name) / "evidence"
    snapshot.mkdir()
    try:
        for source in sorted(evidence_path.glob("*.json")):
            (snapshot / source.name).write_bytes(source.read_bytes())
        from .evaluate_plan import evidence_for_subject, load_evidence_documents

        loaded, _ = load_evidence_documents(snapshot)
        descriptor = evidence_set_provenance(evidence_for_subject(loaded, subject_id))
    except Exception:
        temporary.cleanup()
        raise
    return temporary, snapshot, descriptor


def evaluate_plan_locked(
    base_evaluate: Callable[..., JsonObject],
    provenance: ContentArtifactProvenance,
    plan: JsonObject,
    *args: Any,
    **kwargs: Any,
) -> JsonObject:
    validate_assessment_plan_any(plan)
    require_artifact_provenance(plan, provenance, label="assessment plan")
    projected = _project_plan_v1(plan)
    evaluation_kwargs = dict(kwargs)
    evaluator_document: dict[str, str] | None = None
    evidence_document: dict[str, Any] | None = None
    evaluation_args = args
    evidence_snapshot: tempfile.TemporaryDirectory[str] | None = None
    try:
        requested_opa = str(evaluation_kwargs.get("opa", "opa"))
        evaluator, resolved_opa = resolve_opa_evaluator(requested_opa)
        evaluation_kwargs["opa"] = resolved_opa
        evaluator_document = evaluator.document()

        if evaluation_args:
            original_evidence = Path(evaluation_args[0])
            evidence_snapshot, snapshot_path, evidence_document = _v3_evidence_snapshot(
                original_evidence,
                plan["subject"]["id"],
            )
            evaluation_args = (snapshot_path, *evaluation_args[1:])
        elif "evidence_path" in evaluation_kwargs:
            original_evidence = Path(evaluation_kwargs["evidence_path"])
            evidence_snapshot, snapshot_path, evidence_document = _v3_evidence_snapshot(
                original_evidence,
                plan["subject"]["id"],
            )
            evaluation_kwargs["evidence_path"] = snapshot_path
        else:
            raise ArtifactProvenanceError(
                "v3 assessment execution requires an evidence directory to bind"
            )

        report = copy.deepcopy(
            base_evaluate(projected, *evaluation_args, **evaluation_kwargs)
        )
    finally:
        if evidence_snapshot is not None:
            evidence_snapshot.cleanup()

    _rewrite_assessment_plan_identity(report, projected, plan)
    report["schema"] = ASSESSMENT_RESULTS_V3
    report.update(provenance.fields())
    if evaluator_document is not None:
        report["evaluator"] = evaluator_document
    if evidence_document is not None:
        report["evidence"] = evidence_document
    validate_assessment_results_any(report)
    return report


def evaluate_plan_v3(
    base_evaluate: Callable[..., JsonObject],
    provenance: ContentArtifactProvenance,
    plan: JsonObject,
    *args: Any,
    **kwargs: Any,
) -> JsonObject:
    return evaluate_plan_locked(base_evaluate, provenance, plan, *args, **kwargs)


def load_result_reports_any(
    path: Path | None,
    *,
    base_validator: Callable[..., None],
) -> list[JsonObject]:
    if path is None:
        return []
    if not path.exists():
        raise ValueError(f"results path does not exist: {path}")
    paths = [path] if path.is_file() else sorted(path.rglob("*.json"))
    reports: list[JsonObject] = []
    for candidate in paths:
        document = load_json(candidate)
        if isinstance(document, dict) and document.get("schema") in {
            ASSESSMENT_RESULTS_V1,
            ASSESSMENT_RESULTS_V3,
        }:
            validate_assessment_results_any(
                document,
                source=candidate,
                base_validator=base_validator,
            )
            reports.append(document)
    return reports


def load_policy_plan_set_any(
    root: Path,
    *,
    base_validator: Callable[..., None],
) -> dict[str, tuple[Path, JsonObject]]:
    if not root.is_dir():
        raise ValueError(f"policy diff set directory does not exist: {root}")
    candidates = sorted(root.rglob("*.json"))
    if not candidates:
        raise ValueError(f"policy diff set contains no JSON plans: {root}")
    plans: dict[str, tuple[Path, JsonObject]] = {}
    for path in candidates:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("schema") not in {
            ASSESSMENT_PLAN_V1,
            ASSESSMENT_PLAN_V3,
        }:
            raise ValueError(f"not an assessment plan in policy diff set: {path}")
        validate_assessment_plan_any(
            document,
            source=path,
            base_validator=base_validator,
        )
        subject_id = document["subject"]["id"]
        if subject_id in plans:
            previous = plans[subject_id][0]
            raise ValueError(
                f"duplicate subject plan {subject_id!r} in {root}: {previous} and {path}"
            )
        plans[subject_id] = (path, document)
    return plans


def _locked_plan_show(args: Any, compliance_module: Any) -> None:
    plan_path = compliance_module._resolve_plan_show_path(
        args.plan,
        args.project_config.path("plan"),
    )
    if plan_path.is_dir():
        plans: list[tuple[Path, JsonObject]] = []
        for candidate in sorted(plan_path.rglob("*.json")):
            document = load_json(candidate)
            if document.get("schema") in {
                ASSESSMENT_PLAN_V1,
                ASSESSMENT_PLAN_V3,
            }:
                validate_assessment_plan_any(document, source=candidate)
                plans.append((candidate, document))
        if not plans:
            raise ValueError(f"plan directory contains no assessment plans: {plan_path}")
        if len(plans) == 1:
            _, plan = plans[0]
        else:
            entries = [
                compliance_module._plan_index_entry(plan, path)
                for path, plan in plans
            ]
            if args.format == "json":
                print(json.dumps({
                    "schema": "compliance.example/assessment-plan-index/v1alpha1",
                    "plans": entries,
                }, indent=2, sort_keys=True))
            else:
                print(compliance_module._format_plan_index(entries))
            return
    else:
        plan = load_json(plan_path)
        validate_assessment_plan_any(plan, source=plan_path)
    if args.format == "json":
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(compliance_module._format_plan_summary(plan))


def _patch(
    module: Any,
    name: str,
    replacement: Any,
    originals: list[tuple[Any, str, Any]],
) -> None:
    originals.append((module, name, getattr(module, name)))
    setattr(module, name, replacement)


@contextmanager
def locked_artifact_runtime(config: ProjectConfig) -> Iterator[None]:
    """Temporarily install version-appropriate wrappers for one locked CLI invocation."""
    if not config.is_locked:
        yield
        return

    provenance = locked_artifact_provenance(config)

    from . import artifact_validation as artifact_validation_module
    from . import assessment as assessment_module
    from . import compliance as compliance_module
    from . import policy_diff as policy_diff_module
    from .evaluate_plan import evaluate_plan_document as base_evaluate_plan
    from .render_plan import render_plan as base_render_plan

    base_validate_plan = artifact_validation_module.validate_assessment_plan
    base_validate_results = artifact_validation_module.validate_assessment_results

    def render_locked(*args: Any, **kwargs: Any) -> JsonObject:
        return render_plan_locked(base_render_plan, provenance, *args, **kwargs)

    def evaluate_locked(plan: JsonObject, *args: Any, **kwargs: Any) -> JsonObject:
        return evaluate_plan_locked(base_evaluate_plan, provenance, plan, *args, **kwargs)

    def validate_plan_locked(
        document: JsonObject,
        *,
        source: Path | None = None,
    ) -> None:
        validate_assessment_plan_any(
            document,
            source=source,
            base_validator=base_validate_plan,
        )

    def validate_results_locked(
        document: JsonObject,
        *,
        source: Path | None = None,
    ) -> None:
        validate_assessment_results_any(
            document,
            source=source,
            base_validator=base_validate_results,
        )

    def load_results_locked(path: Path | None) -> list[JsonObject]:
        return load_result_reports_any(path, base_validator=base_validate_results)

    def load_plan_set_locked(root: Path) -> dict[str, tuple[Path, JsonObject]]:
        return load_policy_plan_set_any(root, base_validator=base_validate_plan)

    originals: list[tuple[Any, str, Any]] = []
    try:
        for module in (compliance_module, assessment_module):
            _patch(module, "render_plan", render_locked, originals)
        _patch(compliance_module, "evaluate_plan_document", evaluate_locked, originals)
        _patch(compliance_module, "validate_assessment_plan", validate_plan_locked, originals)
        _patch(policy_diff_module, "validate_assessment_plan", validate_plan_locked, originals)
        _patch(assessment_module, "validate_assessment_results", validate_results_locked, originals)
        _patch(compliance_module, "load_result_reports", load_results_locked, originals)
        _patch(policy_diff_module, "load_policy_plan_set", load_plan_set_locked, originals)
        _patch(
            compliance_module,
            "_run_plan_show",
            lambda args: _locked_plan_show(args, compliance_module),
            originals,
        )
        yield
    finally:
        for module, name, original in reversed(originals):
            setattr(module, name, original)
