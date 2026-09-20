# ADR 0021: Project-governed framework obligation declarations and bounded satisfaction

- **Status:** Accepted architecture under [#159](https://github.com/packetlss/compliance/issues/159); implemented by [#161](https://github.com/packetlss/compliance/issues/161), experimental, not frozen
- **Date:** 2026-09-13
- **Refines:** [ADR 0006](0006-regulatory-assurance-and-external-adapter-boundary.md), [ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md), [ADR 0016](0016-closed-world-policy-assessment.md), and [ADR 0018](0018-durable-assessment-explanation-facts.md)
- **Superseded in part by:** [ADR 0022](0022-criterion-ownership-and-external-judgment-retirement.md), for the basis-category model and external-judgment architecture
- **Exploration:** [#158](https://github.com/packetlss/compliance/issues/158)

## Context

The first Alder Forge DEFSTAN/DCC tranche represented several organizational
obligations as synthetic `ControlRequirement` / `ControlRealization` paths backed by
`organization.assertion/v1` evidence. This was a useful pre-freeze proving consumer,
but it exposed a circular pattern when the obligation is exactly governance's own
reviewed adoption or implementation declaration:

```text
governance declaration
  -> assertion of the same declaration
  -> evidence assessment
  -> Objective pass
```

That round trip adds no independent assurance when the asserted fact cannot change
without governance changing its declaration. Conversely, actual review occurrence,
training completion, deployed technical state, and other independently observable
facts can drift while governance intent remains unchanged and therefore still require
ordinary evidence-backed assessment.

Mappings and `external_refs` provide attributable traceability, but cannot establish
which external obligations governance meant to account for or whether the mapped set
is complete. Inventory, groups, assignments, current `Coverage`, Requirements,
Realizations, technical Baselines, waivers, and assessment results each have different
existing responsibilities. None owns a closed, reviewed framework-obligation ledger.

ADR 0016 correctly rejects generic framework satisfaction inferred from mappings or
the results that happen to exist. This decision preserves that rejection and permits
one narrower statement only when governance separately supplies a closed declaration
and the projection validates every declared basis against its exact inputs.

## Decision

### One project-governance responsibility

Introduce the durable responsibility named `FrameworkObligationDeclaration`:

> A closed, versioned, project-governed declaration of which framework/profile
> obligations are accounted for under a declared project scope and exactly what
> reviewed satisfaction basis governance assigns to each obligation.

The declaration is project-owned governance state, alongside but distinct from
inventory, assignments, waivers, private policy, and generated assessment artifacts.
It is not an ordinary named policy source and must not be placed in one for
convenience. A later implementation may define a dedicated project path and resource
family; this ADR establishes semantic ownership without freezing that path, a JSON
shape, schema URI, identity algorithm, or CLI.

The declaration is not:

- an `AssessmentResult`, certification or conformity claim;
- a policy resolver, assessment engine, evidence source, or result dependency;
- a current-status or mutable latest-result store;
- a complete or authoritative copy of an external framework; or
- durable `Coverage`.

Current `Coverage` remains the current, ephemeral, inventory/policy-resolution-derived,
evidence-independent, non-persisted, non-identity-bearing and non-assessment-owning
operator view. User-facing prose may call the declaration's scope **declared
coverage**, but that phrase does not rename or extend the existing `Coverage` surface.

### Minimum semantic content

A valid declaration owns, semantically:

1. the exact framework, profile and version reference that governance declares;
2. a versioned declaration identity and one attributable project owner/review context;
3. one declared project coverage/scope identity and description;
4. a closed obligation ledger whose entries are identified without source or file
   order semantics;
5. an explicit `applicable`, `excluded`, or `not-applicable` disposition for every
   ledger entry, with an attributable rationale or reference for exclusions and N/A;
6. the reviewed company interpretation or exact interpretation reference/pin where
   applicable;
7. exactly one satisfaction-basis category for every obligation;
8. for every applicable governance portion, the implementation/process subject or
   reference, responsible owner, review/approval information, and a governance-
   determination responsibility that distinguishes valid reviewed affirmative or
   negative conclusions from insufficient establishment;
9. for assessed or direct portions, exact typed company-policy references/pins that
   can be matched to frozen plan provenance; and
10. a scope binding expressed with the project's existing identity and
    `InventoryGroup` concepts where possible, never another label-selector language,
    inventory hierarchy, or discovered population.

Wire representation may later combine or normalize these facts, but must not weaken
them. A filename, directory, repository coordinate, mapping count, `external_refs`
set, or the set of plans/results that happen to be present cannot imply ledger
membership or completeness. Duplicate, divergent, missing, unresolved, or
inconsistent required declaration facts cannot be silently omitted or produce
`satisfied`; an attributable incomplete/invalid projection is `not_established`.

The closed ledger means only:

> This is the complete obligation set governance declared for this exact declared
> coverage.

The product does not independently retrieve or verify the authoritative external
framework universe, decide legal or contractual applicability, or prove that the
declared ledger exhausts that universe. Explicit excluded and not-applicable entries
are governance accounting and do not imply external-authority acceptance.

### Historical five-category model and superseding target

The original accepted model below had five basis categories. ADR 0022 preserves this
section as historical rationale for the #161 implementation. The #169 runtime
cutover retains only
`governance-declared`, `evidence-assessed-objective`, `direct-technical-policy`, and
`mixed-governance-assessed`. It removes `external-judgment` and `externalReference`
without reinterpreting historical declarations.

Each ledger entry has exactly one of these categories, independently of its
applicable/excluded/not-applicable disposition:

1. **Governance-declared** — the represented obligation is decided, for this bounded
   internal accounting model, by governance's reviewed determination about its own
   implementation or adoption. The determination may be affirmative, conclusively
   negative, or insufficient to establish either. This is governance accounting, not
   evidence of an independently observable implementation fact.
2. **Evidence-assessed Objective** — exact ordinary `ControlRequirement` meaning,
   its complete selected `ControlRealization`, and its evidence-backed assessment
   establish the company basis.
3. **Direct technical policy basis** — exact `Baseline` / `BaselineOverlay` policy
   and its ordinary technical assessment are the complete declared company basis.
4. **Mixed governance + assessed basis** — both an attributable reviewed governance
   determination, with its applicable implementation or gap reference, and exact
   ordinary evidence-backed Objective or direct-policy assessment are required.
5. **External judgment** — historical #161 category for satisfaction depending on an
   authority, recognition, or judgment the product does not establish; superseded by
   ADR 0022 and removed from current runtime by #169.

Use this decision rule:

> Could satisfaction change independently of governance's declared implementation
> without governance changing the declaration?

If no, the reviewed governance determination is normally sufficient for the bounded
internal framework-accounting model. It can establish affirmative adoption,
conclusive non-adoption, or that governance has not established either. A synthetic
Objective and assertion evidence should not be created merely to re-prove the
determination. Examples include a reviewed board security direction or adoption of
an internal governance process when the obligation being represented is exactly that
governed adoption.

If yes, the independently observable *descriptive* fact may remain assessment evidence
only if Compliance owns the complete criterion under ADR 0022. A requirement
that a process be adopted can be governance-declared while an actual periodic review,
training completion for a required population, successful restore exercise, or
deployed technical posture remains assessed. When both portions are required, use the
mixed category rather than treating governance as evidence.

### Governance determination semantics

Every applicable governance portion, whether governance-declared or mixed, is
interpreted through an attributable governance determination. Only a valid reviewed
determination can establish an affirmative or conclusive negative conclusion. The
semantic model must distinguish at least:

1. **Affirmatively satisfied** — governance reviewed and determined that the required
   process, policy, direction, or other governance implementation is adopted or
   implemented.
2. **Conclusively unsatisfied** — governance reviewed and determined that the required
   implementation is not adopted or not implemented. This is a known governance gap,
   not missing declaration state.
3. **Not established** — the determination is absent, invalid, ambiguous, unreviewed,
   or otherwise insufficient to establish either an affirmative or negative
   conclusion.

These are semantic distinctions, not accepted JSON names, enum values, schema
layout, or wire representation. A governance-negative determination remains entirely
declaration-side. It is not an assessment `fail`, does not create an
`AssessmentResult`, Control, Objective, evidence document, or result dependency, and
does not change assessment `pass` / `fail` / `unknown` / `error` / `waived`
semantics.

Excluded and not-applicable entries retain their explicit category, interpretation,
rationale and review provenance for closed-ledger history, but they do not enter the
applicable satisfaction condition. Their declared disposition is not an external N/A
or recognition decision.

### Existing policy responsibilities remain separate

The declaration may reference exact policy objects as satisfaction bases; it does not
replace or move their meaning:

| Object | Retained responsibility |
| --- | --- |
| `ControlRequirement` | Technology-neutral assessed Objective meaning |
| `ControlRealization` | Complete evidence-backed implementation recipe for one assessed Objective/environment |
| `RequirementBaseline` | Grouping of assessed Objectives |
| `Baseline` / `BaselineOverlay` | Direct technical desired state |
| reusable `Control` and evidence contracts | Independently observed assessment capability |

Exactly-one applicable realization selection, complete `satisfaction.allOf`, evidence
qualification, conservative Objective/baseline roll-up, and fail-only waiver behavior
remain unchanged for every assessed Objective. Technical policy remains independently
useful without an Objective wrapper.

A technical Baseline forms a complete obligation basis only because the declaration
explicitly pins that policy root and says it is the complete company basis for that
obligation. `external_refs` and mappings remain traceability only. No synthetic
Objective is required solely for framework symmetry.

A mixed basis is deliberately a conjunction of different authorities:

```text
reviewed governance determination + implementation/gap reference
        +
ordinary exact evidence-backed assessment
        -> bounded obligation satisfaction
```

The governance portion is governance state, not evidence. The assessed portion is an
ordinary validated plan/result interpretation. Results do not consume other results,
and this decision introduces no result dependency graph, cross-time result
equivalence, richer realization algebra, or alternative assessment roll-up. Either
portion can conclusively prevent mixed-obligation satisfaction; uncertainty in one
portion cannot erase a conclusive failure in the other.

### Scope binding and frozen subject denominator

The declaration belongs to exactly one project scope. Its declared coverage reuses
stable project and `InventoryGroup` identities to name the governed scope and to bind
assessed/direct portions to their required subject scope. It must not embed a second
selector language, infer scope from policy mappings, or treat entity identity as an
asset population.

For every historical projection, an exact operation anchor is required as the frozen
scope witness. Its selection witness, resolved group memberships, member commitments
and dispositions provide the historical subject denominator. The projection must
verify that the supplied operation contains the declaration-required group scope and
that every `result_required` member needed by an assessed/direct basis has the exact
valid bound plan/result support required by the pinned basis. A different operation,
current inventory, current `Coverage`, an approximate group match, or a subset of
convenient results cannot fill a missing slot. A scope mismatch is
`not_established`.

An all-governance declaration still uses the exact operation anchor to bind the
declared project scope at the historical instant, but it does not manufacture an
assessment result, synthetic Objective, or evidence dependency. Exact plan/result
pairs are required only for assessed/direct portions. The operation can prove
completeness only against the supplied governed inventory and selection semantics. It
never proves that all real-world subjects or the correct real-world population were
supplied.

### Ephemeral framework-satisfaction projection

Framework satisfaction is an interpretation, not a new durable result:

```text
exact FrameworkObligationDeclaration
+ exact retained operation anchor as scope witness
+ exact bound plans/results required by assessed/direct portions
+ explicit query/as-of instant where qualification is required
-> ephemeral framework-satisfaction projection
```

Every input is supplied explicitly and validated independently. The projection must
match exact declaration policy pins and scope bindings to exact retained plan
provenance, use the operation's closed denominator, validate each exact plan/result
pair, and preserve every obligation's basis and explanation. It does not reassess
evidence, re-resolve current policy or inventory, select a new realization, or mutate
historical outcomes.

The declaration is not embedded or frozen in ordinary assessment plans. A framework
accounting edit by itself therefore changes the declaration's own version/content
identity but must not regenerate unrelated:

- `control-library` identity;
- project-private technical or Objective policy-source identity;
- planning composition;
- `member_plan_digest`;
- `operation_id`;
- bound `plan_id`; or
- assessment-result identity.

Normal plans retain resolved technical/Objective policy, mappings and operation
facts; they do not acquire framework-ledger content or identity. Historical
interpretation requires retention and explicit supply of the exact declaration
snapshot separately from the exact retained plans/results. Deleting either required
input can make later interpretation unavailable without rewriting an immutable
assessment outcome.

If implementation cannot make the projection independently reproducible and
verifiable without embedding declaration content in ordinary plans or changing
plan/result semantics, it must return to architecture rather than broadening this
decision locally.

### Status and qualification semantics

The projection has exactly three top-level framework-satisfaction states. A required
basis means every governance and assessed/direct portion required by the applicable
obligation's declared category. Roll-up is fail-first:

```text
any conclusive required basis failure
    -> not_satisfied

no conclusive failure,
but one or more required bases are not established
    -> not_established

every required basis affirmatively satisfied
    -> satisfied
```

| State | Meaning |
| --- | --- |
| `satisfied` | Every applicable declared obligation has every required governance and assessed/direct portion affirmatively satisfied, with no required waiver/deviation. The historical external-judgment qualification is superseded by ADR 0022's target model. |
| `not_satisfied` | At least one applicable required basis has a conclusive governance-negative determination or assessed failure. |
| `not_established` | No conclusive required failure exists, but at least one required governance determination or assessed/direct basis is not established; this also covers incomplete/invalid accounting or a required waived failure. Historical external-judgment handling remains readable only until its separately promoted removal. |

Consequently:

- an affirmative reviewed governance determination may contribute satisfaction;
- explicit reviewed governance non-implementation/non-adoption produces
  `not_satisfied`, even if another required basis passes or is not established;
- an absent, invalid, ambiguous, unreviewed, or otherwise insufficient governance
  determination produces `not_established` when no conclusive failure exists;
- conclusive required evidence-assessed or direct technical `fail` produces
  `not_satisfied`, even if another required governance or assessed basis is missing
  or inconclusive;
- assessed/direct `unknown`, `error`, missing, stale, invalid, incomplete, or
  scope/plan/policy-misaligned support produces `not_established` when no conclusive
  failure exists;
- assessed/direct `pass` may contribute satisfaction when every other required basis
  is established;
- a waived required failure produces `not_established` and exposes the internally
  accepted deviation;
- governance cannot override an assessed failure or uncertainty;
- empty applicable scope, incomplete ledger accounting, or a non-assessable/missing
  denominator where an assessed/direct basis requires support cannot manufacture
  `satisfied`.

For a mixed obligation, governance affirmative plus assessed pass may contribute
satisfaction. Governance negative plus assessed pass is `not_satisfied`; governance
affirmative plus assessed fail is `not_satisfied`; and governance negative plus
assessed unknown, missing, stale, invalid, or errored support remains
`not_satisfied` because the conclusive governance failure wins. Governance unresolved
plus assessed pass is `not_established`, as is governance affirmative plus assessed
support that is unknown, missing, stale, invalid, or errored. The same fail-first rule
means an assessed failure remains `not_satisfied` when governance is unresolved.

Internal waivers/deviations and separately attributable external-recognition records
are qualifications, not additional top-level states and not successful states. A
recognition record may explain an external authority's position but does not let the
core authenticate or independently establish that proposition. Governance preserves
such attribution through its determination `subject` and review reference/context.
Current qualification, including timeliness, declaration drift, comparison-plan
mismatch, waiver expiry, or external recognition, is shown separately from historical
satisfaction.

Do not use `compliant` as normative core terminology. The preferred short operator
wording for `satisfied` is:

> **Satisfied under declared coverage.**

The strongest supported expanded statement is:

> For exact declaration D and exact assessment operation O at time T, every
> obligation governance declared applicable in D has the required declared and
> assessed satisfaction basis under D.

It does not establish legal or contractual applicability, authoritative framework
completeness, external conformity, certification, DCC status, MOD/IASME acceptance,
correct Cyber Risk Profile selection, real-world population completeness, continuous
effectiveness, or external recognition of an internal exception. Content/source
identity provides attribution and integrity, never authority or truth by itself.

### History and revision

Declaration revisions are new immutable governance states. The historical basis is
the exact old declaration plus exact old operation-bearing plans/results. Later
changes to governance, the declaration, inventory, assignments, policy, evidence,
waivers, or external recognition do not rewrite those assessment outcomes or the
declaration under which they were interpreted.

Changing an obligation from governance-declared to evidence-assessed, direct,
mixed, or the historical external judgment category (or in the other direction) requires a new declaration
revision. It never retroactively reinterprets an older declaration. A caller may
explicitly project a different declaration against compatible retained assessment
facts as a new interpretation, but must identify that exact declaration and expose
any pin/scope/time misalignment; it is not the historical assertion under the old
declaration.

There is no mutable “latest compliance result.” Current qualification is derived at
an explicit query/as-of instant and stays separate from both the immutable assessment
outcomes and the declaration revision.

## Alder Forge migration direction (implemented by #169)

The #169 cutover migrated the pre-freeze Alder Forge proving consumers as follows:

- `1101` becomes governance-declared instead of an assertion-backed synthetic
  Objective.
- `0002` becomes governance-declared and `not_established`; Governance may name the
  CE Plus dependency as its determination subject.
- `1202` becomes governance-declared and `not_established` in the proving case;
  Compliance does not recompute the risk-management judgment.
- `2410` becomes governance-declared and affirmative from governed software-policy
  issuance/review/adoption state.
- `2602` becomes governance-declared; it is negative only after Governance explicitly
  reviews/adopts the external training basis, otherwise not established.
- The synthetic organizational programme `RequirementBaseline` is removed when the
  declaration owns the closed obligation ledger.
- `2201` remains an evidence-assessed Objective.
- `2409` remains direct technical policy whose complete obligation role is explicit
  in the declaration.

Superseded #157 project resources were deleted rather than preserved through
compatibility aliases.

## Capability implications

The governance distinction does not eliminate independently observable technical or
operational facts:

- account ownership remains a justified attributable observation, without a
  population-completeness inference;
- remote-access posture remains justified;
- vulnerability snapshots remain justified as bounded scan/treatment observations,
  while governance owns completeness of the claimed population;
- logging posture remains justified;
- component integrity remains detection/posture focused, with response process
  separate; and
- backup posture and restore-exercise occurrence/success are distinct observable
  facts and should not be collapsed.

These are future capability candidates only. This decision accepts no generic
process, GRC, activity-history, population, or universal process-evidence
abstraction.

## Consequences, implementation boundary, and non-goals

The architecture gains one durable governance input and one ephemeral interpretation
responsibility without redesigning assessment. The design is **implemented
experimentally** under [#161](https://github.com/packetlss/compliance/issues/161)
and amended/cut over to ADR 0022 under
[#169](https://github.com/packetlss/compliance/issues/169). Its current resource,
schema, path, runtime, CLI, projection and digest representations remain pre-freeze.
The implementation preserves the identity-isolation and exact-history boundaries
above; no compatibility aliases or dual representations were introduced.

This ADR and its bounded implementation do not authorize:

- a durable framework result artifact or framework state embedded in ordinary
  assessment results;
- new Controls, evidence contracts, or remaining DEFSTAN programme work;
- a generic framework, conformity, certification, GRC, workflow, process, or
  activity-history engine;
- universal process evidence, percentage scoring, or a richer realization algebra;
- legal applicability, Cyber Risk Profile determination, external authority
  verification, assessor sampling, or population discovery;
- result dependencies or new cross-time result equivalence;
- plan/result identity changes or declaration embedding in ordinary plans;
- persistent `Coverage` or current/latest compliance state;
- compatibility scaffolding; or
- a freeze of the declaration/projection representation, schema, wire, identifier
  or identity algorithm.
