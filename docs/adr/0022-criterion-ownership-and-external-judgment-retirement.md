# ADR 0022: Criterion ownership is the first assessment admission gate

- **Status:** Accepted architecture under [#167](https://github.com/packetlss/compliance/issues/167); runtime cutover implemented by [#169](https://github.com/packetlss/compliance/issues/169)
- **Date:** 2026-09-14
- **Supersedes in part:** the unqualified manual/procedural-assurance wording in [ADR 0006](0006-regulatory-assurance-and-external-adapter-boundary.md), the generic assertion/external-conclusion path described by [ADR 0016](0016-closed-world-policy-assessment.md), and the `external-judgment` basis category in [ADR 0021](0021-project-governed-framework-obligation-declarations.md)
- **Preserves:** ADR 0010 evidence selection, outcome, error and refusal semantics; the seven-field evidence envelope; operation/plan/result identity and immutable history
- **Exploration:** [#166](https://github.com/packetlss/compliance/issues/166)

## Context

ADR 0016 correctly narrowed the core from establishing external applicability,
recognition and conformity to evaluating supplied company policy against attributable
evidence. That boundary alone did not decide whether a conclusion-shaped observation
from another operational, assurance or external domain may be converted into a core
`AssessmentResult`.

The first Alder Forge proving consumers and the current generic
`organization.assertion/v1` contract exposed the gap. A fact can drift independently
of governance yet still be another domain's normative conclusion: for example, a risk
assessment's completeness, a training population's completion, an assessor's
judgment, or an external certification's validity. Recasting such a conclusion as a
Control only recreates the other domain inside Compliance; it does not produce an
independent Compliance assessment.

ADR 0021 also accepted `external-judgment` as a fifth framework-basis category.
The #161 implementation retained that category and its `externalReference` field
until the #169 cutover removed both from the current runtime/schema contract without
reinterpreting historical declarations or results.

## Decision

### Criterion ownership precedes evidence admission

Compliance may produce an `AssessmentResult` only when company Compliance policy
owns the complete normative criterion and deterministically evaluates it from
Control-unaware descriptive observations.

```text
Governance
  -> company requirements and policy
  -> issuance, review, adoption and approved service/design choices
  -> reviewed external and other non-core determinations

Compliance core
  -> exact governed inventory, scope and policy resolution
  -> company-policy-owned criteria over descriptive observations
  -> exact provenance, operation accounting and immutable AssessmentResults

Other operational or assurance domain
  -> discovery, reconciliation, workflow and domain-specific conclusions
  -> descriptive observations only where Compliance owns the criterion

External legal, certification or regulatory authority
  -> never inferred, authenticated or established by the generic core
```

Policy cannot obtain criterion ownership merely by restating “authority X says yes.”
That can establish only that a supplied record contains those words; it cannot
independently establish the underlying proposition's truth, sufficiency, validity or
recognition. If Governance or another operational, assurance, legal, certification or
regulatory domain owns the conclusion, Compliance must not recreate it merely to
emit `pass` or `fail`. Governance records its reviewed determination instead.

For governance-owned state, the strongest core claim is:

> In exact declaration D, attributable governance owner G recorded determination X,
> under review context R, about subject/reference S.

An affirmative determination means that Governance reviewed and accepted a basis for
its declared internal accounting. It does not mean that Compliance authenticated a
certificate, established assessor correctness, training truth, risk completeness,
legal sufficiency, external recognition, or framework/certification conformity.
`subject` and the reviewed reference/context preserve external attribution; neither is
evidence that the core independently established the external proposition.

### Manual and procedural material

Manual is a collection method, not a satisfaction-basis category. Manual or
procedural material is legitimate Compliance evidence only when all of the following
are true:

1. Company Compliance policy owns the complete normative criterion.
2. The producer reports a descriptive independently defined state, event,
   measurement, identifier, timestamp, relationship or count.
3. The producer can emit that observation without knowing the Control, Objective,
   framework obligation, desired value, threshold or desired outcome.
4. Compliance performs the normative comparison; it does not map an upstream
   approval, adequacy, completion, acceptance or compliance conclusion directly to
   `pass`/`fail`.
5. Subject, temporal meaning, selection unit, unknown representation and field
   semantics are explicit.
6. The interpretation needs no hidden discovery, population reconciliation,
   methodology, professional judgment, authority recognition or workflow.

A human may record a physical/configuration observation or measured event fact. A
human or external system's `adequate`, `complete`, `approved`, `certified`,
`population established`, or equivalent conclusion is governance or external-domain
judgment unless the exact underlying criterion is genuinely Compliance-owned and can
be recomputed from descriptive facts without reproducing that other domain.

### Reusable admission test for Controls and evidence types

Before applying the #111 producer-contract representation/reuse rules to a new
Control or evidence type, answer these questions in order:

1. State the exact claim a `pass` would make.
2. Identify the owner of its normative criterion.
3. If Governance or another domain owns it, stop and use governance determination
   state.
4. Identify the descriptive observation independently of the desired outcome.
5. Reject decisive conclusion-shaped fields such as `positive`, `approved`,
   `complete`, `adequate`, `certified`, or equivalent domain judgments.
6. Confirm that Compliance can compute the conclusion from declared policy and typed
   facts without reproducing discovery, reconciliation, methodology, workflow or
   authority validation.
7. Confirm producer unawareness of the Control, Objective/framework identity and
   desired outcome.
8. Only then apply #111's subject/relationship, authority, permissions, cadence,
   atomicity, selection-unit and reuse rules.
9. Confirm ordinary ADR 0010 selection works without merging, precedence,
   filtering or cross-subject reuse.
10. Confirm result wording cannot imply population completeness, external truth or
    recognition, conformity, certification or legal sufficiency.
11. Use `mixed-governance-assessed` only when its assessed portion independently
    passes this test.
12. Escalate before adding trust, selector, lifecycle, population or result-graph
    semantics.

This is an admission test, not a new evidence envelope, selector, evidence status,
identity algorithm or compatibility reader. Existing descriptive technical evidence
contracts remain valid unless separately found to fail this test.

### Framework-basis target

The target `FrameworkObligationDeclaration` model has exactly four basis categories:

1. `governance-declared`
2. `evidence-assessed-objective`
3. `direct-technical-policy`
4. `mixed-governance-assessed`

`mixed-governance-assessed` is valid only when its assessed portion passes the
criterion-ownership admission test independently. `external-judgment` is superseded
architecture, not an independently useful target category. The #169 runtime cutover
removed it and its `externalReference` framework-basis field without reinterpreting
historical declarations or results.

The three governance determination states remain declaration-side: affirmative,
negative and not established. They never create an `AssessmentResult` or change ADR
0010 `pass`/`fail`/`unknown`/`error`/refusal behavior.

### Alder Forge migration classification (implemented by #169)

The #169 bounded migration uses these classifications:

| Obligation | Target classification | Target state / boundary |
| --- | --- | --- |
| `0002` | `governance-declared` | `not_established`; Governance may name the CE Plus dependency as its determination subject. |
| `1202` | `governance-declared` | `not_established` in the proving case; Compliance does not recompute risk-management judgment. |
| `2410` | `governance-declared` | `affirmative`; governed software-policy revision is authoritative issuance/review/adoption state. |
| `2602` | `governance-declared` | `negative` only after Governance explicitly reviews/adopts the current external training basis; otherwise `not_established`. It is never mechanically derived from HR/LMS semantics. |
| `2201` | `evidence-assessed-objective` | Retained ordinary MFA Objective. |
| `2409` | `direct-technical-policy` | Retained ordinary direct technical policy. |

### Rejected and separately routed current contracts

PR #165 did not merge under its current contract. Its proposed
`organization.risk-assessment/v1` / `organization.risk-assessment.current` and
`organization.awareness-training/v1` / `organization.awareness-training.complete`
contracts are rejected: their decisive fields are other-domain conclusions. The
the #169 cutover keeps `organization.assertion/v1` and
`organization.assertion.required` deleted; it does not restore a generic
organization conclusion/assertion family. Issue #164's direction is superseded for
these organizational semantics.

The bounded follow-on [#172](https://github.com/packetlss/compliance/pull/172)
removed `iam.service.observation/v1` from the current contract. The retained
`iam.integration.observation/v1` path describes the exact-subject
consumer-to-service relationship, while Governed Policy supplies the required
service consumed by `iam.integration.required`. No service-level conclusion,
selector, trust mechanism or result dependency was introduced.

## Consequences and preserved boundaries

ADR 0006's manual/procedural assurance remains possible only under the bounded rule
above. ADR 0016 retains closed-world operation accounting, typed descriptive
evidence, provenance, immutable history and the external-adapter boundary, but its
generic external/assertion conclusion path is superseded. ADR 0021 retains the
closed governance declaration and ephemeral projection, but its five-category model
and external-judgment result wording are superseded by this target model.

The architecture documentation tranche initially changed no runtime source. The #169
runtime migration removes the retired current schema, Control and Alder resources
while preserving ADR 0010 selection/outcome/refusal semantics, the evidence envelope,
plan/operation/result identity, immutable historical meaning and compatibility
behavior. Historical declarations and results are not reinterpreted.

## Non-decisions

This ADR does not define external authority verification, certification, legal
applicability, PKI/signature verification, policy lifecycle or scheduling, a generic
GRC/process/activity-history abstraction, population discovery, a result graph, or
new selector/collection semantics. It does not authorize source/runtime/schema
changes. If the target cannot be made true without changing a preserved boundary,
return to architecture before implementation.
