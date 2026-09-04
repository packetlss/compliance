# Compliance repository instructions

This repository is the **sole authoritative development and documentation repository for consolidated non-sensitive compliance source**.

## Durable authority

Before implementation, read the applicable bounded GitHub issue, this file, and the current normative destination documentation:

- `docs/ARCHITECTURE.md`
- `docs/REPOSITORIES.md`
- `docs/DEVELOPMENT_WORKFLOW.md`
- `docs/CONTRACT_MATURITY.md`
- accepted ADRs in `docs/adr/`

Historical `packetlss-labs/compliance-workspace` and former component repositories remain design/migration/release provenance only. Their repository topology, gitlinks, issue numbers, workflow assumptions, and historical copies of architecture documents are not current authority when they differ from destination state.

Preserve these invariants:

- runtime and semantic identity is content-addressed; Git repository, owner, commit, checkout path, historical workspace pin, URL, and source order are acquisition/review metadata unless a contract explicitly consumes those exact bytes;
- `tooling/` is the explicit tooling source/build root and the Python distribution identity remains `compliance-tooling` unless separately reviewed;
- policy inputs are independently named/materialized semantic roots, including `shared-library`, `verification-policy`, and real or synthetic environment-private sources;
- repository co-location must not create a merged policy tree or source precedence;
- source/file order is nonsemantic; exact-identical same-identity definitions may coalesce and divergent definitions fail closed;
- ordinary technical assessment and optional requirement/realization assurance remain complementary paths;
- missing, stale, invalid, or inconclusive required evidence produces `unknown`, never `pass`;
- authored realization/adoption state is not evidence of implementation;
- the provenance-bearing assessment plan is the external-adapter handoff;
- in-core configuration compilation/rendering, backend credentials/state, apply authority, and executable adapter/plugin runtime remain outside the core;
- verification policy remains source-only and must not regain an independent hosted release lane merely because it is co-located;
- real private inventory, evidence, realizations, credentials, secrets, provider state, generated results, and other need-to-know operational data stay outside this repository;
- generated evidence, plans, results, caches, and backend/external-adapter outputs are not authoritative source and remain untracked;
- firewall-related repositories and product work are out of scope unless explicitly reopened.

## Logical roots

Current authoritative non-sensitive roots include:

```text
tooling/
policy-sources/control-library/policies/      # shared-library
policy-sources/verification-policy/policies/  # verification-policy
projects/mock-fleet/
projects/server-personas/
verification/fixtures/iam-private-boundary/
verification/scenarios/
```

Each project remains logically independent. Canonical scenarios own complete integration/feature coverage. `tooling/` is the sole Python project/build root unless a separately reviewed package decision changes it.

The synthetic IAM fixture proves a private-source boundary only by physically materializing its retained `policy/` tree into a separate temporary `environment-private` source before execution. Never make it pass through implicit repository traversal or by copying the restricted realization into either central policy source. Real private environments remain separate.

## Provenance successor boundary

ADR 0007 successor implementation (`project-config/v1alpha3`, composition lock, assessment provenance and v4 plan/results) is accepted design but remains bounded work in destination #31–#36. Until those consumer cutovers complete, preserve the current experimental runtime contracts required by active source.

Do not silently redesign detailed requirement/realization assurance semantics while implementing ADR 0007. Destination #37 owns that design.

Expected identity never substitutes for actual identity. Source/editable execution records actual tooling source identity without a fake wheel. Installed-wheel execution may claim an actual wheel digest only through verified acquisition/install provenance. Git/repository/path/release coordinates remain nonsemantic.

## Development workflow

Normal work follows:

```text
classify/design
  -> bounded GitHub issue
  -> fresh branch from current main
  -> focused implementation
  -> PR
  -> local validation where material
  -> CI on the reviewed revision
  -> review/re-review
  -> human squash merge
```

Do not implement directly on `main`.

Implementation-local questions may be resolved when they do not change semantics, architecture/trust boundaries, public or cross-component contracts, release identity, introduce a new common abstraction, or materially broaden issue scope. Architectural findings return to the design loop and must be recorded durably before implementation relies on them.

Normal CI uses the single destination checkout and must not restore old sibling-acquisition `COMPLIANCE_CI_*` credentials, PAT fallback, historical sibling clones/checkouts, repository-coordinate integration manifests, or a workspace-baseline dependency.

Stable validation contexts are:

- `component-validation`
- `verification-scenarios`
- `installed-release-provenance`

Provider branch protection/rulesets/required-status enforcement are optional operational hardening under ADR 0008; project workflow and reviewed CI evidence remain required regardless of provider enforcement.

## Historical repositories

The former `packetlss-labs` component repositories and `compliance-workspace` are provenance-only retirement surfaces. Active future work is owned by destination issues #31–#38. Do not start new implementation in a historical repository or refresh the retired workspace topology.

Historical commits, issues, pull requests, tags, Releases, and hosted assets must remain discoverable and must not be rewritten or republished merely because source authority moved here.

## Retirement exception

Destination #29 temporarily authorizes automatic routine retirement work only when the action is bounded documentation/routing/provenance/mechanical cleanup, changes no semantics/release identity/trust boundary/public contract, exact-head applicable CI is green, the reviewed diff matches its issue contract, and no active work/history is lost.

Any architectural finding, persistent functional CI failure, unexpected historical source change, unroutable active work, provenance-loss risk, unavailable required archive/settings operation, or firewall dependency stops retirement and requires human intervention.

This retirement exception does not authorize automatic semantic implementation or change the normal human final-merge rule for product work. It ends when #29 retirement is complete.