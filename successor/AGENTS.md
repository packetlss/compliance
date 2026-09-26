# Successor source area

Read root `AGENTS.md`, the accepted task contract, and the existing owners:

- [ADR 0025](../docs/adr/0025-trusted-snapshot-successor.md) for trust, supersession and promotion gates;
- [Successor architecture](../docs/SUCCESSOR_ARCHITECTURE.md) for behavior and open decisions;
- [Development workflow](../docs/DEVELOPMENT_WORKFLOW.md#successor-lane-activation) for target routing, checks and activation;
- [Repositories](../docs/REPOSITORIES.md#successor-repository-strategy) for isolation and cutover.

This is a temporary isolated source area, currently instruction/README files only.
#208 bootstraps infrastructure on `main`; it does not authorize an application
skeleton, production platform, schema, criterion implementation or #209 execution.
#209 remains blocked until bootstrap merge AND recorded administrator activation.

After activation, start successor tasks in a new T3 worktree from verified current
`successor`, and target PRs at `successor`. Record the exact target/base/head. Read
successor architecture at that target revision; do not substitute default-branch
copies or create a second specification here. Shared decisions require explicit
reconciliation; no automatic main merges or mechanical legacy cherry-picks.

Runtime, build, tests and packaged execution must be independent of legacy modules,
CLI, generated schemas and fixture builders. Commodity infrastructure tools are
allowed. Use `scripts/dev foundation` for bootstrap infrastructure; it installs no
legacy application stack and claims no application/acceptance/packaging coverage.
The bounded scope guard currently admits only these two successor files and listed
shared owners. A separately accepted executable contract must extend it together
with real head and current-target integration checks. Legacy application changes
require separately reviewed cross-boundary authorization and affected validation.

No direct implementation pushes to the integration branch. Exact-head independent
review, current-target-base evidence and human final squash merge remain required.
Real private inventory, evidence, realizations, credentials and results stay outside
this repository. Generated execution material is untracked.
