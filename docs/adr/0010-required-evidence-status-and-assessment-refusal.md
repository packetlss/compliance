# ADR 0010: Required evidence, attributable errors, and assessment refusal

- **Status:** Accepted design, not yet implemented
- **Date:** 2026-09-05
- **Promotion contract:** [#61](https://github.com/packetlss/compliance/issues/61)
- **Runtime implementation:** [#32](https://github.com/packetlss/compliance/issues/32), after [#31](https://github.com/packetlss/compliance/issues/31)

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
matrix below. It supersedes only the tooling decision's schema-invalid-evidence
→ `error` classification, retaining the historical decision and rationale.
Preserving that classification or deferring this common boundary to #37 would
leave the accepted invalid-evidence constraint unresolved.

This promotion changes architecture and implementation contracts only. Current
runtime behavior and tests are unchanged until #32 implements the correction.
The project remains pre-freeze without external compatibility consumers; no
historical result, release, or artifact is reinterpreted or rewritten.

## Decision

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
| Required evidence schema-valid but stale | `unknown` |
| Matching evidence has valid routing/identity but fails applicable schema validation | `unknown`; never supply invalid evidence to OPA |
| Valid and invalid matching candidates coexist | Controls requiring that type are `unknown` |
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

### Preserve evidence provenance

Schema-invalid content can still be content-addressable and attributable.
Preserve the existing `evidence-document-digest/v1alpha1` and
`evidence-set-digest/v1alpha1` algorithms, including complete-document canonical
JSON digests and the existing sorted ID/digest set projection described in the
[tooling provenance contract](../../tooling/docs/artifact-provenance.md).
Do not add or change an evidence identity algorithm or infer identity from paths.

When a rejected document remains validly identified and routed, retain it in the
subject evidence snapshot. Bind its validation diagnostics to its evidence ID
and digest. Digest the same snapshot actually considered by evaluation, including
rejected documents, rather than a filtered set of successfully selected inputs.
Preserve existing provenance obligations for current-subject unused evidence
types, even though those types are outside an individual control's validation
scope. If the existing contract cannot represent or verify that snapshot, refuse;
never silently omit unrepresentable evidence to manufacture provenance.

### Structured, deterministic diagnostics

Retain `observed.evidence_validation_errors`. #32 must provide machine-actionable
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
underlying `fail` may become `waived`. Invalid-evidence `unknown` and execution
`error` remain unwaivable. This does not redesign existing N/A handling,
applicability, or broader assurance semantics.

### CLI and operator semantics

The eventual implementation must make invalid-evidence `unknown` operationally
prominent and retain validation-failure diagnostics in human and JSON
explanations. Status counts move schema-invalid evidence from `error` to
`unknown`. Successful artifact creation must not be presented as a passing
assessment: persisted `unknown` or attributable `error` can represent a
completed run. Refusal or write failure is command failure and publishes no new
assessment-results envelope. Existing historical output is not a new result of
a refused run. This promotion introduces no status or filter grammar and
implements none of these operator changes.

## Implementation ownership and non-goals

[#32](https://github.com/packetlss/compliance/issues/32) explicitly accepts this
semantic correction as the **sole exception** to “preserve current semantic
payload” / “unchanged domain behavior.” Its implementation must satisfy this
matrix, validation-before-selection, OPA exclusion, existing evidence identity,
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

### Separate candidate-selection finding

The exploration found that equal collection timestamps can currently fall back
to traversal order. [#62](https://github.com/packetlss/compliance/issues/62) owns
the unresolved follow-up:

> Evidence candidate selection must not become filename/traversal-order dependent
> when equally eligible candidates can change assessment results.

This ADR chooses no tie-break or supersession policy and does not solve that
finding in #32 incidentally. The finding does not block #31.

## Validation and escalation

Promotion requires documentation/ADR checks, valid links and issue references,
a documentation-only diff, fresh-context exact-head semantic consistency review,
and green exact-head CI. Runtime conformance cases belong to #32, not this PR.

Return to architecture if rejected evidence cannot be bound under existing
provenance algorithms; a new result state or evidence identity algorithm is
required; mixed valid/invalid behavior needs an authority/supersession model;
current roll-ups cannot represent this decision; an external compatibility
consumer/freeze exists; or implementation materially overlaps unresolved #37
semantics. No runtime, test, release, historical-artifact, identity-algorithm,
new artifact-family, adapter, or firewall change is authorized by this promotion.
