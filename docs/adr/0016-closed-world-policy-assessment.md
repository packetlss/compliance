# ADR 0016: Closed-world company policy assessment

- **Status:** Implemented under #78; experimental, not frozen
- **Date:** 2026-09-06
- **Promotion history:** [#37](https://github.com/packetlss/compliance/issues/37)
- **Supersedes:** [ADR 0013](0013-scoped-assurance-and-obligation-instances.md), [ADR 0014](0014-attributable-applicability-and-authority-acceptance.md), [ADR 0015](0015-bounded-external-claims-and-assurance-recognition.md)
- **Clarifies:** [ADR 0006](0006-regulatory-assurance-and-external-adapter-boundary.md)

Current runtime routing: [#78](https://github.com/packetlss/compliance/issues/78)
implements the bounded successor. [Operation accounting](../../tooling/docs/operation-accounting.md)
specifies its embedded projection and concrete typed assertion examples. The
promotion-stage statements below retain the original design history; #37 is closed
promotion history. New residual architecture requires a focused exploration.

## Context and authority

ADRs 0013–0015 coupled exact policy assessment with externally authoritative
population completeness, applicability acceptance and recognition. Those designs
were not implemented. Exact accounting and scoped evidence remain necessary;
independently establishing the external universe and its authority is a governance
responsibility. This decision deliberately narrows core responsibility and replaces
the three decisions, including their migration tables and implementation routing.
Only the retained semantics stated here carry forward as successor obligations.

Optional company objective assurance remains core under ADR 0006 alongside
standalone technical baselines. Its external mapping/claim language does not
make engine-established external legal or certification conformity a generic core
responsibility. The external-adapter boundary is unchanged.

[ADR 0012](0012-explicit-policy-parameter-resolution.md) remains unchanged, including
parameter identity, resolution, direct typed consumption and policy-owned freshness.
Its earlier current-routing paragraph referring to ADRs 0013–0015 is historical
routing, replaced by this decision; it does not restore their superseded duties.
The distinction between valid company policy and differing external conditions
remains intact. #73 is implemented; this promotion changes documentation only.

## Decision: responsibility boundary

> The compliance core evaluates explicitly supplied company policy against
> attributable reality. It deterministically resolves supplied inventory, groups,
> assignments, requirements, parameters, realizations and dependencies; evaluates
> qualifying evidence; and preserves immutable attributable results. It does not
> independently establish that governance supplied every real-world asset, selected
> every externally applicable obligation, or chose a legally/regulatorily sufficient
> demonstration.

The strongest generic assertion is:

> Given these exact supplied inventory, scope, assignments, policy, evidence and
> evaluator inputs, these are the resolved obligations and their assessment results
> at the recorded instant.

### Closed-world scope and frozen accounting

```text
supplied inventory
    -> deterministic groups
    -> applicable assignments
    -> exact resolved policy/requirement instances
    -> expected assessment set
    -> attributable results
```

Use the existing `Subject`, `InventoryGroup` and `PolicyAssignment` foundation.
Resolve the supplied operation over stable subject identity and the group DAG.
Overlapping membership uses set union while preserving **all** applicable membership
and assignment paths. Coalescing exact-identical same-identity definitions must not
lose an independently applicable assignment or hide divergent policy. Source/file,
traversal and assignment order grant no precedence; conflicts fail deterministically.

Resolve exact company requirement revisions, parameters, governed subjects and
quantification. A per-host requirement creates instances for its applicable hosts;
an entity requirement creates an entity-scoped instance; a system requirement
retains that system scope. Do not multiply every requirement by every group member.
Organizational identity neither enumerates assets nor supplies beneficiary evidence.

The future implementation must account for the exact resolved expected assessment
set for the supplied operation and detect omitted expected results. Aggregate/run
success cannot be inferred solely from results that happen to exist. Accounting
must remain attributable to the exact supplied inputs and resolved instances, so
a missing result cannot silently shrink the denominator. Complete accounting is
necessary, not sufficient, for success: normal outcomes and conservative roll-up
still apply. This is an architectural obligation, **not a choice of future wire
representation**, artifact family, version or algorithm. Do not introduce
`ClaimScope`, `PopulationSnapshot`, external completeness artifacts or a parallel
inventory/scope hierarchy.

If supplied scope contains A/B/C, results for only A/B cannot establish whole-target
success. If real-world C was never supplied to inventory, that omission is outside
the core's completeness guarantee: an exact A/B result is unchanged and says
nothing about C. No separate claim population or external population/obligation
completeness gates are required.

### Policy truth and evidence truth

| Responsibility | Owner and meaning |
| --- | --- |
| What the organization requires and what demonstration it accepts | Authored company policy |
| Why that policy is appropriate, externally applicable or legally sufficient | Governance and policy authoring |
| Observable or assurance facts about reality | Typed attributable evidence |
| Whether admissible evidence satisfies exact resolved policy | Compliance core |

Authored policy must never manufacture reality. For example, policy saying
“qualifying CE+ assurance is required” creates a dependency; it does not pass
until attributable evidence satisfying that dependency's evidence contract exists.
An authored `adopted`, `implemented`, issuer name, approval reference, framework
mapping, signature reference or content digest alone does not establish satisfaction.
Content-addressed provenance preserves which decisions, references and bytes were
used; it does not endorse correctness, truth, authority or legal sufficiency.

Preserve independent technical `Baseline` / `BaselineOverlay` assessment and
optional company requirement/realization assurance. Realizations remain design-time
demonstration designs with exactly-one deterministic selection. Preserve ADR 0012
resolved parameters and direct typed dependency consumption, policy-owned freshness,
independently attributable technical results, conservative roll-up and fail-only
waivers. Neither adoption nor a waiver manufactures a passing observation.

### Typed external and procedural assurance evidence

> A required dependency identifies its evidence contract; only attributable
> evidence satisfying that contract may determine it.

Explicit assurance/certificate evidence dependencies are ordinary policy dependencies
where selected policy requires them. Apply normal evidence qualification and
[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) outcomes.
There are no universal certificate semantics. Issuer, scheme, holder, covered
subjects, exclusions, validity, signatures or similar fields are required only
where the selected evidence type/schema/dependency contract requires them.

Preserve exact evidence/assertion identity and attribution to the consuming
requirement/dependency and governed scope, including source content and the relevant
assertion within a document when needed to identify what was consumed. Evidence
for A cannot satisfy B unless the exact resolved consumer relationship and evidence
contract legitimately establish that beneficiary relationship. A familiar issuer,
matching framework ID, corporate relationship or signature reference is insufficient.
No generic recognition, certificate, authority or external-claim engine follows.

### Common assurance cannot broaden automatically

```text
broad service assurance
!=
automatic assurance for every possible beneficiary
```

Reuse requires an explicit named beneficiary dependency, attributable source
assurance and required correlation/integration evidence. A shared IAM service's
assurance does not establish that every application actually integrates with it.
Authored integration intent cannot replace evidence of the required relationship.

The initial successor may use appropriately typed attributable evidence if sufficient.
This ADR does **not** require direct assessment-result-to-assessment-result
consumption. Such consumption introduces dependency graphs, cycle handling and
temporal semantics; if implementation exploration finds it necessary, obtain a
separate architecture decision first. ADR 0013's anticipated mechanism is not a
reason to preserve that complexity. No generic cross-time result equivalence is
introduced; selected evidence still qualifies at the recorded assessment instant.

### Framework mappings and bounded reporting

Framework/regulatory references and mappings are attributable company policy,
explanation and reporting content, not runtime external authority. The core may
group or trace company results by exact external references and explicit authored
targets. If supplied company target P contains O1/O2/O3, internal resolution and
accounting cannot silently omit O2. The engine does not establish that those three
exhaust every externally applicable obligation.

A supported conclusion may be:

> All required instances in company target P revision R passed for resolved
> subjects A and B.

Never silently upgrade this to “all company assets comply”, “framework F is
satisfied”, or “certification/legal conformity is established”. Mapping coverage,
including complete/partial/supporting descriptions, remains authored content;
accumulating mappings cannot manufacture external conformity. Empty supplied
scope or absent policy supplies no basis for such an external claim either.

External conformity comparison is outside the generic core unless a future explicit
company-policy dependency models a concrete condition to evaluate. ADR 0012 still
permits internally valid passing company policy while an external condition differs;
this ADR neither changes parameter resolution nor adds an external comparison gate.

### Invalid inputs, N/A and outcome boundaries

Fail closed on inconsistencies inside supplied inputs. Do not guess unresolved
group references, accept group cycles, correlate ambiguous subject identities,
choose among conflicting assignments/policy, invent unresolved required parameters,
accept invalid dependency targets or tolerate tampering/integrity failures.

| Condition | Preserved boundary |
| --- | --- |
| Invalid group/identity/assignment/policy/dependency resolution | Affected required resolution is invalid; no partial valid plan or success synthesized from omitted inputs |
| Required ADR 0012 parameter unresolved | Non-assessable policy; not an evidence `unknown` substitute |
| No policy assignment | Unassigned/outside supplied assessment scope, not automatically N/A |
| No matching realization for an assigned objective | Existing separate `not_implemented` coverage and failing requirement behavior, not evidence `unknown` or external N/A |
| Missing/stale/schema-invalid/ambiguous/inconclusive required evidence after valid dependency resolution | ADR 0010 `unknown`, never pass |
| Admissible conclusive negative evidence | Normal `fail` |
| Trustworthy attributable execution failure | ADR 0010 `error` |
| Shared plan/routing/composition/provenance/snapshot/evaluator/result integrity prevents trustworthy publication | ADR 0010 assessment-wide refusal; no new trustworthy assessment envelope |
| Existing explicit N/A where supported | Remains distinct under existing behavior, pending separate architecture review |

This ADR does not redesign N/A or define new wire statuses. Never infer external
N/A from absent assignments, evidence or realizations. Pre-assessment resolution
failure is distinct from evidence insufficiency after a valid dependency resolves.
The absence of external completeness machinery weakens none of these internal
resolution, qualification or integrity boundaries.

Historical results remain immutable under their exact frozen operation scope,
relevant assignments, resolved policy/requirement content, selected realization/dependencies, parameters,
evidence snapshot, evaluator, composition, waiver attribution and recorded instant.
Later membership, policy, mapping or evidence changes do not rewrite them.
[ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md) retains
its immutable-history and separately routed operational interpretation boundary.

## Deterministic conceptual conformance examples

These use exact supplied inputs and recorded assessment instant `t`. They are
conceptual obligations, not executable future-behavior fixtures or new schemas.

| Supplied case | Required conclusion |
| --- | --- |
| Target consists of A/B; every resolved required instance for A/B passes | Exact A/B target success; report the supplied planning composition and frozen scope |
| Same inputs/results, but real-world C exists and was omitted upstream | A/B result unchanged; no statement about C or real-world inventory exhaustiveness |
| Target consists of A/B/C; A/B pass but C's expected result is absent | Incomplete accounting; no aggregate success |
| DAG has left={A,B}, right={B,C}, parent including both | Resolve A/B/C once each; retain both paths to B and every applicable assignment; identical definitions may coalesce, divergent ones conflict |
| Missing group reference, cycle, ambiguous B identity, conflicting assignment or invalid required dependency target | Fail closed at required resolution, never shrink the expected set to produce success |
| Host requirement for A/B and governance requirement for entity E | Exactly two host instances and one entity instance; no requirements-by-host Cartesian product |
| Supplied inventory labels place A in a CE+-required group with an explicit company assignment; B does not match | Resolve the assigned CE+-style policy for A from supplied attributes; no inference of external legal applicability for either A or B |
| Valid resolved CE+-style dependency for A has no qualifying evidence | `unknown`; the authored requirement or issuer name cannot pass it |
| Certificate/assertion covers A only; B requires assurance and has no qualifying beneficiary evidence | A's evidence cannot satisfy B; B's resolved evidence dependency is `unknown` |
| Admissible assurance evidence conclusively says the selected required condition is not met | `fail`, not `unknown` merely because the evidence is negative |
| Shared IAM assurance exists, but application A lacks required integration evidence and B has no named reuse dependency | A's valid integration evidence dependency is `unknown`; no automatic IAM support for B |
| Named application A has a valid beneficiary dependency with qualifying source assurance and required correlation/integration evidence | Support may satisfy A's exact dependency through typed evidence; no automatic support for other applications or need for a direct result graph |
| Company target P revision R contains O1/O2/O3; only O1/O3 have results | O2 remains an omission; no complete P success even if every existing result passes |
| All mapped company checks pass, including mappings labelled complete | Exact company result only; neither framework satisfaction nor certification/legal conformity is manufactured |
| Company policy allows 45m, external condition says 30m, evidence satisfies resolved company policy | Company result remains valid; generic core does not establish external conformity or change ADR 0012 bindings |
| Required ADR 0012 parameter has no concrete value | Non-assessable policy; do not evaluate a partial plan or invent evidence `unknown` |
| Assigned company objective has no matching realization | Existing `not_implemented` coverage and failing requirement behavior remain |
| Valid dependency lacks evidence, evidence is stale/schema-invalid/inconclusive, or newest tied candidates diverge under ADR 0010 | Required result is `unknown`; existing evidence-selection semantics remain unchanged |
| Evaluator fails but trustworthy execution/result attribution exists | Attributable `error` under ADR 0010 |
| Shared plan or snapshot integrity is tampered so trustworthy publication is impossible | Assessment-wide refusal under ADR 0010 |
| No assignment, or an existing explicit N/A determination | Unassigned remains distinct from explicit N/A; no external N/A inferred from absence |
| B leaves a group, policy changes or assurance expires after `t` | Historical result and exact input attribution remain immutable; no query-time rewrite |

## Deliberately relinquished guarantees and consequences

The core no longer intends to establish:

- external real-world inventory exhaustiveness;
- authoritative external obligation-universe completeness;
- external legal/applicability authority conflicts or supersession;
- generic destination recognition authority; or
- independent external conformity conditions.

This is deliberate responsibility narrowing. Governance and policy authoring own
those judgments. External population-completeness determinations, generic external
applicability inference, authority-acceptance bases as a separate runtime subsystem,
authoritative external universe validation, recognition rules, framework equivalence
or automatic substitutions, and engine-established certification conclusions are
removed from the successor core responsibility. Retaining them would reintroduce
the superseded external-claim design under different names.

The mitigation is exact supplied-policy/scope provenance, bounded result wording
and governance's ability to model additional assurance requirements as ordinary
explicit policy dependencies. A limited or poorly chosen policy can pass; the
core does not endorse its completeness or legal sufficiency. Conversely, policy
cannot author a passing reality assertion: required evidence must still qualify.

## Ownership, next exploration and non-goals

| Surface | Retained responsibility and next exploration |
| --- | --- |
| Tooling inventory/planning | Existing Subject/group DAG/assignment resolution and exact governed instances; inspect closed-world expected assessment/run accounting |
| Policy contracts and tooling evidence qualification | Explicit selected external/procedural dependencies and typed attributable evidence; inspect exact beneficiary/scope attribution |
| Company/adopter policy and governance | Choose inventory, requirements, demonstration and external references; own external sufficiency and authority judgments |
| Plan/results/provenance/reporting | Immutable resolved scope/policy/evidence attribution, omission detection and bounded company results; no new wire family chosen |
| Common assurance | Determine whether any explicit reuse mechanism is actually needed; typed evidence may suffice; direct result graphs require separate review |

At promotion time, #37 remained open for residual assurance questions. The next
step was narrow **read-only repository-grounded implementation exploration** of
closed-world expected assessment/run accounting, typed external/procedural assurance
dependencies and evidence qualification, exact beneficiary/scope attribution, and
whether explicit common-assurance reuse is needed. Inspect actual post-#73 code;
do not assume a direct result graph or a coordinated migration of ADRs 0013–0015.
Return a bounded implementation contract after resolving blocking architecture.
This promotion authorizes no runtime implementation or future-behavior tests.

Non-goals are runtime/schema/fixture/generated-artifact changes, legal interpretation,
framework equivalence, generic authority/IAM, sampling inference, dynamic scope
language, cross-time result equivalence, direct cross-assessment result graphs
without separate review, evidence storage, continuous compliance, monitoring or
query-time ageing, adapter/apply behavior, release changes, private operational
inputs and firewall work. Existing explicit N/A is not redesigned. Broader residual
questions do not broaden the authorized next exploration. Return to architecture
before implementation depends on new semantics or cannot preserve exact scope,
qualification, immutable attribution or existing outcome boundaries.

## Promotion validation

Require `git diff --check`, applicable repository/documentation/link validation,
coherent supersession and active routing, these conceptual examples, fresh-context
exact-head independent read-only review with findings resolved, and all four stable
exact-head CI contexts: `component-validation`, `verification-scenarios`,
`installed-release-provenance`, `macos-portability`. Runtime and semantic schema
bytes remain untouched; current experimental behavior remains until a separately
authorized implementation cutover. No compatibility or identity algorithm is
frozen. Return a PR for human review; a human retains final squash-merge authority.
