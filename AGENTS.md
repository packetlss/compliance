# Compliance repository instructions

This repository is the sole authoritative development and documentation repository for consolidated non-sensitive compliance source.

## Authority and reading order

Conversation history, agent memory, and scratch files are not normative. Use this order when reconstructing work:

1. the accepted issue or PR-only implementation contract;
2. this file and the nearest applicable nested `AGENTS.md`;
3. the routed architecture, workflow, and component documentation below;
4. accepted ADRs and executable tests.

Read only the material applicable to the task. If instructions conflict, stop and surface the conflict rather than choosing silently.

| Change area | Required routing |
| --- | --- |
| Architecture, semantics, trust, release, or compatibility | `docs/ARCHITECTURE.md`, `docs/CONTRACT_MATURITY.md`, applicable ADRs |
| Successor source/workflow | `successor/AGENTS.md`, `docs/DEVELOPMENT_WORKFLOW.md`, `docs/REPOSITORIES.md`; explicit target branch and recorded activation |
| Accepted successor direction, acceptance stories, or platform-experiment specification | `docs/adr/0025-trusted-snapshot-successor.md`, `docs/SUCCESSOR_ARCHITECTURE.md`; no executable successor work without its separately promoted contract |
| Repository ownership or development workflow | `docs/REPOSITORIES.md`, `docs/DEVELOPMENT_WORKFLOW.md` |
| Tooling, CLI, schemas, provenance, packaging | `tooling/AGENTS.md`, then its linked detailed contract |
| Reusable policy and controls | `policy-sources/control-library/AGENTS.md` |
| Synthetic verification policy | `policy-sources/verification-policy/AGENTS.md` |
| Ordinary development projects | `projects/AGENTS.md` |
| Canonical composed verification | `verification/scenarios/AGENTS.md` |
| IAM private-boundary fixture | `verification/fixtures/iam-private-boundary/AGENTS.md` |

Historical `packetlss-labs` repositories are archived provenance only. Never treat their topology, workflow, or historical copies of current documents as active authority.

ADR 0025 and the successor architecture describe **accepted direction, not an
implemented replacement**. Existing component instructions and contracts govern
the implemented legacy tree. Do not carry its content identity, schemas, Python
packaging or artifact mechanisms into the successor by default. Do not apply target
retirements to legacy runtime or validation without an explicitly reviewed migration.
Roadmap #85 owns sequencing, not a second architecture specification. #208 owns
bounded two-lane bootstrap; #209 is blocked on bootstrap merge and recorded lane
activation. After activation, read successor authority on the successor target,
while main retains legacy authority and this route. Reconcile material shared
decisions explicitly; do not maintain competing successor specifications.

## T3 Code task lifecycle

Use one T3 Code project at this repository root.

- **Explore:** use a read-only thread against a clean checkout of the task's explicit integration branch (`main` for legacy/shared bootstrap, activated `successor` for successor work) for uncertain architecture, semantic, trust, or cross-component design. Inspect and reason, but do not edit files or mutate GitHub. End with either no action or a promotion packet covering objective, write scope, design basis, acceptance criteria, non-goals, invariants, expected failures, validation, escalation conditions, and dependencies. Narrow understood nonsemantic work may begin directly in an implementation worktree with a PR-only contract.
- **Implement:** start a new T3-managed worktree from the verified current integration target. #208 bootstrap targets `main`; after recorded activation, successor tasks start from and target `successor`. Record actual target and exact base/head in each contract/PR. A durable issue is required for architecture, semantics, trust/release boundaries, cross-component contracts, dependent migrations, or work expected to span sessions. A narrow nonsemantic documentation, test, refactor, or mechanical change may use the PR body as its contract.
- **Review:** use a fresh-context, read-only thread against the exact PR head. Review and CI may run concurrently. The reviewer reports findings and does not edit the implementation worktree. Material fixes return to implementation and require re-review and CI of the new head.
- **Merge:** CI and independent review provide evidence; a human retains final squash-merge authority.

Do not implement directly on `main` or `successor`. T3-generated branch names are allowed; durable task identity comes from the linked issue or PR, not the branch name. Do not run two editing threads in the same worktree concurrently.

Implementation-local questions may be resolved only when they do not change semantics, architecture or trust boundaries, public or cross-component contracts, release identity, introduce a new common abstraction, or materially broaden scope. Otherwise return to exploration and update the durable contract before proceeding.

## Global invariants

- **Implemented legacy only:** runtime and semantic identity is content-addressed; Git repository, owner, commit, checkout path, URL, and source order are acquisition/review metadata unless a contract explicitly consumes those bytes. ADR 0025 owns the successor trust reduction.
- **Implemented legacy only:** `tooling/` is the sole Python source/build root and the distribution remains `compliance-tooling`. These remain enforced until an explicitly reviewed migration; they do not select the successor platform or packaging.
- Policy inputs are independently named and materialized semantic roots. Co-location must not create a merged tree or precedence.
- Source/file order is nonsemantic. Exact-identical same-identity definitions may coalesce; divergent definitions fail closed.
- Technical assessment and optional requirement/realization assurance remain complementary paths.
- Missing, stale, invalid, or inconclusive required evidence produces `unknown`, never `pass`; authored realization/adoption state is not implementation evidence.
- The resolved assessment plan is the external-adapter handoff (provenance-bearing under the legacy contract). Backend compilation, credentials/state, apply authority, and executable adapter/plugin runtime remain outside the core.
- Real private inventory, evidence, realizations, credentials, secrets, provider state, and results stay outside this repository.
- Generated evidence, plans, results, caches, and adapter/backend output are untracked execution material, not authored policy. Retained plans/results preserve their exact historical assertion; legacy validation/identity rules remain enforced, while successor record representation/admission remains an open decision.
- Verification policy remains source-only with no independent hosted release lane.
- Firewall and network-policy work is out of scope unless explicitly reopened.

Detailed requirement/realization assurance contracts remain separately routed; do
not redesign them incidentally.

## Validation and pull requests

Use applicable fast tests against the working tree during implementation. Select full canonical local gates by change impact or reproduction need; they are not an unconditional pre-PR requirement. Canonical gates that export committed inputs require a clean, committed candidate revision; create a checkpoint commit before running them. Local evidence never substitutes for exact-head CI.

Every PR must record its contract, change and behavioral impact, validation actually performed, architecture/provenance/compatibility/trust impact, material findings, and exact-head independent review outcome. Preserve these stable CI contexts on every PR targeting `main`, including this bootstrap, and on successor PRs affecting shared infrastructure. Their implementation-specific responsibilities validate the legacy tree until a bounded successor migration replaces them; target retirement is not permission to bypass them:

- `component-validation`
- `verification-scenarios`
- `installed-release-provenance`
- `macos-portability`

Successor-only bootstrap PRs require real `successor-foundation` infrastructure
execution. The workflow checks every PR to either target without path filters.
Bounded scope admission refuses legacy application/build/fixture changes on
successor; separately reviewed cross-boundary contracts must amend routing and
validate every affected responsibility. Application/acceptance/Linux/native macOS
packaging checks are pending #209, not placeholder jobs. See the exact matrix and
administrator activation checklist in `docs/DEVELOPMENT_WORKFLOW.md`.

Normal validation uses one destination checkout. Do not restore historical sibling acquisition, `COMPLIANCE_CI_*` credentials, PAT fallback, repository-coordinate manifests, or mutable branch resolution. A PR is complete only when its contract is satisfied, applicable local and exact-head CI evidence is green, findings are resolved, and generated state is clean.

Review and all checks required by the target/scope bind to the exact PR head and
reviewed target. If only the base advances, preserve that PR-head evidence and
refresh only the separate `integration-current-main` or
`integration-current-successor` proof for the exact current target base. Retargeting
requires review of that target and its actual validation responsibilities. A PR-head change
invalidates review, head CI, and integration evidence. Synthetic integration is
mechanical compatibility evidence only: return to implementation or architecture
when the intervening base delta materially changes authority, trust/release
boundaries, contracts, dependencies, scope, or invariants.
