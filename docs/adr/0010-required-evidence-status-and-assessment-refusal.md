# ADR 0010: Required evidence, attributable errors, and assessment refusal

- **Status:** Accepted and implemented
- **Date:** 2026-09-05
- **Promotion contracts:** [#61](https://github.com/packetlss/compliance/issues/61) (invalid evidence), [#62](https://github.com/packetlss/compliance/issues/62) (evidence selection ambiguity)
- **Runtime implementation:** [#32](https://github.com/packetlss/compliance/issues/32), after [#31](https://github.com/packetlss/compliance/issues/31)
- **Required-only evidence-core simplification:** [#84](https://github.com/packetlss/compliance/issues/84)

## Context and authority

[ADR 0006](0006-regulatory-assurance-and-external-adapter-boundary.md) requires
missing, stale, invalid, or inconclusive required evidence to produce `unknown`.
The tooling [architecture decision log](../../tooling/docs/architecture.md#11-decision-log)
recorded a 2026-08-29 rule making matching schema-invalid evidence an attributable
`error`, deliberately distinguishing it from missing evidence. That rule is
implemented in the predecessor evaluator. [ADR 0007](0007-unified-actual-and-expected-composition-provenance.md)
then required preservation of current semantic meaning during provenance migration.
Those statements left conflicting authority for invalid required evidence.

This ADR chooses **alternative A**: promote one common system-level evidence
validity/status/refusal boundary and explicitly reconcile #32. It clarifies
ADRs 0006 and 0007 and owns the normative definitions and evidence-condition
matrix below. It supersedes the tooling decision's schema-invalid-evidence
→ `error` classification, retaining the historical decision and rationale.
Preserving that classification or deferring this common boundary to #37 would
leave the accepted invalid-evidence constraint unresolved.

#62 extends this ADR with evidence selection ambiguity: deterministic ordering
does not establish legitimate authority among distinct equally latest eligible
documents. The predecessor traversal-order selection behavior is superseded as
normative authority. Complete-document differences do not by themselves imply
that observations contradict each other.

The #32 runtime implements these corrections. The project remains pre-freeze
without external compatibility consumers; no
historical result, release, or artifact is reinterpreted or rewritten.

[ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md) owns interpretation of historical results across wall-clock time and the v4 factual temporal-provenance clarification in #32. This ADR retains assessment-time validity/freshness eligibility, schema-invalid evidence, selection ambiguity, attributable `error`, and assessment-wide refusal unchanged.

Current routing clarification: [ADR 0016](0016-closed-world-policy-assessment.md#invalid-inputs-na-and-outcome-boundaries)
supersedes ADRs 0013–0015 with closed-world company policy assessment. Invalid
required policy/dependency resolution cannot become a partial valid plan or evidence
`unknown`. After valid dependency resolution, this ADR retains required-evidence
`unknown`, attributable execution `error` and shared-integrity refusal. Technical
evidence selection and roll-up, and ADR 0012's unresolved-policy boundary, are
unchanged. No separate external claim/applicability-authority subsystem is required.

## Decision

### Required-only dependency and evidence-envelope core

Every declared control evidence dependency is required by definition. The
dependency contract and its frozen/effective representation therefore have no
`required` discriminator, and optional evidence is not a supported policy or
runtime concept. This removes only that evidence-dependency axis; unrelated
requirement-baseline, parameter, applicability, and JSON Schema uses of
`required` retain their existing meanings.

The normative typed evidence envelope requires document identity, subject and
type routing, collection time, collector metadata, and payload. It has no
collector-supplied `integrity.digest`: assessment did not independently verify
that payload checksum, so it is not an integrity or trust guarantee. Do not
replace it with another checksum, signature abstraction, or second evidence
identity. An opaque extension named `integrity` remains ordinary complete-
document content where a type schema permits extensions and gains no product
semantics.

The existing complete-document `evidence-document-digest/v1alpha1` and sorted
ID/digest-set `evidence-set-digest/v1alpha1` algorithms remain the sole evidence
identity/provenance mechanisms and are unchanged by this simplification.

### Definitions and shared prerequisites

| Outcome | Normative meaning |
| --- | --- |
| `unknown` | Criterion truth cannot be established from admissible evidence, but the lack of determination can be safely attributed and explained. |
| `error` | Criterion execution or decision interpretation failed, while trusted orchestration can still construct an attributable valid result. |
| Assessment-wide refusal | Assessment identity, routing, provenance, shared prerequisites, or result-envelope integrity cannot be established strongly enough to publish a trustworthy assessment result. |

Refusal is an assessment completion boundary, not a new child status, result
axis, or artifact family. Before producing per-control results, establish a
trustworthy plan, schema catalog, composition/provenance, evaluator identity,
evidence snapshot/provenance, and explicit evidence routing. A failure of these
shared prerequisites cannot be represented as child `unknown` or `error` when
the result envelope itself cannot be trusted. Later shared integrity failures
likewise refuse publication, even if some child evaluations have completed.

### Normative evidence-condition matrix

The `unknown` and `error` rows presuppose trustworthy shared prerequisites and
safely attributable affected controls. Refusal takes precedence over publishing
an envelope containing otherwise attributable children.

| Condition | Required outcome |
| --- | --- |
| Required evidence absent from a valid snapshot | `unknown` |
| All matching candidates schema-valid but stale | Existing stale `unknown` |
| Unique latest valid/fresh eligible candidate | Select that document |
| Multiple canonical-identical latest eligible candidates | Coalesce for selection only; preserve complete snapshot provenance |
| Multiple distinct equally latest valid/fresh eligible candidates | Evidence selection ambiguity: dependent controls `unknown`; select none and do not invoke their OPA criteria |
| Same payload but different IDs, collector metadata, or extensions at the latest eligible instant | Distinct complete documents: dependent controls `unknown`; no OPA |
| Same ID but different complete-document digests at the latest eligible instant | Distinct documents: dependent controls `unknown`; no OPA |
| Older tied candidates plus a unique newer valid/fresh eligible candidate | Select the newer document |
| Matching evidence has valid routing/identity but fails applicable schema validation | `unknown`; never supply invalid evidence to OPA |
| Valid and schema-invalid matching candidates coexist, regardless of timestamps | Existing invalid-evidence `unknown` for controls requiring that type; no OPA; validation precedes tie selection |
| One required evidence type is invalid among several required types | Affected controls are `unknown` |
| Valid, fresh evidence is insufficient or inconclusive | `unknown` |
| Identified OPA execution failure | Attributable `error` if trusted orchestration can construct a valid result |
| Undefined, non-JSON, non-object, or otherwise unusable criterion decision | Attributable `error` under the same condition |
| Criterion-local exception with trustworthy affected scope and synthesizable valid output | Attributable `error` |
| Unreadable/invalid JSON whose relevance cannot safely be established | Refusal |
| Non-object evidence document | Refusal |
| Missing, malformed, or ambiguous subject routing | Refusal |
| Current-subject evidence without interpretable type | Refusal |
| Required stable evidence identity absent when provenance requires it | Refusal |
| Invalid or unresolvable required schema or schema catalog | Refusal |
| Invalid or non-assessable plan | Refusal |
| Composition/provenance mismatch | Refusal |
| Evaluator identity unavailable or unverifiable | Refusal |
| Evidence snapshot cannot be obtained, digested, represented, or verified | Refusal |
| Internal failure leaves affected-control scope or valid output untrustworthy | Refusal |
| Shared result/provenance envelope validation failure | Refusal |

A validator implementation failure is not proof that evidence is schema-invalid.
Apply the execution-failure boundary: only a safely scoped failure with trusted
orchestration and a valid attributable result may become `error`; otherwise
refuse. Failure to establish the shared schema catalog is always refusal.

Do not infer subject or type routing from filenames or directory placement.
A valid empty evidence snapshot is distinct from an inaccessible or unverifiable
evidence source: the former can establish absence; the latter requires refusal.

### Validate every matching candidate before selection

All documents matching the explicit subject and a required evidence type must
be validated against the applicable schema before freshness or candidate
selection. If any matching candidate is invalid, every control requiring that
type is `unknown`; invalid matching evidence never reaches OPA. This includes
invalid older/stale candidates alongside valid newer/fresh candidates.

Do not select around invalid evidence using filenames, traversal order, source
order, collection time alone, or a “newest valid wins” assumption. A rule allowing
supersession requires a separately accepted authority/selection contract.
Unrelated, explicitly routed subjects are outside a control's matching scope;
unused types remain subject to the snapshot/provenance obligations below.

### Evidence selection ambiguity and sequencing

Selection is scoped to the subject, required evidence type, and applicable
eligibility/freshness requirements. Controls depending on that type under those
requirements share the selection outcome; controls with independent successful
required-evidence selections remain assessable. Existing freshness eligibility
semantics and the assessment/evaluation instant are unchanged.

The normative order is:

1. Establish the shared prerequisites above.
2. Route evidence by explicit subject and type.
3. Validate every matching candidate against the applicable schema. Any invalid
   matching candidate makes dependent controls `unknown`, regardless of timestamps;
   do not continue to selection for that matching set.
4. Determine eligibility/freshness using the existing requirements.
5. Identify the greatest eligible collection instant. Absence or all-stale evidence
   retains its existing `unknown` outcome.
6. Compare candidates tied at that instant as complete canonical JSON documents
   under the existing evidence-document identity contract. Coalesce only
   canonical-identical duplicates, for selection only.
7. Select the unique remaining document. If more than one distinct document
   remains, select none and synthesize attributable, provenance-bound `unknown`
   for every dependent control: this is **evidence selection ambiguity**.
8. Invoke OPA only for controls whose required evidence selections all succeeded.

For ambiguity, do not fall back to an older candidate, combine/merge payloads,
or choose by filename, traversal order, evidence ID, digest, collector identity,
source order, or other undeclared precedence. Evidence ID/digest may order
representation and diagnostics, never establish selection authority. Complete
canonical-document comparison includes IDs, collector metadata, extension
fields, and the rest of the document, not just payload or collector identity.

This per-control `unknown` is distinct from assessment-wide refusal. Unsafe
routing, attribution, snapshot identity, shared prerequisites, or result-envelope
integrity still require assessment-wide refusal under the matrix above.

### Preserve evidence provenance

Schema-invalid content can still be content-addressable and attributable.
Preserve the existing `evidence-document-digest/v1alpha1` and
`evidence-set-digest/v1alpha1` algorithms, including complete-document canonical
JSON digests and the existing sorted ID/digest set projection described in the
[tooling provenance contract](../../tooling/docs/artifact-provenance.md).
Do not add or change an evidence identity algorithm or infer identity from paths.
Collector identity semantics are unchanged. The envelope simplification above
removes only the non-verifying collector-supplied `integrity.digest` field.

When a rejected document remains validly identified and routed, retain it in the
subject evidence snapshot. Bind its validation diagnostics to its evidence ID
and digest. Digest the same snapshot actually considered by evaluation, including
rejected, nonselected, and ambiguous documents, rather than a filtered set of
successfully selected inputs. Selection-only duplicate coalescing must not reduce
the complete snapshotted provenance or change existing set normalization.
Preserve existing provenance obligations for current-subject unused evidence
types, even though those types are outside an individual control's validation
scope. If the existing contract cannot represent or verify that snapshot, refuse;
never silently omit unrepresentable evidence to manufacture provenance.

### Structured, deterministic diagnostics

Retain `observed.evidence_validation_errors`. The runtime provides machine-actionable
attribution equivalent to:

- stable diagnostic type/code;
- evidence type, evidence ID, and evidence digest;
- unambiguous schema reference tied to the applicable schema in the trusted composition;
- instance JSON Pointer;
- schema pointer/keyword where available;
- human-readable validation message; and
- optional source/schema location metadata.

Order diagnostics deterministically using semantic references and pointers
(evidence type, ID/digest, schema reference, instance/schema pointers and code),
not filesystem traversal order. Source/schema locations are explanatory metadata;
they must not become routing authority or canonical semantic identity. Preserve
ADR 0007's exclusion of location metadata from semantic artifact identity.

The result reason must be location-independent, for example:

```text
Required evidence was rejected as invalid; criterion not determined.
```

Validation failure must remain distinguishable from absence through these
structured observations and explanations, without requiring a different status.

For evidence selection ambiguity, provide structured diagnostics containing at
least:

- stable ambiguity code `evidence_selection_ambiguity`;
- subject and required evidence type;
- applicable schema reference in the trusted composition;
- applicable freshness requirement;
- assessment/evaluation instant;
- tied selection (collection) instant; and
- tied candidate evidence ID + complete-document digest pairs.

Order ambiguity diagnostics by semantic references (subject, type, schema,
requirements, instants, code), with candidate pairs ordered by ID and digest.
Optional filesystem locations are nonsemantic diagnostics only. Expose the
ambiguity and candidate references in both JSON and human explanations with a
location-independent reason, for example “Required evidence selection is
ambiguous; criterion not determined.” Do not describe candidates as contradictory
merely because complete documents differ. Diagnostic ordering must not become
selection precedence.

### Logical roll-up and waivers

Preserve the existing logical required-child precedence:

```text
any fail                 -> fail
else any error           -> error
else any unknown/missing -> unknown
else any waived          -> waived
else                     -> pass
```

Reporting/presentation priority is not logical roll-up precedence. Only an
underlying `fail` may become `waived`. Invalid-evidence and selection-ambiguity
`unknown` and execution `error` remain unwaivable. This does not redesign existing N/A handling,
applicability, or broader assurance semantics.

### CLI and operator semantics

The eventual implementation must make invalid-evidence and selection-ambiguity `unknown`
operationally prominent and retain their structured diagnostics in human and JSON
explanations. Status counts move schema-invalid evidence from `error` to
`unknown`. Successful artifact creation must not be presented as a passing
assessment: persisted `unknown` or attributable `error` can represent a
completed run. Refusal or write failure is command failure and publishes no new
assessment-results envelope. Existing historical output is not a new result of
a refused run. This promotion introduces no status or filter grammar and
implements none of these operator changes.

## Implementation ownership and non-goals

[#32](https://github.com/packetlss/compliance/issues/32) explicitly accepts these
schema-invalid-evidence and evidence-selection corrections as the **only
exceptions** to “preserve current semantic payload” / “unchanged domain behavior.” Its implementation must satisfy this
matrix, validation-before-selection, ambiguity detection before OPA, dependent-control
`unknown` synthesis, OPA exclusion, existing evidence identity,
deterministic provenance-bound diagnostics, logical roll-ups and fail-only
waivers, without reinterpreting historical results. #32 remains blocked on #31.

[#31](https://github.com/packetlss/compliance/issues/31) is independent and remains
unblocked by this decision. Its composition/configuration foundation and
transitional refusal before v4 generation are unchanged.

[#37](https://github.com/packetlss/compliance/issues/37) may rely on this common
evidence validity/refusal boundary. It retains assurance terminology,
manual/hybrid evidence qualification, authority for procedural evidence, N/A
determinations, mapping coverage, adoption/realization semantics, and broader
assurance result design. This ADR resolves none of those matters. ADR 0009's
vocabulary and generic independently named-source model remain unchanged.

#62's accepted decision supersedes the earlier unresolved candidate-selection
follow-up. #32 implements it alongside the schema-invalid-evidence correction;
it must not stop on an unresolved #62. It must prove filename, traversal,
materialization, and source-order independence, retaining semantic result
identity invariance under those permutations. This adds no dependency to #31.

Collector authority/precedence, explicit supersession, payload merging or
multi-observation control semantics, new freshness or current-status semantics,
and #37 assurance semantics are outside this decision and #32's correction.

## Validation and escalation

Promotion requires documentation/ADR checks, valid links and issue references,
a documentation-only diff, fresh-context exact-head semantic consistency review,
and green exact-head CI. Runtime conformance cases belong to #32, not this PR.

Return to architecture if rejected evidence cannot be bound under existing
provenance algorithms; a new result state or evidence identity algorithm is
required; mixed valid/invalid behavior needs an authority/supersession model;
current roll-ups cannot represent this decision; an external compatibility
consumer/freeze exists; or implementation materially overlaps unresolved #37
semantics. Also return to exploration if selection needs a new equivalence
algorithm, collector precedence, explicit supersession, payload merging or
multi-observation semantics, changed freshness eligibility, or a new artifact
family. No runtime, test, release, historical-artifact, identity-algorithm,
new artifact-family, adapter, or firewall change is authorized by this promotion.
