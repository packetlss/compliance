"""Purpose-specific current inventory projections and formatting."""

from __future__ import annotations

import copy
from collections import defaultdict
from typing import Any

from .render_plan import resolve_groups


JsonObject = dict[str, Any]


def format_selector(group: JsonObject) -> str:
    labels = group.get("selector", {}).get("match_labels", {})
    return ",".join(f"{key}={value}" for key, value in sorted(labels.items()))


def format_group_graph(groups: list[JsonObject]) -> str:
    children: dict[str, list[str]] = defaultdict(list)
    roots = []
    for group in groups:
        if not group.get("parents"):
            roots.append(group["id"])
        for parent in group.get("parents", []):
            children[parent].append(group["id"])
    for values in children.values():
        values.sort()

    lines: list[str] = []

    def visit(group_id: str, prefix: str, connector: str) -> None:
        group = next(group for group in groups if group["id"] == group_id)
        selector = format_selector(group)
        suffix = f"  [{selector}]" if selector else ""
        lines.append(f"{prefix}{connector}{group_id}{suffix}")
        nested = children.get(group_id, [])
        for index, child in enumerate(nested):
            last = index == len(nested) - 1
            visit(
                child,
                prefix + ("    " if connector == "└── " else "│   " if connector else ""),
                "└── " if last else "├── ",
            )

    for index, root in enumerate(sorted(roots)):
        if index:
            lines.append("")
        visit(root, "", "")
    return "\n".join(lines)


def _asset_facts(subject: JsonObject) -> JsonObject:
    # The read surface intentionally exposes only the stable governed facts used
    # by ordinary inventory/coverage navigation.  Adapter-specific attributes and
    # arbitrary annotations remain in Inventory and may affect resolution through
    # their existing owners; they are not blindly copied across this presentation
    # boundary.
    return {
        "asset_id": subject["id"],
        "asset_type": subject["type"],
        "lifecycle": subject["status"],
        "labels": dict(sorted(subject.get("labels", {}).items())),
        "source": copy.deepcopy(subject["inventory"]),
    }


def _group_facts(group: JsonObject) -> JsonObject:
    metadata = group.get("metadata", {})
    facts: JsonObject = {
        "group_id": group["id"],
        "parents": sorted(group.get("parents", [])),
        "selector_labels": dict(
            sorted(group.get("selector", {}).get("match_labels", {}).items())
        ),
        "explicit_assets": sorted(group.get("members", [])),
    }
    for field in ("labels", "annotations"):
        if field in metadata:
            facts[field] = copy.deepcopy(metadata[field])
    return facts


def _assignment_facts(assignment: JsonObject) -> JsonObject:
    return {
        "assignment_id": assignment["id"],
        "target_group": assignment["target"]["group"],
        "policy_references": sorted(assignment["baselines"]),
        "parameter_policy_references": sorted(
            assignment.get("parameter_policies", [])
        ),
    }


def build_inventory_list(
    resource: str,
    subjects: dict[str, JsonObject],
    groups: list[JsonObject],
    assignments: list[JsonObject],
) -> JsonObject:
    """Build one bounded view of supplied normalized inventory facts."""
    if resource == "assets":
        return {
            "schema": "compliance.example/inventory-assets-view/v1alpha1",
            "assets": [_asset_facts(subjects[key]) for key in sorted(subjects)],
        }
    if resource == "groups":
        return {
            "schema": "compliance.example/inventory-groups-view/v1alpha1",
            "groups": [
                _group_facts(group)
                for group in sorted(groups, key=lambda item: item["id"])
            ],
        }
    if resource == "assignments":
        return {
            "schema": "compliance.example/inventory-assignments-view/v1alpha1",
            "assignments": [
                _assignment_facts(assignment)
                for assignment in sorted(assignments, key=lambda item: item["id"])
            ],
        }
    raise ValueError(f"unknown inventory resource: {resource}")


def _compact_mapping(value: JsonObject) -> str:
    return ",".join(f"{key}={value[key]}" for key in sorted(value)) or "-"


def _table(title: str, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render(values: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(values)
        ).rstrip()

    lines = [title, "", render(headers), render(tuple("─" * width for width in widths))]
    lines.extend(render(row) for row in rows)
    return "\n".join(lines)


def format_inventory_list(document: JsonObject) -> str:
    schema = document["schema"]
    if schema.endswith("inventory-assets-view/v1alpha1"):
        rows = [
            (
                item["asset_id"],
                item["asset_type"],
                item["lifecycle"].upper(),
                _compact_mapping(item["labels"]),
                item["source"]["source"],
                item["source"]["observed_at"],
            )
            for item in document["assets"]
        ]
        return _table(
            f"Supplied inventory assets ({len(rows)})",
            ("ASSET", "TYPE", "LIFECYCLE", "LABELS", "SOURCE", "OBSERVED AT"),
            rows,
        )
    if schema.endswith("inventory-groups-view/v1alpha1"):
        rows = [
            (
                item["group_id"],
                ",".join(item["parents"]) or "-",
                _compact_mapping(item["selector_labels"]),
                ",".join(item["explicit_assets"]) or "-",
            )
            for item in document["groups"]
        ]
        return _table(
            f"Supplied inventory groups ({len(rows)})",
            ("GROUP", "PARENTS", "SELECTOR", "EXPLICIT ASSETS"),
            rows,
        )
    if schema.endswith("inventory-assignments-view/v1alpha1"):
        rows = [
            (
                item["assignment_id"],
                item["target_group"],
                ",".join(item["policy_references"]),
            )
            for item in document["assignments"]
        ]
        return _table(
            f"Supplied policy assignments ({len(rows)})",
            ("ASSIGNMENT", "TARGET GROUP", "POLICY REFERENCES"),
            rows,
        )
    raise ValueError(f"unsupported inventory view schema: {schema}")


def build_inventory_explanation(
    subject: JsonObject,
    groups: list[JsonObject],
) -> JsonObject:
    """Explain only supplied asset facts and resolved membership attribution."""
    groups_by_id = {group["id"]: group for group in groups}
    resolved = resolve_groups(groups_by_id, subject)
    return {
        "schema": "compliance.example/inventory-asset-explanation/v1alpha1",
        "asset": _asset_facts(subject),
        "resolved_groups": copy.deepcopy(resolved),
    }


def _membership_description(group: JsonObject) -> str:
    rendered_sources = []
    for source in group["sources"]:
        if source["membership"] == "selector":
            labels = source["source"]["match_labels"]
            rendered_sources.append(
                "selector "
                + ",".join(
                    f"{key}={value}" for key, value in sorted(labels.items())
                )
            )
        elif source["membership"] == "explicit":
            rendered_sources.append("explicit member")
        else:
            rendered_sources.append("inherited via " + ", ".join(source["via"]))
    return "; ".join(rendered_sources)


def format_inventory_explanation(document: JsonObject) -> str:
    asset = document["asset"]
    source = asset["source"]
    lines = [
        f'Asset: {asset["asset_id"]}',
        f'Type: {asset["asset_type"]}',
        f'Lifecycle: {asset["lifecycle"]}',
        f'Inventory source: {source["source"]}',
        f'External ID: {source["external_id"]}',
        f'Observed at: {source["observed_at"]}',
    ]
    if "revision" in source:
        lines.append(f'Revision: {source["revision"]}')
    lines.append("Labels:")
    if not asset["labels"]:
        lines.append("  none")
    for key, value in asset["labels"].items():
        lines.append(f"  {key}={value}")
    lines.append("Resolved groups:")
    if not document["resolved_groups"]:
        lines.append("  none")
    for group in document["resolved_groups"]:
        lines.append(f'  {group["id"]}: {_membership_description(group)}')
    return "\n".join(lines)
