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

from jsonschema import Draft202012Validator, FormatChecker

from .artifact_validation import (
    validate_assessment_plan,
    validate_assessment_results,
)
from .control_realization import roll_up_plan_requirements
from .policy_sources import PolicySources, rego_module_paths
from .render_plan import load_evidence_schema_catalog
from .waivers import active_waiver, load_waivers


JsonObject = dict[str, Any]
DURATION_PATTERN = re.compile(r"^(?P<amount>[0-9]+)(?P<unit>[smhd])$")
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
EVIDENCE_FORMAT_CHECKER = FormatChecker()


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
    evidence_ids: list[str] | None = None,
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
        "evidence_ids": evidence_ids if evidence_ids is not None else list(dict.fromkeys(
            document["id"]
            for document in assessment_input["evidence"]
            if isinstance(document.get("id"), str)
        )),
    }


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
        return control_error_result(
            assessment_input,
            process.stderr.strip() or "OPA evaluation failed",
        )
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError:
        return control_error_result(
            assessment_input,
            "OPA returned an undefined or non-JSON result",
        )
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
    from .assessment_provenance import stage, artifact_digest, RESULTS_SCHEMA, RESULTS_DIGEST_ALGORITHM, validate_selection_plan, validate_selection_snapshot
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
    evidence, evidence_sources, evidence_descriptor = snapshot_evidence(evidence_path, plan['subject']['id'])

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
    evaluated_at = (evaluated_at or datetime.now(UTC)).replace(microsecond=0)
    if evaluated_at.utcoffset() is None:
        raise ValueError('assessment time must have an explicit timezone')
    waivers, waiver_revision = load_waivers(waiver_path)
    technical_assessment_id = (
        f'assessment:{plan["id"].removeprefix("sha256:")[:16]}:'
        f'{evaluated_at.isoformat()}'
    )
    assessment_id = (
        f'assessment:{plan["id"].removeprefix("sha256:")[:16]}:'
        f'{waiver_revision.removeprefix("sha256:")[:16]}:{evaluated_at.isoformat()}'
    )
    results = []
    for control in plan["controls"]:
        waiver = active_waiver(
            waivers,
            plan["subject"]["id"],
            control["instance_id"],
            evaluated_at,
        )
        evidence_requirements = control.get("evidence", [])
        selected_evidence, uses, validation_errors, ambiguities = select_evidence(
            evidence, evidence_requirements, evaluated_at, plan['subject']['id'],
            validators, schema_references, evidence_sources,
        )
        selected_uses.extend({'instance_id': control['instance_id'], **use} for use in uses)
        assessment_input = {
            "schema": "compliance.example/assessment-input/v1",
            "assessment": {
                "id": technical_assessment_id,
                "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
                "plan_id": plan["id"],
            },
            "subject": plan["subject"],
            "control": control,
            "evidence": selected_evidence,
            # Waivers must not influence the technical decision produced by Rego.
            "waiver": None,
        }
        if (validation_errors or ambiguities or any(not any(use['requirement_index'] == index for use in uses) for index, _ in enumerate(evidence_requirements))):
            observed = {}
            if validation_errors:
                reason = 'Required evidence was rejected as invalid; criterion not determined.'
                observed['evidence_validation_errors'] = validation_errors
            elif ambiguities:
                reason = 'Required evidence selection is ambiguous; criterion not determined.'
            else:
                reason = 'Required evidence is missing or stale; criterion not determined.'
            if ambiguities:
                observed['evidence_selection_ambiguities'] = ambiguities
            result = control_error_result(assessment_input, reason, observed=observed)
            result['status'] = 'unknown'
        else:
            try:
                result = evaluate_control(opa, policies, assessment_input, control["entrypoint"])
                from .artifact_validation import assessment_results_schema_path
                schema = load_json(assessment_results_schema_path())
                item_schema = {'$defs': schema['$defs']}
                item_schema['$ref'] = schema['properties']['results']['items']['$ref']
                candidate = {**result, 'waiver_revision': waiver_revision} if isinstance(result, dict) else result
                from ._canonical_json import canonical_json_bytes
                canonical_json_bytes(candidate)
                errors = list(Draft202012Validator(item_schema, format_checker=FormatChecker()).iter_errors(candidate))
                expected = control_error_result(assessment_input, '')
                fields = ('control_id', 'instance_id', 'subject_id', 'plan_id')
                if errors or any(result.get(key) != expected[key] for key in fields) or result.get('status') == 'waived' or 'waiver' in result or any(key in result.get('observed', {}) for key in ('evidence_validation_errors', 'evidence_selection_ambiguities')):
                    result = control_error_result(assessment_input, 'OPA returned an unusable decision')
            except Exception:
                result = control_error_result(assessment_input, 'Criterion execution failed')
        result["waiver_revision"] = waiver_revision
        if waiver is not None and result.get("status") == "fail":
            result["status"] = "waived"
            result["waiver"] = {**waiver, "underlying_status": "fail"}
        results.append(result)

    requirement_assessments, requirement_baseline_assessments = (
        roll_up_plan_requirements(plan, results)
    )

    def summarize(items: list[JsonObject]) -> JsonObject:
        return {
            status: sum(1 for item in items if item.get("status") == status)
            for status in ("pass", "fail", "unknown", "not_applicable", "error", "waived")
        }

    report = {
        "schema": RESULTS_SCHEMA,
        "assessment_id": assessment_id,
        "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
        "plan_id": plan["id"],
        "waiver_revision": waiver_revision,
        "subject_id": plan["subject"]["id"],
        "operation": copy.deepcopy(plan['operation']),
        "summary": summarize(results),
        "requirement_summary": summarize(requirement_assessments),
        "requirement_baseline_summary": summarize(requirement_baseline_assessments),
        "resolved_policy": {key: copy.deepcopy(plan[key]) for key in (
            "subject", "resolved_groups", "controls", "excluded_controls", "requirements",
            "resolved_requirement_baselines", "resolved_baselines", "assignments", "resolution")},
        "results": results,
        "requirement_assessments": requirement_assessments,
        "requirement_baseline_assessments": requirement_baseline_assessments,
    }
    report['digestAlgorithm'] = RESULTS_DIGEST_ALGORITHM
    report['provenance'] = {
        **plan['provenance'], 'evaluationComposition': stage(evaluation),
        'evaluator': evaluator.document(), 'evidence': evidence_descriptor,
        'selectedEvidence': sorted(selected_uses, key=lambda item: (item['instance_id'], item['requirement_index'])),
    }
    report['id'] = artifact_digest(report)
    validate_selection_plan(report, plan)
    validate_selection_snapshot(report, evidence)
    validate_assessment_results(report)
    return report


def write_json(document: JsonObject, output: Path) -> None:
    if document.get("schema") in {"compliance.example/assessment-plan/v4"}:
        validate_assessment_plan(document, source=output)
    elif document.get("schema") in {"compliance.example/assessment-results/v4"}:
        validate_assessment_results(document, source=output)
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
