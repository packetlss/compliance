# Development workflow

This document defines the engineering lifecycle for `packetlss/compliance`. It applies to human-written changes and work performed through T3 Code or another agent interface.

The issue, PR, CI, review, and definition-of-done requirements are independent of implementation agent.

These engineering requirements remain in force for successor documentation and
later work. The toolchain, artifact/provenance and implementation-specific lane
descriptions below validate the **implemented legacy** tree. #208 supplies the
bounded successor infrastructure lane and routing described here; it replaces no
legacy behavior or required main responsibility. [ADR 0025](adr/0025-trusted-snapshot-successor.md#staged-promotion-gates)
owns successor promotion gates; its target retirements do not change workflows or
relax any existing required context. The
[experiment specification](SUCCESSOR_ARCHITECTURE.md#bounded-platform-experiment-specification)
requires separate authorization before execution. No successor platform is selected
by the existing Python development setup.

## Repository authority and handoff

Durable repository artifacts are normative project state. Git is the handoff boundary between design, implementation, review, and future sessions.

Chat history, T3 thread history, provider session history, AI memory, and scratch state are not normative. A fresh human or agent must be able to reconstruct implementation work from this repository, its issue or PR-only contract, and linked durable design material.

Use each artifact for one role:

- architecture docs — explicitly routed implemented legacy and accepted successor semantics, invariants, boundaries, ownership and public/cross-component contracts;
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

Use an ordinary thread against a clean checkout of the task's explicit integration branch with a read-only task contract and a supervised permission mode. It may inspect source, run non-mutating checks, test assumptions, compare alternatives, and construct a promotion packet. It does not edit files, create branches, or mutate GitHub.

The promotion packet contains the objective, write scope, design basis, acceptance criteria, non-goals, invariants, expected invalid behavior, validation, escalation conditions, and dependencies. Only accepted decisions that constrain future work become repository documentation or ADRs.

### Implementation thread

Resolve the task target explicitly with `scripts/dev task --target main` or, after
activation, `scripts/dev task --target successor`. The command reports the current
remote SHA without creating refs or establishing activation. Create a new
T3-managed worktree from that verified revision. #208 bootstrap targets main;
subsequent successor tasks branch from and target successor. The initial prompt
and issue/PR record actual target, exact base/head, contract, instruction route,
write scope, validation and escalation conditions. One implementation thread owns
edits in a worktree at a time.

T3's shared configuration offers explicit legacy setup and foundation actions;
it does not automatically install the legacy stack when creating any worktree.
Legacy commands retain setup-on-demand. `scripts/dev setup --target successor`
only reports infrastructure prerequisites; `scripts/dev foundation` runs the real
standard-library infrastructure suite using Python 3, Git, Bash and jq. It needs no
legacy runtime, dependency installation or fixture builder. This infrastructure
Python use does not select the successor application language.

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

Three stable contexts own the validation layers; `macos-portability` is an
additional required native-platform context. All four execute on every main PR
and on successor PRs touching listed shared infrastructure. Their responsibilities
remain unchanged.

### `component-validation`

Runs repository validation plus focused tooling, policy-source, ordinary-project and IAM private-boundary gates. It does not run the complete feature suite.

### `verification-scenarios`

Runs the canonical deterministic composed scenario/feature suite from a temporary non-Git assembly of explicit destination roots. It owns all 27 retained public CLI leaves and 19 retained domain features.

### `installed-release-provenance`

Runs release-critical installed/no-Git, locked-artifact, release preparation/tag and generic policy-source release/provenance validation.

### `macos-portability`

Runs repository setup/doctor, focused identity/tooling checks, and representative package/release entrypoints on macOS arm64 with native Bash and utilities. Linux CI remains the full automated validation authority.

Historical pre-freeze readability is not a default required gate unless an explicit freeze or bounded historical-reproduction contract requires it.

## Two-lane validation matrix

| Actual PR target / changed scope | Required head execution | Combined H/B execution when H lacks current B |
| --- | --- | --- |
| `main`, including #208 bootstrap | `component-validation`, `verification-scenarios`, `installed-release-provenance`, `macos-portability` | Same four responsibilities plus infrastructure validation; status `integration-current-main` |
| `successor`, bootstrap-only files | `successor-foundation` | Real foundation tests and scope admission; status `integration-current-successor` |
| `successor`, listed shared infrastructure/coordination owners | `successor-foundation` **and all four legacy contexts** | Foundation and all four legacy responsibilities; status `integration-current-successor` |
| `successor`, legacy application/build/fixture or unlisted files | Refuse with paths and contract guidance | Refuse; no successful integration proof |
| Separately promoted executable experiment | **Pending #209:** foundation plus real semantics, end-to-end acceptance, Linux and native macOS packaged execution | Every adopted experiment responsibility; never foundation alone |

The reviewed target B's `toolchain/dev.py` owns the small explicit bootstrap path sets: successor instructions
and its architecture/ADR are successor-only; root coordination docs, task templates,
T3 configuration and the named workflow/development/infrastructure-test files are
shared. Other paths fail closed on successor, including application files until
#209 extends scope and real checks together. There is no per-PR bypass label,
configurable impact framework or implicit authorization from a target branch.
A separately reviewed cross-boundary contract must amend admission and cover every
affected responsibility before legacy application changes may target successor.

Both scope jobs check out trusted B and classify before any proposed code is
merged/executed; main unconditionally requires all four legacy responsibilities.
Readiness loads the fixed classifier file from the same exact target B through
GitHub, rather than letting the local proposed classifier waive duties. This is
read-only and requires no local fetch of B. A classifier change cannot waive its
own validation. #209 must first land scope expansion through a reviewed PR within
already-admitted shared paths, with foundation and all four legacy responsibilities.
Its executable PR then adds genuine application checks and their integration
wiring, with required-check enforcement before that first executable merge. No
placeholder application check is added by the preliminary routing change.

`destination-validation.yml` receives every PR targeting main/successor, including
retarget edits, and pushes to those branches. It checks out exact authored H for
PR validation; only duty selection uses trusted B. No required context is path-filtered away. `validation-routing`
admits scope; `successor-foundation` always reports, verifies required dependencies
and executes real routing/readiness/workflow/isolation tests. It also runs on main
as supplemental infrastructure evidence. Only explicitly unaffected legacy jobs
may be skipped for successor-only changes; their names are never used as proof of
legacy execution. Foundation proves infrastructure only, not application stories,
acceptance or packaging. Those future jobs do not exist yet.

## Branches and PRs

Use short-lived branches and isolated worktrees from the verified current task target (`main` or activated `successor`). T3-generated branch names are accepted; branch names are operational metadata rather than durable task identity. Identify the task through its linked issue or PR and a clear T3 thread title. Do not implement directly on `main` or `successor`.

Every PR links its issue when one is required, or contains its narrow PR-only contract, and records:

- what changed and why;
- behavioral impact;
- validation actually performed;
- architecture/provenance/compatibility impact;
- material implementation findings or `None`;
- the independently reviewed exact head, reviewed target and outcome; and
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

Review the current PR head, not a stale earlier revision. Independent review and
all target/scope-required contexts are PR-head evidence: they bind to exact
authored head H and reviewed target. A head change invalidates all of them. A
base-only advance does not invalidate that evidence. Record `Reviewed target:`
alongside `Reviewed head:`; a retarget requires review of the new target and its
actual checks, and cannot reuse the other lane's integration status.

Before merge, an unchanged PR head that does not already contain its current base
also needs successful `integration-current-main` or `integration-current-successor`
evidence, according to its actual target, attached to H. The trusted on-demand
workflow constructs a disposable local merge of exact current target base B and H,
runs every responsibility for that target/scope on the combined candidate, and
publishes a commit status whose description is exactly
`base=<40-hex-current-base-sha>`. It never pushes the synthetic commit or updates
the PR branch. Run `scripts/dev integration` explicitly to request it; `scripts/dev
readiness` is read-only and only reports whether the review, head contexts, and
when needed the exact head/base integration status are current. Both commands
accept `--target main|successor` to assert the expected target and refuse a mismatch.
Readiness resolves trusted PR metadata, rejects unsupported targets and rechecks
open state, H, target and its current B at the end; earlier successful integration
is insufficient after B changes.

The existing `current-main-integration.yml` filename remains the dispatch entrypoint
for both targets. Dispatch on the **actual integration branch**, never an unreviewed
head: `scripts/dev integration` does this explicitly. The workflow verifies its ref
and workflow SHA against the current target before validation; a raced base advance
requires redispatch. It resolves metadata and publishes statuses in separate jobs
that never check out or execute proposed code. Validation jobs have read-only
permissions, no secret bindings and no persisted checkout credentials. Publication
rechecks open state/head/target/base and treats failed, cancelled, skipped or missing
required execution as failure. No synthetic commit is pushed.

GitHub must first register a dispatch workflow on default main. Before bootstrap
merge, the old trusted main workflow still owns actual integration for this PR;
local tests exercise the proposed successor path but cannot activate it. After
merge, demonstrate dispatch from both supported target refs. Future executable
contracts must extend **both** exact-head and current-target integration execution
with every new application responsibility, including native macOS. A foundation
pass cannot stand in for these. If the target's trusted workflow does not yet run
newly proposed responsibilities, do not claim combined evidence: update/review the
candidate to contain current B, or first land separately reviewed real wiring on
the target. No unreviewed workflow dispatch or unconditional success substitute.

Synthetic integration is mechanical compatibility evidence, not architectural
approval. Examine the intervening base delta and return to implementation or
architecture when it changes semantic or architecture authority, trust/release
boundaries, public or cross-component contracts, explicit dependencies, accepted
scope/invariants, or exposes a material semantic conflict. Independent parallel
work may otherwise remain on its reviewed head until human squash merge.

A PR is complete only when its implementation contract is satisfied, required
local/CI validation is recorded and green, fresh-context review is recorded,
current-base integration evidence is present when required, implementation
findings are captured, generated/temporary state is clean, and no unresolved
architectural finding remains.

Historical preservation is distinct from current compatibility. Do not keep active complexity solely because an unfrozen historical artifact exists.

## Private/trust boundaries

Real private environment inputs remain outside this repository. The synthetic IAM fixture tests private-source isolation only by separately materializing `environment-private`; it does not convert a public/co-located fixture into an access-control boundary.

Generated evidence/plans/results, backend state and adapter output remain untracked
execution material, not authored policy authority. Exact retained validated
plans/results still own their historical assertion. Credentials and real private
operational data stay outside this repository.

## Firewall boundary

Firewall/network-policy work is out of scope unless explicitly reopened by the product owner. Closed historical issue #38 does not authorize technical coupling.

## Successor lane activation

**Pending until separately recorded after human bootstrap merge.** #208's PR may
be reviewed and merged before activation; issue closure alone does not unblock
#209. No bootstrap action creates successor, changes protection/rulesets/default
branch, publishes tags/releases, or resets another branch/worktree.

Administrator/human follow-through must record this precise checkpoint in #208 and
link it from #85 before starting #209:

1. Record the reviewed bootstrap PR, human squash merge SHA and current main SHA.
   Verify the merge is an ancestor of current main and its routing/workflow files
   are present. Reconcile any material intervening change. After explicit human
   authorization, create `refs/heads/successor` at that verified bootstrap-containing
   main SHA, recording actor/time/SHA. If successor already exists, stop and inspect;
   never reset it or discard any existing worktree. Keep main the default. Refresh
   imported T3 project actions from `t3.json`, removing any previously saved automatic
   legacy setup action before creating successor worktrees.
2. Inspect repository and inherited rulesets, all matching ref conditions, classic
   protection, bypass actors and effective branch rules. Capture API/UI evidence;
   `protected: true` is insufficient. Configure successor for PR-only updates, no
   ordinary direct writes, no force pushes and no branch deletion; human final
   squash merge remains mandatory. Require the actual `successor-foundation` check,
   bound to the observed GitHub Actions source where supported. Do not require the
   four legacy contexts unconditionally on successor: foundation enforces them
   when shared scope affects legacy. Keep main's existing rules and four validation
   responsibilities. Do not weaken enforcement or add a broad administrator bypass
   just to proceed.
3. Preserve independent exact-head review with the recorded reviewed target and
   accepted disposition. If an independent human approver is available, configure
   the appropriate review requirement; do not invent an approval identity or count
   agent review as a GitHub approval. If the repository cannot enforce the intended
   review/PR restrictions, document the exact missing capability and leave activation
   pending for a human decision. Do not silently substitute a written policy for
   claimed server enforcement.
4. Open a small genuine successor instruction PR from an isolated successor-based
   worktree. Observe `validation-routing` and actual `successor-foundation`
   execution on its exact H; confirm successor-only changes do not provision the
   legacy stack. Use an unmerged negative probe to demonstrate legacy-path refusal
   and shared-infrastructure routing to all four legacy jobs. Exercise the dispatch
   entrypoint with `--ref successor`, observing `integration-current-successor`
   attached to H with `base=<B>` after real combined validation. Record workflow
   run URLs, job names/conclusions, PR H, target B and effective rules. Demonstrate
   a failed required check blocks ordinary merge and direct updates are prohibited;
   inspect capabilities without attempting a destructive write. No probe is merged
   without independent review and a human. Verify main dispatch/checks still work.
5. Recheck the effective required-check names/source, matching rules/bypass behavior
   and current successor SHA. Record activated/pending explicitly with evidence and
   any unmet administrator actions. #209 may start only when this checkpoint is
   complete. Stage its new required application checks with real jobs; register and
   enforce them before its first merge, once jobs actually report. Record their
   head/integration matrix and workflow availability at that time.

Observed pre-bootstrap configuration (2026-09-26): main was
`d3e014dd7dd40910fa4a669525227e8ae8ba7176`; default branch main; squash-only merges.
Active repository ruleset `protect_main` (`23062092`) matched `~DEFAULT_BRANCH`
and contained deletion/non-fast-forward rules with an always-admin bypass.
Effective main rules contained no required-check or PR-review rule; classic main
protection returned 404. Thus the four checks and independent review were project
requirements, **not verified server-enforced checks**, despite `protected: true`.
Successor enforcement requires administrator configuration. Main hardening, if
wanted, needs explicit human authorization; this bootstrap changes no live setting.
Reinspect at activation rather than assuming this observation is still current.

GitHub behavior was checked against primary documentation for
[workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
and [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
PR branch filters apply to the target; dispatch availability starts on default;
GitHub can accept skipped/neutral required checks. Consequently the always-running
foundation aggregation and read-only readiness demand actual successful required
execution. These documented rules do not replace observed activation evidence.

Final legacy cutover remains separately governed by the
[exact-tree cutover contract](REPOSITORIES.md#exact-tree-successor-cutover), including
fresh behavioral owners, operator acceptance, both packaged platforms, historical
access and validation of the exact tree that removes legacy.
