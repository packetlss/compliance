#!/usr/bin/env python3
"""Run the synthetic examples for every public compliance CLI command."""

from __future__ import annotations

import argparse
import copy
import io
import json
import shlex
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Sequence

from tools.compliance import main as compliance_main
from tools.project_config import load_config
from tools.render_plan import (
    BaselineResolutionError,
    content_digest,
    load_inventory_inputs,
    render_plan,
    resolve_baseline,
)

try:
    from .prepare_policy_diff_set import prepare_demo
except ImportError:  # Direct execution by path.
    from prepare_policy_diff_set import prepare_demo


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
PROJECT_REGISTRY = WORKSPACE_ROOT / "compliance.yaml"
MOCK_COLLECTOR = WORKSPACE_ROOT / "tooling/collectors/mock-api/collect.py"
FEATURE_COVERAGE_PATH = Path(__file__).resolve().with_name("feature-coverage.json")
LINUX_ROLLOUT_ROOT = (
    WORKSPACE_ROOT
    / "verification/scenarios/projects/linux-hardening-rollout"
)
EXAMPLE_INSTANT = "2026-09-01T00:00:00Z"
MOCK_FLEET_PRIMARY_AWS_SUBJECT = "cloud-account/aws-111122223333"
MOCK_FLEET_SECONDARY_AWS_SUBJECT = "cloud-account/aws-444455556666"
MOCK_FLEET_AWS_SUBJECTS = frozenset(
    {MOCK_FLEET_PRIMARY_AWS_SUBJECT, MOCK_FLEET_SECONDARY_AWS_SUBJECT}
)

CLI_EXAMPLES = {
    ("config", "show"): "resolved project registry and project configuration",
    ("config", "validate"): "strict project registry and project validation",
    ("config", "list"): "project registry",
    ("inventory", "validate"): "resource schemas, references, and DAG",
    ("inventory", "list"): "subject, group, and assignment identities",
    ("inventory", "graph"): "multi-parent group hierarchy",
    ("inventory", "explain"): "subject membership and policy coverage",
    ("policy", "validate"): "policy schemas, pins, contracts, and Rego entrypoints",
    ("policy", "diff"): "stored subject-plan semantic comparison",
    ("policy", "diff-set"): "stored project-plan snapshot comparison",
    ("waiver", "validate"): "waiver schemas, windows, and overlaps",
    ("waiver", "list"): "deterministic waiver lifecycle view",
    ("waiver", "explain"): "one waiver and its approval provenance",
    ("plan", "render"): "immutable per-subject assessment plan",
    ("plan", "show"): "single-plan detail and multi-plan index",
    ("assessment", "run"): "off-subject OPA evaluation and immutable results",
    ("assessment", "status"): "fleet coverage and current evaluation state",
    ("assessment", "groups"): "overlapping resolved-group aggregation",
    ("assessment", "frameworks"): "objective and technical external mappings",
    ("assessment", "explain"): "joined policy, result, and waiver explanation",
}

DOMAIN_EXAMPLES = {
    "collector.mock-api": "typed evidence from deterministic API fixtures",
    "evidence.contracts": (
        "deterministic collector output and retained typed evidence contracts"
    ),
    "evidence.schema-enforcement": "invalid typed evidence fails its controls closed",
    "inventory.multi-parent-dag": "one subject resolved through multiple parents",
    "policy.multi-source-realization": "private realization over verification intent",
    "policy.control-implementations": "every reusable implementation appears in a plan",
    "policy.invalid-resolution": "conflicting assignments fail plan resolution closed",
    "policy.overlay-provenance": "tailor, annotate, add, exclude, and seal lineage",
    "policy.overlay-substitute": "equivalent implementation substitution freezes both sides",
    "policy.seal-enforcement": "lower overlays cannot change sealed controls",
    "waiver.application": "only an underlying failure becomes waived",
    "waiver.filters": "subject and lifecycle filters compose deterministically",
    "requirements.all-of": "technical decisions roll up conservatively",
    "requirements.realization-roll-up": (
        "selected realizations produce attributable objective and baseline results"
    ),
    "requirements.missing-evidence": (
        "missing technical evidence keeps objectives unknown"
    ),
    "assessment.framework-alignment": "tailored mappings remain distinct",
    "assessment.filters": (
        "group, outcome, plan-alignment, reference, and level filters are exact"
    ),
    "output.json-contracts": "machine-readable operator views carry versioned schemas",
}
EXAMPLE_COLLECTORS = {
    "mock-api": "automated",
}
EXAMPLE_EVIDENCE_TYPES = {
    "aws.account.configuration/v1": "automated",
    "aws.s3.account-public-access-block/v1": "automated",
    "linux.access.configuration/v1": "automated",
    "linux.packages/v1": "automated",
    "linux.sysctl/v1": "automated",
    "saas.tenant.configuration/v1": "automated",
    "macos.homebrew/v1": "synthetic-fixture",
    "macos.security/v1": "synthetic-fixture",
    "macos.system/v1": "synthetic-fixture",
}
EXAMPLE_OVERLAY_OPERATIONS = frozenset(
    ("tailor", "exclude", "substitute", "annotate", "add", "seal")
)
SHOW_SELECTIONS = frozenset(
    {
        "all",
        "collector",
        "evidence",
        "evidence.schema-enforcement",
        *(command[0] for command in CLI_EXAMPLES),
        *(".".join(command) for command in CLI_EXAMPLES),
    }
)


class ExampleFailure(RuntimeError):
    pass


def mock_fleet_inventory_contract_holds(
    validation_output: str,
    graph: str,
    explanation: str,
) -> bool:
    """Check stable mock-fleet inventory identities without coupling to its size."""
    return (
        "3 subject(s)" in validation_output
        and "cloud-services" in graph
        and "production-services" in graph
        and "aws-production-accounts" in graph
        and "aws-production-accounts" in explanation
    )


def mock_fleet_filter_contract_holds(
    filtered_status: dict,
    filtered_frameworks: dict,
    secondary_result: dict,
) -> bool:
    """Check exact failing AWS selection and the retained passing AWS case."""
    status_subjects = {
        subject.get("subject_id")
        for subject in filtered_status.get("subjects", [])
    }
    framework_mappings = filtered_frameworks.get("mappings", [])
    framework_subjects = {
        mapping.get("subject_id") for mapping in framework_mappings
    }
    return (
        filtered_status.get("filters") == {
            "groups": ["aws-production-accounts"],
            "outcomes": ["fail"],
            "plan_alignment": [],
        }
        and status_subjects == {MOCK_FLEET_PRIMARY_AWS_SUBJECT}
        and all(
            subject.get("historical_outcome") == "fail"
            for subject in filtered_status.get("subjects", [])
        )
        and secondary_result.get("subject_id") == MOCK_FLEET_SECONDARY_AWS_SUBJECT
        and secondary_result.get("summary") == {
            "pass": 5,
            "fail": 0,
            "unknown": 0,
            "not_applicable": 0,
            "error": 0,
            "waived": 0,
        }
        and filtered_frameworks.get("filters") == {
            "external_refs": ["CSA-CCM-v4.1:LOG-domain"],
            "groups": ["aws-production-accounts"],
            "levels": ["technical"],
            "outcomes": [],
            "plan_alignment": [],
        }
        and framework_subjects == MOCK_FLEET_AWS_SUBJECTS
        and all(
            mapping.get("external_ref") == "CSA-CCM-v4.1:LOG-domain"
            and mapping.get("mapping_level") == "technical"
            for mapping in framework_mappings
        )
    )


def validate_feature_coverage() -> dict:
    document = json.loads(FEATURE_COVERAGE_PATH.read_text(encoding="utf-8"))
    if document.get("schema") != "compliance.example/feature-coverage/v1alpha1":
        raise ExampleFailure("feature coverage catalog has an unsupported schema")
    scenarios = document.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        raise ExampleFailure("feature coverage catalog has no scenarios")

    owners: dict[str, str] = {}
    duplicates: list[str] = []
    for scenario_id, scenario in scenarios.items():
        if scenario.get("role") not in {
            "verification",
            "development",
            "boundary",
        }:
            raise ExampleFailure(f"feature scenario {scenario_id!r} has an invalid role")
        for feature in scenario.get("features", []):
            if feature in owners:
                duplicates.append(feature)
            owners[feature] = scenario_id

    expected = {
        *(f"cli.{'.'.join(command)}" for command in CLI_EXAMPLES),
        *DOMAIN_EXAMPLES,
    }
    actual = set(owners)
    if duplicates or actual != expected:
        raise ExampleFailure(
            "feature coverage catalog mismatch: "
            f"duplicates={sorted(set(duplicates))}, "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    return document


class ExampleRunner:
    def __init__(self, root: Path, *, show: set[str] | None = None):
        self.root = root
        self.show = show or set()
        self.cli_covered: set[tuple[str, str]] = set()
        self.domain_covered: set[str] = set()

    @staticmethod
    def _project(project: str) -> list[str]:
        return ["--config", str(PROJECT_REGISTRY), "--project", project]

    def _show_selected(self, feature: str) -> bool:
        family = feature.split(".", 1)[0]
        return bool({"all", family, feature} & self.show)

    def _display(self, feature: str, command: Sequence[str], output: str) -> None:
        if not self._show_selected(feature):
            return
        print(f"\nSHOW {feature}")
        print("$ " + shlex.join(command))
        print(output.rstrip() or "(no output)")

    def _pass(self, feature: str) -> None:
        if not self.show or self._show_selected(feature):
            print(f"PASS {feature}")

    def cli(
        self,
        command: tuple[str, str],
        arguments: Sequence[str],
        *,
        expected_exit: int = 0,
        contains: Sequence[str] = (),
    ) -> str:
        if command not in CLI_EXAMPLES:
            raise ExampleFailure(f"unregistered CLI example: {' '.join(command)}")
        stdout = io.StringIO()
        stderr = io.StringIO()
        exit_code = 0
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                compliance_main(list(arguments))
            except SystemExit as error:
                exit_code = error.code if isinstance(error.code, int) else 1
        output = stdout.getvalue() + stderr.getvalue()
        if exit_code != expected_exit:
            raise ExampleFailure(
                f"{' '.join(command)} exited {exit_code}, expected {expected_exit}\n"
                + output
            )
        missing = [fragment for fragment in contains if fragment not in output]
        if missing:
            raise ExampleFailure(
                f"{' '.join(command)} missing output {missing!r}\n" + output
            )
        self.cli_covered.add(command)
        self._pass(f"cli.{'.'.join(command)}")
        self._display(
            ".".join(command),
            ["compliance", *arguments],
            output,
        )
        return stdout.getvalue()

    def domain(self, feature: str, condition: bool, detail: str = "") -> None:
        if feature not in DOMAIN_EXAMPLES:
            raise ExampleFailure(f"unregistered domain example: {feature}")
        if not condition:
            raise ExampleFailure(f"{feature} failed: {detail}")
        self.domain_covered.add(feature)
        self._pass(feature)

    def collect(self, project: str, *, fixtures: Path | None = None) -> Path:
        evidence = self.root / project / "evidence"
        fixture_root = fixtures or (
            WORKSPACE_ROOT / f"compliance-project-{project}/fixtures"
        )
        command = [
            sys.executable,
            str(MOCK_COLLECTOR),
            str(fixture_root),
            str(evidence),
            "--collected-at",
            EXAMPLE_INSTANT,
        ]
        completed = subprocess.run(
            command,
            cwd=WORKSPACE_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise ExampleFailure(completed.stdout + completed.stderr)
        self.domain_covered.add("collector.mock-api")
        self._display(
            "collector.mock-api",
            command,
            completed.stdout + completed.stderr,
        )
        return evidence

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def verify_overlay_edges(self) -> None:
        output = self.root / "policy-overlays"
        output.mkdir(parents=True, exist_ok=True)
        base = {
            "apiVersion": "compliance.example/v1",
            "kind": "Baseline",
            "metadata": {"id": "example.base", "revision": 1},
            "spec": {
                "controls": [{
                    "instance_id": "example.setting",
                    "implementation": "example.setting-equals",
                    "parameters": {"expected": "strict"},
                }],
            },
        }

        def catalog_document(document: dict) -> dict:
            prepared = copy.deepcopy(document)
            prepared["_digest"] = content_digest(document)
            prepared["_source"] = "runnable-example"
            return prepared

        catalog = {"example.base@1": catalog_document(base)}
        base_control = resolve_baseline("example.base@1", catalog)["controls"][
            "example.setting"
        ]
        fingerprint = base_control["definition_fingerprint"]
        substitute = {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "example.substitute", "revision": 1},
            "spec": {
                "extends": [{
                    "baseline": "example.base@1",
                    "digest": catalog["example.base@1"]["_digest"],
                }],
                "operations": [{
                    "op": "substitute",
                    "target": "example.setting",
                    "expected_parent_fingerprint": fingerprint,
                    "implementation": "example.alternative-setting-equals",
                    "parameters": {"expected": "strict"},
                    "equivalence_ref": "example-review/EQUIV-001",
                }],
            },
        }
        catalog["example.substitute@1"] = catalog_document(substitute)
        substituted = resolve_baseline("example.substitute@1", catalog)["controls"][
            "example.setting"
        ]
        derivation = substituted["derivations"][0]
        self.domain(
            "policy.overlay-substitute",
            substituted["alignment"] == "substituted"
            and derivation["before"]["implementation"] == "example.setting-equals"
            and derivation["after"]["implementation"]
            == "example.alternative-setting-equals"
            and derivation["equivalence_ref"] == "example-review/EQUIV-001",
        )

        sealed = {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "example.sealed", "revision": 1},
            "spec": {
                "extends": [{
                    "baseline": "example.base@1",
                    "digest": catalog["example.base@1"]["_digest"],
                }],
                "operations": [{
                    "op": "seal",
                    "target": "example.setting",
                    "expected_parent_fingerprint": fingerprint,
                    "blocked_operations": ["tailor", "exclude", "substitute"],
                    "reason": "The example parent requires this exact criterion.",
                }],
            },
        }
        catalog["example.sealed@1"] = catalog_document(sealed)
        sealed_control = resolve_baseline("example.sealed@1", catalog)["controls"][
            "example.setting"
        ]
        blocked_child = {
            "apiVersion": "compliance.example/v1",
            "kind": "BaselineOverlay",
            "metadata": {"id": "example.blocked-child", "revision": 1},
            "spec": {
                "extends": [{
                    "baseline": "example.sealed@1",
                    "digest": catalog["example.sealed@1"]["_digest"],
                }],
                "operations": [{
                    "op": "tailor",
                    "target": "example.setting",
                    "expected_parent_fingerprint": sealed_control[
                        "definition_fingerprint"
                    ],
                    "parameters": {"expected": "weaker"},
                    "deviation": {
                        "id": "DEV-EXAMPLE-001",
                        "classification": "runnable-example",
                        "rationale": "Demonstrate that sealing rejects this change.",
                        "approval_ref": "example-approval/DEV-EXAMPLE-001",
                        "review_after": "2027-08-29",
                    },
                }],
            },
        }
        catalog["example.blocked-child@1"] = catalog_document(blocked_child)
        rejected = False
        try:
            resolve_baseline("example.blocked-child@1", catalog)
        except BaselineResolutionError as error:
            rejected = error.details["type"] == "sealed-control"
        self.domain("policy.seal-enforcement", rejected)

        for name, document in (
            ("base", base),
            ("substitute", substitute),
            ("sealed", sealed),
            ("blocked-child", blocked_child),
        ):
            (output / f"{name}.json").write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def run(self) -> None:
        validate_feature_coverage()
        mock = self._project("mock-fleet")
        iam = self._project("iam-realization")
        rollout = self._project("linux-hardening-rollout")

        self.cli(
            ("config", "show"),
            [*mock, "config", "show", "--format", "json"],
            contains=('"project": "mock-fleet"',),
        )
        self.cli(
            ("config", "validate"),
            [*rollout, "config", "validate"],
            contains=("valid project registry", "project linux-hardening-rollout"),
        )
        self.cli(
            ("config", "list"),
            [
                "--config", str(PROJECT_REGISTRY),
                "--project", "mock-fleet",
                "config", "list",
            ],
            contains=("mock-fleet", "iam-realization", "linux-hardening-rollout"),
        )

        self.cli(
            ("inventory", "validate"),
            [*rollout, "inventory", "validate"],
            contains=("3 subject(s)", "4 assignment(s)"),
        )

        mock_inventory_validation = self.cli(
            ("inventory", "validate"),
            [*mock, "inventory", "validate"],
            contains=("3 subject(s)",),
        )
        for resource in ("subjects", "groups", "assignments"):
            self.cli(
                ("inventory", "list"),
                [*mock, "inventory", "list", resource],
            )
        graph = self.cli(
            ("inventory", "graph"),
            [*mock, "inventory", "graph"],
            contains=("aws-production-accounts", "production-services"),
        )
        explanation = self.cli(
            ("inventory", "explain"),
            [*mock, "inventory", "explain", "cloud-account/aws-111122223333"],
            contains=("Resolved groups", "Policy assignments"),
        )
        self.domain(
            "inventory.multi-parent-dag",
            mock_fleet_inventory_contract_holds(
                mock_inventory_validation,
                graph,
                explanation,
            ),
        )

        self.cli(
            ("policy", "validate"),
            [*rollout, "policy", "validate"],
            contains=("4 realization(s)", "13 control manifest(s)"),
        )
        self.cli(
            ("policy", "validate"),
            [*iam, "policy", "validate"],
            contains=("6 realization(s)", "13 control manifest(s)"),
        )
        self.domain("policy.multi-source-realization", True)
        self.verify_overlay_edges()

        self.cli(
            ("waiver", "validate"),
            [*rollout, "waiver", "validate"],
            contains=("valid waiver catalog",),
        )
        self.cli(
            ("waiver", "list"),
            [
                *rollout,
                "waiver",
                "list",
                "--at",
                "2026-09-01T00:00:00Z",
            ],
            contains=("ACTIVE", "standard-app-01-auditd-rollout"),
        )
        self.cli(
            ("waiver", "explain"),
            [
                *rollout,
                "waiver",
                "explain",
                "standard-app-01-auditd-rollout",
                "--at",
                "2026-09-01T00:00:00Z",
            ],
            contains=("risk-acceptance/RA-2026-042", "security-risk-owner"),
        )
        waiver_json = self.cli(
            ("waiver", "list"),
            [
                *rollout,
                "waiver",
                "list",
                "--at",
                "2026-09-01T00:00:00Z",
                "--subject",
                "host/standard-app-01",
                "--state",
                "active",
                "--format",
                "json",
            ],
        )
        waiver_document = json.loads(waiver_json)
        self.domain(
            "waiver.filters",
            waiver_document["summary"]["active"] == 1
            and len(waiver_document["waivers"]) == 1,
        )
        self.domain(
            "output.json-contracts",
            waiver_document["schema"]
            == "compliance.example/waiver-catalog/v1alpha1",
        )

        mock_evidence = self.collect("mock-fleet")
        iam_evidence = self.collect("iam-realization")
        rollout_evidence = self.collect(
            "linux-hardening-rollout",
            fixtures=LINUX_ROLLOUT_ROOT / "fixtures",
        )
        self.domain(
            "collector.mock-api",
            all(path.is_dir() and any(path.glob("*.json")) for path in (
                mock_evidence,
                iam_evidence,
                rollout_evidence,
            ))
            and all(
                self._read(path)["collected_at"] == EXAMPLE_INSTANT
                for evidence_root in (
                    mock_evidence,
                    iam_evidence,
                    rollout_evidence,
                )
                for path in evidence_root.glob("*.json")
            ),
        )
        emitted_evidence_types = {
            self._read(path)["type"]
            for evidence_root in (
                mock_evidence,
                iam_evidence,
                rollout_evidence,
            )
            for path in evidence_root.glob("*.json")
        }
        self.domain(
            "evidence.contracts",
            emitted_evidence_types
            == {
                evidence_type
                for evidence_type, mode in EXAMPLE_EVIDENCE_TYPES.items()
                if mode == "automated"
            },
            f"emitted {sorted(emitted_evidence_types)}",
        )

        mock_plans = self.root / "mock-fleet/plans"
        for subject_id in (
            "cloud-account/aws-111122223333",
            "cloud-account/aws-444455556666",
            "saas/acme-projects/company",
        ):
            self.cli(
                ("plan", "render"),
                [*mock, "plan", "render", subject_id, "--output", str(mock_plans)],
                contains=("wrote sha256:",),
            )

        rollout_plans = self.root / "linux-hardening-rollout/plans"
        for subject_id in (
            "host/standard-app-01",
            "host/container-app-01",
            "host/persona-conflict-01",
        ):
            self.cli(
                ("plan", "render"),
                [
                    *rollout,
                    "plan",
                    "render",
                    subject_id,
                    "--output",
                    str(rollout_plans),
                ],
            )
        self.cli(
            ("plan", "show"),
            [*rollout, "plan", "show", str(rollout_plans)],
            contains=("Assessment plans (3)",),
        )

        invalid_plan = rollout_plans / "host__persona-conflict-01.json"
        self.domain(
            "policy.invalid-resolution",
            self._read(invalid_plan)["resolution"]["status"] == "invalid",
        )

        # The tooling-owned macOS fixture preserves semantic overlay-lineage
        # coverage without coupling the executable suite to a boundary project.
        macos_fixture = WORKSPACE_ROOT / "tooling/tests/fixtures/macos-project"
        mock_config = load_config(PROJECT_REGISTRY, "mock-fleet")
        macos_subject, macos_groups, macos_assignments = load_inventory_inputs(
            macos_fixture / "inventory",
            macos_fixture / "assignments",
            "workstation/tooling-macos-fixture",
            WORKSPACE_ROOT / "tooling/schemas/inventory/resource.schema.json",
        )
        macos_document = render_plan(
            macos_subject,
            macos_groups,
            macos_assignments,
            mock_config.policy_sources,
        )
        macos_plan = self.root / "macos-fixture/plan.json"
        macos_plan.parent.mkdir(parents=True, exist_ok=True)
        macos_plan.write_text(
            json.dumps(macos_document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        macos_operations = {
            step["operation"]
            for control in [
                *self._read(macos_plan)["controls"],
                *self._read(macos_plan)["excluded_controls"],
            ]
            for step in control["lineage"]
        }
        mock_plan = self._read(
            mock_plans / "cloud-account__aws-111122223333.json"
        )
        mock_operations = {
            step["operation"]
            for control in [
                *mock_plan["controls"],
                *mock_plan["excluded_controls"],
            ]
            for step in control["lineage"]
        }
        self.domain(
            "policy.overlay-provenance",
            (EXAMPLE_OVERLAY_OPERATIONS - {"substitute"})
            <= macos_operations | mock_operations,
            f"observed {sorted(macos_operations | mock_operations)}",
        )

        mock_results = self.root / "mock-fleet/results"

        invalid_evidence = self.root / "evidence-schema/evidence"
        invalid_evidence.mkdir(parents=True, exist_ok=True)
        invalid_path: Path | None = None
        for path in mock_evidence.glob("*.json"):
            document = self._read(path)
            if (
                document["subject"]["id"] == "cloud-account/aws-111122223333"
                and document["type"] == "aws.account.configuration/v1"
            ):
                document["payload"]["account"]["id"] = "not-an-account-id"
                invalid_path = invalid_evidence / path.name
            (invalid_evidence / path.name).write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if invalid_path is None:
            raise ExampleFailure("AWS evidence fixture was not available to invalidate")

        schema_plan = self.root / "evidence-schema/plan.json"
        schema_result = self.root / "evidence-schema/result.json"
        schema_arguments = [
            *mock,
            "assessment",
            "run",
            "cloud-account/aws-111122223333",
            "--evidence",
            str(invalid_evidence),
            "--plan-output",
            str(schema_plan),
            "--output",
            str(schema_result),
            "--at",
            EXAMPLE_INSTANT,
        ]
        self.cli(("assessment", "run"), schema_arguments)
        schema_document = self._read(schema_result)
        schema_errors = [
            result for result in schema_document["results"]
            if result["observed"].get("evidence_validation_errors")
        ]
        self.domain(
            "evidence.schema-enforcement",
            bool(schema_errors)
            and all(
                result["observed"].get("evidence_validation_errors")
                for result in schema_errors
            )
            and all(result["status"] == "unknown" for result in schema_errors),
        )
        self._display(
            "evidence.schema-enforcement",
            ["compliance", *schema_arguments],
            json.dumps(
                {
                    "summary": schema_document["summary"],
                    "schema_errors": schema_errors,
                },
                indent=2,
                sort_keys=True,
            ),
        )

        for subject_id in (
            "cloud-account/aws-111122223333",
            "cloud-account/aws-444455556666",
            "saas/acme-projects/company",
        ):
            self.cli(
                ("assessment", "run"),
                [
                    *mock,
                    "assessment",
                    "run",
                    subject_id,
                    "--evidence",
                    str(mock_evidence),
                    "--plan-output",
                    str(mock_plans),
                    "--output",
                    str(mock_results),
                    "--at",
                    EXAMPLE_INSTANT,
                ],
                contains=("control result(s)",),
            )
        self.cli(
            ("assessment", "status"),
            [*mock, "assessment", "status", "--results", str(mock_results)],
            contains=("cloud-account/aws-111122223333", "saas/acme-projects/company"),
        )
        filtered_status_json = self.cli(
            ("assessment", "status"),
            [
                *mock,
                "assessment",
                "status",
                "--results",
                str(mock_results),
                "--group",
                "aws-production-accounts",
                "--outcome",
                "fail",
                "--format",
                "json",
            ],
        )
        filtered_status = json.loads(filtered_status_json)
        self.cli(
            ("assessment", "groups"),
            [*mock, "assessment", "groups", "--results", str(mock_results)],
            contains=("aws-production-accounts",),
        )
        frameworks = self.cli(
            ("assessment", "frameworks"),
            [*mock, "assessment", "frameworks", "--results", str(mock_results)],
            contains=("CSA-CCM-v4.1", "TAILORED"),
        )
        self.domain(
            "assessment.framework-alignment",
            "TAILORED" in frameworks and "UNALTERED" in frameworks,
        )
        filtered_frameworks = self.cli(
            ("assessment", "frameworks"),
            [
                *mock,
                "assessment",
                "frameworks",
                "--results",
                str(mock_results),
                "--group",
                "aws-production-accounts",
                "--reference",
                "CSA-CCM-v4.1:LOG-domain",
                "--level",
                "technical",
                "--format",
                "json",
            ],
        )
        filtered_framework_document = json.loads(filtered_frameworks)
        secondary_result = self._read(
            mock_results / "cloud-account__aws-444455556666.json"
        )
        self.domain(
            "assessment.filters",
            mock_fleet_filter_contract_holds(
                filtered_status,
                filtered_framework_document,
                secondary_result,
            ),
        )
        self.domain(
            "output.json-contracts",
            filtered_status["schema"] == "compliance.example/assessment-status/v1"
            and filtered_framework_document["schema"]
            == "compliance.example/framework-mapping-status/v1alpha1",
        )
        self.cli(
            ("assessment", "explain"),
            [
                *mock,
                "assessment",
                "explain",
                "cloud-account/aws-111122223333",
                "--results",
                str(mock_results),
            ],
            contains=("Active controls", "remediation:"),
        )

        iam_plans = self.root / "iam-realization/plans"
        iam_results = self.root / "iam-realization/results"
        self.cli(
            ("assessment", "run"),
            [
                *iam,
                "assessment",
                "run",
                "host/restricted-linux-01",
                "--evidence",
                str(iam_evidence),
                "--plan-output",
                str(iam_plans),
                "--output",
                str(iam_results),
                "--at",
                EXAMPLE_INSTANT,
            ],
        )
        iam_report = next(iam_results.glob("*.json"))
        iam_document = self._read(iam_report)
        iam_requirement = iam_document["requirement_assessments"][0]
        self.domain(
            "requirements.all-of",
            len(iam_document["requirement_assessments"]) == 1
            and iam_requirement["status"] == "fail"
            and iam_document["requirement_baseline_assessments"][0]["status"]
            == "fail",
        )
        self.domain(
            "requirements.realization-roll-up",
            iam_requirement["adoption"]["status"] == "implemented"
            and "realization" in iam_requirement
            and iam_requirement["check_summary"]["pass"] == 3
            and iam_requirement["check_summary"]["fail"] == 1
            and iam_document["requirement_baseline_assessments"][0]["requirements"]
            == [{"requirement": iam_requirement["requirement"], "status": "fail"}],
        )

        rollout_results = self.root / "linux-hardening-rollout/results"
        self.cli(
            ("assessment", "run"),
            [
                *rollout,
                "assessment",
                "run",
                "host/standard-app-01",
                "--evidence",
                str(rollout_evidence),
                "--plan-output",
                str(rollout_plans),
                "--output",
                str(rollout_results),
                "--at",
                EXAMPLE_INSTANT,
            ],
        )
        standard_document = self._read(
            rollout_results / "host__standard-app-01.json"
        )
        self.domain(
            "waiver.application",
            standard_document["summary"] == {
                "pass": 2,
                "fail": 0,
                "unknown": 4,
                "not_applicable": 0,
                "error": 0,
                "waived": 1,
            }
            and standard_document["evaluated_at"] == EXAMPLE_INSTANT
            and standard_document["requirement_summary"]["unknown"] == 1
            and any(
                result["status"] == "waived"
                and result["waiver"]["id"] == "standard-app-01-auditd-rollout"
                and result["waiver"]["underlying_status"] == "fail"
                for result in standard_document["results"]
            ),
        )
        self.domain(
            "requirements.missing-evidence",
            standard_document["requirement_summary"]["unknown"] == 1
            and standard_document["requirement_baseline_summary"]["unknown"] == 1
            and sum(
                result["status"] == "unknown"
                for result in standard_document["results"]
            ) == 4,
        )

        self.cli(
            ("assessment", "run"),
            [
                *rollout,
                "assessment",
                "run",
                "host/container-app-01",
                "--evidence",
                str(rollout_evidence),
                "--plan-output",
                str(rollout_plans),
                "--output",
                str(rollout_results),
                "--at",
                EXAMPLE_INSTANT,
            ],
        )
        container_document = self._read(
            rollout_results / "host__container-app-01.json"
        )
        self.domain(
            "requirements.all-of",
            container_document["summary"]["pass"] == 8
            and container_document["requirement_summary"]["pass"] == 1
            and container_document["requirement_baseline_summary"]["pass"] == 1
            and iam_document["requirement_assessments"][0]["status"] == "fail",
        )
        self.cli(
            ("assessment", "explain"),
            [
                *rollout,
                "assessment",
                "explain",
                "host/standard-app-01",
                "--results",
                str(rollout_results),
            ],
            contains=(
                "Control objectives:",
                "company.iam.role-based-access@1",
                "waiver: standard-app-01-auditd-rollout",
            ),
        )

        diff_root = self.root / "policy-diff"
        diff_pairs = prepare_demo(diff_root)
        changed_before = (
            diff_pairs["changed"][0] / "cloud-account__aws-111122223333.json"
        )
        changed_after = (
            diff_pairs["changed"][1] / "cloud-account__aws-111122223333.json"
        )
        self.cli(
            ("policy", "diff"),
            [
                "--no-config",
                "policy",
                "diff",
                str(changed_before),
                str(changed_after),
            ],
            expected_exit=1,
            contains=("EFFECTIVE POLICY CHANGED", "remediation"),
        )
        for name, expected_exit in (("unchanged", 0), ("changed", 1), ("incomplete", 2)):
            before, after = diff_pairs[name]
            self.cli(
                ("policy", "diff-set"),
                ["--no-config", "policy", "diff-set", str(before), str(after)],
                expected_exit=expected_exit,
                contains=("Policy plan-set diff",),
            )

        self.cli(
            ("plan", "render"),
            ["--config", str(WORKSPACE_ROOT / "verification/scenarios/projects/technical-only-packages/compliance.yaml"),
             "plan", "render", "host/technical-A", "--output", str(self.root / "technical-only-plans")],
        )
        self.cli(
            ("plan", "render"),
            ["--config", str(WORKSPACE_ROOT / "verification/scenarios/projects/company-iam-policy-assessment/compliance.yaml"),
             "plan", "render", "host/A", "--output", str(self.root / "company-iam-plans")],
        )
        focused = self.root / "organization-assertion-plan-input"
        for name in ("inventory", "assignments", "waivers"):
            (focused / name).mkdir(parents=True)
        (focused / "compliance.json").write_text(json.dumps({
            "schema": "compliance.example/project-config/v1alpha3",
            "policySources": [
                {"name": "control-library", "path": str(WORKSPACE_ROOT / "policy-sources/control-library/policies")},
                {"name": "verification-policy", "path": str(WORKSPACE_ROOT / "policy-sources/verification-policy/policies")},
            ],
            "paths": {"inventory":"inventory", "assignments":"assignments", "evidence":"evidence",
                      "plan":"plans", "results":"results", "waivers":"waivers"},
        }))
        (focused / "inventory/entity.json").write_text(json.dumps({
            "apiVersion":"compliance.example/v1alpha1", "kind":"Subject",
            "metadata":{"name":"focused-entity", "labels":{"operation-profile":"synthetic"}},
            "spec":{"id":"entity/focused", "type":"entity", "lifecycle":"active",
                    "source":{"name":"synthetic-inventory", "externalId":"entity/focused", "observedAt":EXAMPLE_INSTANT}},
        }))
        (focused / "inventory/group.json").write_text(json.dumps({
            "apiVersion":"compliance.example/v1alpha1", "kind":"InventoryGroup", "metadata":{"name":"focused-entities"},
            "spec":{"subjectRefs":[{"id":"entity/focused"}]},
        }))
        (focused / "assignments/policy.json").write_text(json.dumps({
            "apiVersion":"compliance.example/v1alpha1", "kind":"PolicyAssignment", "metadata":{"name":"focused-assertion"},
            "spec":{"targetRef":{"kind":"InventoryGroup", "name":"focused-entities"},
                    "baselineRefs":[{"name":"verification.operation.entity", "revision":"1"}]},
        }))
        self.cli(
            ("plan", "render"),
            ["--config", str(focused / "compliance.json"), "plan", "render", "entity/focused",
             "--output", str(self.root / "organization-assertion-plans")],
        )
        declared_implementations = {
            self._read(path)["metadata"]["id"]
            for path in (
                WORKSPACE_ROOT / "policy-sources/control-library/policies/controls"
            ).glob("**/control.json")
        }
        planned_implementations: set[str] = set()
        for path in self.root.glob("**/*.json"):
            try:
                document = self._read(path)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if document.get("schema") != "compliance.example/assessment-plan/v4":
                continue
            planned_implementations.update(
                control["implementation"]
                for control in [
                    *document["controls"],
                    *document["excluded_controls"],
                ]
            )
        self.domain(
            "policy.control-implementations",
            planned_implementations == declared_implementations,
            "missing "
            + ", ".join(sorted(declared_implementations - planned_implementations)),
        )

        missing_cli = sorted(set(CLI_EXAMPLES) - self.cli_covered)
        missing_domain = sorted(set(DOMAIN_EXAMPLES) - self.domain_covered)
        if missing_cli or missing_domain:
            raise ExampleFailure(
                f"unverified examples: CLI={missing_cli}, domain={missing_domain}"
            )
        print(
            f"\nVerified {len(self.cli_covered)} CLI commands and "
            f"{len(self.domain_covered)} domain features."
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="empty directory in which to retain generated example artifacts",
    )
    parser.add_argument(
        "--show",
        action="append",
        default=[],
        metavar="FEATURE",
        help=(
            "print captured output for a command family or exact command; "
            "repeatable, and accepts 'all'"
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list valid --show selections and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list:
        print("Available --show selections:")
        for selection in sorted(SHOW_SELECTIONS):
            print("  " + selection)
        return
    unknown = sorted(set(args.show) - SHOW_SELECTIONS)
    if unknown:
        parser.error(
            "unknown --show selection(s): " + ", ".join(unknown)
            + "; use --list to inspect valid selections"
        )
    if args.output is not None:
        output = args.output.resolve()
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise SystemExit(f"example output must be an empty directory: {output}")
        output.mkdir(parents=True, exist_ok=True)
        ExampleRunner(output, show=set(args.show)).run()
        print(f"Retained example artifacts under {output}")
        return
    with tempfile.TemporaryDirectory(prefix="compliance-examples-") as temporary:
        ExampleRunner(Path(temporary), show=set(args.show)).run()


if __name__ == "__main__":
    main()
