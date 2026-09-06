"""Small, synthetic inputs for tooling contracts; no external repository data.

Each test class gets a disposable tree. Schemas here exercise the generic schema
reader, not the reusable library's schema definitions (owned by its own gate).
"""

import copy
import json
import shutil
import tempfile
from pathlib import Path

from tools.render_plan import content_digest, control_definition_fingerprint

TOOLING = Path(__file__).resolve().parents[1]
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def write(root, path, value):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


def resource(kind, identifier, spec, revision=1):
    return {
        "apiVersion": "compliance.example/v1",
        "kind": kind,
        "metadata": {"id": identifier, "revision": revision},
        "spec": spec,
    }


def instance(identifier, implementation, parameters, **extra):
    return {
        "instance_id": identifier,
        "implementation": implementation,
        "parameters": parameters,
        "evidence": {"observation": {"max_age": "1d"}},
        **extra,
    }


def fixture_root(test):
    temporary = tempfile.TemporaryDirectory(prefix="tooling-contract-")
    cleanup = test.addClassCleanup if isinstance(test, type) else test.addCleanup
    cleanup(temporary.cleanup)
    root = Path(temporary.name).resolve()
    build_fixture(root)
    return root


def build_fixture(root):
    shared = root / "shared"
    selection = root / "selection"
    private = root / "iam/policy"
    for directory in (shared, selection, private):
        directory.mkdir(parents=True)
    shutil.copytree(TOOLING / "schemas", root / "schemas")
    control_instance = {
        "type": "object",
        "required": ["instance_id", "implementation"],
        "properties": {
            "instance_id": {"type": "string"},
            "implementation": {"type": "string"},
        },
    }
    specs = {
        "control": {
            "type": "object",
            "required": ["entrypoint", "parameters_schema", "applies_to", "evidence"],
        },
        "baseline": {
            "type": "object",
            "required": ["controls"],
            "properties": {"controls": {"type": "array", "items": control_instance}},
        },
        "baseline-overlay": {
            "type": "object",
            "required": ["extends", "operations"],
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "allOf": [
                            {
                                "if": {
                                    "properties": {
                                        "op": {"enum": ["tailor", "exclude"]}
                                    }
                                },
                                "then": {"required": ["deviation"]},
                            }
                        ],
                    },
                }
            },
        },
        "control-requirement": {"type": "object", "required": ["title"]},
        "requirement-baseline": {"type": "object", "required": ["requirements"]},
        "control-realization": {
            "type": "object",
            "required": ["requirement", "applies_to", "adoption"],
        },
    }
    for name, spec in specs.items():
        write(
            shared,
            f"schemas/policy/{name}.schema.json",
            {
                "$schema": DRAFT,
                "type": "object",
                "required": ["apiVersion", "kind", "metadata", "spec"],
                "properties": {
                    "metadata": {"type": "object", "required": ["id"]},
                    "spec": spec,
                },
            },
        )
    for kind in ("linux-host", "macos-workstation", "aws-account"):
        write(
            shared,
            f"schemas/evidence/{kind}.schema.json",
            {
                "$schema": DRAFT,
                "type": "object",
                "properties": {
                    "type": {"const": f"test.{kind}/v1"},
                    "subject": {"properties": {"type": {"const": kind}}},
                },
            },
        )
    controls = [
        (
            "macos/security-setting-equals",
            "macos.security.setting_equals",
            {"setting": {"type": "string"}, "expected": {}},
            ["setting", "expected"],
        ),
        (
            "macos/minimum-version",
            "macos.system.minimum_version",
            {"minimum": {"type": "string"}},
            ["minimum"],
        ),
        (
            "macos/packages",
            "macos.packages.required",
            {"required": {"type": "array"}},
            ["required"],
        ),
        (
            "linux/packages",
            "linux.packages.required",
            {"ecosystem": {"type": "string"}, "required": {"type": "array"}},
            ["ecosystem", "required"],
        ),
        (
            "linux/sysctl",
            "linux.sysctl.values",
            {"settings": {"type": "array"}},
            ["settings"],
        ),
        (
            "aws/block",
            "aws.s3.account_public_access_block",
            {
                "block_public_acls": {"type": "boolean"},
                "block_public_policy": {"type": "boolean"},
                "ignore_public_acls": {"type": "boolean"},
                "restrict_public_buckets": {"type": "boolean"},
            },
            [],
        ),
        (
            "test/minimum",
            "test.minimum",
            {"minimum": {"type": "integer"}},
            ["minimum"],
        ),
    ]
    for path, identifier, properties, required in controls:
        kind = (
            "macos-workstation"
            if path.startswith("macos/")
            else "aws-account"
            if path.startswith("aws/")
            else "linux-host"
        )
        spec = {
            "entrypoint": "data.test.contract.evaluate",
            "applies_to": [kind],
            "evidence": [
                {"id": "observation", "type": f"test.{kind}/v1"}
            ],
            "parameters_schema": "parameters.schema.json",
            "severity": "medium",
            "remediation": "Apply the synthetic test setting.",
        }
        write(
            shared,
            f"controls/{path}/control.json",
            resource("Control", identifier, spec),
        )
        write(
            shared,
            f"controls/{path}/parameters.schema.json",
            {
                "$schema": DRAFT,
                "type": "object",
                "properties": properties,
                "required": required,
            },
        )
    (shared / "controls/test/policy.rego").write_text(
        "package test.contract\nimport rego.v1\nevaluate := true\n"
    )

    def baseline(path, identifier, controls, revision=1):
        return write(
            selection,
            path,
            resource("Baseline", identifier, {"controls": controls}, revision),
        )

    def overlay(path, identifier, parent, operations):
        return write(
            selection,
            path,
            resource(
                "BaselineOverlay",
                identifier,
                {
                    "extends": [
                        {
                            "baseline": f"{parent['metadata']['id']}@{parent['metadata']['revision']}",
                            "digest": content_digest(parent),
                        }
                    ],
                    "operations": operations,
                },
            ),
        )

    def operation(op, control, number, **extra):
        return {
            "op": op,
            "target": control["instance_id"],
            "expected_parent_fingerprint": control_definition_fingerprint(control),
            "deviation": {
                "id": f"DEV-MAC-{number:03}",
                "classification": "support-policy",
                "rationale": "Synthetic fixture parameter adjustment.",
                "approval_ref": "test/approval",
                "review_after": "2027-01-31",
            },
            **extra,
        }

    minimum = instance(
        "test.macos.minimum",
        "macos.system.minimum_version",
        {"minimum": "26.6.0"},
        external_refs=["TEST:retention"],
    )
    optional = instance(
        "benchmark.example.macos.audit-formula-required",
        "macos.packages.required",
        {"required": ["example-audit-tool"]},
    )
    upstream = baseline(
        "baselines/upstream.json",
        "benchmark.example.macos-hardening",
        [minimum, optional],
        "2026.1",
    )
    overlay(
        "baselines/company/macos.json",
        "company.macos-policy",
        upstream,
        [
            operation("tailor", minimum, 1, parameters={"minimum": "26.0.0"}),
            operation("exclude", optional, 2),
        ],
    )
    baseline(
        "baselines/managed-workstation.json",
        "managed-workstation",
        [
            instance(
                "test.macos.setting",
                "macos.security.setting_equals",
                {"setting": "test", "expected": True},
            )
        ],
    )
    baseline(
        "baselines/developer.json",
        "company.developer-workstation",
        [
            instance(
                "developer.macos.shellcheck-required",
                "macos.packages.required",
                {"required": ["shellcheck"]},
            )
        ],
    )
    count = instance(
        "csa-ccm.aws.audit-log-retention",
        "test.minimum",
        {"minimum": 1},
        external_refs=["TEST:retention"],
    )
    upstream_count = baseline("baselines/count.json", "test.count", [count])
    overlay(
        "baselines/company/company-aws-foundation.json",
        "company.aws-foundation",
        upstream_count,
        [operation("tailor", count, 3, parameters={"minimum": 2})],
    )
    packages = [
        instance(
            "test.packages.base",
            "linux.packages.required",
            {"ecosystem": "linux-native", "required": [{"id": "curl"}, {"id": "git"}]},
        ),
        instance(
            "test.packages.extra",
            "linux.packages.required",
            {"ecosystem": "linux-native", "required": [{"id": "git"}, {"id": "jq"}]},
        ),
        instance(
            "test.sysctl.base",
            "linux.sysctl.values",
            {"settings": [{"key": "net.ipv4.ip_forward", "value": "0"}]},
        ),
    ]
    baseline("baselines/linux.json", "test.linux", packages)
    baseline(
        "baselines/conflict.json",
        "test.conflict",
        [
            instance(
                "test.sysctl.other",
                "linux.sysctl.values",
                {"settings": [{"key": "net.ipv4.ip_forward", "value": "1"}]},
            )
        ],
    )
    aws_parameters = dict.fromkeys(
        (
            "block_public_acls",
            "block_public_policy",
            "ignore_public_acls",
            "restrict_public_buckets",
        ),
        True,
    )
    baseline(
        "baselines/cloud.json",
        "test.cloud",
        [
            instance(
                "test.cloud.base",
                "aws.s3.account_public_access_block",
                aws_parameters,
                external_refs=["TEST:cloud"],
            )
        ],
    )
    baseline(
        "baselines/cloud-conflict.json",
        "test.cloud-conflict",
        [
            instance(
                "test.cloud.other",
                "aws.s3.account_public_access_block",
                {**aws_parameters, "block_public_policy": False},
            )
        ],
    )

    requirement = write(
        selection,
        "requirements/company/company-role-based-access.json",
        resource(
            "ControlRequirement",
            "company.iam.role-based-access",
            {
                "title": "Synthetic access requirement",
                "statement": "A synthetic all-of requirement.",
                "external_refs": ["TEST:access"],
            },
        ),
    )
    pin = {
        "requirement": "company.iam.role-based-access@1",
        "digest": content_digest(requirement),
    }
    write(
        selection,
        "requirement-baselines/company/company-iam-baseline.json",
        resource(
            "RequirementBaseline",
            "test.iam",
            {
                "title": "Synthetic requirement baseline",
                "requirements": [{**pin, "required": True}],
            },
        ),
    )
    checks = [
        instance(f"test.access.{index}", "test.minimum", {"minimum": index})
        for index in range(4)
    ]
    realization = resource(
        "ControlRealization",
        "company.linux.central-role-access",
        {
            "requirement": pin,
            "applies_to": {
                "subject_types": ["linux-host"],
                "match_labels": {"iam-profile": "company-linux"},
            },
            "adoption": {
                "status": "implemented",
                "method": "automated",
                "owner": "test",
            },
            "checks": checks,
            "satisfaction": {"allOf": [check["instance_id"] for check in checks]},
        },
    )
    realization["metadata"]["classification"] = "internal"
    write(
        selection,
        "realizations/company/company-linux-role-based-access.json",
        realization,
    )
    restricted = copy.deepcopy(realization)
    restricted["metadata"]["id"] = "restricted.linux.central-role-access"
    restricted["spec"]["applies_to"]["match_labels"] = {
        "iam-profile": "restricted-linux"
    }
    restricted["spec"]["based_on"] = {
        "realization": "company.linux.central-role-access@1",
        "digest": content_digest(realization),
    }
    write(
        private,
        "realizations/restricted/restricted-linux-role-based-access.json",
        restricted,
    )

    def inventory_resource(kind, name, spec, labels=None):
        return {
            "apiVersion": "compliance.example/v1alpha1",
            "kind": kind,
            "metadata": {"name": name, **({"labels": labels} if labels else {})},
            "spec": spec,
        }

    def subject(project, identifier, kind, labels=None, attributes=None):
        return write(
            root,
            f"{project}/inventory/{identifier.split('/')[-1]}.json",
            inventory_resource(
                "Subject",
                identifier.split("/")[-1],
                {
                    "id": identifier,
                    "type": kind,
                    "lifecycle": "active",
                    "source": {
                        "name": "tooling-unit-test",
                        "externalId": identifier,
                        "observedAt": "2026-08-28T12:00:00Z",
                    },
                    **({"attributes": attributes} if attributes else {}),
                },
                labels,
            ),
        )

    def group(project, name, subjects):
        write(
            root,
            f"{project}/inventory/group-{name}.json",
            inventory_resource(
                "InventoryGroup",
                name,
                {"subjectRefs": [{"id": value} for value in subjects]},
            ),
        )

    def assignment(project, name, group_name, baseline_name):
        write(
            root,
            f"{project}/assignments/{name}.json",
            inventory_resource(
                "PolicyAssignment",
                name,
                {
                    "targetRef": {"kind": "InventoryGroup", "name": group_name},
                    "baselineRefs": [{"name": baseline_name, "revision": "1"}],
                },
            ),
        )

    for name in ("host/configuration-linux-01", "host/configuration-linux-conflict-01"):
        subject("linux", name, "linux-host")
    group(
        "linux",
        "all",
        ["host/configuration-linux-01", "host/configuration-linux-conflict-01"],
    )
    group("linux", "conflict", ["host/configuration-linux-conflict-01"])
    assignment("linux", "linux-configuration-demo", "all", "test.linux")
    assignment("linux", "conflict", "conflict", "test.conflict")
    for identifier in ("111122223333", "444455556666"):
        subject(
            "cloud",
            "cloud-account/aws-" + identifier,
            "aws-account",
            attributes={"accountId": identifier},
        )
    group(
        "cloud",
        "all",
        ["cloud-account/aws-111122223333", "cloud-account/aws-444455556666"],
    )
    group("cloud", "conflict", ["cloud-account/aws-444455556666"])
    assignment("cloud", "cloud", "all", "test.cloud")
    assignment("cloud", "conflict", "conflict", "test.cloud-conflict")
    subject(
        "iam",
        "host/restricted-linux-01",
        "linux-host",
        {"iam-profile": "restricted-linux"},
    )
    group("iam", "company-assets", ["host/restricted-linux-01"])
    assignment("iam", "iam", "company-assets", "test.iam")
    write(
        root,
        "iam/fixtures/technical-results-failing.json",
        {
            "subject": {
                "id": "host/restricted-linux-01",
                "type": "linux-host",
                "labels": {"iam-profile": "restricted-linux"},
            },
            "results": [
                {
                    "instance_id": check["instance_id"],
                    "status": "fail" if index == 3 else "pass",
                }
                for index, check in enumerate(checks)
            ],
        },
    )
    waiver = inventory_resource(
        "Waiver",
        "test-package-waiver",
        {
            "subjectRef": {"id": "host/configuration-linux-01"},
            "controlRef": {"instanceId": "test.packages.extra"},
            "validFrom": "2026-08-01T00:00:00Z",
            "expiresAt": "2026-10-01T00:00:00Z",
            "rationale": "Synthetic accepted failure",
            "owner": "test",
            "approval": {
                "reference": "test/waiver-approval",
                "approvedBy": "test",
                "approvedAt": "2026-08-01T00:00:00Z",
            },
        },
    )
    write(root, "linux/waivers/waiver.json", waiver)
    for project in ("cloud", "linux", "iam"):
        (root / project / "waivers").mkdir(exist_ok=True)
        write(
            root,
            f"{project}/compliance.yaml",
            {
                "schema": "compliance.example/project-config/v1alpha3",
                "policySources": [
                    {"name": "control-library", "path": "../shared"},
                    {"name": "verification-policy", "path": "../selection"},
                ]
                + (
                    [{"name": "environment-private", "path": "policy"}]
                    if project == "iam"
                    else []
                ),
                "paths": {
                    "inventory": "inventory",
                    "assignments": "assignments",
                    "evidence": "generated/evidence",
                    "plan": "generated/plans",
                    "results": "generated/results",
                    "waivers": "waivers",
                },
            },
        )
    write(
        root,
        "compliance.yaml",
        {
            "schema": "compliance.example/project-registry/v1alpha1",
            "defaultProject": "cloud",
            "projects": {
                name: {"config": f"{name}/compliance.yaml"}
                for name in ("cloud", "linux", "iam")
            },
        },
    )
