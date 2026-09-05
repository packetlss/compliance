# Operator CLI, Project Registries, and Project Configuration


The ADR 0007 actual composition and v4 assessment contracts are documented
in [Actual composition and expected enforcement](composition.md). Existing
predecessor workflows described here remain supported pending consumer cutover.

Status: **Implemented prototype (v0.2)**
Last updated: **2026-09-05**

The control-plane workflows share one `compliance` command. Inventory
inspection, plan rendering, evaluation, and reporting remain separate modules
behind that interface; combining their command surface does not combine their
architectural responsibilities.

Collectors remain independent executables. They may run on governed subjects,
integration hosts, or collection services with different privileges and
dependencies. Their boundary with the control plane is the versioned evidence
document, not an in-process Python API.

## Command hierarchy

```text
compliance
├── config
│   ├── show
│   ├── validate
│   └── list
├── inventory
│   ├── validate
│   ├── list {subjects,groups,assignments}
│   ├── graph
│   └── explain SUBJECT
├── policy
│   ├── validate
│   ├── diff BEFORE AFTER [--format {table,json}]
│   └── diff-set BEFORE_DIRECTORY AFTER_DIRECTORY [--format {table,json}]
├── waiver
│   ├── validate
│   ├── list
│   └── explain WAIVER
├── plan
│   ├── render SUBJECT
│   └── show [PLAN]
└── assessment
    ├── run SUBJECT [--at RFC3339]
    ├── status
    ├── groups
    ├── frameworks
    └── explain SUBJECT
```

`assessment run` is the normal local end-to-end operation. It resolves and
persists the subject's immutable assessment plan, selects evidence, evaluates
each active control with OPA, and persists an immutable result envelope.
It evaluates at the current UTC instant by default. `--at` supplies an explicit
timezone-aware RFC 3339 instant for deterministic verification or deliberate
historical replay; the recorded result ID and `evaluated_at`, evidence
freshness, and waiver lifecycle selection all use that instant.
`plan render` remains useful for review, CI, and debugging without evaluation.
V1alpha3 projects persist strict `assessment-plan/v4` and `assessment-results/v4`
documents in unlocked, direct-expected and composition-locked modes. Predecessor
v1/v3 workflows remain available until their separate consumer migrations.
Before OPA, v4 establishes actual provenance, explicit subject/type routing and
a complete subject evidence snapshot. It validates every matching required
evidence candidate against the trusted schema before freshness or selection.

Under [ADR 0010](../../docs/adr/0010-required-evidence-status-and-assessment-refusal.md),
schema-invalid required evidence produces attributable `unknown`, including
mixed valid/invalid candidates. Distinct equally latest eligible complete
documents also produce `unknown` without dependent OPA calls. Canonical-identical
duplicates coalesce for selection only. Independent controls remain assessable;
missing/stale required evidence stays unknown. No ordering precedence, older
fallback or payload merging is introduced.

JSON and human explanations retain structured validation and selection ambiguity
diagnostics, including exact evidence ID/digest and schema references. Invalid
required-evidence counts belong to unknown. V4 reserves error for attributable
execution/decision failures, while preserving the predecessor invalid optional
evidence error behavior. Optional evidence selection semantics are not redesigned.
Only underlying fail may be waived; logical roll-ups remain unchanged.

Creating an artifact is not a passing assessment: persisted unknown or attributable
error may represent a completed run. Untrustworthy routing, shared prerequisites,
provenance or result integrity refuse publication. Refusal/write failure is command
failure with no new results envelope; atomic writes preserve previous output.
No new status/filter grammar or historical reinterpretation is introduced.

The CLI
validates plans before persistence and whenever they
are displayed or evaluated. Result files
are validated before persistence and when assessment views load them. A file
that declares one of these schemas but has malformed provenance, a stale plan
digest, inconsistent counts, mismatched child revisions, or an invalid
objective roll-up fails with its file and JSON Pointer instead of being treated
as usable history.
`policy validate` validates every reusable `Control` manifest and its local
parameter schema, checks every `Baseline` and `BaselineOverlay` document against
the schema selected by its `apiVersion` and `kind`, then resolves the complete
baseline DAG. It also validates `ControlRequirement`, `RequirementBaseline`,
and `ControlRealization` documents, their digest pins, complete `allOf`
coverage, implementation applicability, and effective parameters. It catches
cycles, duplicate instances, stale pins, invalid
overlay semantics, unknown implementations, and effective parameters that do
not satisfy their implementation contract. This includes overlay-generated and
excluded instances. Human output reports baseline and control counts;
`--format json` provides the same counts and structured errors for CI.
`assessment run` also rolls technical results into requirement and top
requirement-baseline results. `assessment status` shows objective and check
counts separately, while `assessment explain` displays the selected
realization and its provenance. For every active or excluded control with a
reviewed overlay deviation, the human explanation also displays alignment,
deviation ID and classification, rationale, approval reference, and review
date. Normative overlay operations also show the immutable inherited and
resulting implementation, disposition, and parameters. The JSON explanation
retains the same information in
`plan.controls[].deviations` or `plan.excluded_controls[].deviations`.

The assessment plan is the machine-readable external-adapter handoff. Its
active and excluded control records retain stable implementation and instance
IDs, resolved parameters, definition fingerprints, derivations, deviations,
baseline and requirement/realization lineage, source paths, subject identity,
plan identity, and named policy-source content digests. A separate program may
map those records to IaC, PaC, MDM, ticketing, or configuration-management
output. Core tooling has no configuration compiler, renderer, adapter registry,
or executable plugin loader. Adapter availability is not required for
assessment. External output is neither proof of execution nor compliance
evidence and must reference its source assessment plan when it records
provenance.

`policy diff` compares two stored assessment plans (v4, or predecessor v1) for the same
subject. Both inputs are validated against the strict schema, content digest,
coverage counts, and cross-field invariants before comparison. The command
does not load or re-resolve the current policy catalog, so its explanation is
based only on the immutable policy and provenance captured in the two plans.

The initial scope compares policy-relevant subject context, resolved groups,
assignments, technical and requirement baselines, coverage, resolution,
requirements, and active or excluded controls. Controls are matched by stable
`instance_id`; a transition from active to excluded or back is reported as
`excluded` or `activated`. Requirements and resolved baselines are matched by
stable identity without their revision so a revision upgrade appears as a
modification rather than an unrelated removal and addition. Modified entries
include their exact before/after objects and changed top-level fields. This
retains effective parameters, implementation, disposition, inheritance
lineage, derivation records, deviations, approval references, and provenance
for review without reconstructing history from current sources.

Plan IDs, policy-source digests, and inventory, assignment, and policy
revisions are reported as comparison context. A change to those envelope
revisions alone does not claim that this subject's effective policy changed;
actual scope, requirement, control, coverage, or resolution changes do. The
machine-readable output uses the schema
`compliance.example/policy-diff/v1alpha1`.

Exit status is designed for CI:

- `0` — comparison completed and effective policy is unchanged;
- `1` — comparison completed and effective policy changed; and
- `2` — the comparison is invalid or incomplete, including malformed input,
  different subjects, or either plan having invalid policy resolution.

An incomplete comparison still prints a valid report when both stored
artifacts are structurally valid, making their resolution state inspectable
while preventing CI from treating an invalid plan as an ordinary policy
change.

`policy diff-set` applies that same stored-plan comparison to two release
snapshot directories. It recursively loads every `*.json` file, requires each
file to be a valid v4 or predecessor v1 assessment plan, rejects empty sets and
duplicate subject identities, and matches plans by stable subject ID. It never
loads a policy catalog or combines project catalogs. Operators should therefore
pass one project-scoped plan snapshot on each side.

Valid subjects present on only one side are `added` or `removed`; paired
subjects are `modified` or `unchanged` according to the effective-policy diff.
Revision-only context churn remains `unchanged`. Any subject with an invalid
resolution is `incomplete`, including a one-sided invalid plan. The aggregate
report uses `compliance.example/policy-diff-set/v1alpha1`, embeds the complete
single-subject diff for each pair, and summarizes added, removed, modified,
unchanged, and incomplete subjects. Exit status retains the same contract:
`0` for a complete unchanged set, `1` for a complete set with effective
changes, and `2` for malformed input or any incomplete subject.

`waiver validate` checks the strict resource schema, unique identities,
timezone-aware bounded intervals, approval timing, and overlapping windows.
`waiver list` exposes active, scheduled, and expired resources and supports
exact subject and lifecycle filters. `waiver explain` shows one resource's
target, validity, rationale, ownership, approval, and digest. Both views accept
`--at RFC3339` for deterministic review and `--format json` for automation.
`assessment run` resolves the configured catalog at evaluation time. A matching
active waiver changes only an underlying failure to `waived`; `assessment
explain` retains the failure and displays the applied approval snapshot. See
[`waivers.md`](waivers.md).

The counts are intentionally independent. `Controls` is the number of concrete
technical checks in the rendered plan. `Objectives` is the number of assigned
high-level `ControlRequirement` objects. Therefore `Objectives: 0` is expected
for a project that only assigns technical baselines; it is not a warning and
does not suppress control evaluation. Projects that assign requirement
baselines receive objective and top-baseline roll-ups in addition to their
technical results.

`assessment frameworks` exposes every current `external_refs` mapping in the
selected project. Objective mappings carry rolled-up requirement status;
technical mappings carry independently attributable check status and parent
alignment. `TAILORED` or otherwise deviated mappings remain visibly distinct
from unaltered mappings, so a company-policy pass is not silently promoted into
an upstream-framework conformance claim. The command supports exact
`--reference`, `--level {objective,technical}`, and resolved `--group` filters,
all repeatable with OR semantics. Its JSON output preserves claim type,
alignment, current/outdated status, subject, and policy-object identity.

## Historical results and operational views

The predecessor `assessment status` implementation re-renders the present plan,
calls a matching `plan_id` result `current`, presents the stored result state,
calls a different-plan result `outdated`, and calls absence `pending`. Its report
timestamp is query time; it does not re-evaluate selected evidence or waiver age.
The `current/outdated` wording above describes that predecessor behavior only.

System [ADR 0011](../../docs/adr/0011-historical-assessment-and-operational-evidence-timeliness.md) has its factual v4 representation implemented under #32; its operational view remains **accepted design, not yet implemented**.
Future status/explanation/group views must separately expose historical outcomes
at `evaluated_at`, **Plan-aligned / Different plan / Plan alignment unavailable**,
selected-evidence timeliness as of explicit `q`, recorded waiver validity, and
existing coverage/applicability. Prefer **Selected evidence within recorded age
limits as of …**, **Evidence stale — reassessment due**, and **Evidence timeliness
unavailable**. Concurrent stale and unavailable conditions must both remain visible.
Historical PASS with stale evidence cannot support a “currently passing” claim.
Avoid unqualified “current PASS”, “currently secure” and overloaded “outdated”.

Historical WAIVED stays waived; show **Recorded waiver within validity window** or
**Recorded waiver expired** separately using the recorded exception. **No assessment**
does not establish refusal: show **Assessment refused — no new result** only from
explicit trustworthy attempt information, retaining any older result as history.
No persisted attempt/status artifact is introduced.

#32 retains factual v4 provenance only for ADR 0011 and does not derive query-time
fresh/stale/current state. The later operational-view tranche depends on #32 and
owns temporal derivation, presentation, temporal tests and one canonical time-advance
scenario. It consumes a validated v4 result, exact assessed plan, current comparison
plan and explicit query instant. No new CLI grammar or runtime change is implemented
by this promotion; ADR 0010 assessment-time behavior remains separately owned.

## Project registries and project configuration

Canonical verification materializes `verification/scenarios/integration/compliance.yaml`
at its temporary assembly root as a registry of independently configured projects.
The `project-registry` contract maps project names to configuration locations.
It requires a valid `defaultProject`; omitting `--project` selects that default:

```yaml
schema: compliance.example/project-registry/v1alpha1
defaultProject: linux-hardening-rollout
projects:
  linux-hardening-rollout:
    config: verification/scenarios/projects/linux-hardening-rollout/compliance.yaml
  mock-fleet:
    config: projects/mock-fleet/compliance.yaml
  server-personas:
    config: projects/server-personas/compliance.yaml
  iam-realization:
    config: verification/fixtures/iam-private-boundary/compliance.yaml
```

Each referenced project has its own `compliance.yaml`. For example,
`projects/mock-fleet/compliance.yaml` declares:

```yaml
schema: compliance.example/project-config/v1alpha1
policySources:
  - name: control-library
    path: ../../policy-sources/control-library/policies
  - name: verification-policy
    path: ../../policy-sources/verification-policy/policies
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
  resourceSchema: ../../tooling/schemas/inventory/resource.schema.json
```

Maintained projects declare all seven operational path keys and at least one
named policy source, so a valid project is ready for the complete
operator workflow rather than only the command first used against it. The
canonical project tree and path-ownership rules are defined in
[`project-layout.md`](project-layout.md).

`tooling/` is the sole Python/build root. From the destination root use
`uv run --project tooling compliance` with an explicit project config, or select
a project through the materialized registry. Source paths are acquisition
locations; explicit names and content digests define policy identity. Destination
[ADR 0005](../../docs/adr/0005-content-addressed-development-boundaries.md),
[ADR 0009](../../docs/adr/0009-active-compliance-vocabulary.md), the system
[architecture](../../docs/ARCHITECTURE.md), and the
[repository map](../../docs/REPOSITORIES.md) govern current authority.

Project registry and project files are versioned configuration, not Kubernetes
resources. They have no
resource identity, lifecycle, grouping, or API-storage semantics, so they do
not use `kind`, `metadata`, and `spec`. Kubernetes-shaped contracts remain the
right choice for inventory objects that do have those semantics.

A project registry only selects one project configuration. It does not compose
policy, acquire sources, or merge inventories, assignments, waivers, evidence,
plans, or results. Registry content and location do not enter policy composition
identity; repository/workspace topology is nonsemantic. Selecting the same
project directly or through a registry resolves equivalent runtime inputs.
The retired `workspace-config` discriminator is unsupported, with no alias.

A project is an operator boundary with its own inventory, assignments, evidence, plans, and
results; projects may reference a shared policy catalog. From the destination
root, select an ordinary project explicitly:

```sh
uv run --project tooling compliance --config projects/mock-fleet/compliance.yaml inventory validate
uv run --project tooling compliance --config projects/server-personas/compliance.yaml waiver list
```

Framework-oriented examples:

```sh
uv run compliance --project mock-fleet assessment frameworks
uv run compliance --project mock-fleet assessment frameworks \
  --reference CSA-CCM-v4.1:LOG-domain
uv run compliance --project iam-realization assessment frameworks \
  --level objective
```

If `--project` is omitted, the project registry's `defaultProject` is used. In the canonical
assembly above, unqualified commands select `linux-hardening-rollout`.
`compliance config list` shows all projects, the selected project, and the
default. Running from inside an example directory discovers that example's
project config directly, so `--project` is unnecessary there.

Configuration behavior is deterministic:

1. `--config PATH` selects an explicit project registry or project file.
2. `--no-config` disables discovery and cannot be combined with `--project`.
3. Otherwise, the nearest `compliance.yaml` is selected by searching from the
   current directory toward the filesystem root.
4. A project registry selects `--project NAME`, or its `defaultProject` when omitted;
   a standalone project config rejects `--project` rather than silently
   ignoring it.
5. Command-line path options override configured paths. Repeating
   `--policy-source NAME=PATH` replaces the configured policy-source set for
   that command; source paths resolve from the current working directory.
6. Configured relative paths resolve from the directory containing the config
   file. Explicit command-line relative paths resolve from the current working
   directory.
7. A required path or policy-source set missing from both the command and
   configuration is an error.

The legacy `--policies PATH` and `paths.policies` forms remain available for a
single source and cannot be combined with the named form. New automation should
use names because source identity and per-source revisions are included in
validation output and rendered plans:

```sh
uv run --project tooling compliance --no-config policy validate \
  --policy-source control-library=policy-sources/control-library/policies \
  --policy-source verification-policy=policy-sources/verification-policy/policies
```

Configured source order and repeated flag order have no precedence. The CLI
normalizes sources by name, coalesces only identical resource identities with
complete provenance, and rejects divergent identities. An optional `digest`
field on a configured source verifies an immutable `sha256:` pin; maintained
development projects omit it because they are editable development trees.
The IAM validation assembly additionally supplies the independently materialized
`environment-private` source; see the [fixture boundary](../../verification/fixtures/iam-private-boundary/README.md).

Only documented fields are accepted. Project registry and project files are validated
against `tools/schemas/project-registry.schema.json` and
`tools/schemas/project-config.schema.json`. Unknown fields, unknown path names,
empty values, invalid project names, multiple YAML documents, missing project
files, unknown project selections, and unsupported schema versions fail rather
than being ignored. `compliance config show` prints the project registry (`project_registry` in JSON), selected
project file, fully resolved paths, and named policy sources; its JSON form is
suitable for automation:

```sh
uv run compliance config show
uv run compliance config show --format json
uv run compliance config validate
uv run compliance config list
```

Configuration initially contains stable repository and artifact locations.
Operational selections such as subject, group, state, output format, and color
remain command arguments. This avoids hiding the scope of an operator action
inside a project default.

Canonical projects use extensionless `plan` and `results` paths. These are
per-subject artifact directories: `plan render` and `assessment run` derive a
stable JSON filename from the subject ID. This gives single-subject and fleet
projects identical behavior while `assessment status` reads the configured
result directory recursively. Paths with a filename extension remain supported
for explicit single-artifact workflows. `plan show` opens the only plan in a
single-subject directory and renders an index when several plans exist. Select
one fleet plan with its stable subject ID or an explicit file path:

```sh
uv run compliance --project mock-fleet plan show
uv run compliance --project mock-fleet \
  plan show cloud-account/aws-111122223333
```

The directory index also supports `--format json` for scripting.

Evidence paths are directories and may contain documents for several subjects.
Before type and freshness selection, the input builder scopes documents to the
exact `subject.id` in the rendered plan. Evidence for another subject is never
passed to OPA for the current assessment.

## YAML editor schemas

Every authored `.yaml` or `.yml` file in the repository starts with a portable
`yaml-language-server` schema directive. Inventory resources point to the
combined inventory resource schema; root and project `compliance.yaml` files
point to their respective project registry or project configuration schemas; waiver
resources point to the tooling-owned waiver resource schema. Tests
resolve every directive and validate every YAML document, so a new YAML file
without a schema association fails the build.

## Supported operator entry point

`compliance` is the sole supported operator entry point. Inventory, planning,
evaluation, assessment reporting, and requirement roll-up remain separate
internal modules behind the unified command, but those module paths are not
supported scripts or a public Python API. Operator documentation and automation
must use `compliance` so configuration, discovery, help, exit status, and error
handling remain consistent.
