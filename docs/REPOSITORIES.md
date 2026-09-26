# Repository and logical ownership map

Repository layout is not semantic policy, release, or runtime identity. This
document owns repository strategy and current logical ownership. Existing roots,
release units and implementation-specific validation responsibilities below describe
the **implemented legacy** tree. [ADR 0025](adr/0025-trusted-snapshot-successor.md)
accepts a successor. [ADR 0026](adr/0026-minimal-successor-production-architecture.md)
promotes Go and initially Linux packaged/offline production. #208 activated its
development lane; #209 is disposable experiment evidence, not production code.

## Successor repository strategy

Keep this repository as the sole authority for non-sensitive successor source and
documentation. Preserve the legacy baseline in Git history and plan a separately
authorized durable legacy reference before cutover. #206 creates no repository,
tag or release, rewrites no history and deletes no legacy code.

Use `successor/` as the explicitly temporary isolated source area under #208. Its
bootstrap began with instructions/README only; the merged #209 experiment now
lives in its own subtree. Production must be fresh and must not import that subtree. `main` remains the working legacy/default branch. After the
[recorded activation checkpoint](DEVELOPMENT_WORKFLOW.md#successor-lane-activation),
`successor` is a temporary integration branch receiving small reviewed PRs.
Successor-specific authority is read at that target, using these existing document
owners; reconcile material shared decisions explicitly. No automatic main merge,
mechanical legacy-feature cherry-pick or competing successor specification. New implementation
must not import legacy runtime modules, invoke the legacy CLI, depend on legacy test
helpers or use legacy generated schemas as authority. Existing authored intent and
edge cases may inform fresh examples; code and fixtures do not survive by default.
No staging directory is an access-control boundary: real private inputs remain in
their separate authorized environments.

At explicit cutover there is one current implementation, under
[ADR 0025's compatibility decision and gates](adr/0025-trusted-snapshot-successor.md#repository-and-compatibility-decision).
The current `tooling/` Python root, `compliance-tooling` distribution, policy-source
release construction and CI responsibilities remain in force for legacy work until
their owning bounded migrations are reviewed. They do not prescribe the successor's
source layout, release units or platform.

## Active repository

`packetlss/compliance` is the active development repository for non-sensitive compliance source.

| Logical area | Destination root | Responsibility |
| --- | --- | --- |
| Tooling | `tooling/` | CLI, planner/evaluator, collectors, tooling-owned schemas, provenance/release implementation and tests; Python distribution `compliance-tooling` |
| Shared policy | `policy-sources/control-library/` | Reusable controls/helpers, policy/evidence/parameter contracts, provider-neutral policy release/archive construction; semantic source `control-library` |
| Verification policy | `policy-sources/verification-policy/` | Synthetic baselines, requirements/realizations, mappings, deliberate conflicts and verification-only resources; semantic source `verification-policy`; source-only lifecycle |
| Ordinary projects | `projects/mock-fleet/`, `projects/server-personas/`, `projects/alder-forge-dcc-level3/` | Independent exploratory/reference project inventory, assignments, fixtures, waivers and generated-state paths |
| IAM synthetic boundary | `verification/fixtures/iam-private-boundary/` | Synthetic proof of a separately materialized `environment-private` source; not a real private-data repository |
| Canonical scenarios | `verification/scenarios/` | Deterministic complete integration, expected outcomes, all 27 public CLI leaves and 19 domain features |
| System architecture/workflow | `docs/`, root `AGENTS.md` | Routed implemented legacy and accepted successor architecture, ADRs, workflow, repository/trust boundaries and migration provenance |
| Successor staging | `successor/` | Temporary isolated area with disposable #209 experiment; production paths require separately reviewed admission and implementation contracts |
| CI/toolchain | `.github/`, `toolchain/`, root scripts/tests | Stable component, scenario and installed-release gates |

## Logical ownership rules

### Tooling

Change `tooling/` for executable CLI/planner/evaluator behavior, generic collectors, tooling-owned schemas, actual/expected composition provenance implementation, package/release construction, and detailed executable contracts.

In-core configuration compiler/renderers/configuration artifacts/plugin runtime remain removed. Assessment plans are the external-adapter handoff.

### Policy sources

Reusable control/helper/schema changes belong to `control-library`. Synthetic verification-only policy belongs to `verification-policy`. These are independent semantic roots even though they share one Git repository.

Do not duplicate reusable controls into verification policy. Do not move private environment parameters/realizations into either central source. Release coordinates/repository paths are not policy-source identity.

### Projects

Each ordinary `projects/<id>/` is logically independent. Co-location does not permit inventories, assignments, fixtures, waivers, evidence, results, or project catalogs to merge across project boundaries.

Generated evidence/plans/results/caches/adapter outputs remain untracked runtime
state, not authored policy. Retained validated plans/results remain authoritative
for their exact historical assertion; retention is externally owned.

### Private environments and synthetic IAM proof

Real need-to-know environments remain separate repositories/workspaces and execution contexts.

The destination IAM fixture is deliberately non-sensitive. Its `policy/` tree must be copied into a separate temporary `environment-private` source before execution; the central fixture path is not itself the runtime source boundary.

### Verification and integration

Stable complete end-to-end behavior belongs to `verification/scenarios/`. Component areas retain focused tests and do not duplicate the complete feature suite.

`verification-scenarios` proves ordinary technical assessment, objective assurance, pass/fail/unknown/waiver/conflict behavior, private-source materialization, provenance, and external-adapter handoff without executing adapters.

### System architecture

Current system architecture, repository/trust boundaries, workflow and accepted
ADRs belong to `packetlss/compliance/docs/`. Component documents own detailed local
contracts. Historical issues and repositories preserve rationale and delivery
history; new scope requires a current implementation contract.

## Release units

Source repository and release unit are distinct concepts.

- `compliance-tooling` Python distribution remains independently versioned/releasable from `tooling/`.
- `control-library` retains independently digestible/releasable policy-source construction.
- `verification-policy` remains source-only with no current hosted release lane.
- Generic policy-source artifact schemas/validation are tooling-owned.
- Historical hosted releases remain in their original repositories and are not republished by retirement.

## Validation ownership

The four contexts below remain mandatory for main and affected shared
infrastructure. Successor-only bootstrap uses `successor-foundation`; the
[workflow matrix](DEVELOPMENT_WORKFLOW.md#two-lane-validation-matrix) owns exact
routing, current experiment duties and future production CI migration. Ordinary
successor work stops running legacy application gates only after that migration;
genuinely shared repository-global infrastructure retains both affected lanes.

| Stable context | Owner |
| --- | --- |
| `component-validation` | Focused repository/tooling/policy/project/IAM validation |
| `verification-scenarios` | Canonical complete composed integration/feature suite |
| `installed-release-provenance` | Installed/no-Git, locked artifact, release preparation/tag and generic release provenance |
| `macos-portability` | Native macOS arm64 setup/doctor, focused identity/tooling checks and representative package/release entrypoints; Linux remains the full automated validation authority |

Normal validation uses the current destination revision and temporary non-Git materialization. No old sibling App/PAT acquisition is required.

## Historical repositories

These archived repositories retain pre-consolidation history and release/design provenance:

- `packetlss-labs/compliance-tooling`
- `packetlss-labs/compliance-control-library`
- `packetlss-labs/compliance-verification-policy`
- `packetlss-labs/compliance-development-projects`
- `packetlss-labs/compliance-project-iam-realization`
- `packetlss-labs/compliance-verification-scenarios`
- `packetlss-labs/compliance-workspace`

Exact source cutover commits and digests are recorded in `docs/history/pre-consolidation.md`.

Historical repository separation must not be reintroduced merely because a policy source needs its own digest, a fixture tests isolated materialization, or historical Git is useful provenance.

## Separate repositories remain appropriate when

Use a separate repository/execution boundary when there is a material real reason such as:

- need-to-know/visibility separation;
- distinct ownership/approval authority;
- a genuinely independent lifecycle that benefits from separate source control; or
- a downstream/private consumer whose acquisition boundary is itself meaningful.

Do not create one solely to simulate semantic source isolation or internal development topology.

## Exact-tree successor cutover

Cutover is a separately accepted migration, not part of #208 or an automatic
consequence of a successful experiment. Preserve legacy source/tooling access at
recorded immutable revisions through an authorized historical reference before
removal; do not create tags/releases as part of this bootstrap.

Map each legacy assertion to retained behavior with a fresh executable owner, a
deliberately retired guarantee from ADR 0025, or an implementation detail not
ported. Output equality and old test counts are not acceptance criteria. Before
retirement require:

- all required successor stories with executable owners and resolved operating contracts;
- an operator walkthrough of personas, Objectives, failures and retained history;
- real packaged assessment and retained explanation outside the checkout on the
  supported production platform, initially Linux, without legacy runtime or a
  normal-runtime network dependency; native macOS is not a product gate;
- build/test/runtime independence with legacy unavailable;
- recorded historical source and tooling access; and
- coherent final instruction, release and required-check routing.

Prepare and validate the **exact removal candidate**: remove obsolete runtime,
build/test helpers, packaging, active docs and CI jobs in that candidate, then run
all adopted successor responsibilities on it. A green successor build alongside
legacy is insufficient. Record exact head/base, independent review, current-base
integration where needed, operator evidence and human cutover authority. There is
no permanent legacy mode, compatibility reader, branch rename/force-push shortcut
or deletion of main. Legacy stays usable until this explicit cutover.
