"""Internal assessment-plan evaluation implementation."""

from __future__ import annotations

import json
import re
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
from .policy_sources import PolicySources, policy_source_revisions, rego_module_paths
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


def fresh_evidence(
    documents: list[JsonObject],
    requirements: list[JsonObject],
    evaluated_at: datetime,
) -> list[JsonObject]:
    selected: list[JsonObject] = []
    for requirement in requirements:
        maximum_age = parse_duration(requirement["max_age"])
        candidates = []
        for document in documents:
            if document.get("type") != requirement["type"]:
                continue
            collected_at = datetime.fromisoformat(document["collected_at"].replace("Z", "+00:00"))
            if evaluated_at - collected_at <= maximum_age:
                candidates.append((collected_at, document))
        if candidates:
            selected.append(max(candidates, key=lambda candidate: candidate[0])[1])
    return selected


def evidence_for_subject(
    documents: list[JsonObject],
    subject_id: str,
) -> list[JsonObject]:
    """Select only evidence explicitly bound to the assessed subject."""
    return [
        document
        for document in documents
        if isinstance(document.get("subject"), dict)
        and document["subject"].get("id") == subject_id
    ]


def _json_pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else ""


def load_evidence_documents(
    evidence_path: Path,
) -> tuple[list[JsonObject], dict[int, str]]:
    """Load JSON object evidence while retaining operator-facing source paths."""
    documents: list[JsonObject] = []
    sources: dict[int, str] = {}
    for path in sorted(evidence_path.glob("*.json")):
        try:
            document = load_json(path)
        except (OSError, json.JSONDecodeError) as error:
            raise SystemExit(
                "refusing to evaluate assessment plan: unreadable evidence document "
                f"{path}: {error}"
            ) from error
        if not isinstance(document, dict):
            raise SystemExit(
                "refusing to evaluate assessment plan: evidence document must be a "
                f"JSON object: {path}"
            )
        documents.append(document)
        sources[id(document)] = path.relative_to(evidence_path).as_posix()
    return documents, sources


def evidence_validation_errors(
    documents: list[JsonObject],
    requirements: list[JsonObject],
    schemas: dict[str, JsonObject],
    *,
    sources: dict[int, str] | None = None,
) -> list[JsonObject]:
    """Validate subject-scoped documents for the evidence types a control uses."""
    errors: list[JsonObject] = []
    sources = sources or {}
    required_types = sorted({requirement["type"] for requirement in requirements})
    validators: dict[str, Draft202012Validator] = {}

    for evidence_type in required_types:
        schema = schemas.get(evidence_type)
        if schema is None:
            errors.append({
                "type": "evidence-schema-unavailable",
                "evidence_type": evidence_type,
                "message": "no schema is available for the declared evidence type",
            })
            continue
        validators[evidence_type] = Draft202012Validator(
            schema,
            format_checker=EVIDENCE_FORMAT_CHECKER,
        )

    for document in documents:
        evidence_type = document.get("type")
        if not isinstance(evidence_type, str):
            continue
        validator = validators.get(evidence_type)
        if validator is None:
            continue
        validation_errors = sorted(
            validator.iter_errors(document),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )
        for error in validation_errors:
            detail: JsonObject = {
                "type": "evidence-schema-validation-failed",
                "evidence_type": evidence_type,
                "source": sources.get(id(document), "<memory>"),
                "schema_source": schemas[evidence_type].get("_source", "<unknown>"),
                "path": _json_pointer(error.absolute_path),
                "message": error.message,
            }
            if isinstance(document.get("id"), str):
                detail["evidence_id"] = document["id"]
            errors.append(detail)
    return errors


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
        "inventory_revision": assessment_input["assessment"]["inventory_revision"],
        "assignment_revision": assessment_input["assessment"]["assignment_revision"],
        "policy_revision": assessment_input["assessment"]["policy_revision"],
        "status": "error",
        "reason": reason,
        "severity": assessment_input["control"]["severity"],
        "remediation": assessment_input["control"]["remediation"],
        "expected": {},
        "observed": observed or {},
        "external_refs": assessment_input["control"].get("external_refs", []),
        "alignment": assessment_input["control"].get("alignment", "unmapped"),
        "evidence_ids": evidence_ids if evidence_ids is not None else [
            document["id"]
            for document in assessment_input["evidence"]
            if isinstance(document.get("id"), str)
        ],
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
) -> JsonObject:
    """Evaluate an already rendered plan and return its immutable result envelope."""
    validate_assessment_plan(plan)
    if plan["resolution"]["status"] != "valid":
        raise SystemExit("refusing to evaluate an invalid assessment plan")
    coverage = plan.get("coverage", {})
    if coverage.get("status") != "assigned" or not coverage.get("assessable"):
        reason = coverage.get("reason", "plan-is-not-assessable")
        raise SystemExit(f"refusing to evaluate assessment plan: {reason}")

    if "policy_sources" in plan:
        actual_sources = policy_source_revisions(policies)
        if actual_sources != plan["policy_sources"]:
            raise SystemExit(
                "refusing to evaluate assessment plan: configured policy source "
                "revisions do not match the rendered plan"
            )

    if not evidence_path.is_dir():
        raise SystemExit(f"evidence path is not a directory: {evidence_path}")
    loaded_evidence, evidence_sources = load_evidence_documents(evidence_path)
    evidence = evidence_for_subject(loaded_evidence, plan["subject"]["id"])

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

    evaluated_at = (evaluated_at or datetime.now(UTC)).replace(microsecond=0)
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
        validation_errors = evidence_validation_errors(
            evidence,
            evidence_requirements,
            evidence_schemas,
            sources=evidence_sources,
        )
        selected_evidence = fresh_evidence(
            evidence,
            evidence_requirements,
            evaluated_at,
        ) if not validation_errors else []
        assessment_input = {
            "schema": "compliance.example/assessment-input/v1",
            "assessment": {
                "id": technical_assessment_id,
                "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
                "policy_revision": plan["policy_revision"],
                "inventory_revision": plan["inventory_revision"],
                "assignment_revision": plan["assignment_revision"],
                "plan_id": plan["id"],
            },
            "subject": plan["subject"],
            "control": control,
            "evidence": selected_evidence,
            # Waivers must not influence the technical decision produced by Rego.
            "waiver": None,
        }
        if validation_errors:
            first = validation_errors[0]
            location = first.get("source", first["evidence_type"])
            pointer = first.get("path", "")
            reason = (
                f"Evidence schema validation failed at {location}{pointer}: "
                f"{first['message']}"
            )
            if len(validation_errors) > 1:
                reason += f" ({len(validation_errors)} errors total)"
            evidence_ids = sorted({
                error["evidence_id"]
                for error in validation_errors
                if isinstance(error.get("evidence_id"), str)
            })
            result = control_error_result(
                assessment_input,
                reason,
                observed={"evidence_validation_errors": validation_errors},
                evidence_ids=evidence_ids,
            )
        else:
            result = evaluate_control(
                opa,
                policies,
                assessment_input,
                control["entrypoint"],
            )
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
        "schema": "compliance.example/assessment-results/v1",
        "assessment_id": assessment_id,
        "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z"),
        "plan_id": plan["id"],
        "policy_revision": plan["policy_revision"],
        "inventory_revision": plan["inventory_revision"],
        "assignment_revision": plan["assignment_revision"],
        "waiver_revision": waiver_revision,
        "subject_id": plan["subject"]["id"],
        "summary": summarize(results),
        "requirement_summary": summarize(requirement_assessments),
        "requirement_baseline_summary": summarize(requirement_baseline_assessments),
        "results": results,
        "requirement_assessments": requirement_assessments,
        "requirement_baseline_assessments": requirement_baseline_assessments,
    }
    validate_assessment_results(report)
    return report


def write_json(document: JsonObject, output: Path) -> None:
    if document.get("schema") == "compliance.example/assessment-plan/v1":
        validate_assessment_plan(document, source=output)
    elif document.get("schema") == "compliance.example/assessment-results/v1":
        validate_assessment_results(document, source=output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, indent=2, sort_keys=True)
        stream.write("\n")
