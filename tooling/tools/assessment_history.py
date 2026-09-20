"""Validated, non-persisted context for one exact historical assessment operation.

This module consolidates only historical artifact admission and the existing
operation-accounting/current-qualification orchestration.  It is not a report
model, artifact family, store, or semantic owner: ``operation.py`` still owns
accounting and qualification, plans own policy meaning, and results own outcomes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .artifact_validation import validate_assessment_plan, validate_assessment_results
from .assessment_provenance import digest, validate_result_against_plan
from .operation import account_operation, qualify_operation
from .render_plan import load_json
from .waivers import parse_timestamp


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ValidatedHistoricalAssessmentContext:
    """Derived exact-history inputs after all available mandatory validation."""

    anchor: JsonObject
    assessed_plans: tuple[JsonObject, ...]
    reports: tuple[JsonObject, ...]
    assessment_instant: str
    query_instant: str
    comparison_anchor: JsonObject | None
    account: JsonObject

    @property
    def plans_by_id(self) -> dict[str, JsonObject]:
        return {plan["id"]: plan for plan in self.assessed_plans}

    @property
    def reports_by_id(self) -> dict[str, JsonObject]:
        return {report["id"]: report for report in self.reports}


def _canonical_instant(value: str, *, field: str) -> str:
    return parse_timestamp(value, field=field).isoformat().replace("+00:00", "Z")


def _unique_exact_documents(
    documents: Iterable[JsonObject],
    *,
    identity_field: str,
    label: str,
) -> list[JsonObject]:
    indexed: dict[str, JsonObject] = {}
    for source in documents:
        document = copy.deepcopy(source)
        identity = document.get(identity_field)
        if not isinstance(identity, str) or not identity:
            raise ValueError(f"{label} is missing its exact identity")
        existing = indexed.get(identity)
        if existing is not None and digest(existing) != digest(document):
            raise ValueError(
                f"multiple distinct {label} documents have the same exact identity"
            )
        indexed[identity] = document
    return [indexed[identity] for identity in sorted(indexed)]


def build_historical_assessment_context(
    anchor: JsonObject,
    assessed_plans: Iterable[JsonObject],
    reports: Iterable[JsonObject],
    *,
    assessment_instant: str,
    query_instant: str,
    comparison_anchor: JsonObject | None = None,
) -> ValidatedHistoricalAssessmentContext:
    """Admit exact retained history before any purpose-specific interpretation.

    Missing assessed plans remain representable: their results receive intrinsic
    validation but only result-owned facts may be projected.  Whenever an exact
    assessed plan is supplied, its result relation is mandatory even when that
    result does not fill a slot in the selected anchor operation.
    """

    anchor_copy = copy.deepcopy(anchor)
    validate_assessment_plan(anchor_copy)
    plans = _unique_exact_documents(
        [anchor_copy, *assessed_plans],
        identity_field="id",
        label="assessment plan",
    )
    for plan in plans:
        validate_assessment_plan(plan)

    admitted_reports = _unique_exact_documents(
        reports,
        identity_field="id",
        label="assessment result",
    )
    plans_by_id = {plan["id"]: plan for plan in plans}
    for report in admitted_reports:
        validate_assessment_results(report)
        assessed_plan = plans_by_id.get(report["plan_id"])
        if assessed_plan is not None:
            validate_result_against_plan(report, assessed_plan)

    comparison_copy = copy.deepcopy(comparison_anchor)
    if comparison_copy is not None:
        validate_assessment_plan(comparison_copy)

    assessed_at = _canonical_instant(
        assessment_instant, field="assessment instant"
    )
    queried_at = _canonical_instant(query_instant, field="query instant")
    account = account_operation(anchor_copy, admitted_reports, assessed_at, plans)
    qualify_operation(
        account,
        admitted_reports,
        parse_timestamp(queried_at, field="query instant"),
        comparison_copy,
        plans,
    )
    return ValidatedHistoricalAssessmentContext(
        anchor=anchor_copy,
        assessed_plans=tuple(plans),
        reports=tuple(admitted_reports),
        assessment_instant=assessed_at,
        query_instant=queried_at,
        comparison_anchor=comparison_copy,
        account=account,
    )


def load_assessment_plans(paths: Iterable[Path]) -> list[JsonObject]:
    """Load explicitly supplied v4 plans, indexed only by exact plan identity."""

    plans: list[JsonObject] = []
    for path in paths:
        if not path.exists():
            raise ValueError(f"assessment plan input does not exist: {path}")
        candidates = [path] if path.is_file() else sorted(path.rglob("*.json"))
        found = False
        for candidate in candidates:
            document = load_json(candidate)
            if not isinstance(document, dict) or document.get("schema") != (
                "compliance.example/assessment-plan/v4"
            ):
                if path.is_file():
                    raise ValueError(f"assessment plan input is not a v4 plan: {path}")
                continue
            found = True
            validate_assessment_plan(document, source=candidate)
            plans.append(document)
        if path.is_dir() and not found:
            raise ValueError(f"assessment plan directory contains no v4 plans: {path}")
    return _unique_exact_documents(
        plans, identity_field="id", label="assessment plan"
    )


def load_result_reports(path: Path | None) -> list[JsonObject]:
    """Load explicitly supplied intrinsically valid result envelopes."""

    if path is None:
        return []
    if not path.exists():
        raise ValueError(f"results path does not exist: {path}")
    paths = [path] if path.is_file() else sorted(path.rglob("*.json"))
    reports: list[JsonObject] = []
    for candidate in paths:
        document = load_json(candidate)
        if isinstance(document, dict) and str(document.get("schema", "")).startswith(
            "compliance.example/assessment-results/"
        ):
            validate_assessment_results(document, source=candidate)
            reports.append(document)
    return _unique_exact_documents(
        reports, identity_field="id", label="assessment result"
    )


def load_historical_assessment_context(
    anchor_path: Path,
    assessed_plan_paths: Iterable[Path],
    results_path: Path | None,
    *,
    assessment_instant: str,
    query_instant: str,
    comparison_anchor_path: Path | None = None,
) -> ValidatedHistoricalAssessmentContext:
    """Load and validate one explicit historical query from filesystem inputs."""

    anchor = load_json(anchor_path)
    validate_assessment_plan(anchor, source=anchor_path)
    plans = load_assessment_plans([anchor_path, *assessed_plan_paths])
    reports = load_result_reports(results_path)
    comparison = None
    if comparison_anchor_path is not None:
        comparison = load_json(comparison_anchor_path)
        validate_assessment_plan(comparison, source=comparison_anchor_path)
    return build_historical_assessment_context(
        anchor,
        plans,
        reports,
        assessment_instant=assessment_instant,
        query_instant=query_instant,
        comparison_anchor=comparison,
    )
