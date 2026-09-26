# Successor source area

Read root `AGENTS.md`, the accepted task contract, and the existing owners:

- [ADR 0025](../docs/adr/0025-trusted-snapshot-successor.md) for trust, supersession and promotion gates;
- [ADR 0026](../docs/adr/0026-minimal-successor-production-architecture.md) for production platform, operating/value contracts, test selection and sequence;
- [Successor architecture](../docs/SUCCESSOR_ARCHITECTURE.md) for behavior and acceptance stories;
- [Development workflow](../docs/DEVELOPMENT_WORKFLOW.md#successor-lane-activation) for target routing, checks and activation;
- [Repositories](../docs/REPOSITORIES.md#successor-repository-strategy) for isolation and cutover.

This temporary isolated area contains the merged disposable #209 experiment.
#208 activation and #209 Phase A/B are complete. ADR 0026 promotes fresh Go
production with trusted embedded OPA and initially Linux packaging; the experiment
is not seed code or a test suite to port. Production requires separately promoted
bounded contracts and trusted-base path admission after #217 human merge.

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
and shared owners, and only `successor/experiments/209-platform/` for #209's disposable
experiment. Other application paths fail closed. Exact experiment responsibilities
are `successor-experiment`, `successor-package-linux`, `successor-package-macos`
alongside `successor-foundation`; shared scope also requires all four legacy jobs.
These current duties are not the production target: use the workflow owner's
[bounded CI migration](../docs/DEVELOPMENT_WORKFLOW.md#durable-production-successor-ci),
which retires experiment wiring and native macOS production gating. No workflow or
ruleset change is authorized by #217.

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
