#!/usr/bin/env python3
"""Check retained-project v4 artifacts against the actual validation inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from tools.artifact_validation import validate_assessment_plan, validate_assessment_results
from tools.assessment_provenance import validate_selection_plan, validate_selection_snapshot
from tools.compliance import build_parser
from tools.evidence_provenance import evidence_document_digest, evidence_set_provenance
from tools.policy_sources import source_tree_digest
from tools.project_config import load_config
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM, tooling_source_digest


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assembly-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    root, run = args.assembly_root.resolve(), args.run_root.resolve()
    project = root / "projects" / args.project
    config = load_config(root / "compliance.yaml", args.project)
    require(config.source == project / "compliance.yaml", "registry selected another project")
    require(config.schema == "compliance.example/project-config/v1alpha3", "predecessor project config")
    require("resourceSchema" not in config.paths, "project authored an inventory schema")
    parsed = build_parser(config).parse_args(["inventory", "validate"])
    require(parsed.resource_schema == root / "tooling/schemas/inventory/resource.schema.json",
            "inventory/assignment validation did not select executing tooling's schema")
    for key, relative in {"inventory": "inventory", "assignments": "assignments", "waivers": "waivers",
                          "evidence": "generated/evidence", "plan": "generated/plans",
                          "results": "generated/results"}.items():
        require(config.path(key) == project / relative, f"{key} escaped project isolation")
    names = ("control-library", "verification-policy")
    require({source.name: source.path for source in config.policy_sources} == {
        name: root / "policy-sources" / name / "policies" for name in names
    }, "named materialized sources changed")
    actual = {
        "tooling": {
            "source": {"digestAlgorithm": TOOLING_SOURCE_DIGEST_ALGORITHM,
                       "digest": tooling_source_digest(root / "tooling")},
            "execution": {"kind": "source"},
        },
        "policySources": [{"name": name, "content": {
            "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
            "digest": source_tree_digest(root / "policy-sources" / name / "policies"),
        }} for name in names],
    }
    opa = Path(shutil.which("opa")).resolve()
    version = subprocess.check_output([str(opa), "version"], text=True)
    evaluator = {
        "name": "opa",
        "version": next(line.split(": ", 1)[1] for line in version.splitlines() if line.startswith("Version: ")),
        "executableSha256": "sha256:" + hashlib.sha256(opa.read_bytes()).hexdigest(),
    }
    expected_subjects = {
        "mock-fleet": {"cloud-account/aws-111122223333", "cloud-account/aws-444455556666", "saas/acme-projects/company"},
        "server-personas": {"host/standard-app-01", "host/container-app-01", "host/persona-conflict-01"},
    }[args.project]
    plans = list((run / "plans").glob("*.json"))
    require({load(path)["subject"]["id"] for path in plans} == expected_subjects,
            "plan catalog crossed project boundaries or lost a subject")
    for plan_dir, result_dir, evidence_dir in (("plans", "results", "evidence"),
                                               ("unknown-plans", "unknown-results", "empty-evidence")):
        for path in (run / plan_dir).glob("*.json"):
            plan = load(path)
            require(plan["schema"] == "compliance.example/assessment-plan/v4", "predecessor plan")
            validate_assessment_plan(plan)
            planning = plan["provenance"]["planningComposition"]
            require(planning["actual"] == actual, "planning composition differs from materialized bytes")
            require(planning["enforcement"] == {"directExpectedContent": {}, "compositionLock": None},
                    "unlocked project claims expected enforcement")
            require(plan["requirements"] == [] and plan["resolved_requirement_baselines"] == [],
                    "technical-only project acquired authored objectives")
            result_path = run / result_dir / path.name
            if plan["resolution"]["status"] == "invalid":
                require(not result_path.exists(), "invalid plan produced a result")
                continue
            report = load(result_path)
            require(report["schema"] == "compliance.example/assessment-results/v4", "predecessor result")
            validate_assessment_results(report)
            validate_selection_plan(report, plan)
            provenance = report["provenance"]
            require(provenance["evaluationComposition"]["actual"] == actual,
                    "evaluation composition differs from materialized bytes")
            require(provenance["evaluationComposition"]["enforcement"] == planning["enforcement"],
                    "evaluation enforcement changed")
            require(provenance["evaluator"] == evaluator, "evaluator differs from executing OPA bytes/version")
            documents = [load(p) for p in (run / evidence_dir).glob("*.json")]
            documents = [doc for doc in documents if doc["subject"]["id"] == plan["subject"]["id"]]
            require(provenance["evidence"] == evidence_set_provenance(documents),
                    "complete subject evidence snapshot differs from collected documents")
            validate_selection_snapshot(report, documents)
            # These fixtures have one fresh document per required type; assert the
            # complete selection table, including plan association and collection time.
            expected_selections = []
            for control in plan["controls"]:
                for index, requirement in enumerate(control["evidence"]):
                    candidates = [doc for doc in documents if doc["type"] == requirement["type"]]
                    require(len(candidates) <= 1, "fixture no longer has unique required evidence")
                    for doc in candidates:
                        expected_selections.append({"instance_id": control["instance_id"],
                            "requirement_index": index, "requirement": requirement,
                            "id": doc["id"], "digest": evidence_document_digest(doc),
                            "collected_at": doc["collected_at"]})
            expected_selections.sort(key=lambda item: (item["instance_id"], item["requirement_index"]))
            require(provenance["selectedEvidence"] == expected_selections,
                    "successful selections lost exact document, time, or assessed requirement association")
            for field in ("requirement_assessments", "requirement_baseline_assessments"):
                require(report[field] == [], "technical-only result acquired objective assessments")
            for field in ("requirement_summary", "requirement_baseline_summary"):
                require(not any(report[field].values()), "technical-only result acquired objective roll-up")
    print(f"{args.project}: actual v4 composition, evaluator, evidence, and selection provenance passed.")


if __name__ == "__main__":
    main()
