# Development workflow

This document defines the engineering lifecycle for `packetlss/compliance`. It applies to human-written changes and work performed by ChatGPT, Codex, or a hybrid workflow.

The issue, PR, CI, review, and definition-of-done requirements are independent of implementation agent.

## Repository authority and handoff

Durable repository artifacts are normative project state. Git is the handoff boundary between design, implementation, review, and future sessions.

Chat history, Codex session history, AI memory, and scratch state are not normative. A fresh human or agent must be able to reconstruct required work from this repository, a bounded issue, and linked durable design material.

Use each artifact for one role:

- architecture docs — current semantics, invariants, boundaries, ownership, public/cross-component contracts;
- ADRs — significant decisions, alternatives, rationale and consequences;
- issues — bounded implementation contracts;
- tests — executable behavior/invariant evidence;
- PRs — proposed delta, validation, findings and review history;
- Git/releases — reviewed implementation and historical provenance.

A design decision constraining implementation must be recorded durably before implementation relies on it.

## Design → implementation → feedback loop

```text
research / design / clarify
  -> durable design decision when needed
  -> bounded GitHub issue
  -> implementation
  -> local validation / findings
       | implementation-local
       |   -> resolve within issue
       |
       + architectural finding
           -> return to design
           -> update durable contract/issue
  -> short-lived branch + PR
  -> CI on reviewed revision
  -> independent review / re-review
  -> squash merge
```

Implementation-local findings may be resolved when they do not alter semantic meaning, architecture/trust boundaries, public/cross-component contracts, release identity, a new common abstraction, or issue scope.

Return to design when a proposed resolution would:

- change semantic meaning;
- add/remove/weaken an architecture invariant;
- move an architecture or trust boundary;
- change a public or cross-component contract;
- introduce a new common abstraction;
- materially broaden scope; or
- contradict normative documentation.

Implementation convenience must not silently become architecture.

## Change classification

Use the narrowest scope that correctly satisfies the issue.

| Class | Typical owner / integration behavior |
| --- | --- |
| Architecture/workflow | Destination docs/ADR issue; implementation waits for durable decision when semantics change |
| Single logical component | Component root only; focused component validation plus applicable stable destination contexts |
| Cross-component contract | One coordinating destination issue may authorize an atomic PR across co-located roots; canonical integration required |
| Canonical integration | `verification/scenarios/`; complete public behavior/feature coverage |
| Installed-release/provenance | `tooling/` plus release validation lane |
| Pre-freeze compatibility removal | Owning component after current replacement and consumer cutover are explicit |
| Repository retirement | Destination #29 and its bounded retirement issues; no semantic changes |

Co-location permits atomic cross-component changes only when the issue contract explicitly authorizes that scope.

## Implementation modes

### ChatGPT

Prefer ChatGPT for architecture, requirements, semantics, research, design alternatives, roadmaps, ADRs, issue construction, GitHub coordination, review, and bounded repository-visible edits where local execution adds little signal.

### Codex

Prefer Codex for work materially benefiting from a runnable checkout: substantial implementation, source exploration, refactoring, dependency/tool use, build/test/debug loops, OPA/compiler behavior, migration execution, performance work, and concrete review remediation.

A normal handoff is concise: implement issue #N; read `AGENTS.md`, the issue, and linked durable design; inspect current repository state; implement only the bounded contract; run required validation; resolve implementation-local questions; return architectural findings rather than silently changing semantics/boundaries/contracts/scope; record findings and validation in the PR.

### Hybrid

Use hybrid flow when design/semantics and repository-local implementation are both material.

Choose the least operationally expensive execution mode that preserves correctness.

## Implementation issues

A meaningful implementation issue should state enough durable context for a fresh implementation session:

- objective and write scope;
- design basis;
- required behavior and acceptance criteria;
- non-goals;
- architecture/provenance/compatibility/trust constraints;
- expected invalid/failure behavior;
- escalation conditions;
- required validation; and
- dependencies/sequencing.

Link authoritative ADRs rather than duplicating them.

## Repository-local validation

Substantial implementation uses a runnable checkout/worktree and the repository's accepted toolchain. CI is an independent clean-environment gate, not a substitute for material local implementation testing.

Normal validation must not recreate the retired multi-repository workspace dependency graph. Component gates use co-located explicit roots, repository-owned fixtures, installed artifacts, or canonical integration as appropriate.

Runtime/provenance tests should materialize committed inputs into temporary non-Git roots where that proves independence from checkout/Git topology.

## Validation architecture

Three stable contexts own the validation layers.

### `component-validation`

Runs repository validation plus focused tooling, policy-source, ordinary-project and IAM private-boundary gates. It does not run the complete feature suite.

### `verification-scenarios`

Runs the canonical deterministic composed scenario/feature suite from a temporary non-Git assembly of explicit destination roots. It owns all 20 retained public CLI leaves and 18 retained domain features.

### `installed-release-provenance`

Runs release-critical installed/no-Git, locked-artifact, release preparation/tag and generic policy-source release/provenance validation.

Historical pre-freeze readability is not a default required gate unless an explicit freeze or bounded historical-reproduction contract requires it.

## Branches and PRs

Use short-lived branches from current `main`, conventionally:

```text
issue-<number>/<short-description>
```

Do not implement directly on `main`.

Every PR links its issue and records:

- what changed and why;
- behavioral impact;
- validation actually performed;
- architecture/provenance/compatibility impact;
- material implementation findings or `None`; and
- integration/migration impact where applicable.

Squash merge is the normal merge method.

## Merge authority

Normal implementation PRs require human final merge after review and green CI.

Retirement controller #29 is a narrow temporary exception: bounded documentation, routing, provenance, and mechanical retirement PRs may be squash-merged automatically when the issue explicitly allows it, the exact reviewed head has all applicable stable CI contexts green, the diff matches the nonsemantic contract, and no active work/provenance is lost. Any architecture/release/trust/public-contract decision leaves this exception and returns to normal human design authority.

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

## Review and definition of done

Review the current PR head, not a stale earlier revision. A PR is complete only when its issue contract is satisfied, required local/CI validation is recorded/green, implementation findings are captured, generated/temporary state is clean, and no unresolved architectural finding remains.

Historical preservation is distinct from current compatibility. Do not keep active complexity solely because an unfrozen historical artifact exists.

## Private/trust boundaries

Real private environment inputs remain outside this repository. The synthetic IAM fixture tests private-source isolation only by separately materializing `environment-private`; it does not convert a public/co-located fixture into an access-control boundary.

Generated evidence/results, credentials, backend state, adapter output and private operational data remain non-authoritative/untracked.

## Firewall boundary

Firewall/network-policy work is out of scope unless explicitly reopened by the product owner. Destination #38 is a dormant conceptual-alignment issue and does not authorize technical coupling.
