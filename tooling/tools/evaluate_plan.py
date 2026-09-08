"""Internal assessment-plan evaluation implementation."""

from __future__ import annotations

import copy

import json
import re
import os
import tempfile
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema import FormatChecker

from .artifact_validation import (
    validate_assessment_plan,
    validate_assessment_results,
)
from .control_realization import compact_plan_outcomes
from .policy_sources import PolicySources, rego_module_paths
from .render_plan import load_evidence_schema_catalog
from .waivers import active_waiver, load_waivers


JsonObject = dict[str, Any]
DURATION_PATTERN = re.compile(r"^(?P<amount>[0-9]+)(?P<unit>[smhd])$")
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
EVIDENCE_FORMAT_CHECKER = FormatChecker()

EVALUATION_ERRORS = {
    'criterion_execution_failed': (
        'criterion_execution', 'Criterion execution failed.'
    ),
    'criterion_decision_invalid': (
        'criterion_decision', 'Criterion decision was unusable.'
    ),
    'criterion_reported_error': (
        'criterion_decision', 'Criterion reported an evaluation error.'
    ),
}


class CriterionExecutionFailure(RuntimeError):
    """The resolved evaluator failed while invoking a criterion."""


class CriterionDecisionFailure(ValueError):
    """The evaluator returned a decision that cannot be accepted."""


@EVIDENCE_FORMAT_CHECKER.checks("date-time")
def _is_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str):
        return True
    if RFC3339_PATTERN.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def parse_duration(value: str) -> timedelta:
    match = DURATION_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(f"unsupported duration: {value}")
    amount = int(match.group("amount"))
    unit = match.group("unit")
    return {
        "s": timedelta(seconds=amount),
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
    }[unit]


def _json_pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else ""


def control_error_result(
    assessment_input: JsonObject,
    reason: str,
    *,
    observed: JsonObject | None = None,
) -> JsonObject:
    """Return the common immutable error shape without invoking Rego."""
    return {
        "control_id": assessment_input["control"]["implementation"],
        "instance_id": assessment_input["control"]["instance_id"],
        "subject_id": assessment_input["subject"]["id"],
        "plan_id": assessment_input["assessment"]["plan_id"],
        "status": "error",
        "reason": reason,
        "severity": assessment_input["control"]["severity"],
        "remediation": assessment_input["control"]["remediation"],
        "expected": {},
        "observed": observed or {},
        "external_refs": assessment_input["control"].get("external_refs", []),
        "alignment": assessment_input["control"].get("alignment", "unmapped"),
    }


def _classified_error_result(
    assessment_input: JsonObject,
    code: str,
) -> JsonObject:
    stage_name, reason = EVALUATION_ERRORS[code]
    result = _compact_result_fields(control_error_result(assessment_input, reason))
    result['evaluation_error'] = {'stage': stage_name, 'code': code}
    return result


def _compact_evaluator_decision(
    decision: JsonObject,
    assessment_input: JsonObject,
) -> JsonObject:
    """Validate the evaluator boundary and retain only evaluation-owned facts."""
    expected = control_error_result(assessment_input, "placeholder")
    required = set(expected)
    if set(decision) != required:
        raise ValueError("evaluator decision fields are invalid")
    for field in (
        "control_id", "instance_id", "subject_id", "plan_id", "severity",
        "remediation", "external_refs", "alignment",
    ):
        if decision[field] != expected[field]:
            raise ValueError(f"evaluator decision {field} differs from assessed plan")
    if decision["status"] not in {"pass", "fail", "unknown", "not_applicable", "error"}:
        raise ValueError("evaluator decision status is invalid")
    if not isinstance(decision["reason"], str) or not decision["reason"]:
        raise ValueError("evaluator decision reason is invalid")
    if not isinstance(decision["expected"], dict) or not isinstance(decision["observed"], dict):
        raise ValueError("evaluator decision expected/observed values must be objects")
    if any(key in decision["observed"] for key in (
        "evidence_validation_errors", "evidence_selection_ambiguities"
    )):
        raise ValueError("evaluator cannot originate orchestration diagnostics")
    from ._canonical_json import canonical_json_bytes
    canonical_json_bytes(decision)
    return _compact_result_fields(decision)


def _compact_result_fields(decision: JsonObject) -> JsonObject:
    return {
        "instance_id": decision["instance_id"],
        "status": decision["status"],
        "reason": decision["reason"],
        "expected": copy.deepcopy(decision["expected"]),
        "observed": copy.deepcopy(decision["observed"]),
    }


def _technical_control_input(control: JsonObject) -> JsonObject:
    """Keep source-authored check prose outside the executable OPA input."""
    projected = copy.deepcopy(control)
    projected.pop("title", None)
    projected.pop("purpose", None)
    definition = projected.get("policy_inputs", {}).get("definition")
    if isinstance(definition, dict):
        spec = definition.get("spec")
        if isinstance(spec, dict):
            spec.pop("title", None)
            spec.pop("purpose", None)
    return projected


def evaluate_control(
    opa: str,
    policy_sources: PolicySources,
    assessment_input: JsonObject,
    entrypoint: str,
) -> JsonObject:
    modules = rego_module_paths(policy_sources, include_tests=False)
    data_arguments = [argument for path in modules for argument in ("--data", str(path))]
    process = subprocess.run(
        [opa, "eval", "--format=raw", *data_arguments, "--stdin-input", entrypoint],
        input=json.dumps(assessment_input),
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise CriterionExecutionFailure('criterion process failed')
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise CriterionDecisionFailure('criterion returned non-JSON output') from error
def evaluate_plan_document(
    plan: JsonObject,
    evidence_path: Path,
    policies: PolicySources,
    *,
    opa: str = "opa",
    evaluated_at: datetime | None = None,
    waiver_path: Path | None = None,
    composition_report: JsonObject | None = None,
) -> JsonObject:
    """Evaluate an already rendered plan and return its immutable result envelope."""
    validate_assessment_plan(plan)
    from .assessment_provenance import (
        RESULTS_DIGEST_ALGORITHM, RESULTS_SCHEMA, artifact_digest, stage,
        validate_result_against_plan, validate_selection_snapshot,
    )
    from .composition import require_composition
    from .evaluator import resolve_opa_evaluator
    from .evidence_selection import snapshot_evidence, prepare_schemas, select_evidence
    evaluation = composition_report or require_composition(policies)
    planning = plan['provenance']['planningComposition']
    if evaluation['actual']['policySources'] != planning['actual']['policySources']:
        raise ValueError('evaluation policy composition differs from planning composition')
    lock = evaluation['enforcement']['compositionLock']
    if lock is not None and planning['actual'] != lock['expected']:
        raise ValueError('planning composition differs from selected evaluation lock')
    evaluator, opa = resolve_opa_evaluator(opa)
    if plan["resolution"]["status"] != "valid":
        raise SystemExit("refusing to evaluate an invalid assessment plan")
    from .operation import plan_disposition
    disposition = plan_disposition(plan)
    if disposition != 'result_required':
        raise SystemExit(f"refusing to evaluate assessment plan: {disposition}")

    if not evidence_path.is_dir():
        raise SystemExit(f"evidence path is not a directory: {evidence_path}")
    evidence, evidence_descriptor = snapshot_evidence(evidence_path, plan['subject']['id'])

    required_evidence_types = {
        requirement["type"]
        for control in plan["controls"]
        for requirement in control.get("evidence", [])
    }
    evidence_schemas: dict[str, JsonObject] = {}
    if required_evidence_types:
        evidence_schemas, evidence_schema_errors = load_evidence_schema_catalog(policies)
        if evidence_schema_errors:
            raise SystemExit(
                "refusing to evaluate assessment plan: evidence schema catalog is "
                f"invalid: {json.dumps(evidence_schema_errors, sort_keys=True)}"
            )

    validators, schema_references = prepare_schemas(evidence_schemas, required_evidence_types)
    selected_uses = []
    dependency_dispositions = []
    evaluated_at = (evaluated_at or datetime.now(UTC)).replace(microsecond=0)
    if evaluated_at.utcoffset() is None:
        raise ValueError('assessment time must have an explicit timezone')
    waivers, _ = load_waivers(waiver_path)
    results = []
    for control in plan["controls"]:
        waiver = active_waiver(
            waivers,
            plan["subject"]["id"],
            control["instance_id"],
            evaluated_at,
        )
        evidence_requirements = control.get("evidence", [])
        selected_evidence, uses, dispositions = select_evidence(
            evidence, evidence_requirements, evaluated_at, plan['subject']['id'],
            validators, schema_references,
        )
        selected_uses.extend({'instance_id': control['instance_id'], **use} for use in uses)
        dependency_dispositions.extend(
            {'instance_id': control['instance_id'], **item}
            for item in dispositions
        )
        assessment_input = {
            "schema": "compliance.example/assessment-input/v1",
            "assessment": {
                "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
                "plan_id": plan["id"],
            },
            "subject": plan["subject"],
            "control": _technical_control_input(control),
            "evidence": selected_evidence,
            # Waivers must not influence the technical decision produced by Rego.
            "waiver": None,
        }
        selected_dependencies = {use['dependency_id'] for use in uses}
        if (dispositions or any(
                requirement['id'] not in selected_dependencies
                for requirement in evidence_requirements)):
            disposition_names = {item['disposition'] for item in dispositions}
            if 'invalid' in disposition_names:
                reason = 'Required evidence was rejected as invalid; criterion not determined.'
            elif 'ambiguous' in disposition_names:
                reason = 'Required evidence selection is ambiguous; criterion not determined.'
            else:
                reason = 'Required evidence is missing or stale; criterion not determined.'
            result = _compact_result_fields(
                control_error_result(assessment_input, reason)
            )
            result['status'] = 'unknown'
        else:
            try:
                decision = evaluate_control(
                    opa, policies, assessment_input, control["entrypoint"]
                )
            except CriterionDecisionFailure:
                result = _classified_error_result(
                    assessment_input, 'criterion_decision_invalid'
                )
            except Exception:
                result = _classified_error_result(
                    assessment_input, 'criterion_execution_failed'
                )
            else:
                try:
                    result = _compact_evaluator_decision(decision, assessment_input)
                except Exception:
                    result = _classified_error_result(
                        assessment_input, 'criterion_decision_invalid'
                    )
                else:
                    if result['status'] == 'error':
                        result = _classified_error_result(
                            assessment_input, 'criterion_reported_error'
                        )
        if waiver is not None and result.get("status") == "fail":
            result["status"] = "waived"
            result["waiver"] = {**waiver, "underlying_status": "fail"}
        results.append(result)

    results.sort(key=lambda item: item["instance_id"])
    requirement_assessments, requirement_baseline_assessments = (
        compact_plan_outcomes(plan, results)
    )

    report = {
        "schema": RESULTS_SCHEMA,
        "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
        "plan_id": plan["id"],
        "subject_id": plan["subject"]["id"],
        "dependency_dispositions": sorted(
            dependency_dispositions,
            key=lambda item: (item['instance_id'], item['dependency_id']),
        ),
        "results": results,
        "requirement_assessments": requirement_assessments,
        "requirement_baseline_assessments": requirement_baseline_assessments,
    }
    report['digestAlgorithm'] = RESULTS_DIGEST_ALGORITHM
    report['provenance'] = {
        'schema': 'compliance.example/assessment-provenance/v1alpha1',
        'evaluationComposition': stage(evaluation),
        'evaluator': evaluator.document(), 'evidence': evidence_descriptor,
        'selectedEvidence': sorted(selected_uses, key=lambda item: (item['instance_id'], item['dependency_id'])),
    }
    from .artifact_validation import result_outcome
    report['outcome'] = result_outcome(report)
    report['id'] = artifact_digest(report)
    validate_assessment_results(report)
    validate_result_against_plan(report, plan)
    validate_selection_snapshot(
        report, evidence, plan=plan, validators=validators,
        schema_references=schema_references,
    )
    return report


def write_json(document: JsonObject, output: Path, *, plan: JsonObject | None = None) -> None:
    if document.get("schema") in {"compliance.example/assessment-plan/v4"}:
        validate_assessment_plan(document, source=output)
    elif document.get("schema") in {"compliance.example/assessment-results/v4"}:
        validate_assessment_results(document, source=output)
        if plan is None:
            raise ValueError("publishing assessment results requires the exact assessed plan")
        from .assessment_provenance import validate_result_against_plan
        validate_result_against_plan(document, plan)
    elif str(document.get("schema", "")).startswith(("compliance.example/assessment-plan/", "compliance.example/assessment-results/")):
        raise ValueError("unsupported assessment artifact schema")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Encode before opening any output, then atomically publish a complete envelope.
    encoded = json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
