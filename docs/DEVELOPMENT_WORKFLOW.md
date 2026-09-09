# Development workflow

This document defines the engineering lifecycle for `packetlss/compliance`. It applies to human-written changes and work performed through T3 Code or another agent interface.

The issue, PR, CI, review, and definition-of-done requirements are independent of implementation agent.

## Repository authority and handoff

Durable repository artifacts are normative project state. Git is the handoff boundary between design, implementation, review, and future sessions.

Chat history, T3 thread history, provider session history, AI memory, and scratch state are not normative. A fresh human or agent must be able to reconstruct implementation work from this repository, its issue or PR-only contract, and linked durable design material.

Use each artifact for one role:

- architecture docs — current semantics, invariants, boundaries, ownership, public/cross-component contracts;
- ADRs — significant decisions, alternatives, rationale and consequences;
- issues — durable implementation contracts and multi-step coordination;
- tests — executable behavior/invariant evidence;
- PRs — proposed delta, validation, findings and review history;
- Git/releases — reviewed implementation and historical provenance.

A design decision constraining implementation must be recorded durably before implementation relies on it.

## Explore → promote → implement → review

```text
read-only exploration thread
  -> no action, or a distilled promotion packet
  -> durable design decision when needed
  -> GitHub issue when durable coordination is required
  -> new implementation thread in an isolated worktree
  -> working-tree tests
  -> committed candidate and impact-selected canonical local validation
  -> PR linked to the issue/thread
  -> concurrent fresh-context review and CI on the exact PR head
       | no finding
       |   -> exact-head CI -> human squash merge
       | implementation-local
       |   -> return to implementation -> re-review
       |
       + architectural finding
           -> return to exploration
           -> update durable design and contract before implementation resumes
```

Implementation-local findings may be resolved when they do not alter semantic meaning, architecture/trust boundaries, public/cross-component contracts, release identity, a new common abstraction, or issue scope.

Return to exploration when a proposed resolution would:

- change semantic meaning;
- add/remove/weaken an architecture invariant;
- move an architecture or trust boundary;
- change a public or cross-component contract;
- introduce a new common abstraction;
- materially broaden scope; or
- contradict normative documentation.

Implementation convenience must not silently become architecture.

## Change classification

Use the narrowest scope that correctly satisfies the implementation contract.

| Class | Typical owner / integration behavior |
| --- | --- |
| Architecture/workflow | Destination docs/ADR issue; implementation waits for durable decision when semantics change |
| Single logical component | Component root only; focused component validation plus applicable stable destination contexts |
| Cross-component contract | One coordinating destination issue may authorize an atomic PR across co-located roots; canonical integration required |
| Canonical integration | `verification/scenarios/`; complete public behavior/feature coverage |
| Installed-release/provenance | `tooling/` plus release validation lane |
| Pre-freeze compatibility removal | Owning component after current replacement and consumer cutover are explicit |

Co-location permits atomic cross-component changes only when a durable issue explicitly authorizes that scope.

## T3 Code thread modes

Use one T3 Code project rooted at this repository. Logical component roots remain repository-level ownership boundaries, not separate T3 projects.

### Exploration thread

Use an ordinary thread against a clean default-branch checkout with a read-only task contract and a supervised permission mode. It may inspect source, run non-mutating checks, test assumptions, compare alternatives, and construct a promotion packet. It does not edit files, create branches, or mutate GitHub.

The promotion packet contains the objective, write scope, design basis, acceptance criteria, non-goals, invariants, expected invalid behavior, validation, escalation conditions, and dependencies. Only accepted decisions that constrain future work become repository documentation or ADRs.

### Implementation thread

Create a new T3-managed worktree from current `main`. The initial prompt names the issue or PR-only contract, applicable instruction route, write scope, required validation, and escalation conditions. One implementation thread owns edits in a worktree at a time.

Resolve implementation-local questions within the contract. Return architectural findings to exploration rather than silently changing semantics, boundaries, contracts, or scope. Use fast working-tree tests during development; create a checkpoint commit before canonical gates that validate committed exported inputs.

### Review thread

After a PR is ready, start a fresh-context thread against its exact head. The review is read-only and checks both the implementation contract and repository standards. It reports actionable findings with locations and evidence, and does not edit the implementation worktree.

Material fixes return to the implementation thread and require re-review of the new head. Record the reviewer/provider, reviewed head, findings, and disposition in the PR. A review from another agent context is useful evidence but is not a substitute for human final merge authority.

## Implementation contracts

A durable issue is required for architecture or semantic changes, trust/repository/release boundaries, public or cross-component contracts, dependent migrations, backlog coordination, and work expected to span threads or sessions.

A narrow nonsemantic documentation, test, refactor, or mechanical change may use its PR body as the implementation contract when it is expected to complete in one worktree and does not need independent backlog identity.

Every implementation contract states enough durable context for a fresh implementation session:

- objective and write scope;
- design basis;
- required behavior and acceptance criteria;
- non-goals;
- architecture/provenance/compatibility/trust constraints;
- expected invalid/failure behavior;
- escalation conditions;
- required validation; and
- dependencies/sequencing.

Link authoritative ADRs rather than duplicating them. A thread transcript may be referenced for convenience but cannot supply missing normative scope.

## Repository-local validation

Substantial implementation uses a T3 worktree and the repository's accepted toolchain. CI is an independent clean-environment gate, not a substitute for material local implementation testing.

Fast focused tests must read current uncommitted changes. Canonical component and scenario gates export committed inputs and therefore run only after a checkpoint commit from a clean worktree. Run applicable working-tree checks locally; select full canonical local gates by impact or reproduction need. A local pass never replaces CI.

Normal validation must not recreate the retired multi-repository workspace dependency graph. Component gates use co-located explicit roots, repository-owned fixtures, installed artifacts, or canonical integration as appropriate.

Runtime/provenance tests should materialize committed inputs into temporary non-Git roots where that proves independence from checkout/Git topology.

## Validation architecture

Three stable contexts own the validation layers.

### `component-validation`

Runs repository validation plus focused tooling, policy-source, ordinary-project and IAM private-boundary gates. It does not run the complete feature suite.

### `verification-scenarios`

Runs the canonical deterministic composed scenario/feature suite from a temporary non-Git assembly of explicit destination roots. It owns all 22 retained public CLI leaves and 19 retained domain features.

### `installed-release-provenance`

Runs release-critical installed/no-Git, locked-artifact, release preparation/tag and generic policy-source release/provenance validation.

### `macos-portability`

Runs repository setup/doctor, focused identity/tooling checks, and representative package/release entrypoints on macOS arm64 with native Bash and utilities. Linux CI remains the full automated validation authority.

Historical pre-freeze readability is not a default required gate unless an explicit freeze or bounded historical-reproduction contract requires it.

## Branches and PRs

Use short-lived branches and isolated worktrees from current `main`. T3-generated branch names are accepted; branch names are operational metadata rather than durable task identity. Identify the task through its linked issue or PR and a clear T3 thread title. Do not implement directly on `main`.

Every PR links its issue when one is required, or contains its narrow PR-only contract, and records:

- what changed and why;
- behavioral impact;
- validation actually performed;
- architecture/provenance/compatibility impact;
- material implementation findings or `None`;
- the independently reviewed exact head and outcome; and
- integration/migration impact where applicable.

Squash merge is the only normal merge method. Delete merged branches after merge and settle the linked T3 thread.

## Merge authority

All PRs require human final merge after independent review and green exact-head CI. Agents must not enable or invoke automatic merge unless a future durable decision explicitly creates a new bounded exception.

## CI and dependency direction

Target dependency direction is:

```text
focused component validation
        |
        v
canonical composed integration
        |
        v
installed/release provenance as applicable
```

Normal destination CI uses one repository checkout. It must not depend on historical component repositories, the old workspace, sibling App credentials, PAT fallback, mutable branch resolution, or repository-coordinate acquisition manifests.

Stable context names should change only through bounded migration with replacement evidence.

CI may cancel a superseded run for an older head of the same PR. It must not path-filter away a stable context or treat a stale green revision as evidence for the current head.

## Review and definition of done

Review the current PR head, not a stale earlier revision. The candidate must contain the freshly resolved current `main` head; advancing `main` requires candidate integration and new exact-head evidence. `scripts/dev readiness` checks the compact PR review record and required contexts but never posts, mutates, or merges. A PR is complete only when its implementation contract is satisfied, required local/CI validation is recorded and green, fresh-context review is recorded, implementation findings are captured, generated/temporary state is clean, and no unresolved architectural finding remains.

Historical preservation is distinct from current compatibility. Do not keep active complexity solely because an unfrozen historical artifact exists.

## Private/trust boundaries

Real private environment inputs remain outside this repository. The synthetic IAM fixture tests private-source isolation only by separately materializing `environment-private`; it does not convert a public/co-located fixture into an access-control boundary.

Generated evidence/results, credentials, backend state, adapter output and private operational data remain non-authoritative/untracked.

## Firewall boundary

Firewall/network-policy work is out of scope unless explicitly reopened by the product owner. Destination #38 is a dormant conceptual-alignment issue and does not authorize technical coupling.
