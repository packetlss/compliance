# ADR 0015: Bounded external claims and explicit assurance recognition

- **Status:** Accepted design, not yet implemented
- **Date:** 2026-09-05
- **Parent and promotion contract:** [#37](https://github.com/packetlss/compliance/issues/37)
- **Coordinated decisions:** [ADR 0013](0013-scoped-assurance-and-obligation-instances.md), [ADR 0014](0014-attributable-applicability-and-authority-acceptance.md)

## Context

Company policy assessments and external claims answer different questions.
Passing selected mapped controls cannot establish whole-framework conformity,
and possessing a certificate cannot establish satisfaction outside its exact
scope or without accepted destination recognition. [ADR 0006](0006-regulatory-assurance-and-external-adapter-boundary.md)
keeps requirements company-owned and mappings bounded;
[ADR 0012](0012-explicit-policy-parameter-resolution.md) distinguishes resolved
company intent from external conformity. This decision makes completeness and
recognition explicit without changing technical assessment or introducing a
certification engine in this promotion.

## Decision

### Two completeness gates

A bounded external claim requires both:

1. the claimed population is established under ADR 0013; and
2. every applicable obligation instance within that population is exhaustively
   accounted for.

Passing only assessments that happen to exist establishes neither gate.
Accounting is necessary but not sufficient for a positive claim: a completely
accounted failing obligation still prevents conformity. The evidence, conformity
conditions and permitted qualifications must support the exact claim being made.

The exact external claim target must pin:

- framework/scheme and revision;
- profile/claim target;
- authoritative external obligation denominator, or the exact accepted basis
  establishing that denominator;
- population proposition;
- evaluation instant `t`; and
- permitted qualifications/exclusions.

The target's authoritative external obligation set precedes applicability and
instance formation. A locally authored list of mappings cannot silently become
that denominator. ADR 0013's exact resolved applicable instance set is the claim
completeness denominator after scope and ADR 0014 applicability resolution; an
unresolved relevant obligation cannot disappear from that accounting.

`outside claim` may arise only from the explicitly bounded target. It is not an
ad-hoc exclusion available to shrink a purported whole-framework denominator.
An explicit profile may bound the claim to fewer obligations but must identify
itself as that profile, not imply whole-framework conformity.

### Complete obligation accounting

For every relevant external obligation retain complete attribution through:

```text
exact external obligation and target
    -> applicability decision and governed scope
    -> company interpretation (or visible missing interpretation)
    -> exact company requirement revisions
    -> mapping and conformity conditions
    -> realization/dependency coverage and results
    -> qualifications and residual gaps
```

Several partial mappings do not manufacture complete coverage. The exact mapping
and conformity conditions must establish the claimed coverage; neither mapping
count, matching framework IDs nor passing company results can do so. An explicit
company interpretation is still company policy, not automatic adoption imposed
by an external applicability determination.

For example, company `timeout = 45m` may be internally well-formed and assessable
while an external condition `timeout <= 30m` is false. A passing company result
then cannot establish external conformity. An external condition explicitly
adopted into the company's structural parameter constraints still validates
company policy under ADR 0012; this decision does not bypass those constraints.

Missing company interpretation, missing realization, unresolved policy and
required-evidence `unknown` are distinct gaps/outcomes. Realizations are
design-time demonstration designs, not evidence. Exactly-one realization
selection and existing conservative roll-up and fail-only waivers remain.

### Four distinct relationships

| Relationship | Semantic effect |
| --- | --- |
| Framework alignment/mapping | Correspondence only; no satisfaction |
| Evidence reuse/support | Exact evidence may be consumed by a destination dependency, which independently judges suitability |
| Required external assurance | Possession of qualifying certification, attestation or result is itself a required dependency |
| Authoritative recognition | An accepted pinned destination rule grants a specified external assurance result a defined satisfaction effect |

Recognition satisfies a **named assurance dependency** and then participates in
normal objective roll-up. It never directly overwrites an objective or framework
result, nor excuses another failed/unknown required dependency. Required possession
of certification and recognition of a certification's assurance effect are not
interchangeable. Evidence support alone implies neither of them.

Retain the exact accepted destination recognition rule, its destination dependency,
purpose, scope, conditions, specified external result and defined effect, with
applicable authority acceptance under ADR 0014's narrow boundary. Recognition
rules remain semantically distinct from applicability determinations and
population-completeness bases; shared envelope fields do not justify one generic
`Determination` abstraction.

Do not introduce generic equivalence, automatic transitive recognition,
opportunistic fallback/`anyOf` realization selection, framework-ID matching as
satisfaction, or strictest/min/max recognition logic. A rule accepting A for one
destination does not automatically accept A for another or a result recognized
by A. The named dependency must actually be part of the selected design.

### Qualified external assurance

A qualified external assurance statement must preserve:

- exact assertion/result identity, including the exact assertion inside a
  multi-assertion source;
- issuer, scheme and revision;
- holder and covered scope;
- exclusions and qualifications;
- temporal validity relevant to claim instant `t`;
- exact local scope correlation;
- source provenance; and
- applicable authority acceptance.

Preserve exact attribution to the normalized assertion and, where relevant,
exact source-artifact byte/content identity. No generic attachment artifact
family is required. A digest proves which assertion/bytes were consumed, not
issuer authority, observation truth or acceptance by the destination.

Unknown scope never broadens. Legal/corporate relationships never imply inherited
certification. A parent's certificate covering a named service does not cover
all subsidiaries, applications or hosts. Shared assurance requires ADR 0013's
explicit scoped consumption and admissible integration evidence where integration
is necessary. A destination independently judges reused evidence's suitability.

Direct local assessments contribute at the same `t`. An imported external result
must meet its exact qualification and accepted consumption/recognition conditions;
this is not generic equivalence to a fresh local assessment. Cross-time result
equivalence remains an architecture escalation, not an incidental cache feature.
Historical claims retain the exact scope, statement, rule, validity facts and
acceptance used; later membership, rule or certificate changes do not rewrite them.

### Empty denominator and failure boundaries

A legitimate zero-applicable-obligation determination may establish only that no
obligations were determined applicable for the exact target. It must not
manufacture positive conformity/certification from an empty denominator, even if
a generic empty-child roll-up would otherwise pass. This constrains the external
claim and does not change technical roll-up.

Safely attributable inability to establish population, applicability, obligation
denominator, mapping/coverage or recognition effect leaves the bounded claim
unestablished. Independently valid technical/objective assessment is publishable
where its own plan is valid. Pre-assessment claim/policy resolution is not silently
mapped into evidence `unknown`.

Once a dependency is validly resolved, missing/stale/invalid/inconclusive required
evidence follows [ADR 0010](0010-required-evidence-status-and-assessment-refusal.md).
A trustworthy attributable execution failure retains `error`. Invalid/tampered
shared plan, routing, composition/provenance, evidence snapshot, evaluator identity
or result-envelope integrity that prevents trustworthy publication requires ADR
0010 refusal. [ADR 0012](0012-explicit-policy-parameter-resolution.md)'s unresolved
required-policy boundary remains unchanged. These distinctions do not define new
artifact statuses or permit publishing partial invalid plans.

## Conceptual conformance vectors

| Case | Expected conclusion |
| --- | --- |
| Exact accepted population at `t`, exact target obligation set, resolved instances, complete company interpretations/conformity mappings and sufficient passing required dependencies | Bounded claim may be established only within that target, population and permitted qualifications |
| All existing mapped assessments pass, but a relevant external obligation has no company interpretation | Visible interpretation/obligation gap; no complete external claim |
| All population members assessed but one applicable entity-level obligation omitted | Population gate may hold; obligation completeness gate fails |
| Exact profile includes O1–O3; O4 is outside its target | O4 may be outside that profile claim; cannot present the result as whole-framework conformity |
| Whole-framework target includes O4 but author marks it outside claim to avoid failure | Reject denominator shrinkage; bounded whole-framework claim not established |
| Two partial mappings cover selected technical aspects of O1, with procedural coverage unresolved | No manufactured complete O1 coverage or positive external claim |
| Company policy permits 45m, external condition requires at most 30m, technical assessment passes | Company result remains valid; external conformity fails |
| Certificate covers service S only; claim concerns all of parent E's assets or subsidiary D | Narrow scope cannot broaden through ownership or matching scheme IDs |
| Qualifying certificate C is required possession and that exact dependency is met | Possession dependency contributes normally; it does not establish recognition of other requirements |
| Exact accepted rule recognizes C for dependency D1, D1 is satisfied, D2 fails | Normal objective roll-up remains fail; recognition cannot overwrite D2 or the objective |
| No accepted rule recognizes C for D1, despite framework alignment | Recognition effect unestablished; valid independent technical results remain publishable |
| Rule recognizes A, A recognizes B, but destination does not explicitly recognize B | No transitive recognition of B |
| Exact evidence reused for two valid dependencies with different suitability conditions | Each consumer independently judges suitability; support for one does not imply support for the other |
| A valid required assurance/evidence dependency lacks qualifying evidence or has stale, schema-invalid, ambiguous or inconclusive evidence under ADR 0010 | Apply ADR 0010 evidence semantics as applicable; do not treat an unresolved recognition rule as this evidence case |
| Valid plan and scope, attributable evaluator execution failure | ADR 0010 `error`; current conservative roll-up and fail-only waivers preserved |
| Shared evidence snapshot or plan attribution is tampered/unverifiable | ADR 0010 refusal, even if some technical children passed |
| Required ADR 0012 parameter unbound or conflicting | No assessable policy plan; not a child evidence `unknown` |
| Parameters resolved, no matching realization | Existing separate `not_implemented` coverage/failing requirement behavior; no invented evidence `unknown` |
| Accepted complete applicability accounting determines zero applicable obligations | Report only that exact determination; no vacuous conformity/certification |

## Coordinated migration and remaining architecture

These three ADRs are **accepted design, not yet implemented**. They share
assessment-plan/result, dependency, evidence, mapping and claim surfaces. ADR
count must not determine implementation issue count.

1. Complete [#73](https://github.com/packetlss/compliance/issues/73) / ADR 0012
   independently. Keep it strictly parameter/freshness implementation, without
   scoped assurance, applicability authority, certification, recognition or
   external-claim semantics.
2. Under [#37](https://github.com/packetlss/compliance/issues/37), perform
   repository-grounded implementation planning for ADRs 0013–0015 against the
   actual post-#73 representation. Inventory affected owners, identity projections,
   plan/result validation, dependency/evidence surfaces, mapping/explanation,
   maintained consumers and migration/verification requirements before authorizing
   runtime work.
3. Default to one coordinated successor migration. Multiple implementation issues
   are acceptable only if that investigation demonstrates independently complete,
   executable cutovers avoiding transient schemas, duplicated migration work and
   compatibility scaffolding. Do not create one issue per ADR by assumption.
4. Route blocking residual architecture back to #37 before implementation relies
   on it. Manual/procedural methodology and evidence qualification, sampling
   inference, remaining assurance terminology/adopter annotations and unresolved
   result/representation questions remain explicit architecture responsibilities.
   Promoting these ADRs does not complete #37 or authorize implementation to decide
   unresolved assurance methods.

| Shared surface / owner | Current foundation | Coordinated successor obligation |
| --- | --- | --- |
| Inventory/population / tooling | Subject, group DAG, assignments and per-subject plans | Exact boundary basis, membership paths, time and scope correlation under ADR 0013 |
| Policy/applicability / reusable contracts and adopter sources | Company requirements, external references, explicit assignments | Exact source-owned assertions and narrow acceptance decisions; preserve company adoption independence |
| Dependencies/evidence / policy contracts and tooling | Exactly-one design, required technical evidence and ADR 0010 outcomes | Explicit common consumption, qualified external assurance and named recognition effects without changing technical selection or roll-up |
| Mapping/claim accounting / tooling and adopter policy | Mapped results and existing coverage | Pin target/external denominator, resolve obligation instances, retain interpretation/conformity and residual gaps; both completeness gates |
| Plan/results/identity/validation/explanation / tooling | Content-addressed v4 attribution, followed by ADR 0012 resolved parameters/freshness | Preserve exact immutable claim, assertion, acceptance, dependency, population and time facts with semantic identity participation and tamper validation |
| Policy sources/projects/fixtures/canonical scenarios | Maintained experimental schemas and consumers | Coordinated migration and positive/failure vectors after repository-grounded planning; preserve separate source/private boundaries |

The post-#73 inventory determines concrete representation; this table does not
pretend to specify it in advance. No wire spelling, artifact version, algorithm
or resource discriminator is frozen. Preserve current runtime until its reviewed
cutover. Development artifacts may require regeneration then; historical results,
releases and artifacts remain immutable and retired readers stay retired.
The assessment plan remains the sole external-adapter handoff; no authorization
or attachment artifact family, adapter runtime, release lane or trust-boundary
expansion is introduced.

Return to architecture rather than implement if the concrete successor requires:

- probabilistic population completeness or sampling-to-population inference;
- dynamic scope expressions, generic authority delegation or automatic supersession;
- cross-time result equivalence or generic attachment/artifact infrastructure;
- changed technical evidence selection or roll-up; or
- a representation unable to preserve exact immutable claim attribution.

Monitoring, query-time ageing, continuous-compliance semantics and
[ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md)
operational-view redesign are excluded. Real private inputs remain outside this
repository. Source/file/order/location grants no precedence or authority, and
content-addressed provenance proves consumed content rather than external authority.

## Alternatives, consequences and validation

Mapping-only certification would confuse correspondence with proof. Automatic
recognition or fallback would hide unsatisfied dependencies and widen scope.
Complete accounting and pinned recognition cost explicit authoring and richer
attribution, but preserve useful technical results without overstating external
claims. Empty-denominator handling prevents vacuous certification while leaving
existing technical roll-up intact.

Promotion changes documentation/contracts only: no runtime, schema, fixture,
generated-artifact or assessment behavior edits. Validate `git diff --check`,
applicable repository documentation/link checks, coherent ADR/architecture/maturity
and ownership routing, and the conceptual positive/failure vectors across all
three ADRs. Require fresh-context exact-head independent review with findings
resolved and all four stable exact-head contexts green: `component-validation`,
`verification-scenarios`, `installed-release-provenance`, `macos-portability`.
Human retains final squash merge authority.
