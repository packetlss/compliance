"""Compare immutable rendered subject policy without re-resolving a catalog."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator

from .artifact_validation import validate_assessment_plan


JsonObject = dict[str, Any]
POLICY_DIFF_SCHEMA = "compliance.example/policy-diff/v1alpha1"
POLICY_DIFF_SET_SCHEMA = "compliance.example/policy-diff-set/v1alpha1"
CHANGE_COUNTS = ("added", "removed", "modified", "activated", "excluded")
SUBJECT_CHANGE_COUNTS = (
    "added",
    "removed",
    "modified",
    "unchanged",
    "incomplete",
)


def policy_diff_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas/policy-diff.schema.json"


def policy_diff_set_schema_path() -> Path:
    return Path(__file__).resolve().parent / "schemas/policy-diff-set.schema.json"


def _pointer(path: Any) -> str:
    parts = [str(part).replace("~", "~0").replace("/", "~1") for part in path]
    return "/" + "/".join(parts) if parts else "/"


def _schema_errors(document: JsonObject, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(document),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.message,
        ),
    )
    return [
        f"{_pointer(error.absolute_path)}: {error.message}"
        for error in errors
    ]


def validate_policy_diff(document: JsonObject) -> None:
    """Validate the machine-readable policy-diff report contract."""
    errors = _schema_errors(document, policy_diff_schema_path())
    if errors:
        raise ValueError(
            "generated policy diff failed schema validation: " + "; ".join(errors)
        )


def validate_policy_diff_set(document: JsonObject) -> None:
    """Validate schema and summary invariants for a plan-set diff report."""
    errors = _schema_errors(document, policy_diff_set_schema_path())
    if errors:
        raise ValueError(
            "generated policy diff set failed schema validation: "
            + "; ".join(errors)
        )

    subjects = document["subjects"]
    identities = [item["subject_id"] for item in subjects]
    duplicates = sorted(
        identity
        for identity, count in Counter(identities).items()
        if count > 1
    )
    semantic_errors: list[str] = []
    if duplicates:
        semantic_errors.append(
            "/subjects: duplicate subject identities: " + ", ".join(duplicates)
        )
    if identities != sorted(identities):
        semantic_errors.append("/subjects: subject identities must be sorted")
    counts = Counter(item["change"] for item in subjects)
    summary = document["summary"]
    if summary["total_subjects"] != len(subjects):
        semantic_errors.append(
            f"/summary/total_subjects: expected {len(subjects)}, "
            f"got {summary['total_subjects']}"
        )
    for name in SUBJECT_CHANGE_COUNTS:
        if summary[name] != counts[name]:
            semantic_errors.append(
                f"/summary/{name}: expected {counts[name]}, got {summary[name]}"
            )
    expected_changed = bool(
        counts["added"] or counts["removed"] or counts["modified"]
    )
    if summary["changed"] != expected_changed:
        semantic_errors.append(
            f"/summary/changed: expected {str(expected_changed).lower()}"
        )
    expected_status = "incomplete" if counts["incomplete"] else "complete"
    if document["comparison"]["status"] != expected_status:
        semantic_errors.append(
            f"/comparison/status: expected {expected_status}"
        )
    before_count = sum(item["before"] is not None for item in subjects)
    after_count = sum(item["after"] is not None for item in subjects)
    if document["before"]["plan_count"] != before_count:
        semantic_errors.append(
            f"/before/plan_count: expected {before_count}, "
            f"got {document['before']['plan_count']}"
        )
    if document["after"]["plan_count"] != after_count:
        semantic_errors.append(
            f"/after/plan_count: expected {after_count}, "
            f"got {document['after']['plan_count']}"
        )
    for index, item in enumerate(subjects):
        nested = item.get("diff")
        before = item["before"]
        after = item["after"]
        if before is None and after is None:
            semantic_errors.append(
                f"/subjects/{index}: before and after cannot both be null"
            )
        if item["change"] == "added" and not (before is None and after is not None):
            semantic_errors.append(
                f"/subjects/{index}: added requires only an after plan"
            )
        if item["change"] == "removed" and not (before is not None and after is None):
            semantic_errors.append(
                f"/subjects/{index}: removed requires only a before plan"
            )
        if (
            item["change"] == "added"
            and after is not None
            and after["resolution"] != "valid"
        ):
            semantic_errors.append(
                f"/subjects/{index}: added requires a valid after plan"
            )
        if (
            item["change"] == "removed"
            and before is not None
            and before["resolution"] != "valid"
        ):
            semantic_errors.append(
                f"/subjects/{index}: removed requires a valid before plan"
            )
        if item["change"] in ("modified", "unchanged") and (
            before is None or after is None or nested is None
        ):
            semantic_errors.append(
                f"/subjects/{index}: {item['change']} requires two plans and a diff"
            )
        if (before is None or after is None) and nested is not None:
            semantic_errors.append(
                f"/subjects/{index}: one-sided changes cannot contain a diff"
            )
        if nested is not None:
            nested_valid = True
            try:
                validate_policy_diff(nested)
            except ValueError as error:
                semantic_errors.append(f"/subjects/{index}/diff: {error}")
                nested_valid = False
            if nested_valid and nested["subject_id"] != item["subject_id"]:
                semantic_errors.append(
                    f"/subjects/{index}/diff/subject_id: expected "
                    f"{item['subject_id']}"
                )
            if nested_valid and item["change"] == "modified" and not (
                nested["comparison"]["status"] == "complete"
                and nested["summary"]["changed"]
            ):
                semantic_errors.append(
                    f"/subjects/{index}: modified requires a complete changed diff"
                )
            if nested_valid and item["change"] == "unchanged" and not (
                nested["comparison"]["status"] == "complete"
                and not nested["summary"]["changed"]
            ):
                semantic_errors.append(
                    f"/subjects/{index}: unchanged requires a complete unchanged diff"
                )
            if nested_valid and item["change"] == "incomplete" and (
                nested["comparison"]["status"] != "incomplete"
            ):
                semantic_errors.append(
                    f"/subjects/{index}: incomplete pair requires an incomplete diff"
                )
        elif before is not None and after is not None:
            semantic_errors.append(
                f"/subjects/{index}: paired plans require an embedded diff"
            )
        if item["change"] == "incomplete" and not (
            (before is not None and before["resolution"] == "invalid")
            or (after is not None and after["resolution"] == "invalid")
        ):
            semantic_errors.append(
                f"/subjects/{index}: incomplete requires an invalid plan"
            )
    if semantic_errors:
        raise ValueError(
            "generated policy diff set failed semantic validation: "
            + "; ".join(semantic_errors)
        )


def _reference_identity(reference: str) -> str:
    return reference.rsplit("@", 1)[0]


def _baseline_identity(item: JsonObject) -> str:
    return " -> ".join((
        item["group"],
        item["assignment"],
        _reference_identity(item["reference"]),
    ))


def _requirement_identity(item: JsonObject) -> str:
    return _reference_identity(item["reference"])


def _changed_fields(before: JsonObject, after: JsonObject) -> list[str]:
    return sorted(
        key
        for key in before.keys() | after.keys()
        if before.get(key) != after.get(key)
    )


def _index(
    items: list[JsonObject],
    identity: Callable[[JsonObject], str],
    *,
    label: str,
) -> dict[str, JsonObject]:
    indexed: dict[str, JsonObject] = {}
    for item in items:
        key = identity(item)
        if key in indexed:
            raise ValueError(f"cannot diff duplicate {label} identity: {key}")
        indexed[key] = item
    return indexed


def _collection_changes(
    before_items: list[JsonObject],
    after_items: list[JsonObject],
    *,
    kind: str,
    identity: Callable[[JsonObject], str],
) -> list[JsonObject]:
    before = _index(before_items, identity, label=kind)
    after = _index(after_items, identity, label=kind)
    changes: list[JsonObject] = []
    for key in sorted(before.keys() | after.keys()):
        old = before.get(key)
        new = after.get(key)
        if old is None:
            changes.append({
                "kind": kind,
                "identity": key,
                "change": "added",
                "changed_fields": [],
                "before": None,
                "after": new,
            })
        elif new is None:
            changes.append({
                "kind": kind,
                "identity": key,
                "change": "removed",
                "changed_fields": [],
                "before": old,
                "after": None,
            })
        elif old != new:
            changes.append({
                "kind": kind,
                "identity": key,
                "change": "modified",
                "changed_fields": _changed_fields(old, new),
                "before": old,
                "after": new,
            })
    return changes


def _singleton_change(
    before: JsonObject,
    after: JsonObject,
    *,
    kind: str,
    identity: str,
) -> list[JsonObject]:
    if before == after:
        return []
    return [{
        "kind": kind,
        "identity": identity,
        "change": "modified",
        "changed_fields": _changed_fields(before, after),
        "before": before,
        "after": after,
    }]


def _policy_subject(subject: JsonObject) -> JsonObject:
    """Select subject fields that can affect scope or desired-state targeting."""
    return {
        key: subject[key]
        for key in ("id", "type", "status", "labels", "attributes")
        if key in subject
    }


def _scope_changes(before: JsonObject, after: JsonObject) -> list[JsonObject]:
    changes = _singleton_change(
        _policy_subject(before["subject"]),
        _policy_subject(after["subject"]),
        kind="subject",
        identity=before["subject"]["id"],
    )
    changes.extend(_collection_changes(
        before["resolved_groups"],
        after["resolved_groups"],
        kind="group",
        identity=lambda item: item["id"],
    ))
    changes.extend(_collection_changes(
        before["assignments"],
        after["assignments"],
        kind="assignment",
        identity=lambda item: item["id"],
    ))
    changes.extend(_collection_changes(
        before["resolved_baselines"],
        after["resolved_baselines"],
        kind="baseline",
        identity=_baseline_identity,
    ))
    changes.extend(_collection_changes(
        before["resolved_requirement_baselines"],
        after["resolved_requirement_baselines"],
        kind="requirement_baseline",
        identity=_baseline_identity,
    ))
    changes.extend(_singleton_change(
        before["coverage"],
        after["coverage"],
        kind="coverage",
        identity=before["subject"]["id"],
    ))
    changes.extend(_singleton_change(
        before["resolution"],
        after["resolution"],
        kind="resolution",
        identity=before["subject"]["id"],
    ))
    return sorted(
        changes,
        key=lambda item: (item["kind"], item["identity"], item["change"]),
    )


def _control_index(plan: JsonObject) -> dict[str, JsonObject]:
    return _index(
        [*plan["controls"], *plan["excluded_controls"]],
        lambda item: item["instance_id"],
        label="control",
    )


def _control_changes(before: JsonObject, after: JsonObject) -> list[JsonObject]:
    old_controls = _control_index(before)
    new_controls = _control_index(after)
    changes: list[JsonObject] = []
    for instance_id in sorted(old_controls.keys() | new_controls.keys()):
        old = old_controls.get(instance_id)
        new = new_controls.get(instance_id)
        if old is None:
            change = "added"
            fields: list[str] = []
        elif new is None:
            change = "removed"
            fields = []
        elif old == new:
            continue
        else:
            fields = _changed_fields(old, new)
            dispositions = (old["disposition"], new["disposition"])
            if dispositions == ("evaluate", "excluded"):
                change = "excluded"
            elif dispositions == ("excluded", "evaluate"):
                change = "activated"
            else:
                change = "modified"
        changes.append({
            "kind": "control",
            "identity": instance_id,
            "change": change,
            "changed_fields": fields,
            "before": old,
            "after": new,
        })
    return changes


def _counts(changes: list[JsonObject]) -> JsonObject:
    counter = Counter(item["change"] for item in changes)
    return {name: counter[name] for name in CHANGE_COUNTS}


def _context(plan: JsonObject, source: Path | None) -> JsonObject:
    from .assessment_provenance import digest
    return {
        "path": str(source) if source is not None else "<memory>",
        "plan_id": plan["id"],
        "policy_revision": plan["policy_revision"],
        "policy_sources": plan["policy_sources"],
        "inventory_revision": plan["inventory_revision"],
        "assignment_revision": plan["assignment_revision"],
        "operation_digest": digest(plan['operation']),
    }


def _comparison(before: JsonObject, after: JsonObject) -> JsonObject:
    invalid = [
        side
        for side, plan in (("before", before), ("after", after))
        if plan["resolution"]["status"] != "valid"
    ]
    if not invalid:
        return {"status": "complete", "reason": "valid-plans"}
    return {
        "status": "incomplete",
        "reason": "invalid-resolution",
        "invalid_sides": invalid,
    }


def build_policy_diff(
    before: JsonObject,
    after: JsonObject,
    *,
    before_source: Path | None = None,
    after_source: Path | None = None,
) -> JsonObject:
    """Build a deterministic semantic diff between two stored subject plans."""
    validate_assessment_plan(before, source=before_source)
    validate_assessment_plan(after, source=after_source)
    subject_id = before["subject"]["id"]
    if after["subject"]["id"] != subject_id:
        raise ValueError(
            "policy diff requires plans for the same subject: "
            f"{subject_id!r} != {after['subject']['id']!r}"
        )

    before_context = _context(before, before_source)
    after_context = _context(after, after_source)
    context_fields = [
        field
        for field in (
            "plan_id",
            "policy_revision",
            "policy_sources",
            "inventory_revision",
            "assignment_revision",
            "operation_digest",
        )
        if before_context[field] != after_context[field]
    ]
    scope_changes = _scope_changes(before, after)
    requirement_changes = _collection_changes(
        before["requirements"],
        after["requirements"],
        kind="requirement",
        identity=_requirement_identity,
    )
    control_changes = _control_changes(before, after)
    total_changes = (
        len(scope_changes) + len(requirement_changes) + len(control_changes)
    )
    document: JsonObject = {
        "schema": POLICY_DIFF_SCHEMA,
        "subject_id": subject_id,
        "comparison": _comparison(before, after),
        "context": {
            "changed": bool(context_fields),
            "changed_fields": context_fields,
            "before": before_context,
            "after": after_context,
        },
        "summary": {
            "changed": bool(total_changes),
            "total_changes": total_changes,
            "scope": _counts(scope_changes),
            "requirements": _counts(requirement_changes),
            "controls": _counts(control_changes),
        },
        "scope_changes": scope_changes,
        "requirement_changes": requirement_changes,
        "control_changes": control_changes,
    }
    validate_policy_diff(document)
    return document


def load_policy_plan_set(root: Path) -> dict[str, tuple[Path, JsonObject]]:
    """Load one strict directory tree of uniquely identified assessment plans."""
    if not root.is_dir():
        raise ValueError(f"policy diff set directory does not exist: {root}")
    candidates = sorted(root.rglob("*.json"))
    if not candidates:
        raise ValueError(f"policy diff set contains no JSON plans: {root}")

    plans: dict[str, tuple[Path, JsonObject]] = {}
    for path in candidates:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"invalid JSON assessment plan {path}: {error}"
            ) from error
        if not isinstance(document, dict) or document.get("schema") not in {
            "compliance.example/assessment-plan/v4",
        }:
            raise ValueError(f"not an assessment plan in policy diff set: {path}")
        validate_assessment_plan(document, source=path)
        subject_id = document["subject"]["id"]
        if subject_id in plans:
            previous = plans[subject_id][0]
            raise ValueError(
                f"duplicate subject plan {subject_id!r} in {root}: "
                f"{previous} and {path}"
            )
        plans[subject_id] = (path, document)
    return plans


def _plan_summary(path: Path, plan: JsonObject) -> JsonObject:
    return {
        "path": str(path),
        "plan_id": plan["id"],
        "subject_type": plan["subject"]["type"],
        "policy_revision": plan["policy_revision"],
        "inventory_revision": plan["inventory_revision"],
        "assignment_revision": plan["assignment_revision"],
        "resolution": plan["resolution"]["status"],
        "coverage": plan["coverage"]["status"],
        "active_controls": len(plan["controls"]),
        "excluded_controls": len(plan["excluded_controls"]),
        "requirements": len(plan["requirements"]),
    }


def _subject_set_entry(
    subject_id: str,
    before: tuple[Path, JsonObject] | None,
    after: tuple[Path, JsonObject] | None,
) -> JsonObject:
    before_path, before_plan = before if before is not None else (None, None)
    after_path, after_plan = after if after is not None else (None, None)
    old_summary = (
        _plan_summary(before_path, before_plan)
        if before_path is not None and before_plan is not None
        else None
    )
    new_summary = (
        _plan_summary(after_path, after_plan)
        if after_path is not None and after_plan is not None
        else None
    )

    if before_plan is None:
        change = (
            "added"
            if after_plan["resolution"]["status"] == "valid"
            else "incomplete"
        )
        diff = None
    elif after_plan is None:
        change = (
            "removed"
            if before_plan["resolution"]["status"] == "valid"
            else "incomplete"
        )
        diff = None
    else:
        diff = build_policy_diff(
            before_plan,
            after_plan,
            before_source=before_path,
            after_source=after_path,
        )
        if diff["comparison"]["status"] != "complete":
            change = "incomplete"
        elif diff["summary"]["changed"]:
            change = "modified"
        else:
            change = "unchanged"
    return {
        "subject_id": subject_id,
        "change": change,
        "before": old_summary,
        "after": new_summary,
        "diff": diff,
    }


def build_policy_diff_set(before_root: Path, after_root: Path) -> JsonObject:
    """Compare two strict plan directories by stable subject identity."""
    before = load_policy_plan_set(before_root)
    after = load_policy_plan_set(after_root)
    subjects = [
        _subject_set_entry(subject_id, before.get(subject_id), after.get(subject_id))
        for subject_id in sorted(before.keys() | after.keys())
    ]
    counts = Counter(item["change"] for item in subjects)
    incomplete = bool(counts["incomplete"])
    document: JsonObject = {
        "schema": POLICY_DIFF_SET_SCHEMA,
        "comparison": {
            "status": "incomplete" if incomplete else "complete",
            "reason": "invalid-subject-plans" if incomplete else "valid-plan-sets",
        },
        "before": {"path": str(before_root), "plan_count": len(before)},
        "after": {"path": str(after_root), "plan_count": len(after)},
        "summary": {
            "changed": bool(
                counts["added"] or counts["removed"] or counts["modified"]
            ),
            "total_subjects": len(subjects),
            **{name: counts[name] for name in SUBJECT_CHANGE_COUNTS},
        },
        "subjects": subjects,
    }
    validate_policy_diff_set(document)
    return document


def _compact(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _format_change(change: JsonObject) -> list[str]:
    lines = [
        f"  {change['change'].upper():<9} "
        f"{change['kind']} {change['identity']}"
    ]
    old = change["before"]
    new = change["after"]
    if old is None:
        if change["kind"] == "control":
            lines.append(
                "    criteria: "
                f"implementation={new['implementation']}, "
                f"disposition={new['disposition']}, "
                f"parameters={_compact(new['parameters'])}"
            )
        return lines
    if new is None:
        if change["kind"] == "control":
            lines.append(
                "    previous criteria: "
                f"implementation={old['implementation']}, "
                f"disposition={old['disposition']}, "
                f"parameters={_compact(old['parameters'])}"
            )
        return lines

    lines.append("    fields: " + ", ".join(change["changed_fields"]))
    for field in change["changed_fields"]:
        lines.append(f"    - {field}")
        lines.append(f"      before: {_compact(old.get(field))}")
        lines.append(f"      after:  {_compact(new.get(field))}")
    return lines


def _format_counts(label: str, counts: JsonObject) -> str:
    values = [
        f"{name}={counts[name]}"
        for name in CHANGE_COUNTS
        if counts[name]
    ]
    return f"{label}: " + (", ".join(values) if values else "none")


def format_policy_diff(document: JsonObject) -> str:
    """Render a review-oriented human representation of a policy diff."""
    comparison = document["comparison"]
    summary = document["summary"]
    context = document["context"]
    lines = [
        f"Policy diff: {document['subject_id']}",
        f"Before: {context['before']['plan_id']} ({context['before']['path']})",
        f"After:  {context['after']['plan_id']} ({context['after']['path']})",
        f"Comparison: {comparison['status'].upper()} ({comparison['reason']})",
        "Result: " + (
            "EFFECTIVE POLICY CHANGED"
            if summary["changed"]
            else "NO EFFECTIVE POLICY CHANGES"
        ),
    ]
    if comparison["status"] == "incomplete":
        lines.append("Invalid sides: " + ", ".join(comparison["invalid_sides"]))
    if context["changed"]:
        lines.append("Context changes:")
        for field in context["changed_fields"]:
            lines.append(f"  {field}")
            lines.append(f"    before: {_compact(context['before'][field])}")
            lines.append(f"    after:  {_compact(context['after'][field])}")
    lines.extend([
        "",
        f"Changes: {summary['total_changes']}",
        _format_counts("Scope", summary["scope"]),
        _format_counts("Requirements", summary["requirements"]),
        _format_counts("Controls", summary["controls"]),
    ])

    sections = (
        ("Scope changes", document["scope_changes"]),
        ("Requirement changes", document["requirement_changes"]),
        ("Control changes", document["control_changes"]),
    )
    for title, changes in sections:
        if not changes:
            continue
        lines.extend(["", f"{title}:"])
        for change in changes:
            lines.extend(_format_change(change))
    return "\n".join(lines)


def _short_plan(summary: JsonObject | None) -> str:
    return summary["plan_id"][:23] if summary is not None else "-"


def _subject_detail(item: JsonObject) -> str:
    if item["diff"] is not None:
        diff = item["diff"]
        if diff["comparison"]["status"] != "complete":
            return "invalid resolution"
        return f"{diff['summary']['total_changes']} effective change(s)"
    plan = item["after"] or item["before"]
    if item["change"] == "incomplete":
        return f"{plan['resolution']} resolution"
    return (
        f"{plan['active_controls']} active, "
        f"{plan['excluded_controls']} excluded, "
        f"{plan['requirements']} objective(s)"
    )


def format_policy_diff_set(document: JsonObject) -> str:
    """Render an aggregate plan-set comparison plus changed-subject details."""
    summary = document["summary"]
    comparison = document["comparison"]
    result = (
        "INCOMPLETE"
        if comparison["status"] == "incomplete"
        else (
            "EFFECTIVE POLICY CHANGED"
            if summary["changed"]
            else "NO EFFECTIVE POLICY CHANGES"
        )
    )
    lines = [
        "Policy plan-set diff",
        f"Before: {document['before']['path']} ({document['before']['plan_count']} plans)",
        f"After:  {document['after']['path']} ({document['after']['plan_count']} plans)",
        f"Comparison: {comparison['status'].upper()} ({comparison['reason']})",
        f"Result: {result}",
        (
            "Subjects: "
            f"total={summary['total_subjects']}, added={summary['added']}, "
            f"removed={summary['removed']}, modified={summary['modified']}, "
            f"unchanged={summary['unchanged']}, incomplete={summary['incomplete']}"
        ),
        "",
    ]
    headers = ("STATE", "SUBJECT", "BEFORE", "AFTER", "DETAIL")
    rows = [(
        item["change"].upper(),
        item["subject_id"],
        _short_plan(item["before"]),
        _short_plan(item["after"]),
        _subject_detail(item),
    ) for item in document["subjects"]]
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def render(values: tuple[str, ...]) -> str:
        return "  ".join(
            value.ljust(widths[index])
            for index, value in enumerate(values)
        ).rstrip()

    lines.append(render(headers))
    lines.append(render(tuple("─" * width for width in widths)))
    lines.extend(render(row) for row in rows)

    detailed = [
        item
        for item in document["subjects"]
        if item["diff"] is not None and item["change"] != "unchanged"
    ]
    for item in detailed:
        lines.extend([
            "",
            f"Subject detail: {item['subject_id']}",
            format_policy_diff(item["diff"]),
        ])
    return "\n".join(lines)
