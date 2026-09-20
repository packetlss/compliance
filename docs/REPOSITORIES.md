# Repository and logical ownership map

Repository layout is not semantic policy, release, or runtime identity. This document defines current logical ownership in the consolidated repository.

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
| System architecture/workflow | `docs/`, root `AGENTS.md` | Current normative architecture, ADRs, workflow, repository/trust boundaries and migration provenance |
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
