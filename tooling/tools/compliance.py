#!/usr/bin/env python3
"""Unified operator CLI for the OPA compliance prototype."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Sequence

from .artifact_validation import validate_assessment_plan
from .assessment import (
    HISTORICAL_OUTCOMES,
    PLAN_ALIGNMENTS,
    build_explanation_view,
    build_mappings_view,
    build_run_view,
    build_status_view,
    load_assessment_plans,
    load_result_reports,
    render_explanation_view,
    render_mappings_view,
    render_run_view,
    render_status_view,
)
from .evaluate_plan import evaluate_plan_document, write_json
from .coverage import (
    build_coverage_explanation,
    build_coverage_list,
    format_coverage_explanation,
    format_coverage_list,
    resolve_coverage_plans,
)
from .inventory import (
    build_inventory_explanation,
    build_inventory_list,
    format_group_graph,
    format_inventory_explanation,
    format_inventory_list,
)
from .policy_sources import (
    PolicySource,
    normalize_policy_sources,
    parse_policy_source,
    policy_source_revisions,
)
from .policy_diff import (
    build_policy_diff,
    build_policy_diff_set,
    format_policy_diff,
    format_policy_diff_set,
)
from .project_config import (
    ProjectConfig,
    ProjectConfigError,
    format_config,
    select_config,
    composition_validation,
)
from .render_plan import (
    load_inventory_catalog,
    load_inventory_inputs,
    load_evidence_schema_catalog,
    load_json,
    load_policy_catalogs,
    load_requirement_catalogs,
    render_plan,
    validate_rego_entrypoints,
)
from .waivers import (
    load_waivers,
    parse_timestamp,
    waiver_catalog_document,
)


Handler = Callable[[argparse.Namespace], None]


def default_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas/inventory/resource.schema.json"


def subject_artifact_path(configured_path: Path, subject_id: str) -> Path:
    """Treat extensionless configured artifact paths as per-subject directories."""
    if configured_path.suffix:
        return configured_path
    filename = subject_id.replace("/", "__") + ".json"
    return configured_path / filename


def _path_default(config: ProjectConfig, key: str, fallback: Path | None = None) -> Path | None:
    return config.path(key) or fallback


def _add_path(
    parser: argparse.ArgumentParser,
    flag: str,
    config: ProjectConfig,
    key: str,
    *,
    required: bool = True,
    fallback: Path | None = None,
    help_text: str,
) -> None:
    default = _path_default(config, key, fallback)
    parser.add_argument(
        flag,
        type=Path,
        default=default,
        required=required and default is None,
        help=help_text,
    )


def _add_inventory_sources(parser: argparse.ArgumentParser, config: ProjectConfig) -> None:
    _add_path(
        parser,
        "--inventory",
        config,
        "inventory",
        help_text="inventory resource file or directory",
    )
    _add_path(
        parser,
        "--assignments",
        config,
        "assignments",
        help_text="assignment resource file or directory",
    )
    _add_path(
        parser,
        "--resource-schema",
        config,
        "resourceSchema",
        fallback=default_schema_path(),
        help_text="inventory resource schema",
    )


def _add_policy_sources(parser: argparse.ArgumentParser, config: ProjectConfig) -> None:
    _add_inventory_sources(parser, config)
    _add_policy_source_options(parser, config)


def _add_policies_only(parser: argparse.ArgumentParser, config: ProjectConfig) -> None:
    _add_policy_source_options(parser, config)


def _add_waiver_path(
    parser: argparse.ArgumentParser,
    config: ProjectConfig,
    *,
    required: bool,
) -> None:
    _add_path(
        parser,
        "--waivers",
        config,
        "waivers",
        required=required,
        help_text="waiver resource file or directory",
    )


def _add_policy_source_options(
    parser: argparse.ArgumentParser,
    config: ProjectConfig,
) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--policy-source",
        action="append",
        metavar="NAME=PATH",
        help="replace configured policy sources; repeat for local assembly",
    )
    group.add_argument(
        "--policies",
        type=Path,
        help="legacy single policy root (equivalent to one CLI source)",
    )
    parser.set_defaults(configured_policy_sources=config.policy_sources)


def _resolved_policy_sources(args: argparse.Namespace) -> tuple[PolicySource, ...]:
    if args.policy_source:
        return normalize_policy_sources(
            parse_policy_source(value, base=Path.cwd()) for value in args.policy_source
        )
    if args.policies is not None:
        path = args.policies if args.policies.is_absolute() else Path.cwd() / args.policies
        return (PolicySource("default", path),)
    return normalize_policy_sources(args.configured_policy_sources)


def _load_catalog(args: argparse.Namespace):
    if args.inventory is None or args.assignments is None:
        raise ValueError('current inventory resolution requires --inventory and --assignments')
    return load_inventory_catalog(args.inventory, args.assignments, args.resource_schema)


def _run_config_show(args: argparse.Namespace) -> None:
    print(format_config(args.project_config, args.format))


def _run_config_validate(args: argparse.Namespace) -> None:
    if args.project_config.source is None:
        raise ValueError("no project config found; pass --config or create compliance.yaml")
    if args.project_config.project_registry_source:
        print(
            f"valid project registry: {args.project_config.project_registry_source}; "
            f"project {args.project_config.project_name}: {args.project_config.source} "
            f"({len(args.project_config.paths)} configured path(s), "
            f"{len(args.project_config.policy_sources)} policy source(s), {args.project_config.schema})"
        )
    else:
        print(
            f"valid project config: {args.project_config.source} "
            f"({len(args.project_config.paths)} configured path(s), "
            f"{len(args.project_config.policy_sources)} policy source(s), {args.project_config.schema})"
        )


def _run_config_list(args: argparse.Namespace) -> None:
    config = args.project_config
    if not config.available_projects:
        raise ValueError("selected configuration is a project, not a project registry")
    document = {
        "schema": "compliance.example/project-registry-list/v1",
        "project_registry": str(config.project_registry_source),
        "default_project": config.default_project,
        "selected_project": config.project_name,
        "projects": [
            {"name": name, "config": str(path)}
            for name, path in sorted(config.available_projects.items())
        ],
    }
    if args.format == "json":
        print(json.dumps(document, indent=2, sort_keys=True))
        return
    print(f"Project registry: {config.project_registry_source}")
    print(f"Selected:  {config.project_name}")
    print("")
    print("PROJECT     DEFAULT  CONFIG")
    for project in document["projects"]:
        name = project["name"]
        marker = "yes" if name == config.default_project else ""
        print(f"{name:<11} {marker:<7}  {project['config']}")


def _run_inventory(args: argparse.Namespace) -> None:
    subjects, groups, assignments = _load_catalog(args)
    if args.inventory_command == "validate":
        print(
            f"valid inventory: {len(subjects)} asset(s), "
            f"{len(groups)} group(s), {len(assignments)} assignment(s)"
        )
    elif args.inventory_command == "graph":
        print(format_group_graph(groups))
    elif args.inventory_command == "list":
        document = build_inventory_list(args.resource, subjects, groups, assignments)
        if args.format == "json":
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(format_inventory_list(document))
    elif args.inventory_command == "explain":
        if args.asset_id not in subjects:
            raise ValueError(f"unknown asset id: {args.asset_id}")
        document = build_inventory_explanation(subjects[args.asset_id], groups)
        if args.format == "json":
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(format_inventory_explanation(document))


def _run_coverage(args: argparse.Namespace) -> None:
    subjects, groups, assignments = _load_catalog(args)
    policy_sources = _resolved_policy_sources(args)
    if args.coverage_command == "explain":
        if args.asset_id not in subjects:
            raise ValueError(f"unknown asset id: {args.asset_id}")
        plans = resolve_coverage_plans(
            {args.asset_id: subjects[args.asset_id]},
            groups,
            assignments,
            policy_sources,
            config=args.project_config,
        )
        document = build_coverage_explanation(plans[0])
        if args.format == "json":
            print(json.dumps(document, indent=2, sort_keys=True))
        else:
            print(format_coverage_explanation(document))
        return

    plans = resolve_coverage_plans(
        subjects,
        groups,
        assignments,
        policy_sources,
        config=args.project_config,
    )
    document = build_coverage_list(
        args.resource, subjects, groups, assignments, plans
    )
    if args.format == "json":
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(format_coverage_list(document))


def _run_policy_validate(args: argparse.Namespace) -> None:
    policy_sources = _resolved_policy_sources(args)
    controls, catalog, errors = load_policy_catalogs(policy_sources)
    evidence_schemas, _ = load_evidence_schema_catalog(policy_sources)
    if not errors:
        errors.extend(validate_rego_entrypoints(policy_sources, controls, opa=args.opa))
    requirements, requirement_baselines, realizations, _ = load_requirement_catalogs(
        policy_sources,
        controls,
    )
    try:
        revisions = policy_source_revisions(policy_sources)
    except ValueError:
        revisions = []
    report = {
        "schema": "compliance.example/policy-validation/v1",
        "policy_sources": [
            {
                **revision,
                "path": str(source.path),
                **(
                    {"expected_digest": source.expected_digest}
                    if source.expected_digest
                    else {}
                ),
            }
            for source, revision in zip(policy_sources, revisions, strict=True)
        ],
        "valid": not errors,
        "baseline_count": len(catalog),
        "control_count": len(controls),
        "evidence_schema_count": len(evidence_schemas),
        "requirement_count": len(requirements),
        "requirement_baseline_count": len(requirement_baselines),
        "realization_count": len(realizations),
        "errors": errors,
    }
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif errors:
        print(f"invalid policy catalog: {len(errors)} error(s)")
        for error in errors:
            print("  " + json.dumps(error, sort_keys=True))
    else:
        print(
            f"valid policy catalog: {len(catalog)} baseline document(s), "
            f"{len(controls)} control manifest(s), "
            f"{len(evidence_schemas)} evidence schema(s), "
            f"{len(requirements)} requirement(s), "
            f"{len(requirement_baselines)} requirement baseline(s), "
            f"{len(realizations)} realization(s)"
        )
    if errors:
        raise SystemExit(1)


def _run_policy_diff(args: argparse.Namespace) -> None:
    before = load_json(args.before)
    after = load_json(args.after)
    document = build_policy_diff(
        before,
        after,
        before_source=args.before,
        after_source=args.after,
    )
    if args.format == "json":
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(format_policy_diff(document))
    if document["comparison"]["status"] != "complete":
        raise SystemExit(2)
    if document["summary"]["changed"]:
        raise SystemExit(1)


def _run_policy_diff_set(args: argparse.Namespace) -> None:
    document = build_policy_diff_set(args.before, args.after)
    if args.format == "json":
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(format_policy_diff_set(document))
    if document["comparison"]["status"] != "complete":
        raise SystemExit(2)
    if document["summary"]["changed"]:
        raise SystemExit(1)


def _waiver_instant(value: str | None) -> datetime:
    return (
        parse_timestamp(value, field="--at")
        if value
        else datetime.now(UTC).replace(microsecond=0)
    )


def _format_waiver_catalog(document: dict) -> str:
    summary = document["summary"]
    lines = [
        f'Waivers ({len(document["waivers"])})',
        f'Revision: {document["revision"]}',
        (
            f'State: active={summary["active"]}, scheduled={summary["scheduled"]}, '
            f'expired={summary["expired"]}'
        ),
        "",
    ]
    headers = ("STATE", "WAIVER", "SUBJECT", "CONTROL", "EXPIRES")
    rows = [(
        item["state"].upper(),
        item["id"],
        item["subject_id"],
        item["instance_id"],
        item["expires_at"],
    ) for item in document["waivers"]]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines.append(
        "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(headers)
        ).rstrip()
    )
    lines.append("  ".join("─" * width for width in widths).rstrip())
    lines.extend(
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip()
        for row in rows
    )
    return "\n".join(lines)


def _format_waiver(waiver: dict) -> str:
    return "\n".join([
        f'Waiver: {waiver["id"]}',
        f'State: {waiver["state"]}',
        f'Subject: {waiver["subject_id"]}',
        f'Control: {waiver["instance_id"]}',
        f'Valid: {waiver["valid_from"]} through {waiver["expires_at"]} (exclusive)',
        f'Owner: {waiver["owner"]}',
        f'Rationale: {waiver["rationale"]}',
        f'Approval: {waiver["approval_ref"]}',
        f'Approved by: {waiver["approved_by"]} at {waiver["approved_at"]}',
        f'Digest: {waiver["digest"]}',
    ])


def _run_waiver(args: argparse.Namespace) -> None:
    waivers, revision = load_waivers(args.waivers)
    if args.waiver_command == "validate":
        print(f"valid waiver catalog: {len(waivers)} waiver(s), revision {revision}")
        return
    instant = _waiver_instant(args.at)
    document = waiver_catalog_document(
        waivers,
        revision,
        instant,
        subject_id=getattr(args, "subject_id", None),
        states=set(getattr(args, "state", [])),
    )
    if args.waiver_command == "explain":
        waiver = next(
            (item for item in document["waivers"] if item["id"] == args.waiver_id),
            None,
        )
        if waiver is None:
            raise ValueError(f"unknown waiver id: {args.waiver_id}")
        if args.format == "json":
            print(json.dumps(waiver, indent=2, sort_keys=True))
        else:
            print(_format_waiver(waiver))
        return
    if args.format == "json":
        print(json.dumps(document, indent=2, sort_keys=True))
    else:
        print(_format_waiver_catalog(document))


def _run_plan_render(args: argparse.Namespace) -> None:
    plans = _render_selected_plans(args, diagnostic=True)
    _check_operation_outputs(plans, args.output)
    for plan in plans:
        output = subject_artifact_path(args.output, plan['subject']['id'])
        write_json(plan, output)
        print(f'wrote {plan["id"]} to {output}')


def _render_selected_plans(args, *, diagnostic=False):
    from .operation import render_operation
    subjects, groups, assignments = _load_catalog(args)
    if diagnostic and len(args.subject_id) == 1 and not args.group and not args.all_subjects:
        if args.subject_id[0] not in subjects:
            raise ValueError('unknown subject id: ' + args.subject_id[0])
        return [render_plan(subjects[args.subject_id[0]], groups, assignments,
                            _resolved_policy_sources(args), config=args.project_config)]
    return render_operation(subjects, groups, assignments, _resolved_policy_sources(args),
        {'subjects': args.subject_id, 'groups': args.group, 'all': args.all_subjects},
        config=args.project_config)


def _check_operation_outputs(plans, *roots):
    all_paths = []
    for root in roots:
        paths = [subject_artifact_path(root, p['subject']['id']) for p in plans]
        all_paths.extend(path.resolve() for path in paths)
    if len(all_paths) != len(set(all_paths)):
        raise ValueError('operation output paths collide; use distinct per-subject plan/result directories')


def _format_plan_summary(plan: dict) -> str:
    from .operation import plan_coverage
    coverage = plan_coverage(plan)
    resolution = plan.get("resolution", {})
    external_refs = {
        external_ref
        for item in [
            *plan.get("requirements", []),
            *plan.get("controls", []),
            *plan.get("excluded_controls", []),
        ]
        for external_ref in item.get("external_refs", [])
    }
    lines = [
        f"Assessment plan: {plan.get('id', 'unknown')}",
        f"Subject:         {plan.get('subject', {}).get('id', 'unknown')}",
        f"Resolution:      {resolution.get('status', 'unknown')}",
        f"Coverage:        {coverage.get('status', 'unknown')} "
        f"(assessable={str(bool(coverage.get('assessable'))).lower()})",
        f"Controls:        {len(plan.get('controls', []))} active, "
        f"{len(plan.get('excluded_controls', []))} excluded",
        f"Objectives:      {len(plan.get('requirements', []))}",
        f"External refs:   {len(external_refs)}",
        f"Operation:       {plan['operation']['operation_id']}",
        f"Composition:     {plan['provenance']['planningComposition']['compositionDigest']}",
        f"Policy sources:  {len(plan['provenance']['planningComposition']['actual']['policySources'])}",
    ]
    lines.extend(
        f"  {source['name']}: {source['content']['digest']}"
        for source in plan['provenance']['planningComposition']['actual']['policySources']
    )
    return "\n".join(lines)


def _plan_index_entry(plan: dict, path: Path) -> dict:
    from .operation import plan_coverage
    coverage = plan_coverage(plan)
    return {
        "subject_id": plan.get("subject", {}).get("id", "unknown"),
        "plan_id": plan.get("id", "unknown"),
        "resolution": plan.get("resolution", {}).get("status", "unknown"),
        "coverage": coverage.get("status", "unknown"),
        "assessable": bool(coverage.get("assessable")),
        "active_controls": len(plan.get("controls", [])),
        "excluded_controls": len(plan.get("excluded_controls", [])),
        "objectives": len(plan.get("requirements", [])),
        "path": str(path),
    }


def _format_plan_index(entries: list[dict]) -> str:
    headers = ("SUBJECT", "PLAN", "RESOLUTION", "COVERAGE", "A/X", "OBJECTIVES")
    rows = [(
        entry["subject_id"],
        entry["plan_id"][:23],
        entry["resolution"].upper(),
        entry["coverage"].upper(),
        f'{entry["active_controls"]}/{entry["excluded_controls"]}',
        str(entry["objectives"]),
    ) for entry in entries]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render(values: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        ).rstrip()

    lines = [f"Assessment plans ({len(entries)})", "", render(headers)]
    lines.append(render(tuple("─" * width for width in widths)))
    lines.extend(render(row) for row in rows)
    lines.extend([
        "",
        "Select one with: compliance plan show SUBJECT",
    ])
    return "\n".join(lines)


def _resolve_plan_show_path(
    selector: Path | None,
    configured: Path | None,
    *,
    artifact_name: str = "assessment plan",
    configured_hint: str = "paths.plan",
) -> Path:
    if selector is None:
        if configured is None:
            raise ValueError(
                f"show requires PLAN, SUBJECT, or configured {configured_hint}"
            )
        return configured
    if selector.exists():
        return selector
    if configured is not None and configured.is_dir():
        direct = configured / selector
        if direct.exists():
            return direct
        subject_path = subject_artifact_path(configured, selector.as_posix())
        if subject_path.exists():
            return subject_path
        raise ValueError(
            f"no {artifact_name} for subject {selector.as_posix()!r} in {configured}"
        )
    raise ValueError(f"{artifact_name} does not exist: {selector}")


def _run_plan_show(args: argparse.Namespace) -> None:
    plan_path = _resolve_plan_show_path(
        args.plan,
        args.project_config.path("plan"),
    )
    if plan_path.is_dir():
        plans = []
        for candidate in sorted(plan_path.rglob("*.json")):
            document = load_json(candidate)
            if str(document.get("schema", "")).startswith("compliance.example/assessment-plan/"):
                validate_assessment_plan(document, source=candidate)
                plans.append((candidate, document))
        if not plans:
            raise ValueError(f"plan directory contains no assessment plans: {plan_path}")
        if len(plans) == 1:
            plan_path, plan = plans[0]
        else:
            entries = [_plan_index_entry(plan, path) for path, plan in plans]
            if args.format == "json":
                print(json.dumps({
                    "schema": "compliance.example/assessment-plan-index/v1alpha1",
                    "plans": entries,
                }, indent=2, sort_keys=True))
            else:
                print(_format_plan_index(entries))
            return
    else:
        plan = load_json(plan_path)
        validate_assessment_plan(plan, source=plan_path)
    if args.format == "json":
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print(_format_plan_summary(plan))


def _render_subject_plan(args: argparse.Namespace) -> dict:
    subject, groups, assignments = load_inventory_inputs(
        args.inventory,
        args.assignments,
        args.subject_id,
        args.resource_schema,
    )
    return render_plan(
        subject,
        groups,
        assignments,
        _resolved_policy_sources(args),
        config=args.project_config,
    )


def _run_assessment_view(args: argparse.Namespace) -> None:
    _run_historical_operation_view(args)


def _run_assessment(args: argparse.Namespace) -> None:
    from .operation import InvalidOperationResolution, plan_disposition
    try:
        plans = _render_selected_plans(args)
    except InvalidOperationResolution as error:
        raise SystemExit(str(error)) from error
    _check_operation_outputs(plans, args.plan_output, args.output)
    policy_sources = _resolved_policy_sources(args)
    instant = parse_timestamp(args.at, field='--at') if args.at else datetime.now(UTC)
    instant = instant.replace(microsecond=0)
    for plan in plans:
        plan_output = subject_artifact_path(args.plan_output, plan['subject']['id'])
        write_json(plan, plan_output)
    reports = []
    for plan in plans:
        if plan_disposition(plan) != 'result_required':
            continue
        report = evaluate_plan_document(plan, args.evidence, policy_sources,
            opa=args.opa, evaluated_at=instant, waiver_path=args.waivers,
            composition_report=(composition_validation(args.project_config, require=True)
                                if args.project_config.source else None))
        write_json(
            report,
            subject_artifact_path(args.output, plan['subject']['id']),
            plan=plan,
        )
        reports.append(report)
    from .operation import account_operation
    account = account_operation(
        plans[0], reports, instant.isoformat().replace('+00:00', 'Z'), plans
    )
    view = build_run_view(account, plans, reports)
    if args.format == 'json':
        print(json.dumps(view, indent=2, sort_keys=True))
    else:
        print(render_run_view(view))


def _run_historical_operation_view(args):
    from .operation import (
        account_operation,
        frozen_group_memberships,
        qualify_operation,
    )
    if not args.plan or not args.at or not args.as_of:
        raise ValueError(
            'assessment reporting requires --plan, --at, and --as-of for one exact frozen operation'
        )
    anchor = load_json(args.plan)
    validate_assessment_plan(anchor, source=args.plan)
    instant = parse_timestamp(args.at, field='--at').isoformat().replace('+00:00', 'Z')
    query_instant = parse_timestamp(args.as_of, field='--as-of')
    comparison_anchor = load_json(args.comparison_plan) if args.comparison_plan else None
    assessed_plans = load_assessment_plans([args.plan, *args.assessed_plans])
    reports = load_result_reports(args.results) if args.results and args.results.exists() else []
    account = qualify_operation(
        account_operation(anchor, reports, instant, assessed_plans),
        reports,
        query_instant,
        comparison_anchor,
        assessed_plans,
    )
    by_id = {r['id']: r for r in reports}
    plan_by_id = {plan['id']: plan for plan in assessed_plans}
    known_groups = set(frozen_group_memberships(account['operation']))
    unknown_groups = sorted(set(args.group) - known_groups)
    if unknown_groups:
        raise ValueError('unknown frozen operation group(s): ' + ', '.join(unknown_groups))
    if args.assessment_command == 'explain':
        selected = [r for r in account['members'] if r['subject_id'] == args.asset_id]
        if not selected:
            raise ValueError('asset is absent from frozen operation selection')
        member = selected[0]
        explanation = build_explanation_view(
            account,
            member,
            plan_by_id.get(member['plan_id']),
            by_id.get(member['result_id']),
        )
        if args.format == 'json':
            print(json.dumps(explanation, indent=2, sort_keys=True))
        else:
            print(render_explanation_view(explanation))
        return
    if args.assessment_command == 'mappings':
        view = build_mappings_view(
            account,
            reports,
            assessed_plans,
            group_ids=args.group,
            outcomes=args.outcome,
            plan_alignments=args.plan_alignment,
            external_refs=args.reference,
            levels=args.level,
        )
        if args.format == 'json':
            print(json.dumps(view, indent=2, sort_keys=True))
        else:
            print(render_mappings_view(view))
        return
    view = build_status_view(
        account,
        group_ids=args.group,
        outcomes=args.outcome,
        plan_alignments=args.plan_alignment,
        by_group=args.by == 'group',
    )
    if args.format == 'json':
        print(json.dumps(view, indent=2, sort_keys=True))
    else:
        print(render_status_view(view))


def _set_handler(parser: argparse.ArgumentParser, handler: Handler) -> None:
    parser.set_defaults(handler=handler)


def _add_assessment_view_options(
    parser: argparse.ArgumentParser,
    config: ProjectConfig,
    *,
    allow_filters: bool,
) -> None:
    parser.add_argument(
        '--plan',
        type=Path,
        required=True,
        help='stored plan anchoring one exact frozen operation',
    )
    parser.add_argument(
        '--assessed-plans',
        action='append',
        type=Path,
        default=[],
        help='exact assessed plan file or bounded plan directory; repeatable',
    )
    parser.add_argument(
        '--at', required=True, help='exact recorded operation assessment instant'
    )
    parser.add_argument(
        '--as-of', required=True, help='explicit query instant for current qualifications'
    )
    parser.add_argument('--comparison-plan', type=Path,
                        help='validated v4 plan anchoring the comparison operation')
    _add_path(
        parser,
        "--results",
        config,
        "results",
        required=False,
        help_text="result file or directory tree",
    )
    parser.add_argument("--format", choices=("table", "json"), default="table")
    if allow_filters:
        parser.add_argument(
            "--group",
            action="append",
            default=[],
            help="filter/select a resolved group; repeat for OR semantics",
        )
        parser.add_argument(
            "--outcome",
            action="append",
            choices=HISTORICAL_OUTCOMES,
            default=[],
            help="filter an immutable historical outcome; repeat for OR semantics",
        )
        parser.add_argument(
            "--plan-alignment",
            action="append",
            choices=PLAN_ALIGNMENTS,
            default=[],
            help="filter exact plan alignment; repeat for OR semantics",
        )
    else:
        parser.set_defaults(group=[], outcome=[], plan_alignment=[])


def build_parser(config: ProjectConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compliance",
        description=(
            "Inspect supplied inventory, explain current coverage, and run or "
            "report assessments. Composition diagnostics: compliance composition "
            "show/validate [--format json]."
        ),
    )
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--config",
        type=Path,
        help="project config (default: nearest compliance.yaml)",
    )
    config_group.add_argument(
        "--no-config",
        action="store_true",
        help="disable project config discovery",
    )
    parser.add_argument(
        "--project",
        help="project name from a discovered or explicitly selected project registry",
    )
    parser.set_defaults(project_config=config)
    commands = parser.add_subparsers(dest="command", required=True)

    config_parser = commands.add_parser("config", help="inspect project configuration")
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    config_show = config_commands.add_parser("show", help="show resolved configuration")
    config_show.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(config_show, _run_config_show)
    config_validate = config_commands.add_parser("validate", help="validate project configuration")
    _set_handler(config_validate, _run_config_validate)
    config_list = config_commands.add_parser("list", help="list registered projects")
    config_list.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(config_list, _run_config_list)

    inventory_parser = commands.add_parser("inventory", help="inspect inventory and assignments")
    inventory_commands = inventory_parser.add_subparsers(dest="inventory_command", required=True)
    for name, help_text in (
        ("validate", "validate schemas, references, and the group DAG"),
        ("graph", "show the inventory group DAG"),
    ):
        child = inventory_commands.add_parser(name, help=help_text)
        _add_inventory_sources(child, config)
        _set_handler(child, _run_inventory)
    inventory_list = inventory_commands.add_parser(
        "list", help="list supplied inventory resources"
    )
    inventory_list.add_argument("resource", choices=("assets", "groups", "assignments"))
    inventory_list.add_argument("--format", choices=("table", "json"), default="table")
    _add_inventory_sources(inventory_list, config)
    _set_handler(inventory_list, _run_inventory)
    inventory_explain = inventory_commands.add_parser(
        "explain", help="explain supplied facts and membership for one asset"
    )
    inventory_explain.add_argument("asset_id", metavar="ASSET")
    inventory_explain.add_argument("--format", choices=("table", "json"), default="table")
    _add_inventory_sources(inventory_explain, config)
    _set_handler(inventory_explain, _run_inventory)

    coverage_parser = commands.add_parser(
        "coverage", help="inspect current policy coverage and assessment expectation"
    )
    coverage_commands = coverage_parser.add_subparsers(
        dest="coverage_command", required=True
    )
    coverage_list = coverage_commands.add_parser(
        "list", help="list current asset, group, or assignment coverage"
    )
    coverage_list.add_argument(
        "resource", choices=("assets", "groups", "assignments")
    )
    coverage_list.add_argument("--format", choices=("table", "json"), default="table")
    _add_policy_sources(coverage_list, config)
    _set_handler(coverage_list, _run_coverage)
    coverage_explain = coverage_commands.add_parser(
        "explain", help="explain current policy coverage for one asset"
    )
    coverage_explain.add_argument("asset_id", metavar="ASSET")
    coverage_explain.add_argument("--format", choices=("table", "json"), default="table")
    _add_policy_sources(coverage_explain, config)
    _set_handler(coverage_explain, _run_coverage)

    policy_parser = commands.add_parser(
        "policy",
        help="validate policy inputs or compare rendered asset policy",
    )
    policy_commands = policy_parser.add_subparsers(dest="policy_command", required=True)
    policy_validate = policy_commands.add_parser(
        "validate",
        help="validate controls, parameter contracts, baselines, and overlays",
    )
    _add_policies_only(policy_validate, config)
    policy_validate.add_argument("--format", choices=("table", "json"), default="table")
    policy_validate.add_argument("--opa", default="opa", help="OPA executable")
    _set_handler(policy_validate, _run_policy_validate)
    policy_diff = policy_commands.add_parser(
        "diff",
        help="compare two stored assessment plans for the same asset",
    )
    policy_diff.add_argument("before", type=Path, help="earlier assessment plan")
    policy_diff.add_argument("after", type=Path, help="later assessment plan")
    policy_diff.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(policy_diff, _run_policy_diff)
    policy_diff_set = policy_commands.add_parser(
        "diff-set",
        help="compare two directories of stored assessment plans by asset",
    )
    policy_diff_set.add_argument(
        "before",
        type=Path,
        help="earlier assessment-plan directory",
    )
    policy_diff_set.add_argument(
        "after",
        type=Path,
        help="later assessment-plan directory",
    )
    policy_diff_set.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
    )
    _set_handler(policy_diff_set, _run_policy_diff_set)

    waiver_parser = commands.add_parser(
        "waiver",
        help="validate and inspect approved temporary exceptions",
    )
    waiver_commands = waiver_parser.add_subparsers(
        dest="waiver_command",
        required=True,
    )
    waiver_validate = waiver_commands.add_parser(
        "validate",
        help="validate waiver schemas, identities, windows, and overlaps",
    )
    _add_waiver_path(waiver_validate, config, required=True)
    _set_handler(waiver_validate, _run_waiver)
    waiver_list = waiver_commands.add_parser("list", help="list waiver lifecycle state")
    _add_waiver_path(waiver_list, config, required=True)
    waiver_list.add_argument("--subject", dest="subject_id")
    waiver_list.add_argument(
        "--state",
        action="append",
        choices=("active", "scheduled", "expired"),
        default=[],
    )
    waiver_list.add_argument("--at", help="evaluate lifecycle at an RFC 3339 timestamp")
    waiver_list.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(waiver_list, _run_waiver)
    waiver_explain = waiver_commands.add_parser("explain", help="explain one waiver")
    waiver_explain.add_argument("waiver_id")
    _add_waiver_path(waiver_explain, config, required=True)
    waiver_explain.add_argument("--at", help="evaluate lifecycle at an RFC 3339 timestamp")
    waiver_explain.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(waiver_explain, _run_waiver)

    plan_parser = commands.add_parser("plan", help="render and inspect assessment plans")
    plan_commands = plan_parser.add_subparsers(dest="plan_command", required=True)
    plan_render = plan_commands.add_parser("render", help="render one subject's effective plan")
    plan_render.add_argument("subject_id", nargs='*')
    plan_render.add_argument('--group', action='append', default=[])
    plan_render.add_argument('--all', dest='all_subjects', action='store_true')
    _add_policy_sources(plan_render, config)
    _add_path(
        plan_render,
        "--output",
        config,
        "plan",
        help_text="assessment plan output file, or extensionless per-subject directory",
    )
    _set_handler(plan_render, _run_plan_render)
    plan_show = plan_commands.add_parser("show", help="show or list rendered assessment plans")
    plan_show.add_argument(
        "plan",
        nargs="?",
        type=Path,
        help="assessment plan file or subject ID; omit to use configured plans",
    )
    plan_show.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(plan_show, _run_plan_show)

    assessment_parser = commands.add_parser("assessment", help="run and report assessments")
    assessment_commands = assessment_parser.add_subparsers(
        dest="assessment_command",
        required=True,
    )
    assessment_run = assessment_commands.add_parser(
        "run",
        help="render and evaluate one or more assets in an exact operation",
    )
    assessment_run.add_argument("subject_id", metavar="ASSET", nargs='*')
    assessment_run.add_argument('--group', action='append', default=[])
    assessment_run.add_argument('--all', dest='all_subjects', action='store_true')
    _add_policy_sources(assessment_run, config)
    _add_path(
        assessment_run,
        "--evidence",
        config,
        "evidence",
        help_text="directory containing evidence JSON documents",
    )
    _add_path(
        assessment_run,
        "--plan-output",
        config,
        "plan",
        help_text="rendered plan output file, or extensionless per-subject directory",
    )
    _add_path(
        assessment_run,
        "--output",
        config,
        "results",
        help_text="assessment result output file, or extensionless per-subject directory",
    )
    _add_waiver_path(assessment_run, config, required=False)
    assessment_run.add_argument(
        "--at",
        help="evaluate at an RFC 3339 instant (for deterministic verification)",
    )
    assessment_run.add_argument("--opa", default="opa", help="OPA executable")
    assessment_run.add_argument('--format', choices=('table','json'), default='table')
    _set_handler(assessment_run, _run_assessment)

    assessment_status = assessment_commands.add_parser(
        "status", help="show one exact frozen operation and current qualification"
    )
    _add_assessment_view_options(assessment_status, config, allow_filters=True)
    assessment_status.add_argument(
        "--by",
        choices=("group",),
        help="aggregate the exact operation by group",
    )
    _set_handler(assessment_status, _run_assessment_view)
    assessment_mappings = assessment_commands.add_parser(
        "mappings",
        help="show attributable objective and technical mappings",
    )
    _add_assessment_view_options(assessment_mappings, config, allow_filters=True)
    assessment_mappings.add_argument(
        "--reference",
        action="append",
        default=[],
        help="filter an exact external reference; repeat for OR semantics",
    )
    assessment_mappings.add_argument(
        "--level",
        action="append",
        choices=("objective", "technical"),
        default=[],
        help="filter mapping level; repeat for OR semantics",
    )
    _set_handler(assessment_mappings, _run_assessment_view)
    assessment_explain = assessment_commands.add_parser(
        "explain",
        help="explain one asset's exact assessment slot",
    )
    assessment_explain.add_argument("asset_id", metavar="ASSET")
    _add_assessment_view_options(assessment_explain, config, allow_filters=False)
    _set_handler(assessment_explain, _run_assessment_view)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    arguments = list(argv if argv is not None else sys.argv[1:])
    try:
        config = select_config(arguments)
    except ProjectConfigError as error:
        raise SystemExit(f"compliance: configuration error: {error}") from error

    parser = build_parser(config)
    args = parser.parse_args(arguments)
    try:
        args.handler(args)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
