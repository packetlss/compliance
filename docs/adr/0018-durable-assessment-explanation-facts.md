# ADR 0018: Retain minimal durable assessment explanation facts

- **Status:** Accepted design, not yet implemented
- **Date:** 2026-09-07
- **Architecture contract:** [#98](https://github.com/packetlss/compliance/issues/98)
- **Predecessor:** #97 / ADR 0017 authored human-readable policy and check meaning; implementation remains independent
- **Refines:** [ADR 0007](0007-unified-actual-and-expected-composition-provenance.md), [ADR 0010](0010-required-evidence-status-and-assessment-refusal.md), and [ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md)

## Context and decision boundary

The exact retained assessed plan plus immutable result, followed by mandatory
relational validation, remains the trustworthy historical assertion. The plan owns
resolved policy and dependency meaning. The result owns the assessment-time
conclusion and evaluation facts. Current qualification may separately report plan
alignment, selected-evidence timeliness, recorded-waiver validity and frozen
operation accounting without rewriting that conclusion.

Successful evidence selection already has durable stable attribution through
`provenance.selectedEvidence`:

```text
instance_id + dependency_id + evidence_id + evidence_digest + collected_at
```

The complete subject evidence snapshot is also content-addressed. Those facts do
not, however, say why a required dependency had no successful selection. Replaying
current routing, schema validation, freshness and selection against retained or
newly reacquired evidence would make historical explanation depend on current code,
schemas and payload availability. It is therefore forbidden.

This decision retains the minimum assessment-time facts needed to explain
unsuccessful dependency selection and attributable technical `error`. It does not
change `pass`, `fail`, `unknown`, `error` or `waived` meaning; add a result status;
make a refused attempt a result; create an operation-wide result row; copy policy
meaning into diagnostics; or introduce a history service, run artifact, event log
or generic diagnostic vocabulary.

ADR 0017 separately makes authored plan meaning durable. A reporter may combine
that plan-owned title/purpose with the facts accepted here. This result contract
does not copy those strings and does not implement ADR 0017.

## Repository trace and current fact loss

The current flow is:

```text
plan control dependency
  -> explicit subject/type routing
  -> validation of every matching candidate
  -> assessment-time freshness eligibility
  -> unique greatest-instant selection
  -> criterion evaluation and decision validation
  -> technical outcome
  -> requirement and requirement-baseline roll-up
  -> result-domain semantic projection
  -> exact plan/result relational validation
  -> optional historical accounting and current qualification
```

The current implementation retains invalid and ambiguity observations inside a
technical result, successful selections in evaluation provenance, and applied
waivers on waived technical outcomes. It gives missing and stale evidence the same
reason, allows an `unknown` criterion decision after all selections succeed, and
maps evaluator invocation/decision failures to `error`. Shared plan, routing,
catalog, evaluator-identity, snapshot or result-integrity failures refuse
publication.

| Case | Known at assessment time | Retained now | Lost or unstable now | Later deterministic explanation? |
| --- | --- | --- | --- | --- |
| Selected evidence | Exact dependency, document ID/digest and `collected_at` | Complete snapshot plus `selectedEvidence` | Nothing required by this decision | Yes, with the exact plan |
| Absent evidence | No document matched the routed subject and dependency type | `unknown`, empty selection and generic missing-or-stale reason | Exact dependency disposition | No |
| Stale evidence | Matching schema-valid documents existed but all exceeded `max_age`; the greatest collection instant is known | `unknown`, snapshot identity and generic missing-or-stale reason | Stale disposition and attributable greatest-instant candidate facts | No |
| Schema-invalid evidence | Rejected document references and validator failures | Dependency/type, document ID/digest, schema locators, instance/schema paths, keyword and raw library message | Stable safe contract is mixed with library prose, location duplication and a possibly sensitive evidence-instance path | Partly; attributable, but not suitably stable or minimized |
| Ambiguous latest evidence | At least two distinct, equally latest, valid and fresh documents | Candidate ID/digest pairs, tied instant and redundant subject/evaluation/schema fields | No material selection fact; representation is duplicated inside technical observations | Yes, with the exact plan |
| Criterion inconclusive | Every dependency selected and a valid criterion decision returned `unknown` | Successful selections plus technical status, reason, expected and observed decision facts | Criterion stage is implicit rather than named | Yes after exact dependency accounting and relational validation |
| Evaluator exception or unusable decision | Whether invocation failed or the returned decision could not be accepted | `error`, successful selections, and either generic or raw process reason text | Stable failure class; raw process text may be unstable or private | No |
| Waived fail | Underlying technical `fail` and exact applicable waiver | Underlying failure reason/decision facts and exact applied-waiver snapshot with `underlying_status: fail` | Nothing required by this decision | Yes |
| Incomplete operation | Frozen member requires a result but its exact slot has none | Operation-bearing plan and the results that do exist | No member result, deliberately | Yes; accounting reports the omission without inventing a result |
| Refused assessment | Execution stopped before trustworthy publication, with an ephemeral failure available to the caller | No `AssessmentResult` | Core result history contains no attempt or refusal fact | No, from core results alone |

## Decision

### Domain ownership

| Fact | Owner | Meaning | Lifetime |
| --- | --- | --- | --- |
| Dependency contract, evidence type, effective `max_age`, check meaning | Exact assessed plan | The policy requirement against which evidence was selected | For as long as the plan is retained |
| Successful dependency selection | Result evaluation provenance | Exact document successfully supplied to a criterion | Immutable with the result |
| Unsuccessful dependency disposition | Result assessment decision | Assessment-time reason that a required dependency had no selection | Immutable with the result |
| Criterion decision, including criterion-returned `unknown` | Technical result | What the valid criterion decision asserted after all required selections succeeded | Immutable with the result |
| Attributable evaluation error class | Technical result | Which trusted criterion boundary failed while a valid result remained publishable | Immutable with the result |
| Underlying fail and applied waiver | Technical result and existing waiver snapshot | Technical failure plus why governance accepted it as historical `waived` | Immutable with the result |
| Missing operation member result | Frozen operation plus supplied exact results | Accounting omission, not a technical assessment | Derived whenever the retained operation is accounted |
| Current plan/timeliness/waiver qualification | Historical query | Present comparison against immutable historical facts | Derived at explicit query instant; never stored as the historical outcome |
| Refused attempt history | External orchestration/audit, if any | That an attempt occurred and why orchestration refused it | Outside the core contract and retention responsibility |

### Minimal dependency data model

Choose **a result-level canonical unsuccessful-dependency table**. Add the required
root result field `dependency_dispositions`. It contains only dependencies for which
selection did not succeed. `provenance.selectedEvidence` remains the sole owner of
successful selection; a selected dependency is never repeated in the new table.

Every entry has this common key:

```json
{
  "instance_id": "control.instance",
  "dependency_id": "packages",
  "disposition": "absent"
}
```

`disposition` is exactly one of `absent`, `stale`, `invalid`, or `ambiguous`.
These are dependency-selection facts, not technical result statuses and not a
general lifecycle. Their exact closed variants are:

```json
{
  "instance_id": "control.instance",
  "dependency_id": "packages",
  "disposition": "absent"
}
```

```json
{
  "instance_id": "control.instance",
  "dependency_id": "packages",
  "disposition": "stale",
  "latest_candidates": [
    {
      "evidence_id": "evidence:packages",
      "evidence_digest": "sha256:<complete-document digest>",
      "collected_at": "2026-09-05T10:00:00Z"
    }
  ]
}
```

```json
{
  "instance_id": "control.instance",
  "dependency_id": "packages",
  "disposition": "invalid",
  "diagnostics": [
    {
      "code": "evidence_schema_invalid",
      "evidence_id": "evidence:packages",
      "evidence_digest": "sha256:<complete-document digest>",
      "schema_path": "/properties/payload/properties/packages/type",
      "keyword": "type"
    }
  ]
}
```

```json
{
  "instance_id": "control.instance",
  "dependency_id": "packages",
  "disposition": "ambiguous",
  "candidates": [
    {
      "evidence_id": "evidence:packages-a",
      "evidence_digest": "sha256:<complete-document digest>",
      "collected_at": "2026-09-07T10:00:00Z"
    },
    {
      "evidence_id": "evidence:packages-b",
      "evidence_digest": "sha256:<complete-document digest>",
      "collected_at": "2026-09-07T12:00:00+02:00"
    }
  ]
}
```

The exact assessed dependency type and effective age limit are deliberately not
copied. The dependency key resolves them from the exact plan. The exact schema is
identified by that dependency's evidence type under the result's exact evaluation
composition; no second schema identity or source-location object is needed.

`absent` means zero matching routed candidates existed in the valid snapshot.
`stale` means matching candidates were schema-valid and none was fresh; it retains
every distinct complete-document candidate at the greatest collection instant,
including each document's exact `collected_at` representation. Exact candidate
facts are retained because they make the stale
assertion attributable to the already committed snapshot without retaining bytes
or choosing one tied document by an unauthorized precedence rule.

`invalid` owns one or more stable validation facts. Multiple invalid documents and
multiple distinct schema constraints may coexist. Equal facts coalesce; a diagnostic
count is not semantic. Validation precedes freshness and ambiguity, so `invalid`
cannot coexist with another disposition for the same dependency. An invalid
dependency has no successful selection.

`ambiguous` means at least two distinct complete documents remained at the greatest
fresh eligible instant. Candidate ID/digest/time facts, rather than a count alone, are necessary
for audit attribution and add no identifiers beyond the complete snapshot. They
are never selection precedence and are not described as contradictory merely
because the complete documents differ.

Candidate timestamps retain the exact RFC 3339 strings from their documents, as
successful selections already do. Freshness and greatest-instant equality compare
parsed instants. Therefore two candidates may legitimately show different offset
representations of the same instant; neither representation is selected as a
canonical shared timestamp.

Different dependencies of one control may have different dispositions. For
example, one may be invalid while another is absent. The owning technical result
remains one `unknown`, and the reporter presents every blocking dependency fact.

### Criterion inconclusive and attributable error

A separate criterion-inconclusive object is unnecessary. The existing runtime has
a stable criterion-level concept: after every required dependency has a successful
selection, a structurally valid criterion decision may itself return `unknown`.
The exact plan plus the complete selected/disposition partition proves that the
`unknown` was not caused by dependency selection. The existing technical decision
`reason`, `expected` and `observed` facts retain the criterion's bounded explanation.
Technical-only criteria with no dependencies follow the same rule. No Objective is
synthesized.

For every technical result with status `error`, add required `evaluation_error`:

```json
{
  "stage": "criterion_execution",
  "code": "criterion_execution_failed"
}
```

or:

```json
{
  "stage": "criterion_decision",
  "code": "criterion_decision_invalid"
}
```

or:

```json
{
  "stage": "criterion_decision",
  "code": "criterion_reported_error"
}
```

`criterion_execution_failed` covers a failed evaluator process or an attributable
exception while invoking the criterion. `criterion_decision_invalid` covers
undefined, non-JSON, non-object, wrong-field, invalid-status, invalid-value or
otherwise unusable/unrepresentable evaluator output. `criterion_reported_error`
means the evaluator returned a structurally valid decision whose status was
`error`.

These are the only result-producing error boundaries currently supported. An
unavailable or unidentifiable evaluator, unavailable/invalid schema catalog,
unsafe routing, inaccessible/unrepresentable snapshot, untrustworthy affected
scope, or result-envelope validation failure remains assessment-wide refusal and
publishes no result. A future additional attributable error class requires review
and an explicit closed code, not an arbitrary string or attribute map.

The existing technical `reason` uses this exact safe mapping:

| Code | Required `reason` |
| --- | --- |
| `criterion_execution_failed` | `Criterion execution failed.` |
| `criterion_decision_invalid` | `Criterion decision was unusable.` |
| `criterion_reported_error` | `Criterion reported an evaluation error.` |

For technical `error`, raw standard output/error, exception messages, exception
objects and stack traces are **not retained**. They are neither semantic data nor
non-identity diagnostic detail in the result. The existing technical `reason` must
be a fixed safe, location-independent sentence corresponding to `evaluation_error`,
never copied backend text. Its existing `expected` and `observed` fields must be
empty objects for `error`; the closed `evaluation_error` is the sole retained error
detail. External orchestration may retain operational logs under its own access,
privacy and retention controls; those logs do not become part of the historical
assertion.

This restriction does not redesign evaluator-owned reasons for valid `pass`,
`fail`, `unknown` or underlying waived-fail decisions. Those remain existing
identity-bearing technical decision facts, but they must remain bounded decision
facts and must not copy whole evidence payloads.

### Identity and normalization

All new structured facts are historical assertions and are identity-bearing:

| Field | Identity-bearing | Reason and effect |
| --- | --- | --- |
| `dependency_dispositions[].instance_id` | Yes | Names the affected stable control instance |
| `dependency_id` | Yes | Names the exact authored required dependency |
| `disposition` | Yes | Distinguishes absent, stale, invalid and ambiguous assessment-time reasons |
| Candidate `evidence_id`, `evidence_digest` and `collected_at` | Yes | Commit to exact already-snapshotted documents, their temporal facts and same-ID/different-document distinctions |
| Validation `code`, `schema_path` and `keyword` | Yes | Commit to a stable schema failure without library prose or evidence values |
| `evaluation_error.stage` and `.code` | Yes | Distinguish materially different attributable `error` assertions |
| Raw error text, evidence instance path, schema source location, filesystem path | Not present | They are unnecessary, unstable, location-bearing or potentially private |

The result-domain semantic projection adds normalized `dependency_dispositions`
and each technical outcome's `evaluation_error` where required. Thus two otherwise
equal results that assert absent versus stale evidence, or criterion execution
failure versus invalid criterion output, have different result identities. The
complete evidence-set identity may already differ between absent and stale cases;
that does not make the explicit semantic association redundant.

`dependency_dispositions` sorts by `(instance_id, dependency_id)` and has one entry
per key. `latest_candidates` and `candidates` sort by
`(evidence_id, evidence_digest)` and contain distinct complete-document references.
Invalid diagnostics sort by
`(evidence_id, evidence_digest, schema_path, keyword, code)` and contain distinct
facts. Source, file, traversal and input list order are nonsemantic. Duplicate keys
or noncanonical arrays fail validation; duplicate input facts coalesce only where
the underlying evidence-selection or diagnostic semantics already permit exact
coalescing.

No message or renderer prose is added to the result identity projection. Existing
technical reasons retain their current responsibility; the new code fields, not
wording chosen by an operator view, own the new explanation distinctions.

### Intrinsic result validation

Without an assessed plan or evidence payload, intrinsic result validation must:

1. validate the exact tagged shape of every disposition and error record;
2. enforce canonical ordering, unique dependency keys and unique nested facts;
3. require every candidate/diagnostic ID+digest pair to occur in the complete
   evidence snapshot descriptor;
4. reject a dependency key appearing in both `selectedEvidence` and
   `dependency_dispositions`;
5. require every disposition's `instance_id` and every `evaluation_error` owner to
   name exactly one technical result;
6. require a technical result owning any dependency disposition to be `unknown`;
7. require `evaluation_error` exactly when the technical status is `error`, and
   validate the accepted stage/code pair, canonical fixed reason and empty
   `expected`/`observed` objects;
8. reject `evaluation_error` on `unknown`, including criterion-inconclusive
   `unknown`;
9. preserve current exact applied-waiver shape, `underlying_status: fail`, outcome
   uniqueness, evidence-set identity and result semantic identity validation; and
10. reject raw error detail or legacy orchestration-owned invalid/ambiguity
    diagnostics in technical `observed` after cutover.

Intrinsic validation can prove what the result asserts, parse its recorded
candidate times and establish that referenced documents belong to its snapshot. It
cannot prove from descriptors alone that a candidate time matches the underlying
document, rerun schema validation, or prove that no other document matched. Those
facts are captured by trusted orchestration from the same in-memory snapshot before
publication.

### Mandatory plan/result and publication-time validation

Relational validation with the exact assessed plan must additionally:

1. resolve every selected or unsuccessful key to exactly one active plan dependency;
2. require successful selections plus unsuccessful dispositions to partition every
   active dependency exactly once;
3. require all stale latest candidates to represent the same greatest instant and
   validate each against `evaluated_at` and the assessed dependency `max_age` as
   strictly outside the accepted age limit;
4. require at least two distinct ambiguity candidates at the same greatest instant
   and validate each as eligible under the assessed age limit;
5. bind each invalid diagnostic to the dependency's evidence type under the exact
   evaluation composition and validate its code/path/keyword shape, without
   requiring schema bytes during a later historical query;
6. establish that any technical `unknown` with a complete successful-selection
   partition and no disposition is criterion-level inconclusive;
7. reject an `error` unless all its required dependencies selected successfully;
8. preserve exact control membership, evaluation-source authorization, compact
   requirement/baseline roll-up and waiver applicability checks; and
9. refuse publication on any mismatch.

Before publication, trusted orchestration must also compare every stale, invalid
and ambiguous candidate reference and timestamp/diagnostic fact with the exact
in-memory snapshotted documents used by selection, and confirm invalid schema
paths/keywords against the exact schema catalog used at evaluation. This is the
existing same-snapshot construction trust boundary extended to unsuccessful decisions. It
is not a later evidence re-selection requirement. Historical validation later uses
the immutable asserted facts; it does not require or authorize retained payloads.

### Privacy and minimization

Result artifacts must not become evidence or backend-error archives. This decision
retains only stable dependency keys, already-required snapshot document IDs/digests,
the minimum relevant collection instants, safe schema constraint identifiers and
closed evaluation error codes.

It deliberately does not retain:

- evidence documents, payload fragments, rejected values or provider responses;
- credentials, private inventory, adapter/provider state or arbitrary attributes;
- raw evaluator stdout/stderr, exception messages/objects or stack traces;
- JSON instance paths, because dynamic object member tokens may disclose evidence
  values or identities;
- raw JSON Schema library messages, because wording and embedded values are neither
  stable nor safely bounded;
- filesystem paths or schema source locations; or
- all stale candidates when they are older than the greatest stale instant.

`schema_path` points into policy-owned schema structure, not into evidence data.
The assessed dependency type plus exact evaluation composition identifies the
applicable schema. Evidence IDs and policy source names may themselves be sensitive
metadata, so surrounding retention remains access-controlled, but this decision
introduces no new IDs and does not weaken their existing non-secret identifier
expectation.

Normal human wording is derived from closed codes, schema keywords, safe schema
paths and plan-owned meaning. It is not copied into the result as a new diagnostic
message contract.

### Waiver relationship

Waiver semantics do not change. The criterion first produces an underlying
technical `fail` with its existing reason/expected/observed facts. Only that fail
may become `waived`; the exact applied-waiver snapshot explains the governance
acceptance. A waiver neither erases nor replaces the technical explanation and
never applies to dependency `unknown` or evaluation `error`.

Later expiry qualifies the recorded waiver at query time. Historical `waived`
never changes to `fail`, `unknown` or another status.

### Plan, applicability and operation ownership

No assignment, conflicting policy, unresolved required policy, missing realization,
excluded/non-assessable control and missing operation member remain owned outside
technical result diagnostics:

- inventory/policy coverage explains no assignment;
- policy resolution refuses conflicting or invalid required policy;
- the plan's adoption/assessability facts explain a missing realization;
- the plan/frozen operation explains inactive, unassigned, excluded and
  non-assessable members; and
- frozen accounting plus available exact results explains an omitted required
  member.

Do not create `dependency_dispositions` without an `AssessmentResult`, attach an
operation-wide omission to an existing member's result, or synthesize a result for
the missing member. In `[A, B]` with only A's exact result, A remains whatever it
historically asserted and B's slot remains absent; accounting is incomplete.

### Query-time qualification boundary

Assessment-time disposition and current qualification answer different questions:

```text
historical assessment fact      current qualification
--------------------------      ---------------------
selected fresh at assessment    selected evidence now inside/outside recorded age
waiver applied at assessment    recorded waiver now within/after its interval
exact assessed plan             current comparison plan same/different/unavailable
frozen expected member          exact result present/missing
```

A historical `pass` whose selected evidence later exceeds the assessed `max_age`
remains historical `pass`; current qualification says reassessment is due. A
historical `waived` result remains `waived` when its recorded waiver expires. A
different current plan changes alignment only. Dependency dispositions describe
why the historical criterion was `unknown` at assessment time and are never
recomputed at query time.

If the exact assessed plan is unavailable, the result may expose raw recorded
facts such as a dependency key/disposition, document references, error stage/code,
technical outcome and waiver snapshot. Tooling must say that full historical
interpretation is unavailable. It cannot reliably attach policy meaning or evidence
type, state the recorded freshness limit, validate dependency correspondence,
derive selected-evidence timeliness, validate requirement roll-up, or establish
plan alignment. The plan is not copied back into the result to repair this loss.

### Refusal and attempt history

Choose **Boundary A: orchestration owns attempt/refusal history**.

Assessment-wide refusal continues to publish no `AssessmentResult`. The core
defines no trustworthy attempt artifact and owns no attempt store, run log, event
stream or retention service. A core-only historical query over plans and results
therefore cannot distinguish “never attempted” from “attempted and refused before
publication” and must not claim that either occurred.

An external orchestrator or audit system may make a later attempt/refusal claim
only from its own trustworthy, access-controlled record and authority. Ephemeral
core exit diagnostics can help that caller at execution time but are not durable
core history. A view given such explicit external information may label it as
external orchestration history and keep any older result separate; the core does
not define or validate that record in this tranche.

## Options considered

### Option A: enrich each technical result with every dependency explanation

This is local to the displayed check, but repeats a shared evidence-selection
representation inside open `observed` objects, makes result-wide canonical
dependency uniqueness harder to validate, and encourages successful and
unsuccessful paths to drift. It also preserves the current accidental coupling to
evaluator-shaped output. Rejected.

### Option B: canonical result-level unsuccessful-dependency table

This keeps stable dependency identity explicit, supports several independently
failing dependencies, partitions exactly with the existing successful-selection
table, and gives intrinsic and relational validators one closed structure. It does
not duplicate selected evidence or create a universal state machine. **Accepted.**

### Option C: extend provenance only

Document references are provenance, but absent/stale/invalid/ambiguous are semantic
assessment-time selection decisions required for ordinary explanation. Burying them
in nominally reconstructive provenance would make normal result meaning depend on
provenance drill-down and obscure their identity role. Rejected.

### Option D: no artifact change

The current snapshot descriptor omits nonselected `collected_at` and routing/schema
content. Distinguishing absent from stale or reconstructing an evaluator failure
class would require payload retention, current-code replay or guesswork. Rejected.

### Generic diagnostic framework

A universal `{type, stage, subject, object, severity, message, attributes, causes}`
model adds unneeded extension and compatibility surfaces. Dependency disposition,
technical evaluation error, waiver, plan applicability and operation accounting
already have different semantic owners. Rejected.

## Operator explanations

Normal output combines plan-owned human meaning with result-owned structured facts:

| Case | Concise normal explanation |
| --- | --- |
| No assignment | “No policy assignment applies to this supplied subject; no assessment result is expected.” |
| Conflicting policy | “Policy resolution failed; no trustworthy assessment result was published.” |
| Missing realization | “The assigned objective has no implemented applicable realization; this is plan/adoption state, not evidence UNKNOWN.” |
| Excluded/non-assessable | “This frozen member/control is excluded or non-assessable; no result is required.” |
| Required evidence absent | “Required system packages are installed could not be determined because no `linux.packages/v1` observation was available at assessment time.” |
| Required evidence stale | “Required system packages are installed could not be determined because the latest observation was older than the recorded 24-hour limit at assessment time.” |
| Invalid evidence | “The required `linux.packages/v1` observation was present but did not satisfy its schema (`type` at `/properties/payload/properties/packages/type`).” |
| Ambiguous evidence | “Two equally current observations competed for the required dependency, so neither was selected.” |
| Criterion inconclusive | “All required observations were selected, but the criterion returned UNKNOWN: <bounded criterion reason>.” |
| Criterion execution error | “The criterion could not execute; the historical result is ERROR.” |
| Invalid criterion decision | “The evaluator returned an unusable criterion decision; the historical result is ERROR.” |
| Fail plus waiver | “The check failed: <underlying technical reason>. Governance accepted that failure under waiver `<id>`; the historical result is WAIVED.” |
| Incomplete `[A, B]` | “A has an exact result. B requires a result but none occupies its exact operation slot. Accounting is incomplete; no B result was synthesized.” |
| Historical evidence ageing | “Historical outcome: PASS. Current qualification: selected evidence now exceeds its recorded age limit.” |
| Waiver expiry | “Historical outcome: WAIVED. Current qualification: the recorded waiver has expired.” |
| Different current plan | “Historical outcome unchanged. Current plan alignment: different plan.” |
| Assessed plan unavailable | “The result artifact is retained, but its exact assessed plan is unavailable. Raw result facts can be shown; full policy, dependency, timeliness and alignment interpretation is unavailable.” |
| Refused attempt | “Core result history cannot say whether an attempt occurred. A refusal may be reported only from separately trusted external orchestration history.” |

Advanced drill-down may show, as applicable:

- exact `result_id`, `plan_id`, `operation_id`, subject and `evaluated_at`;
- control `instance_id` and dependency `dependency_id`;
- evaluation composition and evaluator identities;
- evidence-set identity and exact selected, stale, invalid or ambiguous candidate
  ID/digest references;
- stale/ambiguous candidate collection instants, assessed `max_age`, validation code,
  schema keyword/path and policy-source composition digests;
- underlying technical fail facts and complete applied-waiver identity/snapshot; and
- frozen member plan digest, expected result slot and whether an exact result fills it.

Drill-down still does not show evidence payloads, raw error text or private backend
state.

## Migration and compatibility

The assessment v4 wire contract and result digest algorithm are experimental and
unfrozen. Implement this decision as one atomic forward cutover of the current v4
schema, construction, semantic projection and validators. Existing development v4
results lacking `dependency_dispositions` and structured `evaluation_error` become
unsupported by current tooling after cutover. Regenerate fixtures and development
artifacts deliberately; use historical tooling for historical artifacts.

Do not add compatibility readers, writers, aliases, inferred dispositions from old
reasons/observations, or a mixed old/new identity projection. Do not reinterpret or
rewrite an already retained artifact. No evidence, plan, operation/member, waiver,
composition or evaluator identity algorithm changes, and no identifier is promoted
to `/v1`.

## Implementation promotion

Promote one atomic successor issue from #98, sequenced independently from ADR 0017's
implementation. Its exact write scope is:

1. the strict assessment-results v4 schema and mirrors/package data if applicable;
2. evidence selection construction of canonical `dependency_dispositions` from the
   same snapshot used for evaluation;
3. criterion execution/decision boundary classification and safe fixed error
   reasons;
4. retirement of result-owned raw validation messages, evidence-instance paths,
   schema source locators and legacy invalid/ambiguity observation fields;
5. the result-domain semantic projection and provisional result identity vectors;
6. intrinsic result validation, same-snapshot publication validation and mandatory
   exact plan/result relational validation;
7. existing historical qualification/explanation consumers only as necessary to
   consume the new facts, without implementing Stage 5 operator views;
8. tooling contract documentation; and
9. focused unit and canonical scenario coverage for every accepted case below.

Acceptance requires absent/stale distinction; attributable invalid and ambiguity
facts independent of input order; criterion-level `unknown`; each closed `error`
class; no raw private error/payload retention; fail-only waiver preservation; exact
dependency partition and identity effects; incomplete-operation behavior; immutable
historical ageing/waiver/alignment qualification; orphan-plan limits; and refusal
without a result or core attempt claim.

The implementation issue does not authorize ADR 0017 schema/runtime work, Stage 5
CLI views, new statuses, evidence payload retention, compatibility support, result
storage/history, an attempt artifact, synthetic results or operation redesign.

## Consequences and decision test

With the retained exact plan and result, a deterministic reporter can explain the
important assessment-time reason for dependency-selection `unknown`, distinguish it
from criterion-inconclusive `unknown`, classify attributable `error`, and preserve
underlying fail plus waiver explanation. It does so from identity-bound structured
facts without selecting evidence again, copying policy meaning, retaining evidence
payloads or changing the historical outcome.

When no result exists because assessment was refused, core-only history can make no
trustworthy attempt/refusal claim. That claim belongs, if required, to separately
trusted external orchestration or audit history. This precision is intentional and
does not justify a core run or event artifact.

Return to architecture if implementation requires a new result status, evidence
payload retention, a new evidence identity, a changed plan/operation/member identity,
query-time evidence replay, synthetic missing/refused results, a core history or
attempt service, private backend/error-state retention, weakened exact pair
validation, cross-result equivalence, or broader assurance semantics.
