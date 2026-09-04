# Project Directory Layout

Status: **Accepted convention (v0.3)**
Last updated: **2026-09-04**

A project is the smallest independently operable compliance scope. It owns one
inventory projection, its policy assignments, collected evidence, rendered
plans, and assessment results. A workspace-style registry may select one project
at a time, but it does not merge these catalogs or artifacts and does not
require a particular repository topology.

## Canonical layout

Human-maintained projects should use this shape:

```text
project-name/
├── compliance.yaml
├── README.md
├── inventory/
│   ├── subjects/
│   │   └── <one Subject per file>.yaml
│   └── groups/
│       └── <one InventoryGroup per file>.yaml
├── assignments/
│   └── <one PolicyAssignment per file>.yaml
├── waivers/
│   └── <one reviewed Waiver per file>.yaml
├── policy/                     optional project-private partial policy tree
│   └── realizations/
├── generated/
│   ├── evidence/
│   ├── plans/
│   └── results/
└── fixtures/                    optional collector input for examples/tests
```

`compliance.yaml`, `inventory/`, `assignments/`, and `waivers/` are authored inputs.
Everything below `generated/` is derived runtime state and should be ignored by
Git. A project README is expected for maintained examples and operational
projects, although it is not needed by the CLI.

## Scenario project roles

Maintained examples distinguish deterministic verification scenarios from
development, boundary, and downstream external-example projects. Verification
scenarios use realistic synthetic operating stories, fixed inputs and times,
the normal public interfaces, and explicit structured assertions. Development
projects may evolve while discovering new contracts. Boundary examples may
depend on a local machine or separate private source when that dependency is
the behavior being demonstrated.

An external example is a clonable starter workspace that pins supported
tooling, shared-policy-library, and example-company-policy releases. It
optimizes for a clear, idiomatic starting point that users can copy or fork and
replace with their own company policy. It may have its own compatibility tests,
but it is not a core release-gate fixture and no tooling, policy-library,
verification-policy, or verification-scenario repository may depend on it.

A verification README additionally documents its external-framework scope when
present, company intent, intended operating practice, technical realization,
evidence sources, expected results, intentional failures and exceptions, and
the limits of its assurance claim. The complete convention is in
[`verification-scenarios.md`](verification-scenarios.md).

Several project directories may live in one repository when they share owners
and visibility. This does not create one combined project: every directory
retains its own `compliance.yaml`, inventory, assignments, waivers, private
policy inputs, and generated paths, and a registry selects one project at a
time. Repository placement is not project identity.

The `subjects/` and `groups/` subdirectories are collaboration conventions,
not semantic namespaces. The inventory loader recursively reads the configured
`inventory` path; filenames, subdirectory names, YAML document boundaries, and
document order do not affect resource identity or revision digests.

## Complete project configuration

Every project config declares all paths needed by the operator workflow:

```yaml
# yaml-language-server: $schema=../../tools/schemas/project-config.schema.json
schema: compliance.example/project-config/v1alpha1
policySources:
  - name: shared-library
    path: ../compliance-control-library/policies
  - name: verification-policy
    path: ../compliance-verification-policy/policies
  - name: environment-private
    path: policy
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
  resourceSchema: ../compliance-tooling/schemas/inventory/resource.schema.json
```

Relative paths resolve from the directory containing `compliance.yaml`. The
project config is therefore also the project-root marker used by automatic CLI
discovery.

The relative paths above illustrate the current transitional checkout only.
Repository names and sibling placement are not part of the project contract:
each logical policy source is named and content-addressed independently of its
materialization path. A deployed project should resolve each named source to a
verified immutable artifact and obtain the inventory schema from its pinned
tooling installation. The private source may be a partial tree—for example, it
may contain only `realizations/`—because schemas and reusable controls can
resolve from the shared source during environment-local assembly.

Workspace [ADR 0005](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/adr/0005-content-addressed-development-boundaries.md)
governs development topology. Current transition ownership is summarized by the
workspace [architecture](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/ARCHITECTURE.md)
and [repository map](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/REPOSITORIES.md).

Maintained projects declare all seven operational paths together with at least
one named `policySources` entry. This prevents a
project that works for one command from failing later because an operational
location was left implicit.

## Path ownership and sharing

The canonical layout distinguishes project-owned state from reusable shared
content:

| Path | Normal ownership | May be shared? |
|---|---|---|
| `inventory` | Project | No; it defines this project's governed subjects |
| `assignments` | Project | No; it binds this project's groups to policy |
| `evidence` | Project runtime | No; evidence selection is project-scoped |
| `plan` | Project runtime | No; plan revisions belong to this project |
| `results` | Project runtime | No; status views read this project's results |
| `waivers` | Project governance | No; exceptions are approved within this subject and visibility boundary |
| `policySources` | Shared releases plus optional project-private policy | Shared sources yes; private sources remain project-scoped |
| `resourceSchema` | Platform contract | Yes |

Paths make this a logical contract rather than a filesystem sandbox. Shared
policy sources and schemas may sit outside the project directory, as all
maintained repository examples demonstrate. A deployment may also place
generated artifacts in an external mounted store while retaining the same
logical separation.

`paths.policies` remains accepted as a legacy single-source form and cannot be
combined with `policySources`. New projects should use named sources so plans
can retain each source revision and local environments can add private policy
without copying it into a shared catalog.

## Artifact naming

Canonical projects configure extensionless `plan` and `results` paths. The CLI
treats them as directories and derives a stable JSON filename from the subject
ID by replacing `/` with `__`:

```text
host/standard-app-01
  → generated/plans/host__standard-app-01.json
  → generated/results/host__standard-app-01.json
```

This makes a single-subject project behave exactly like a fleet project and
allows more subjects to be added without changing configuration. A configured
path with a file extension remains supported for explicit, single-artifact
workflows, but it is not the canonical maintained-project layout.

Evidence filenames are collector concerns. Correctness depends on the evidence
envelope's exact subject identity, type, timestamps, provenance, and digest—not
on its filename.

## Optional directories

`policy/` is appropriate for reviewed private `Baseline`, `BaselineOverlay`,
or complete `ControlRealization` resources. It follows the same virtual tree
names as shared policy and must not contain mutable copies masquerading as the
authoritative shared release.

`fixtures/` is appropriate for deterministic collector inputs in examples and
tests. It is not part of the compliance control-plane contract and must not
contain desired policy. Production collectors may have no project-local input
directory at all.

Waivers are reviewed project governance inputs and must not be placed under
`generated/`. They do not change desired state, but their lifecycle and
approval data determine whether an observed failure is reported as waived. See
[`waivers.md`](waivers.md). Future project-owned locations such as
source-snapshot definitions should likewise be added only when their domain
contract exists.

Inventory labels may select stable operational personas, but the policy
difference itself does not belong in inventory. The development
`compliance-development-projects/projects/server-personas` project and the stable
`compliance-verification-scenarios/projects/linux-hardening-rollout` scenario
both assign a company base baseline to one leaf group and an explicitly derived
baseline to a sibling feature group. The stable scenario additionally assigns
company operations policy and a complete shared access objective at the
ancestor group. Separate project directories keep their inventory and generated
artifacts isolated while reusable desired policy remains in its independently
named and digested logical source.

External adapters may consume a project's generated assessment plans, but
their outputs and backend state live outside the core project path contract.
Such output is derived runtime/build state, must reference its source plan when
it records provenance, and is not assessment evidence.
