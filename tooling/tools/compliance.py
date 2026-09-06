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
    STATE_PRIORITY,
    build_explanation,
    build_framework_report,
    build_group_report,
    build_status_report,
    filter_status_report,
    load_result_reports,
    render_explanation,
    render_framework_table,
    render_group_table,
    render_table,
)
from .evaluate_plan import evaluate_plan_document, write_json
from .inventory import explain_subject, format_group_graph
from .policy_sources import (
    PolicySource,
    normalize_policy_sources,
    parse_policy_source,
    policy_revision,
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
            f"valid inventory: {len(subjects)} subject(s), "
            f"{len(groups)} group(s), {len(assignments)} assignment(s)"
        )
    elif args.inventory_command == "graph":
        print(format_group_graph(groups))
    elif args.inventory_command == "list":
        values = {
            "subjects": sorted(subjects),
            "groups": sorted(group["id"] for group in groups),
            "assignments": sorted(assignment["id"] for assignment in assignments),
        }[args.resource]
        print(json.dumps(values, indent=2))
    elif args.inventory_command == "explain":
        if args.subject_id not in subjects:
            raise ValueError(f"unknown subject id: {args.subject_id}")
        print(explain_subject(subjects[args.subject_id], groups, assignments))


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
        "policy_revision": policy_revision(revisions) if revisions else None,
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
    for root in roots:
        paths = [subject_artifact_path(root, p['subject']['id']) for p in plans]
        if len(paths) != len(set(paths)):
            raise ValueError('operation output paths collide; use a per-subject directory')


def _format_plan_summary(plan: dict) -> str:
    coverage = plan.get("coverage", {})
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
        f"Policy revision: {plan.get('policy_revision', 'unknown')}",
        f"Policy sources:  {len(plan.get('policy_sources', []))}",
    ]
    lines.extend(
        f"  {source['name']}: {source['digest']}"
        for source in plan.get("policy_sources", [])
    )
    return "\n".join(lines)


def _plan_index_entry(plan: dict, path: Path) -> dict:
    coverage = plan.get("coverage", {})
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


def _assessment_context(args: argparse.Namespace):
    subjects, groups, assignments = _load_catalog(args)
    reports = load_result_reports(args.results)
    known_groups = {group["id"] for group in groups}
    unknown_groups = sorted(set(args.group) - known_groups)
    if unknown_groups:
        raise ValueError("unknown assessment group(s): " + ", ".join(unknown_groups))
    return subjects, groups, assignments, reports, known_groups


def _run_assessment_view(args: argparse.Namespace) -> None:
    if args.plan:
        _run_historical_operation_view(args)
        return
    subjects, groups, assignments, reports, known_groups = _assessment_context(args)
    use_color = not args.no_color and "NO_COLOR" not in os.environ and sys.stdout.isatty()

    if args.assessment_command == "explain":
        if args.subject_id not in subjects:
            raise ValueError(f"unknown subject id: {args.subject_id}")
        plan = render_plan(
            subjects[args.subject_id],
            groups,
            assignments,
            _resolved_policy_sources(args),
            config=args.project_config,
        )
        explanation = build_explanation(plan, reports)
        if args.format == "json":
            print(json.dumps(explanation, indent=2, sort_keys=True))
        else:
            print(render_explanation(explanation, color=use_color))
        return

    if args.assessment_command == "frameworks":
        framework_report = build_framework_report(
            subjects,
            groups,
            assignments,
            _resolved_policy_sources(args),
            reports,
            group_ids=args.group,
            external_refs=args.reference,
            levels=args.level,
            config=args.project_config,
        )
        if args.format == "json":
            print(json.dumps(framework_report, indent=2, sort_keys=True))
        else:
            print(render_framework_table(framework_report))
        return

    report = build_status_report(
        subjects,
        groups,
        assignments,
        _resolved_policy_sources(args),
        reports,
        config=args.project_config,
    )
    if args.assessment_command == "groups":
        state_filtered = filter_status_report(report, [], args.state)
        selected_groups = sorted(set(args.group)) if args.group else sorted(known_groups)
        group_report = build_group_report(state_filtered, selected_groups, args.group)
        if args.format == "json":
            print(json.dumps(group_report, indent=2, sort_keys=True))
        else:
            print(render_group_table(group_report))
        return

    report = filter_status_report(report, args.group, args.state)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_table(report, color=use_color))


def _run_assessment(args: argparse.Namespace) -> None:
    plans = _render_selected_plans(args)
    _check_operation_outputs(plans, args.plan_output, args.output)
    policy_sources = _resolved_policy_sources(args)
    instant = parse_timestamp(args.at, field='--at') if args.at else datetime.now(UTC)
    instant = instant.replace(microsecond=0)
    for plan in plans:
        plan_output = subject_artifact_path(args.plan_output, plan['subject']['id'])
        write_json(plan, plan_output)
    reports = []
    for plan in plans:
        if not plan['coverage']['assessable']:
            continue
        report = evaluate_plan_document(plan, args.evidence, policy_sources,
            opa=args.opa, evaluated_at=instant, waiver_path=args.waivers,
            composition_report=(composition_validation(args.project_config, require=True)
                                if args.project_config.source else None))
        write_json(report, subject_artifact_path(args.output, plan['subject']['id']))
        reports.append(report)
    from .operation import account_operation
    account = account_operation(plans[0], reports, instant.isoformat().replace('+00:00', 'Z'))
    print(json.dumps(account, indent=2, sort_keys=True))


def _run_historical_operation_view(args):
    from .operation import account_operation
    if not args.at:
        raise ValueError('historical operation reporting requires --at and --plan')
    anchor = load_json(args.plan)
    instant = parse_timestamp(args.at, field='--at').isoformat().replace('+00:00', 'Z')
    account = account_operation(anchor, load_result_reports(args.results), instant)
    selected = [r for r in account['members'] if not args.group or
                set(args.group) & {g['id'] for g in r['resolved_groups']}]
    if args.assessment_command == 'explain':
        selected = [r for r in selected if r['subject_id'] == args.subject_id]
        if not selected:
            raise ValueError('subject is absent from frozen operation selection')
    if args.assessment_command == 'frameworks':
        mappings = []
        for row in selected:
            for kind, key in (('objective', 'requirements'), ('technical', 'controls')):
                for item in row['policy'][key]:
                    for reference in item['external_refs']:
                        if (not args.reference or reference in args.reference) and (not args.level or kind in args.level):
                            mappings.append({'subject_id': row['subject_id'], 'external_ref': reference,
                                'mapping_level': kind, 'policy_object': item.get('reference', item.get('instance_id'))})
        account['mappings'] = mappings
    account['filtered'] = bool(args.group or args.state or args.assessment_command == 'explain' or
                               getattr(args, 'reference', []) or getattr(args, 'level', []))
    account['visible_members'] = [r for r in selected if not args.state or r['state'] in args.state]
    if args.format == 'json':
        print(json.dumps(account, indent=2, sort_keys=True))
    else:
        print(account['claim'])
        print(f"Accounting complete: {account['accounting_complete']}; all selected subjects passed: {account['all_passed']}")
        if account['filtered']:
            print('Filtered view; whole-operation accounting is shown separately.')
        for row in account['visible_members']:
            print(f"{row['subject_id']}: {row['state']} ({row['plan_id']})")
        if args.assessment_command in ('explain', 'frameworks', 'groups'):
            print(json.dumps(account.get('mappings', account['visible_members']), indent=2, sort_keys=True))


def _set_handler(parser: argparse.ArgumentParser, handler: Handler) -> None:
    parser.set_defaults(handler=handler)


def _add_assessment_view_options(
    parser: argparse.ArgumentParser,
    config: ProjectConfig,
    *,
    allow_filters: bool,
) -> None:
    _add_policy_sources(parser, config)
    # Historical views need only immutable artifacts. Current views validate
    # their inventory paths in the loader instead of making them parser-wide.
    for action in parser._actions:
        if action.dest in ('inventory', 'assignments'):
            action.required = False
    parser.add_argument('--plan', type=Path, help='stored plan anchoring an exact historical operation')
    parser.add_argument('--at', help='exact recorded operation assessment instant')
    _add_path(
        parser,
        "--results",
        config,
        "results",
        required=False,
        help_text="result file or directory tree",
    )
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI color")
    if allow_filters:
        parser.add_argument(
            "--group",
            action="append",
            default=[],
            help="filter/select a resolved group; repeat for OR semantics",
        )
        parser.add_argument(
            "--state",
            action="append",
            choices=tuple(STATE_PRIORITY),
            default=[],
            help="filter an operator state; repeat for OR semantics",
        )
    else:
        parser.set_defaults(group=[], state=[])


def build_parser(config: ProjectConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compliance",
        description=(
            "Inspect inventory, render policy, and run or "
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
    inventory_list = inventory_commands.add_parser("list", help="list inventory resources")
    inventory_list.add_argument("resource", choices=("subjects", "groups", "assignments"))
    _add_inventory_sources(inventory_list, config)
    _set_handler(inventory_list, _run_inventory)
    inventory_explain = inventory_commands.add_parser("explain", help="explain scope for one subject")
    inventory_explain.add_argument("subject_id")
    _add_inventory_sources(inventory_explain, config)
    _set_handler(inventory_explain, _run_inventory)

    policy_parser = commands.add_parser(
        "policy",
        help="validate policy inputs or compare rendered subject policy",
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
        help="compare two stored assessment plans for the same subject",
    )
    policy_diff.add_argument("before", type=Path, help="earlier assessment plan")
    policy_diff.add_argument("after", type=Path, help="later assessment plan")
    policy_diff.add_argument("--format", choices=("table", "json"), default="table")
    _set_handler(policy_diff, _run_policy_diff)
    policy_diff_set = policy_commands.add_parser(
        "diff-set",
        help="compare two directories of stored assessment plans by subject",
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
        help="render and evaluate one subject's current assessment",
    )
    assessment_run.add_argument("subject_id", nargs='*')
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
    _set_handler(assessment_run, _run_assessment)

    assessment_status = assessment_commands.add_parser("status", help="show fleet status")
    _add_assessment_view_options(assessment_status, config, allow_filters=True)
    _set_handler(assessment_status, _run_assessment_view)
    assessment_groups = assessment_commands.add_parser("groups", help="aggregate status by group")
    _add_assessment_view_options(assessment_groups, config, allow_filters=True)
    _set_handler(assessment_groups, _run_assessment_view)
    assessment_frameworks = assessment_commands.add_parser(
        "frameworks",
        help="show external-framework objective and technical mappings",
    )
    _add_assessment_view_options(assessment_frameworks, config, allow_filters=False)
    assessment_frameworks.add_argument(
        "--group",
        action="append",
        default=[],
        help="filter by a resolved group; repeat for OR semantics",
    )
    assessment_frameworks.add_argument(
        "--reference",
        action="append",
        default=[],
        help="filter an exact external reference; repeat for OR semantics",
    )
    assessment_frameworks.add_argument(
        "--level",
        action="append",
        choices=("objective", "technical"),
        default=[],
        help="filter mapping level; repeat for OR semantics",
    )
    _set_handler(assessment_frameworks, _run_assessment_view)
    assessment_explain = assessment_commands.add_parser(
        "explain",
        help="explain one subject's assessment",
    )
    assessment_explain.add_argument("subject_id")
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
