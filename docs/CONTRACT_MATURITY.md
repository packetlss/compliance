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

These are **experimental**, implemented by #31/#32 and used by all destination consumers after #34–#36. #33 retired predecessor support.

The pre-freeze result/plan ownership refinement is **Experimental, implemented**
under [#90](https://github.com/packetlss/compliance/issues/90).
It removes duplicated plan/operation/planning facts from results, retains evaluation
composition and enforcement, introduces an explicit result-domain projection, and
requires intrinsic result plus exact plan/result relational validation. It freezes
neither the v4 wire form nor the provisional identity algorithm.

Predecessor `project-config/v1alpha1`, `project-config/v1alpha2`, `release-lock/v1alpha2`, assessment plan/results v1 and v3 are **Historical/removed** under #33. Current tooling rejects them; historical reproduction uses historical tooling.

## Historical outcome and operational timeliness

[ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md)
has its original factual representation implemented by #32 and derived historical
operation reporting implemented by #80. #90 retains stable-dependency successful
selection ID/digest and collection facts in the result while the exact assessed plan
owns dependency/`max_age` meaning. The exact plan/result pair, not a duplicated result,
supports full historical interpretation. The refinement does not change evidence
identity algorithms or add a core retention obligation.

The predecessor non-anchored current-inventory/latest-result Assessment view is
removed under #105. Coverage exclusively owns current inventory policy expectation.
Anchored historical Assessment views require an exact frozen operation and explicit
query instant, and expose historical outcome, exact plan alignment, selected-evidence
timeliness, recorded waiver qualification, and frozen accounting independently.
ADR 0010's assessment-time corrections remain its existing responsibility.

## Explicit policy parameters and freshness

[ADR 0012](adr/0012-explicit-policy-parameter-resolution.md) is **Experimental, implemented**, promoted under #37 with the single bounded migration contract [#73](https://github.com/packetlss/compliance/issues/73). It accepts explicit declarations, bindings, descendant tailoring, typed requirement-slot consumption, policy-owned effective freshness and immutable resolved-plan provenance. It does not freeze wire syntax, schema/artifact versions or identity algorithms.

Current requirement/realization schemas support explicit pinned slots and direct typed consumption. Policy bindings own effective `max_age`; Control manifests provide dependency contracts. The experimental frozen records are specified in [policy parameters](../tooling/docs/policy-parameters.md). Successor schema, fingerprint, validation, explanation and policy-diff obligations are in ADR 0012's migration table. Development artifacts may need regeneration; historical artifacts retain their original identity and meaning. ADR 0016 below supersedes ADRs 0013–0015 and narrows core responsibility; ADR 0012 semantics remain unchanged.

## Stage 5 explanation architecture

### Source-authored policy and check meaning

[ADR 0017](adr/0017-source-authored-policy-and-check-meaning.md) is
**Experimental, implemented** under [#100](https://github.com/packetlss/compliance/issues/100).
It places required policy
titles on assignable baseline roots and required intrinsic title/purpose on
canonical Control definitions. Existing Objective, tailoring, exclusion, and
remediation semantics remain separate. The fields are identity-bearing policy
meaning but cannot drive execution.

The implementation landed as one coordinated pre-freeze authoring-schema,
maintained source, resolved-plan, validation, policy-diff, and explanation cutover. No
compatibility reader or digest-algorithm change is planned. Existing runtime
representations now require authored meaning; historical pre-cutover artifacts
retain their original identity and require historical tooling.

### Durable assessment explanation facts

[ADR 0018](adr/0018-durable-assessment-explanation-facts.md) is
**Experimental, implemented** under [#102](https://github.com/packetlss/compliance/issues/102),
from the design accepted under [#98](https://github.com/packetlss/compliance/issues/98).
The bounded successor changes the experimental assessment-results v4 contract to
retain identity-bearing unsuccessful dependency dispositions and closed attributable
criterion error codes. It preserves successful selection, outcome, waiver,
operation-accounting, historical qualification and refusal semantics. Plan-owned
policy/check meaning is referenced by stable keys and is not copied into results.

The cutover is pre-freeze: current development v4 results become unsupported rather
than gaining compatibility inference or dual readers. No evidence, plan,
operation/member, composition, evaluator or waiver identity algorithm changes, and
no identifier is promoted to `/v1`. ADR 0017 and ADR 0018 were implemented as
separate bounded tranches. Neither cutover freezes the v4 wire contract or
provisional result identity algorithm.

### Assessment operator views

Stage 5 Tranche B is **Experimental, implemented** under
[#105](https://github.com/packetlss/compliance/issues/105). Assessment presentation
now consumes exact frozen-operation accounting, exact retained plan/result pairs,
and separately derived current qualification. Its bounded JSON objects are query
output, not artifact families or assessment inputs. The pre-freeze non-anchored
current-plan/latest-result presentation path and the `assessment groups` and
`assessment frameworks` leaves are removed without compatibility aliases;
`assessment status --by group` and `assessment mappings` are the current grammar.
No assessment/result status, artifact identity, Coverage responsibility, or trust
boundary changes.

## Closed-world operation accounting

[ADR 0016](adr/0016-closed-world-policy-assessment.md) is **Experimental,
implemented under [#78](https://github.com/packetlss/compliance/issues/78) and
simplified before freeze under [#87](https://github.com/packetlss/compliance/issues/87)**.
ADRs 0013–0015 remain superseded historical design. The sole new shared runtime
representation is the embedded frozen operation projection inside v4 plans. #90
removes the result copy and resolves the
exact operation-bearing plan by `plan_id`. [The operation contract](../tooling/docs/operation-accounting.md)
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
Issue #37 is closed architecture history. New semantics or escalation require a
new focused architecture promotion. Historical artifacts require their historical
tooling; no historical result is reinterpreted.

## Accepted vocabulary convergence

[ADR 0009](adr/0009-active-compliance-vocabulary.md), implementing #57's architecture decision, makes `control-library` the maintained reusable semantic source name. This intentional pre-freeze rename changes name-bearing composition/provenance identity without changing policy-tree bytes/content digest or the `compliance-control-library` distribution. Historical `shared-library` artifacts remain distinct; no alias is added.

`composition-lock` is the sole forward complete expected-composition abstraction. The `workspace-config` → `project-registry` rename is implemented in Tranche 2 with unchanged selection semantics and no retired-discriminator alias. Registry data remains nonsemantic to composition; tooling source bytes change existing tooling provenance. Neither vocabulary decision freezes a contract or changes technical control/assurance names without separate review.

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

Residual assurance questions, including methodology, sampling, N/A changes and
any direct result dependency graphs, require a new focused architecture promotion.
#78 implements only bounded frozen accounting and typed assertions. Any new common
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
