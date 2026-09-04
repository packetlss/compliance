"""Internal inventory projection and formatting implementation."""

from __future__ import annotations

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


def explain_subject(
    subject: JsonObject,
    groups: list[JsonObject],
    assignments: list[JsonObject],
) -> str:
    groups_by_id = {group["id"]: group for group in groups}
    resolved = resolve_groups(groups_by_id, subject)
    resolved_ids = {group["id"] for group in resolved}
    applicable = sorted(
        (
            assignment
            for assignment in assignments
            if assignment["target"]["group"] in resolved_ids
        ),
        key=lambda assignment: assignment["id"],
    )

    lines = [
        f'Subject: {subject["id"]}',
        f'Type: {subject["type"]}',
        f'Lifecycle: {subject["status"]}',
        "Labels:",
    ]
    for key, value in sorted(subject.get("labels", {}).items()):
        lines.append(f"  {key}={value}")
    lines.append("Resolved groups:")
    for group in resolved:
        rendered_sources = []
        for source in group["sources"]:
            if source["membership"] == "selector":
                labels = source["source"]["match_labels"]
                rendered_sources.append(
                    "selector " + ",".join(f"{key}={value}" for key, value in sorted(labels.items()))
                )
            elif source["membership"] == "explicit":
                rendered_sources.append("explicit member")
            else:
                rendered_sources.append("inherited via " + ", ".join(source["via"]))
        lines.append(f'  {group["id"]}: {"; ".join(rendered_sources)}')
    lines.append("Policy assignments:")
    if not applicable:
        lines.append("  none (coverage gap)")
    for assignment in applicable:
        lines.append(
            f'  {assignment["id"]}: {assignment["target"]["group"]} -> '
            + ", ".join(assignment["baselines"])
        )
    return "\n".join(lines)
