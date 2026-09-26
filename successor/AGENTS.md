# Successor source area

Read root `AGENTS.md`, the accepted task contract, and the existing owners:

- [ADR 0025](../docs/adr/0025-trusted-snapshot-successor.md) for trust, supersession and promotion gates;
- [Successor architecture](../docs/SUCCESSOR_ARCHITECTURE.md) for behavior and open decisions;
- [Development workflow](../docs/DEVELOPMENT_WORKFLOW.md#successor-lane-activation) for target routing, checks and activation;
- [Repositories](../docs/REPOSITORIES.md#successor-repository-strategy) for isolation and cutover.

This is a temporary isolated source area, currently instruction/README files only.
#208 bootstrap and lane activation are complete (see #208 and latest #85 comments).
#209's accepted execution sequence has two PRs: Phase A admits scope/CI duties;
only after its human merge may Phase B add the disposable executable experiment.
Neither phase selects a production platform or authorizes production implementation.

After activation, start successor tasks in a new T3 worktree from verified current
`successor`, and target PRs at `successor`. Record the exact target/base/head. Read
successor architecture at that target revision; do not substitute default-branch
copies or create a second specification here. Shared decisions require explicit
reconciliation; no automatic main merges or mechanical legacy cherry-picks.

Runtime, build, tests and packaged execution must be independent of legacy modules,
CLI, generated schemas and fixture builders. Commodity infrastructure tools are
allowed. Use `scripts/dev foundation` for bootstrap infrastructure; it installs no
legacy application stack and claims no application/acceptance/packaging coverage.
The bounded scope guard admits these two successor files, the listed documentation
and shared owners, and only `successor/experiments/209-platform/` for #209's future
experiment. Other application paths fail closed. Exact experiment responsibilities
are `successor-experiment`, `successor-package-linux`, `successor-package-macos`
alongside `successor-foundation`; shared scope also requires all four legacy jobs.

Scope and duty selection come from reviewed target B, never proposed H. Phase A
adds no application or placeholder job and refuses experiment success until real
jobs exist. After its merge, Phase B adds actual head and current-successor
execution and replaces that refusal with required-result aggregation. Read the
[workflow sequence](../docs/DEVELOPMENT_WORKFLOW.md#209-two-phase-execution-contract)
for the trusted-dispatch limitation when B lacks those jobs and the administrator
checkpoint: enforce the three real contexts before Phase B's human merge.
Legacy application changes still require separately reviewed cross-boundary
authorization and affected validation.

No direct implementation pushes to the integration branch. Exact-head independent
review, current-target-base evidence and human final squash merge remain required.
Real private inventory, evidence, realizations, credentials and results stay outside
this repository. Generated execution material is untracked.
