# ADR 0011: Separate historical assessment outcomes from operational evidence timeliness

- **Status:** Accepted and implemented for v4 historical operation reporting
- **Date:** 2026-09-05
- **Promotion contract:** [#66](https://github.com/packetlss/compliance/issues/66)
- **V4 representation implementation:** [#32](https://github.com/packetlss/compliance/issues/32)
- **Operational view implementation:** [#80](https://github.com/packetlss/compliance/issues/80)
- **Retention-boundary clarification:** [#89](https://github.com/packetlss/compliance/issues/89)
- **Plan/result refinement:** Implemented under [#90](https://github.com/packetlss/compliance/issues/90); experimental, not frozen

## Context and authority

The predecessor status implementation re-renders the present plan, calls a
matching `plan_id` result `current`, directly presents its stored result state,
calls a different-plan result `outdated`, and calls absence `pending`. It timestamps
the report at query time without re-evaluating evidence or waiver age. Those are
current runtime labels, not evidence of present security or continuing validity.

This ADR owns interpretation of assessment results across wall-clock time.
[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) remains the
normative owner of assessment-time evidence validity, freshness eligibility during
evaluation, schema-invalid evidence, evidence selection ambiguity, attributable
execution `error`, and assessment-wide refusal. None of those semantics moves here.
[ADR 0007](0007-unified-actual-and-expected-composition-provenance.md) continues to
own the unified provenance-bearing assessment artifact line.

Accepted option **B**: **#32 includes the small forward-compatible representation
clarification required by this decision.** A complete snapshot descriptor
and criterion-reported evidence IDs alone do not expose all immutable factual
selection and temporal provenance needed for a later view without evidence bytes.
This clarification adds facts to v4, not stored operational judgments.

The original promotion changed documentation and contracts only; it did not change
the then-current predecessor runtime, schemas or tests. #32 implemented the
representation obligation below alongside its existing ADR 0010 corrections. The
derived operational view
was accepted future semantics and is implemented by #80 as a derived reporting tranche.
No historical artifact is rewritten or reinterpreted; no compatibility freeze is
created.

## Decision

### Immutable historical assessment outcome

An immutable historical assertion is the retained exact assessed plan paired with
the result of what was concluded at its recorded `evaluated_at`. The plan owns
resolved intent, operation membership, planning composition/enforcement, evidence
dependencies and other plan semantics. The result owns the immutable outcome,
actual evaluation composition/enforcement, evaluator, complete evidence snapshot,
successful selections, and exact applied-waiver facts. Advancing wall-clock time
must never change a stored `pass`, `fail`, `unknown`, `error`, or `waived`.
Historical technical and requirement/realization roll-ups remain immutable.

Here, **historical** describes the semantics of a retained assessment result, not a
core storage obligation. Assessment semantics do not depend on previously produced
results, and the core does not require or own long-term retention of assessment
plans or results. Retention by the surrounding operating environment enables later
historical interpretation; deleting prior artifacts removes that historical view
but does not affect the ability to perform future assessments. A retained orphaned
result may expose raw recorded facts, but tooling must not claim fully validated
policy interpretation, historical timeliness, requirement meaning, or plan alignment
without resolving and relationally validating the exact assessed plan by `plan_id`.

A multi-subject historical operation needs one retained operation-bearing plan as
the denominator anchor, the exact bound plan for every result requiring full
interpretation, and each retained result. Missing-result plan artifacts are not
invented merely to demonstrate an omission from the anchor's denominator.

### Current-plan alignment

Exact equality of the stored `plan_id` and currently resolved comparison plan ID
means **Plan-aligned**. A nonmatching exact ID means **Different plan**. If comparison
cannot be established, report **Plan alignment unavailable**.

Plan alignment does not mean currently secure, current PASS, evidence still timely,
no drift, or continuous effectiveness. Do not infer semantic equivalence across
different plan IDs, including differences caused only by provenance.

### Operational evidence timeliness

At explicit query instant `q`, determine whether the exact evidence successfully
selected for the historical assessment remains inside the applicable temporal
requirements recorded by the **assessed** plan. Preserve the existing age rule:

```text
q - collected_at <= max_age
```

Equality is within the recorded age limit. This is a derived property of historical
assessment support, not re-evaluation of criterion truth. Do not change assessment-time
freshness eligibility, future-timestamp semantics, illustrative evidence `expires_at`
behavior, the required-only dependency model, or evidence selection. This ADR adds no
alternative temporal eligibility rule.

Never reselect evidence at query time or substitute current mutable evidence for
the historical snapshot. A later fresh document cannot make an old result fresh.
Use the selected-document facts and applicable assessed-plan requirements described
below; do not require original evidence-byte retention. If those facts or requirements
cannot establish timeliness, expose **Evidence timeliness unavailable**, retaining
historical missing/invalid/ambiguous/otherwise inconclusive explanations. Do not
manufacture successful selections for such results or claim timely support from an
empty set of successful required selections when required evidence was not selected.
This does not change the required-only evidence model or existing applicability.

One stale required selected-evidence dependency qualifies the affected control as
needing reassessment. Do not average evidence ages. Concurrent stale and unavailable
dependencies remain independently visible; unavailable information cannot hide a
known stale dependency, and known staleness cannot hide unavailable information.

### Recorded waivers

A historical `waived` result remains historically `waived` after the recorded
waiver interval ends. Independently qualify the recorded applied exception at `q`
using its immutable snapshot and existing start-inclusive/end-exclusive interval:

```text
validFrom <= q < expiresAt
```

Within the interval: **Recorded waiver within validity window**. At or after its
end: **Recorded waiver expired**. Queries before the recorded interval must not
claim that it was within the window; this does not introduce a new waiver lifecycle
or assessment state. Do not substitute a mutable waiver catalog, introduce
revocation authority, or reinterpret historical `waived` as `fail` or `unknown`.
Only underlying failure can receive a waiver; a waiver never establishes compliance.
The retained exception fact is the exact normalized applied-waiver snapshot and its
identity/digest, exact subject/control target, evaluation-time applicability, and
underlying failure. Whole-catalog contents or `waiver_revision` are not part of
assessment-result identity or historical assertion semantics. When no waiver was
applied, no retained proof of an entire waiver catalog is required, and an unrelated waiver
elsewhere cannot change result identity. This does not permit mutable substitution,
revocation semantics, or query-time reinterpretation.

### Refused attempts and absence

Assessment-wide refusal still publishes no new assessment-results artifact. A view
cannot infer a refused attempt merely from absence of a new result. Show
**Assessment refused — no new result** only when trustworthy attempt information
is explicitly available. An older result, if present, remains historical evidence;
it is not output from the refused attempt. This ADR introduces no persisted
attempt/status artifact and no broader history selection or supersession policy.

### State matrix and operator terminology

The rows are independent dimensions, not a replacement result enum. Their
combinations retain each dimension's meaning.

| Dimension / condition | Required interpretation / preferred wording |
| --- | --- |
| Stored `pass` | Historical PASS at `evaluated_at` |
| Stored `fail` | Historical FAIL at `evaluated_at` |
| Stored `unknown` | Historical UNKNOWN at `evaluated_at`; retain the reason |
| Stored `error` | Historical ERROR at `evaluated_at`; retain the attributable failure |
| Stored `waived` | Historical WAIVED at `evaluated_at`; retain underlying failure and applied exception |
| Exact comparison plan ID matches | Plan-aligned |
| Exact comparison plan ID differs, including provenance-only differences | Different plan |
| Current-plan comparison cannot be established | Plan alignment unavailable |
| Selected evidence satisfies recorded applicable age limits at `q` | Selected evidence within recorded age limits as of `q` |
| Any required selected dependency exceeds its recorded age limit | Evidence stale — reassessment due |
| Required historical selection facts or assessed requirements cannot establish timeliness | Evidence timeliness unavailable |
| Stale and unavailable dependencies coexist | Both stale/reassessment and unavailable qualifications remain visible |
| Recorded applied waiver is within its interval at `q` | Recorded waiver within validity window |
| Recorded applied waiver is at or past its exclusive end at `q` | Recorded waiver expired |
| No recorded applied waiver | No applied-waiver qualification; do not invent an exception |
| No assessment result | No assessment; no invented historical outcome |
| Explicit trustworthy information records a refused attempt | Assessment refused — no new result; preserve any older history separately |

Avoid unqualified **current PASS**, **currently secure**, and overloaded **outdated**.
For example, a historical FAIL may simultaneously concern a different plan, depend
on now-stale selected evidence, and be associated with an expired historical
exception. An aggregate may contain both a failing child and a waived child whose
recorded exception has expired; this does not make the failing child waivable by
association.

### Aggregation

Fleet/group views aggregate these dimensions separately:

1. historical result outcomes;
2. plan alignment;
3. evidence timeliness;
4. recorded waiver validity qualification; and
5. frozen accounting dispositions.

A historical PASS with stale evidence must not contribute to any operator-facing
claim equivalent to “currently passing.” Group membership remains a DAG: a subject
may appear in several group aggregates, while fleet unique-subject totals remain
unique. Preserve the four frozen accounting dispositions independently. Do not recompute
historical requirement/realization roll-ups using query-time qualifications.

ADR 0010's logical required-child precedence remains:

```text
fail -> error -> unknown/missing -> waived -> pass
```

Presentation attention order is separate from logical roll-up precedence.

### Continuous-effectiveness boundary

Point-in-time assessment does not establish:

- continuous effectiveness or absence of drift;
- present-state certainty merely because `plan_id` matches;
- present-state certainty merely because evidence remains inside `max_age`;
- remediation or recovery through ageing of an old failure;
- compliance from a waiver;
- observation authenticity from content addressing; or
- complete security or framework compliance from passing modeled checks.

The strongest supported present-time wording is that a historical assessment
remains supported by selected evidence within the recorded age limits at query
instant `q`. This says nothing stronger about the present governed subject.

### Factual temporal provenance and exact plan relation

V4 results/provenance must retain sufficient immutable factual provenance to derive
operational evidence timeliness without the original mutable evidence directory,
re-selection, assumed long-term evidence-byte retention, or evidence-ID-only joins.
Require:

1. Exact attribution from **each control's successful evidence selection** to the
   selected evidence document's **evidence ID and complete-document digest**.
2. The selected document's `collected_at` instant used by existing freshness
   evaluation.
3. The stable authored evidence `dependency_id` for the exact assessed control
   instance, sufficient to resolve its assessed-plan requirement and recorded
   `max_age` without copying the dependency body.
4. A distinction between successfully selected evidence and rejected, ambiguous,
   or otherwise nonselected snapshot candidates.

The selected-document reference must resolve into the complete subject evidence
snapshot descriptor. Same-ID/different-digest evidence remains exactly attributable.
A shared evidence-use table or per-control references are both acceptable; this ADR
does not prescribe JSON layout. List position, filename, source order, and traversal
order cannot identify a dependency. Successful selections order canonically by
`(instance_id, dependency_id)` and duplicate semantic identities fail. Need for a
layout that cannot satisfy these invariants requires architecture escalation.

Trusted assessment orchestration captures these facts from the **same snapshotted
documents consumed by evaluation**, not solely from OPA/criterion self-reported
IDs. The facts are validated and bound into assessment-result identity. They are
factual historical provenance, not persisted judgments such as `fresh`, `stale`,
`current`, or `reassessment_due`; those judgments remain derived view semantics.

The complete evidence snapshot descriptor and successful-selection table are
independent facts and must not be collapsed. The snapshot remains complete for
selected, rejected, ambiguous, unused, duplicate, and otherwise nonselected
documents; only exact canonical duplicates may coalesce for selection.

An intrinsically valid result is not by itself a fully interpretable trusted
historical assertion. Before publication and full interpretation, relational
validation with the exact plan must establish exact plan/subject identity,
evaluation-source authorization, exact active-control and dependency correspondence,
selection references into the complete snapshot, valid compact requirement/baseline
outcomes, exact waiver target/applicability, and fail-only waiver application.
Publication fails closed when this relation cannot be established.

Preserve `evidence-document-digest/v1alpha1` and `evidence-set-digest/v1alpha1`
unchanged, including complete snapshot obligations. [PR #65](https://github.com/packetlss/compliance/pull/65)
and ADR 0010 selection ambiguity semantics remain unchanged. Ambiguity diagnostics
do not substitute for successful-selection provenance. Rejected/nonselected
snapshot candidates must not be relabeled as successful evidence use.

## Implementation ownership and consequences

#32 implemented the original **representation only for this ADR**, preserving all its existing
responsibilities and ADR 0010 corrections. It does not derive query-time
fresh/stale/current state, add a result status, change evidence identity algorithms,
create an artifact family or retention system, or add monitoring/scheduling. It
incorporated these required v4 facts without changing its existing dependencies.

The separately authorized #80 tranche implements a derived operational assessment
view over a validated v4 result, the exact assessed plan, the current comparison
plan, and an explicit
query instant. It depends on #32 and owns status/explanation/group presentation,
removal of misleading equivalent “current” wording, temporal derivation and tests,
and one canonical time-advance scenario. The original promotion neither created
that issue nor authorized its runtime implementation; #80 supplied that authority.

This decision preserves one v4 assessment artifact family, immutable history, exact
plan comparison, complete evidence snapshots, fail-only waivers, refusal without
result, current logical roll-ups, private-source boundaries, location/path/source-order
nonsemantics, and content-addressed provenance. It required the small v4 representation
addition supplied by #32 so #80's view does not depend on mutable evidence or a retention
system. Deferring those facts until the status implementation would have left #32's v4
representation insufficient; storing temporal judgments instead would make immutable
results misleading as time advances.

[#90](https://github.com/packetlss/compliance/issues/90) implements the pre-freeze
cutover from that duplicated representation to the exact `{bound plan, result}`
historical model. Historical tooling must resolve a result's assessed plan solely by
exact `plan_id` from a supplied plan file or bounded plan set and validate the pair
before interpretation—never by filename, traversal order, subject alone, latest,
current-plan substitution, or approximate semantic equality. This adds no storage,
history, result index, run object, retention service, or artifact-discovery subsystem.

## Non-goals, validation and escalation

No evidence collection/scheduling, continuous monitoring, evidence retention/storage,
findings lifecycle, collector precedence/authority, evidence supersession, payload
merging/multi-observation semantics, new freshness eligibility, future timestamp or
evidence `expires_at` behavior, the required-only dependency model, new manual/procedural
assurance, new logical result states, persisted operational-status artifact, adapter
execution, release/signing/acquisition, or firewall/network-policy work is authorized.

The original promotion required coherent documentation and valid links/issues, a
documentation-only diff, `git diff --check`, repository documentation validation,
fresh-context exact-head independent review without unresolved findings, and all four
stable exact-head CI contexts green. Runtime/schema/temporal implementation and tests
were delivered under #32 and #80. Human final squash-merge authority remains unchanged.

Return to architecture if implementation needs original evidence-byte retention as a
prerequisite for timeliness; a new evidence identity/equivalence algorithm; evidence
authority, supersession or multi-observation semantics; changed assessment-time
freshness eligibility; a new result state, persistent artifact family or trust
boundary; changed logical roll-ups; broader assessment-history selection/supersession;
an external compatibility freeze/consumer; removal of evaluation enforcement;
positional dependency identity; a result graph/cross-result dependency; core history,
retention, latest-result, or discovery services; or material overlap with new
assurance semantics.
