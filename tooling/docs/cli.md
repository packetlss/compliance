# Operator CLI, Project Registries, and Project Configuration


The ADR 0007 actual composition and v4 assessment contracts are documented
in [Actual composition and expected enforcement](composition.md). All maintained
consumers use successor contracts; historical artifacts require historical tooling.

Status: **Implemented prototype (v0.2)**
Last updated: **2026-09-11**

The control-plane workflows share one `compliance` command. Their primary
operator sequence is `Inventory → Coverage → Assessment`. Inventory
inspection, current coverage, plan rendering, evaluation, and reporting remain separate modules
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
│   ├── list {assets,groups,assignments} [--format {table,json}]
│   ├── graph
│   └── explain ASSET [--format {table,json}]
├── coverage
│   ├── list {assets,groups,assignments} [--format {table,json}]
│   └── explain ASSET [--format {table,json}]
├── policy
│   ├── validate
│   ├── diff BEFORE AFTER [--format {table,json}]
│   └── diff-set BEFORE_DIRECTORY AFTER_DIRECTORY [--format {table,json}]
├── waiver
│   ├── validate
│   ├── list
│   └── explain WAIVER
├── plan
│   ├── render [ASSET ...] [--group GROUP ... | --all]
│   └── show [PLAN_OR_ASSET]
└── assessment
    ├── run ASSET [--at RFC3339]
    ├── status [--by group] --plan PLAN --at RFC3339 --as-of RFC3339
    ├── mappings --plan PLAN --at RFC3339 --as-of RFC3339
    └── explain ASSET --plan PLAN --at RFC3339 --as-of RFC3339
```

`asset` / `assets` is CLI presentation vocabulary for a supplied governed
object. It does not rename the underlying `Subject` resource, normalized domain
object, schema fields, IDs, or identity algorithms. The replaced pre-freeze
`inventory list subjects` selector is unsupported and has no alias.

## Current inventory and coverage views

`inventory list assets`, `groups`, and `assignments` presents the normalized
facts supplied to the current project: asset identity/type/lifecycle, labels and
source attribution; group parents/selectors/explicit members; or assignment
targets and exact policy references. `inventory explain ASSET` joins only those
supplied asset facts to direct and inherited group-membership attribution. It
does not claim external discovery completeness and does not resolve policy.
Arbitrary Inventory annotations and adapter-specific `attributes` are intentionally
not forwarded through this ordinary presentation boundary. They remain governed
Inventory facts and retain their existing resolution semantics where consumed; the
read view does not create a second governed-fact model.

`coverage list assets`, `groups`, and `assignments` derives current assessment
expectation through the existing planner. The asset view uses exactly
`result_required`, `inactive`, `unassigned`, `no_assessable_policy`, and
`invalid_resolution`. Assignment presence and assessability have separate
counts. Every supplied group and assignment is retained, including zero-member
and zero-assessable-effect rows. Invalid resolution is explicit and never
rendered as an empty successful or unassigned plan.

`coverage explain ASSET` follows current membership and applicable assignments
to authored policy titles, Objectives when present, Checks, effective
parameters, dispositions, adoption, and required evidence. Technical-only
policy goes directly from applicable policy to Check and required evidence; it
does not synthesize an Objective. Resolution errors remain visible and fail
closed under the planner's existing boundary.

These table/JSON objects are bounded, deterministic, experimental query
projections. They are non-authoritative, non-persisted, non-identity-bearing,
and are neither assessment inputs nor artifact families. Coverage does not own
or cache resolution and does not perform evidence selection. `assessment`
continues to own immutable result and historical-operation interpretation.
Ordinary coverage output projects authored deviation rationale/approval facts,
the realization reference, and bounded resolution-failure meaning;
it does not expose plan derivations, fingerprints, lineage, raw provenance,
resource digests, policy-source locators, or raw planner diagnostics. Exact
provenance remains available from the immutable plan and its advanced artifact
surfaces.

For the additive-set capability accepted in
[#127](https://github.com/packetlss/compliance/issues/127) and implemented under
[#129](https://github.com/packetlss/compliance/issues/129), Coverage owns the
ephemeral deterministic projection of **current** effective parameter values and
their derivation through the same planner/resolver. This responsibility boundary
does not freeze CLI spelling or output shape, require ordinary views to expose full
plan provenance, or add a second resolver, persistent Coverage state or cache.
Historical `assessment` explanation continues to use only the exact retained,
relationally validated plan/result pair and never re-resolves current policy.
For each bound Objective slot, JSON explanation includes `slot`, `effective_value`,
and `binding_mode`. Additive slots also include bounded `composition`
with the base value and applicability, semantic contributions and all applicability
paths, and effective member origins. It omits frozen resource documents, digests,
and policy-source locators from the ordinary view.

`assessment run` is the normal local end-to-end operation. It resolves and
persists the subject's immutable assessment plan, selects evidence, evaluates
each active control with OPA, and persists an immutable result envelope.
It evaluates at the current UTC instant by default. `--at` supplies an explicit
timezone-aware RFC 3339 instant for deterministic verification or deliberate
historical replay; the recorded result ID and `evaluated_at`, evidence
freshness, and waiver lifecycle selection all use that instant.
`plan render` remains useful for review, CI, and debugging without evaluation.
V1alpha3 projects persist strict `assessment-plan/v4` and `assessment-results/v4`
documents in unlocked, direct-expected and composition-locked modes.
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

JSON results and human explanations retain canonical result-level unsuccessful
dependency dispositions: `absent`, `stale`, `invalid`, or `ambiguous`. Candidate
facts use exact already-snapshotted evidence ID/digest/collection times. Invalid
facts retain only the closed code plus safe schema path and keyword; evidence paths,
raw validator messages, and schema locations are omitted. V4 error results retain
one closed criterion execution/decision stage and code with fixed safe prose and no
raw evaluator output. Every declared evidence dependency is required;
there is no optional-evidence selection or invalid-optional-evidence error path.
Only underlying fail may be waived; logical roll-ups remain unchanged.

Creating an artifact is not a passing assessment: persisted unknown or attributable
error may represent a completed run. Untrustworthy routing, shared prerequisites,
provenance or result integrity refuse publication. Refusal/write failure is command
failure with no new results envelope; atomic writes preserve previous output.
No new status/filter grammar or historical reinterpretation is introduced.

The CLI
validates plans before persistence and whenever they
are displayed or evaluated. Result files
are intrinsically validated before persistence and when assessment views load them.
Publication and historical interpretation additionally validate each result against
the exact plan named by `plan_id`. Malformed provenance, inconsistent
member/operation/bound-plan identity, mismatched plan/result attribution, or an
invalid compact objective roll-up fails closed instead of being treated as usable
history.
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
Every assignable policy root must provide its authored title, and every Control
must provide its authored title and intrinsic purpose. Validation rejects missing
or whitespace-only meaning, while exact-definition assembly rejects conflicting
same-identity prose.
`assessment run` also rolls technical results into requirement and top
requirement-baseline results. Its bounded table and JSON views identify the exact
operation request, assessment instant, per-asset expectation, exact result-slot
presence, and immutable outcome. `accounting_complete` remains separate from
`all_passed`; neither is inferred from the existence of output artifacts. Ordinary
human output leads with the normalized asset/group scope. Stable operation and plan
identities remain in JSON for drill-down rather than occupying the default table.

`assessment status` reports one exact frozen operation. It requires a retained
operation-bearing `--plan`, exact `--at`, and explicit qualification instant
`--as-of`. Repeatable `--assessed-plans` inputs resolve each retained result only by
exact `plan_id`; no current-plan, subject-only, filename, traversal-order, or latest
fallback exists. `assessment status --by group` uses the same operation and filters
and leaves whole-operation accounting visible and unchanged by filtering. Frozen
group rows retain even an empty group named by the operation's selection witness.
They show group-local exact slot accounting beside separately aggregated current
plan alignment, selected-evidence timeliness, and recorded-waiver qualification.
Frozen accounting-disposition counts keep inactive, unassigned, and no-assessable-
policy members distinct even though none requires a result.
An explicitly supplied missing results path or single non-result file is invalid and
fails closed. Omit `--results` or supply an empty bounded directory to represent no
retained results. A bounded directory may contain other JSON artifact families;
only intrinsically valid result envelopes are admitted from it.
The default per-asset table likewise keeps current waiver qualification distinct
from the immutable historical outcome. A dependency-free check makes no positive
evidence-timeliness claim.

Assessment and Framework historical commands share one narrow, non-persisted
validated historical Assessment context. It admits one exact operation-bearing
anchor, explicitly supplied assessed plans/results, the explicit assessment/query
instants, and an optional comparison anchor. It performs intrinsic artifact
validation, exact identity admission, competing-result detection, every available
mandatory plan/result relational check, and delegates exact accounting and
qualification to `operation.py`. It contains no Inventory, Coverage, Governance,
Framework or policy-diff state. A missing assessed plan still permits only the
existing bounded result-owned fallback; it never causes policy meaning to be
reconstructed.

`assessment explain ASSET` leads with applicable-policy titles, optional Objective
title/statement, Control-owned Check title/purpose, effective parameters, required
evidence, immutable historical outcome, and separately labeled current
qualification. Each applicable policy retains its exact group/assignment path and
the objective/check identities attributed through that path. A technical-only plan
has no synthetic Objective. Objective output keeps frozen adoption distinct from the
immutable requirement outcome and reason. Its JSON is a
bounded projection and never embeds a whole plan or result. Stable operation, plan,
result, asset, check, and dependency identities remain available for drill-down.
Required-evidence rows include exact plan-owned dependency `inputs` when present.
`--retained-evidence FILE_OR_DIRECTORY` is optional presentation enrichment: a
document contributes only after its complete-document digest and Evidence ID match
the exact retained result reference (and its recorded collection instant where
available). Only collector ID/version are exposed; payload bytes are never needed
for historical interpretation. Missing or same-ID/different-digest content provides
no enrichment and does not remove independently retained historical facts.

`assessment status` and `assessment explain` optionally accept
`--external-refusals FILE`. This is caller-trusted external orchestration query
context, not a core resource, result, history, or attempt artifact. The input must
name the exact operation and assessment instant and may qualify only a missing
required result slot. Projection output keeps it in a separate
`external_orchestration` / `external_refusal` field; a missing result alone remains
only a missing slot and never implies refusal.

`framework validate` validates project-governed declarations at the configured
`paths.frameworkDeclarations` path. `framework status DECLARATION --revision REVISION`
and `framework explain` require that exact declaration plus `--plan`, repeatable
`--assessed-plans`, `--results`, `--at`, and `--as-of`, including under `--no-config`.
They never select a latest declaration/result or resolve current policy. Their only
top-level words are “Satisfied under declared coverage”, “Not satisfied under declared
coverage”, and “Satisfaction not established under declared coverage”.

`framework status` is the concise ledger projection: its human table and JSON
obligation rows contain only obligation identity, disposition, basis category, and
effective state beneath the bounded statement, declaration identity, and exact
operation anchor. `framework explain` is the drill-down projection over those same
inputs. It adds each reviewed interpretation and exact governance or assessed support:
governance attribution and review facts, pinned Objective/direct-policy identity and
declared groups, frozen subjects, exact retained Objective and technical outcomes,
current historical qualifications, or an explicit reason support is not established.
Governance support is declaration-side and never appears as a synthetic assessment
result.

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

`policy diff` compares two stored assessment plans (v4) for the same
subject. Both inputs are validated against the strict schema, recomputed
member/operation/bound-plan identities, and cross-field invariants before
comparison. The command
does not load or re-resolve the current policy catalog, so its explanation is
based only on the immutable policy and provenance captured in the two plans.

The initial scope compares policy-relevant subject context, resolved groups,
assignments, technical and requirement baselines, resolution,
requirements, and active or excluded controls. Controls are matched by stable
`instance_id`; a transition from active to excluded or back is reported as
`excluded` or `activated`. Requirements and resolved baselines are matched by
stable identity without their revision so a revision upgrade appears as a
modification rather than an unrelated removal and addition. Modified entries
include their exact before/after objects and changed top-level fields. This
retains effective parameters, implementation, disposition, inheritance
lineage, derivation records, deviations, approval references, and provenance
for review without reconstructing history from current sources.

Plan IDs, member-plan digests, operation IDs, and planning-composition digests
are reported as comparison context. A change to that identity context alone
does not claim that this subject's effective policy changed; actual scope,
requirement, control, or resolution changes do. The
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
file to be a valid v4 assessment plan, rejects empty sets and
duplicate subject identities, and matches plans by stable subject ID. It never
loads a policy catalog or combines project catalogs. Operators should therefore
pass one project-scoped plan snapshot on each side.

Valid subjects present on only one side are `added` or `removed`; paired
subjects are `modified` or `unchanged` according to the effective-policy diff.
Identity-context-only churn remains `unchanged`. Any subject with an invalid
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

`assessment mappings` exposes exact attributable `external_refs` already frozen in
the selected operation. Objective mappings carry a relationally validated rolled-up
requirement outcome; technical mappings carry an independently attributable check
outcome and policy alignment. `TAILORED` or otherwise deviated mappings remain
visibly distinct from unaltered mappings. The command supports exact
`--reference`, `--level {objective,technical}`, and resolved `--group` filters,
all repeatable with OR semantics. The view is traceability only and cannot establish
mapping completeness, external conformity, certification, an audit opinion, or
legal compliance.

## Frozen operation selection and reporting

`plan render` and `assessment run` accept multiple asset IDs, repeated `--group`
selectors, or `--all`. They freeze expected membership before evaluation. Empty
selection fails; unassigned/inactive/no-active-policy rows are accounted without
synthetic pass or N/A. `assessment run` captures one instant and reports
`accounting_complete` separately from `all_passed`.

For immutable history, `assessment status`, `mappings`, and `explain` accept a stored
`--plan` anchor, repeatable `--assessed-plans` exact plan files or bounded plan
directories, an exact `--at` instant, and an explicit `--as-of` instant. Use
`--no-config` when current project inputs are unavailable. Reporting indexes those
ordinary inputs solely by validated `plan_id`, validates every interpreted pair,
and uses only frozen operation facts and exact matching result envelopes. Filters
remain visibly filtered. See [operation accounting](operation-accounting.md)
for wire representation, identity, output paths and the concrete assertion contracts.

## Historical results and operational views

The predecessor non-anchored current-plan/latest-result presentation path is removed.
Current assessment expectation belongs to `coverage`; Assessment does not call that
projection or rebuild it. Historical outcome, exact expected-slot presence, frozen
accounting, plan alignment, evidence timeliness, and waiver qualification are
separate fields and aggregates.
`--outcome` and `--plan-alignment` filter those dimensions independently; no filter
changes or discards the other dimension. Their report timestamp remains query time;
they do not re-evaluate selected evidence or waiver age.

System [ADR 0011](../../docs/adr/0011-historical-assessment-and-operational-evidence-timeliness.md) has its factual v4 representation implemented under #32 and its derived historical operational view implemented under #80.
Anchored status/explanation/group views separately expose historical outcomes
at `evaluated_at`, **Plan-aligned / Different plan / Plan alignment unavailable**,
selected-evidence timeliness as of explicit `q`, recorded waiver validity, and
frozen accounting disposition. Prefer **Selected evidence within recorded age
limits as of …**, **Evidence stale — reassessment due**, and **Evidence timeliness
unavailable**. Concurrent stale and unavailable conditions must both remain visible.
Historical PASS with stale evidence cannot support a “currently passing” claim.
Avoid unqualified “current PASS”, “currently secure” and overloaded “outdated”.

Historical WAIVED stays waived; show **Recorded waiver within validity window** or
**Recorded waiver expired** separately using the recorded exception. **No assessment**
does not establish refusal: show **Assessment refused — no new result** only from
explicit trustworthy attempt information, retaining any older result as history.
No persisted attempt/status artifact is introduced.

Every anchored historical view requires `--as-of RFC3339`; wall-clock time is never
substituted. Optional `--comparison-plan PLAN` supplies the validated comparison
operation. Without it, alignment is unavailable while evidence and recorded-waiver
qualifications remain available. JSON exposes bounded dependency/control details and
separate whole-operation and group summaries; mappings retain historical status where
exact relational interpretation is available. Filters do not alter frozen accounting.
Missing slots have `historical_outcome: null`; missing/no-assessment is never promoted
to an immutable result outcome.

When a result fills an exact frozen slot but its assessed plan is absent from the
bounded input set, `assessment explain` returns only result-owned outcome, reason,
dependency disposition, closed evaluation-error, and recorded-waiver facts, plus the
waiver window qualification derived directly from those result-owned timestamps. It says
that full interpretation is unavailable and does not attach policy/check meaning,
evidence type/freshness, roll-up validity, dependency timeliness, or plan alignment.

#32 retains factual v4 provenance only for ADR 0011. #80 derives the view from a
validated v4 result, exact assessed plan, optional comparison plan and explicit query
instant. ADR 0010 assessment-time behavior remains separately owned.

[#90](https://github.com/packetlss/compliance/issues/90) requires every historical
result that is fully interpreted to resolve its assessed
plan solely by exact `plan_id` and pass plan/result relational validation. An exact
plan file or bounded plan directory/set may be ordinary input. Filename, traversal
order, subject-only matching, latest, current-plan substitution, and approximate
semantic equality cannot resolve the assessed plan. This does not add a history
store, result index, run object, retention service, latest-result database, or
unbounded artifact discovery.

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
  alder-forge-dcc-level3:
    config: projects/alder-forge-dcc-level3/compliance.yaml
  iam-realization:
    config: verification/fixtures/iam-private-boundary/compliance.yaml
```

Each referenced project has its own `compliance.yaml`. For example,
`projects/mock-fleet/compliance.yaml` declares:

```yaml
schema: compliance.example/project-config/v1alpha3
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
```

Maintained projects declare all six operational path keys and at least one
named policy source, so a valid project is ready for the complete
operator workflow rather than only the command first used against it. The
canonical project tree and path-ownership rules are defined in
[`project-layout.md`](project-layout.md).

`tooling/` is the sole Python/build root. From a repository checkout, use
`scripts/dev cli ...` with an explicit project config or select a project
through the root registry. This development adapter executes the managed
environment's installed `compliance` entrypoint from the repository root;
independently installed products use `compliance ...` directly. Source paths
are acquisition locations; explicit names and content digests define policy identity. Destination
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
scripts/dev cli --config projects/mock-fleet/compliance.yaml inventory validate
scripts/dev cli --config projects/server-personas/compliance.yaml waiver list
```

Mapping traceability examples over one retained exact operation:

```sh
scripts/dev cli --project mock-fleet assessment mappings \
  --plan projects/mock-fleet/generated/plans/cloud-account__aws-111122223333.json \
  --assessed-plans projects/mock-fleet/generated/plans --at 2026-09-01T00:00:00Z \
  --as-of 2026-09-01T00:00:00Z
scripts/dev cli --project mock-fleet assessment mappings \
  --plan projects/mock-fleet/generated/plans/cloud-account__aws-111122223333.json \
  --assessed-plans projects/mock-fleet/generated/plans --at 2026-09-01T00:00:00Z \
  --as-of 2026-09-01T00:00:00Z --reference CSA-CCM-v4.1:LOG-domain
```

The synthetic `iam-realization` project is intentionally absent from the root
development registry because its `environment-private` source must be copied to
an independent temporary materialization. `scripts/dev gate iam` owns that
execution path.

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
5. Command-line path options override configured paths. Configured projects reject policy-source and resource-schema overrides.
   With `--no-config`, repeated `--policy-source NAME=PATH` supplies the named
   source set; paths resolve from the current working directory.
6. Configured relative paths resolve from the directory containing the config
   file. Explicit command-line relative paths resolve from the current working
   directory.
7. A required path or policy-source set missing from both the command and
   configuration is an error.

`--no-config --policies PATH` supplies one source; it cannot be combined with
the named CLI form. Project configs require `policySources` and reject
`paths.policies`. Named sources expose each revision in validation output and plans:

```sh
scripts/dev cli --no-config policy validate \
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
`tools/schemas/project-config-v1alpha3.schema.json`. Unknown fields, unknown path names,
empty values, invalid project names, multiple YAML documents, missing project
files, unknown project selections, and unsupported schema versions fail rather
than being ignored. `compliance config show` prints the project registry (`project_registry` in JSON), selected
project file, fully resolved paths, and named policy sources; its JSON form is
suitable for automation:

```sh
scripts/dev cli config show
scripts/dev cli config show --format json
scripts/dev cli config validate
scripts/dev cli config list
```

Configuration initially contains stable repository and artifact locations.
Operational selections such as subject, group, state, output format, and color
remain command arguments. This avoids hiding the scope of an operator action
inside a project default.

Canonical projects use extensionless `plan` and `results` paths. These are
per-asset artifact directories: `plan render` and `assessment run` derive a
stable JSON filename from the underlying Subject ID. This gives single-asset and
fleet projects identical behavior while `assessment status` reads the configured
bounded result directory recursively. Paths with a filename extension remain supported
for explicit single-artifact workflows. `plan show` opens the only plan in a
single-asset directory and renders an index when several plans exist. Select
one fleet plan with its stable asset ID or an explicit file path:

```sh
scripts/dev cli --project mock-fleet plan show
scripts/dev cli --project mock-fleet \
  plan show cloud-account/aws-111122223333
```

The directory index also supports `--format json` for scripting.

Evidence paths are directories and may contain documents for several subjects.
Before type and freshness selection, the input builder scopes documents to the
exact `subject.id` in the rendered plan. Evidence for another subject is never
passed to OPA for the current assessment.

## Experimental external read consumption

The isolated browser exercise at
[`tooling/examples/read-browser/`](../examples/read-browser/) consumes the same
purpose-specific JSON documents emitted by Inventory, Coverage, Assessment,
mappings, Framework and policy-diff commands. Its file-input boundary adds no HTTP
service, persistent state, latest-state selection, browser-specific report object or
public Python API. The page rejects raw plan/result/Evidence/resource documents and
may only navigate, filter, sort and format already-derived response facts. These
response wires remain experimental.

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

## Experimental producer commands

`compliance producer list`, `producer schema`, and `producer validate` expose
explicit-source Evidence contracts and a small tooling-owned Subject check without
project configuration or assessment. See the [producer interface](producer-interface.md)
for file/stdin validation, ownership, limits, examples and the installed/no-Git exercise.

## ADR 0024 Tranche A gap reporting

An exact assigned Objective remains accounted when it has no applicable realization
or has an authored non-implementation declaration. The plan's `implementation_state`
and optional authored adoption retain the basis. Compact Objective/baseline results
carry `implementation_gap` independently from nullable `status`; gap-only results
have null `outcome`. Actual evidence outcomes remain unchanged. Complete accounting
is not successful demonstration: `all_passed` also requires no implementation gaps.
Coverage and historical explanation expose the appropriate current or frozen basis.
Contribution-only parameter baselines create no assessment rows. Current admission
rejects predecessor membership/satisfaction representations; historical artifacts
retain their meaning with historical tooling. See [realizations](control-realization.md).
