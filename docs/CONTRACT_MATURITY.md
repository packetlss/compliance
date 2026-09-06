# Contract maturity and compatibility

Status: **Current pre-freeze development policy**

Historical detailed audits remain in `packetlss-labs/compliance-workspace`; this file owns the active compatibility/freeze rules after documentation authority transfers.

## Compatibility is explicit

The project is development-only and currently has no external compatibility consumers.

A version-like identifier, checked-in schema, generated artifact, Git tag, or historical Release does **not** by itself create a permanent public compatibility promise. Compatibility begins only through an explicit reviewed freeze recorded in durable architecture/release documentation.

Maturity terms:

- **Experimental** — expected to change; no compatibility promise.
- **Likely stable** — direction is sound but not frozen.
- **Compatibility candidate** — suitable for an explicit freeze review, but not yet frozen.
- **Design pass required** — semantic/naming/authority ambiguity remains.
- **Accepted design, not yet implemented** — architecture accepted; current runtime has not fully cut over.
- **Historical/removed** — retained only in historical source/releases, not current product surface.

Historical readability and recommended current use are separate concerns.

## Identity-algorithm freeze lifecycle

For cryptographic identity algorithms:

1. pre-freeze identifiers are provisional development contracts;
2. unqualified `/v1` is reserved for the first explicitly frozen immutable version of an algorithm;
3. pre-freeze algorithms use development identifiers such as `/v1alpha1`;
4. pre-freeze digests/generated artifacts may be regenerated after reviewed semantic changes;
5. after `/v1` freeze, domain normalization, canonical byte representation, digest construction, inclusion/ordering rules, and normative vectors are immutable; and
6. an identity-affecting semantic change after freeze requires a new major algorithm identifier.

For semantic JSON digests, contract-specific domain normalization occurs before RFC 8785/JCS serialization. JCS defines canonical JSON bytes; it does not decide domain semantics such as array ordering or field inclusion.

Raw source-tree, executable, wheel/archive and other byte/path digest algorithms retain their own exact construction and do not use JCS merely because they are content-addressed.

## Current accepted core

The retained first core consists of:

- the `compliance` CLI/tooling;
- ordinary technical `Baseline` / `BaselineOverlay` assessment;
- optional requirement/realization objective assurance;
- arbitrary independently named/digested policy sources;
- inventory/groups/assignments;
- required typed evidence and pass/fail/unknown evaluation;
- waivers and policy diff;
- provenance-bearing assessment plans/results; and
- assessment plans as the external-adapter handoff.

Missing/inconclusive required evidence is `unknown`; authored implementation state is not evidence; source/file order is not precedence; divergent same-identity definitions fail.
Every declared evidence dependency is required and carries no optionality
discriminator. The typed envelope has no normative collector-supplied
`integrity.digest`; the unchanged complete-document and evidence-set digest
algorithms provide assessment snapshot identity.

In-core configuration intents/compiler/renderers/configuration artifact families/backend apply authority are removed and have no ADR 0007 successor.

## ADR 0007 current state

Accepted successor contracts:

```text
project-config/v1alpha3
composition-lock/v1alpha1
assessment-provenance/v1alpha1
assessment-plan/v4
assessment-results/v4
```

with provisional composition/lock/plan/result digest algorithms.

These are **experimental**, implemented by #31/#32 and used by all destination consumers after #34–#36. #33 retires predecessor support.

Predecessor `project-config/v1alpha1`, `project-config/v1alpha2`, `release-lock/v1alpha2`, assessment plan/results v1 and v3 are **Historical/removed** under #33. Current tooling rejects them; historical reproduction uses historical tooling.

## Historical outcome and operational timeliness

[ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md) has its factual representation implemented by #32 and derived historical operation reporting implemented by #80. V4 retains validated, result-identity-bound successful selection ID/digest, selected collection instant and assessed-plan requirement association. The view does not freeze a JSON layout or change evidence identity algorithms.

The non-anchored current-inventory view retains its predecessor result discovery but
separately exposes and aggregates immutable historical outcome, exact rendered-plan
alignment, coverage, and assessment absence. Anchored historical views additionally
require an explicit query instant and expose selected-evidence timeliness, recorded
waiver qualification, and frozen accounting independently. ADR 0010's assessment-time
corrections remain its existing responsibility.

## Explicit policy parameters and freshness

[ADR 0012](adr/0012-explicit-policy-parameter-resolution.md) is **Experimental, implemented**, promoted under #37 with the single bounded migration contract [#73](https://github.com/packetlss/compliance/issues/73). It accepts explicit declarations, bindings, descendant tailoring, typed requirement-slot consumption, policy-owned effective freshness and immutable resolved-plan provenance. It does not freeze wire syntax, schema/artifact versions or identity algorithms.

Current requirement/realization schemas support explicit pinned slots and direct typed consumption. Policy bindings own effective `max_age`; Control manifests provide dependency contracts. The experimental frozen records are specified in [policy parameters](../tooling/docs/policy-parameters.md). Successor schema, fingerprint, validation, explanation and policy-diff obligations are in ADR 0012's migration table. Development artifacts may need regeneration; historical artifacts retain their original identity and meaning. ADR 0016 below supersedes ADRs 0013–0015 and narrows core responsibility; ADR 0012 semantics remain unchanged.

## Closed-world operation accounting

[ADR 0016](adr/0016-closed-world-policy-assessment.md) is **Experimental,
implemented under [#78](https://github.com/packetlss/compliance/issues/78) and
simplified before freeze under [#87](https://github.com/packetlss/compliance/issues/87)**.
ADRs 0013–0015 remain superseded historical design. The sole new shared runtime
representation is the embedded frozen operation projection inside existing v4
plans/results. [The operation contract](../tooling/docs/operation-accounting.md)
defines its normalization and identity. The current projection uses one
`member_plan_digest`, one selector-sensitive `operation_id`, and operation-bound
plan IDs; it has no catalog-wide inventory/assignment revisions or predecessor
plan wrapper digests. This pre-freeze cutover adds no compatibility reader and
promotes no algorithm identifier to `/v1`.

Complete accounting remains separate from assessment success. Typed assertions
and observed consumer relationships use ordinary evidence dependencies. Governance
owns external applicability, sufficiency and inventory exhaustiveness; mappings
never establish external conformity. ADR 0010/0012, explicit N/A, missing-realization
failure, fail-only waivers and technical-only assessment remain unchanged.
#37 remains the parent architecture/escalation issue. Historical artifacts require
their historical tooling; no historical result is reinterpreted.

## Accepted vocabulary convergence

[ADR 0009](adr/0009-active-compliance-vocabulary.md), implementing #57's architecture decision, makes `control-library` the maintained reusable semantic source name. This intentional pre-freeze rename changes name-bearing composition/provenance identity without changing policy-tree bytes/content digest or the `compliance-control-library` distribution. Historical `shared-library` artifacts remain distinct; no alias is added.

`composition-lock` is the sole forward complete expected-composition abstraction. The `workspace-config` → `project-registry` rename is implemented in Tranche 2 with unchanged selection semantics and no retired-discriminator alias. Registry data remains nonsemantic to composition; tooling source bytes change existing tooling provenance. Neither vocabulary decision freezes a contract or changes technical control/assurance names pending #37.

## Current maturity guidance

### Compatibility candidates / likely stable direction

- named policy-source composition by stable name + actual content digest;
- no source-order precedence and identical-only coalescing;
- content-addressed tooling/policy/evaluator/evidence provenance;
- tooling-owned inventory/assignment schema ownership;
- `Subject`, `InventoryGroup`, `PolicyAssignment`, and `Waiver` current core semantics;
- reusable technical `Control`, `Baseline`, and `BaselineOverlay` direction;
- typed evidence envelope/source-owned payload schemas;
- evaluator `{name, version, executableSha256}` execution identity;
- provider-neutral policy-source descriptor/archive construction;
- the retained `compliance` command grammar at a conceptual level.

None of these are frozen merely by this classification.

### Design pass required

Destination #37 retains residual assurance questions, including methodology,
sampling, N/A changes and any direct result dependency graphs. #78 implements
only its bounded frozen accounting and typed assertion successor. Any new common
abstraction, semantics or trust boundary requires renewed architecture review.

### Experimental generated/public views

Machine-readable operator presentation objects, policy diff JSON shapes, and assessment views remain experimental unless separately frozen. Stable semantic exit behavior or invariants may be retained without freezing every JSON field.

### Historical/removed

- configuration intent/compiler/render artifacts and related CLI;
- removed historical assessment/config revisions no longer in current readers;
- historical producer-specific release mechanisms retired before consolidation.

Historical Git/releases remain immutable provenance.

## Release and repository boundaries

Repository co-location does not freeze contracts and does not merge release units.

- `compliance-tooling` distribution remains independently versioned/releasable.
- `control-library` remains independently digestible/releasable.
- `verification-policy` remains source-only with no current hosted release lane.
- real private environment sources remain outside the consolidated repository.

A future downstream release/productization program must choose explicit compatibility commitments from the post-consolidation contract state rather than inheriting stale workspace-era promises.

## Freezing a contract

A freeze review should define at minimum:

- exact normative semantics and authority boundaries;
- canonical representation/normalization where identity-bearing;
- fixed conformance vectors, including edge/failure cases;
- compatibility/evolution rules;
- public acquisition/distribution representation where relevant;
- downstream consumer evidence demonstrating operability; and
- explicit declaration of the compatibility commitment.

No current contract is promoted to a frozen `/v1` identity algorithm or blanket 1.0 compatibility surface by consolidation or retirement.
