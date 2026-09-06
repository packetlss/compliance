# ADR 0013: Scoped assurance, population completeness, and obligation instances

- **Status:** Superseded by [ADR 0016](0016-closed-world-policy-assessment.md)
- **Superseded:** 2026-09-06
- **Date:** 2026-09-05
- **Parent and promotion contract:** [#37](https://github.com/packetlss/compliance/issues/37)
- **Coordinated decisions:** [ADR 0014](0014-attributable-applicability-and-authority-acceptance.md), [ADR 0015](0015-bounded-external-claims-and-assurance-recognition.md)

This decision is historical. [ADR 0016](0016-closed-world-policy-assessment.md) replaces its core
responsibilities, conformance obligations and migration routing. Only semantics
explicitly retained by that successor remain active; this text does not authorize
implementation of external completeness, applicability authority or recognition.

## Context

[ADR 0006](0006-regulatory-assurance-and-external-adapter-boundary.md) preserves
technical baselines and optional company objective assurance. Passing the checks
that happen to be assigned cannot establish that every claimed subject or
obligation was covered. A company-wide service may operate broadly while an
assessment or certificate supports only named beneficiaries. Organizational
identity alone says nothing exhaustive about owned assets.

This decision establishes scope and completeness semantics without adding a
second inventory hierarchy. It extends the accepted architecture, not current
runtime behavior. Existing `Subject`, `InventoryGroup` and `PolicyAssignment`
remain the inventory foundation. No generic `ClaimScope` registry is introduced.

## Decision

### Three distinct scopes

- **Operational scope:** where a control, service or practice operates.
- **Assessment/beneficiary coverage:** the subjects or relationships for which
  an exact assessment or consumed assurance contributes support.
- **Claim population:** the exact population proposition asserted by a bounded
  claim, with an established boundary.

Broad operational reach never automatically enlarges beneficiary coverage or
claim scope. A positive claim requires an established population boundary.
Legal/entity identity does not implicitly enumerate every owned asset, and
corporate relationships do not supply missing membership facts.

### Population completeness and one instant

Population completeness requires both:

1. exact enumeration/resolution of the claimed population; and
2. an attributable basis establishing that enumeration as exhaustive for the
   claimed domain.

An inventory snapshot or a list of successfully assessed subjects is not, by
itself, an exhaustive organizational population basis. Retain the exact basis,
its content/revision, provenance, domain proposition, applicable conditions and
its relationship to the resolved members. An enumerated claim may explicitly
speak only for a named set, such as hosts A and B; it need not establish a larger
organizational universe, but cannot imply that it has done so.

Every bounded claim has one explicit assessment instant `t`. Its population
basis must establish membership and boundary semantics at `t`. The source
snapshot need not have been physically captured exactly at `t`: accepted
semantics may establish the state at `t`, for example an attributable complete
membership record with an effective interval containing `t`. A capture timestamp
alone does not establish those semantics.

Directly contributing local assessments belong to that same point-in-time claim
evaluation at `t`. This is not a requirement that collection occur at `t`:
[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) and
[ADR 0012](0012-explicit-policy-parameter-resolution.md) retain evidence freshness
and resolved policy requirements. Reusing results from another evaluation instant
requires separately qualified imported-result semantics; it is not an incidental
optimization. [ADR 0015](0015-bounded-external-claims-and-assurance-recognition.md)
requires qualification for external assurance, not generic cross-time equivalence.
Historical membership changes never rewrite the historical claim or its basis.

### Group resolution and identity

Resolve the existing group DAG and assignments over stable subject identities.
Overlapping groups use set union: a subject appears once in the population while
all membership and assignment paths remain attributable. Deduplication must not
discard independently applicable policy or hide a conflict. It cannot establish
exhaustiveness that the population basis does not establish.

Cycles, unresolved references and ambiguous identity correlations fail closed;
never guess identity from names, ownership or source order. A failure confined
to an attributable claim relation leaves that claim unestablished. If it also
invalidates required technical policy resolution or shared plan integrity,
those independent boundaries still apply; see the failure matrix below.

### Exact obligation instances

The semantic formation is:

```text
external/company obligation
    + exact governed scope
    + resolved applicability
    -> exact obligation instance
```

Do not form an implicit Cartesian product of all requirements and all population
members. Quantification belongs to the obligation and its resolved applicability:

| Obligation meaning | Exact instances |
| --- | --- |
| A required setting on each applicable host | One instance per applicable host |
| Governance action for a named legal entity | One entity-scoped instance |
| A required assurance property of a named system | One system-scoped instance |

Preserve exact obligation/revision, governed scope and quantification,
applicability decision and population attribution for each instance. External
applicability does not assign or adopt company policy. Missing company
interpretation remains a visible gap, not permission to drop the obligation.
[ADR 0014](0014-attributable-applicability-and-authority-acceptance.md) owns
attributable applicability; [ADR 0015](0015-bounded-external-claims-and-assurance-recognition.md)
owns the external obligation denominator and mapping accounting.

The claim completeness denominator is the **exact resolved set of obligation
instances**. Neither assessment count nor a requirement-by-host count substitutes
for it. An obligation known to be relevant but not resolvable must remain visible
as unresolved accounting; a partial resolved set cannot masquerade as complete.

### Common assurance and scoped consumption

Common/shared assurance may support narrower beneficiaries only through explicit
scoped consumption. Preserve the exact supporting assessment/assertion, consumer
dependency, beneficiary scope and local correlation, conditions and provenance.
Where actual integration is necessary to make that relationship true, admissible
evidence of integration is required. A shared identity service's passing controls
do not demonstrate that an application actually uses it.

The consumer judges the support under its resolved dependency contract. A service
may support multiple named consumers without cloning its operational reach into
each consumer's claim. Its evaluation contributes at the same `t` when local;
imported assurance additionally needs ADR 0015 qualification. Authored integration
or realization designs describe intent, not proof.

### Preserve existing assessment boundaries

Standalone `Baseline` / `BaselineOverlay` assessment remains first-class.
Requirements remain company-owned desired assurance objectives; realizations
remain design-time demonstration designs. Exactly-one realization selection,
conservative result roll-up and fail-only waivers remain unchanged. A missing
realization is distinct from unresolved policy and evidence `unknown`.

| Failure class | Required boundary |
| --- | --- |
| Safely attributable inability to establish a population, applicability decision, obligation denominator, mapping/coverage relation or recognition effect | Bounded claim not established; independently valid technical/objective assessment remains publishable where its own plan is valid |
| Evidence insufficiency after a valid resolved dependency | ADR 0010 evidence semantics as applicable; missing/stale/invalid/inconclusive required evidence is `unknown` |
| Invalid/tampered shared plan, routing, composition/provenance, evidence snapshot, evaluator identity or result-envelope integrity preventing trustworthy publication | ADR 0010 assessment-wide refusal; no new trustworthy assessment envelope |
| Required policy unresolved under ADR 0012 | Preserve its non-assessable policy boundary; do not evaluate a partial plan or synthesize evidence `unknown` |

These are semantic distinctions, not new wire statuses. Pre-assessment
policy/claim-resolution failures must never silently become evidence `unknown`.
An attributable claim problem does not waive checks of shared integrity.

## Conceptual conformance vectors

All examples use exact pinned inputs and one explicit `t`; they are conceptual
acceptance vectors, not executable fixtures or a methodology for sampling.

| Case | Expected conclusion |
| --- | --- |
| Complete accepted population basis names A, B, C at `t`; only A and B were assessed | Population may be established; omitted C's applicable instances prevent claim completeness even if existing assessments pass |
| Snapshot lists A and B, but no basis establishes these as all company hosts | A whole-company population is not established; an explicitly enumerated A/B claim may be supported on its own terms |
| Basis establishes A/B membership throughout an interval containing `t`, captured before `t` | Capture time alone is no barrier; accepted interval semantics must actually establish state at `t` |
| Groups left={A,B}, right={B,C}, parent includes both through a DAG | Population={A,B,C}; retain both paths to B and every assignment; no duplicate population member |
| Group cycle, missing child reference, or two uncertain correlations for B | Affected population unresolved; no guessed enumeration; independent valid assessments survive unless their own prerequisites fail |
| A/B each need a host check and entity E needs one governance obligation | Exactly three instances, not four host-by-requirement instances; omitting E's instance prevents completeness |
| Organization E is named with no exhaustive asset basis | Entity-scoped governance claim possible if otherwise supported; no implied claim about every owned host |
| Shared service passes at `t`, application A explicitly consumes it, required integration evidence is admissible and sufficient | Support contributes to A's named dependency and normal roll-up; no automatic support for B |
| A has a valid integration evidence dependency but required evidence is absent | ADR 0010 evidence `unknown`; a missing authored consumption relation instead leaves coverage unestablished |
| Valid company policy has no matching realization | Existing `not_implemented` coverage and failing requirement behavior remain; not evidence `unknown` |
| Local assessment from yesterday is offered to a claim at today's `t` | Cannot contribute as a direct same-time assessment; no incidental cross-time reuse |
| B leaves after `t` | Historical population, instances, attribution and result remain unchanged |

## Migration and ownership

These changes are **accepted design, not yet implemented**. No wire spelling,
resource discriminator, artifact version or identity algorithm is frozen.

| Surface | Current foundation | Successor obligation |
| --- | --- | --- |
| Inventory/groups/assignments (tooling-owned) | Existing subject identities, group DAG and assignments | Preserve exact union membership and all paths; bind population proposition and exhaustive basis at `t`, without a second hierarchy |
| Optional company assurance (policy contracts and tooling) | Pinned requirements and subject-scoped realizations | Preserve obligation quantification, exact applicable instances, interpretation and explicit shared-consumption dependencies |
| Assessment plan/results/provenance | Content-addressed resolved per-subject intent and attributable outcomes | Preserve exact immutable population/basis, time, instances and consumption facts with relevant identity participation and integrity validation |
| Explanation/mapping/claim accounting | Existing coverage and mapped results | Show both omissions and resolved instances without inferring completeness from existing assessments |
| Maintained consumers and canonical verification | Current experimental schemas and fixtures | After repository-grounded planning, migrate all affected maintained consumers in the coordinated successor; no fixture changes in promotion |

[ADR 0015's coordinated migration route](0015-bounded-external-claims-and-assurance-recognition.md#coordinated-migration-and-remaining-architecture)
owns sequencing and shared escalation. Complete #73 independently first; plan
these three decisions together against its actual representation. Preserve
current experimental runtime until cutover, and preserve historical artifacts.

## Alternatives, consequences and validation

A second scope registry would duplicate inventory and invite inconsistent
membership. Inferring completeness from broad assignments or successful results
would erase omissions. A Cartesian denominator would misstate entity/system
obligations. Explicit scope and instances require more attribution, but make both
support and incompleteness explainable without overstating technical results.

Population-completeness bases, applicability determinations and recognition rules
remain separate semantic concepts even if they share envelope fields. Content
identity establishes consumed bytes, never external authority. Source, file,
order and location grant neither precedence nor authority.

Promotion validation requires `git diff --check`, repository/documentation-link
checks, coherent architecture/maturity/ADR routing, the conceptual vectors across
all three ADRs, fresh-context exact-head independent review and all four stable
exact-head CI contexts. Human retains final squash merge authority. Sampling,
probabilistic completeness, dynamic scope expressions, monitoring, continuous
compliance and ADR 0011 operational-view redesign are not authorized here.
