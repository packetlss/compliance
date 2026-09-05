# Assessment Artifact Provenance


`project-config/v1alpha3` produces assessment plan/results v4 in unlocked,
direct-expected and composition-locked execution. All current consumers use this successor line. Historical artifacts require their historical tooling.

Status: **Current experimental artifact provenance contract; not frozen**

## V4 provenance and semantic identity

The closed v4 schemas retain the assessment payload and adapter handoff. Plans add
`digestAlgorithm`, `id`, and `provenance` with schema
`compliance.example/assessment-provenance/v1alpha1`. `planningComposition` records
actual tooling/source composition, its algorithm/digest, optional descriptive
metadata, and the direct/complete enforcement actually performed. Results copy
that validated planning record and add separately observed `evaluationComposition`,
exact `evaluator`, complete subject `evidence`, and `selectedEvidence`.

The plan and results algorithms are respectively
`compliance.example/assessment-plan-digest/v1alpha1` and
`compliance.example/assessment-results-digest/v1alpha1`. Both SHA-256 hash RFC
8785/JCS bytes after this explicit projection:

- Remove only the top-level `id`.
- For each composition stage retain its normalized `actual`,
  `compositionDigestAlgorithm`, and `compositionDigest`; exclude stage descriptive
  metadata and expected enforcement.
- In result `observed.evidence_validation_errors` and
  `observed.evidence_selection_ambiguities`, exclude optional `source` and
  `schema_source` diagnostic locations. No arbitrary OPA observed/payload keys are
  removed by name.
- Retain all other payload, including `evaluated_at`, plan reference, evaluator,
  full evidence snapshot, successful-selection facts, waiver revision/application,
  requirement/realization roll-ups, and semantic diagnostics.

Schema validation and cross-field checks precede identity acceptance. Composition
source names/content and the policy revision must agree. Evaluation re-digests
policy inputs and refuses any difference from planning, including unlocked runs;
a selected complete lock must also match the planning composition. Evaluation may
use a different provenance-complete tooling build in unlocked mode. Descriptive
metadata and enforcement remain validated despite exclusion from identity.

`id` is the complete result semantic digest; the retained `assessment_id` is the
existing run label, not a replacement for the digest. No identity algorithm is
frozen or renamed to `/v1`. Existing evidence document/set algorithms are unchanged.
The standalone provenance schema permits planning-only or complete evaluation
records; a partial evaluation record is invalid.
Schema diagnostic references use type plus source-name/relative-schema-path
locators resolved in the trusted composition, not a new schema identity algorithm.
Materialization paths are never source identity.

## Accepted v4 temporal provenance

System [ADR 0012](../../docs/adr/0012-explicit-policy-parameter-resolution.md#immutable-plan-and-provenance-obligations)
accepts successor resolved parameter, declaration/schema pin, binding/tailoring,
consumption-edge, exact destination and policy-owned freshness facts in the same
assessment plan/results boundary. [#73](https://github.com/packetlss/compliance/issues/73)
owns their schema, validation and identity/fingerprint migration; they are not
current v4 fields. That migration must preserve the historical selected-document
and exact assessed-dependency/`max_age` attribution below, without re-resolving
parameters during evaluation or rewriting historical artifacts.

The representation requirement of system
[ADR 0011](../../docs/adr/0011-historical-assessment-and-operational-evidence-timeliness.md#v4-factual-temporal-provenance-option-b)
is implemented by #32. Operational evidence timeliness derivation remains
unimplemented and requires its separate future tranche.

Each successful required-evidence selection is an entry in `provenance.selectedEvidence`:

```json
{
  "instance_id": "host.setting",
  "requirement_index": 0,
  "requirement": {"type": "host.settings/v1", "required": true, "max_age": "24h"},
  "id": "evidence:observation",
  "digest": "sha256:<complete-document digest>",
  "collected_at": "2026-09-05T10:00:00.123456Z"
}
```

The control instance and zero-based index resolve the exact evidence requirement
in the assessed `plan_id`; the copied requirement must equal that plan entry and
retains its `max_age`. Entries sort by control instance and requirement index.
The ID/digest pair resolves into `provenance.evidence.documents`; repeated IDs with
different document digests are separate references. The exact selected document's
original collection-time string is retained. Generation validates the selection
facts against both the plan and the in-memory snapshot actually evaluated. Stored
validation checks their structure, unique associations, snapshot references and
identity binding without reopening evidence paths.

These are successful required-evidence **selections**, including when a later criterion fails or
returns unknown/error. A different required type failing selection prevents OPA
for that control but does not erase successful selections of its other types.
Rejected, ambiguous, missing and stale requirements receive no selection record.
Unused and nonselected current-subject documents remain in the complete snapshot;
canonical duplicates coalesce only during selection, not in the snapshot descriptor.
OPA-reported `evidence_ids` neither supply nor override orchestration's facts.
Optional evidence keeps its predecessor selection and invalid-evidence error
behavior; the new selection-fact table and ambiguity correction concern required
evidence only. Optional evidence remains in the complete subject snapshot.

A later view can use these historical records without mutable evidence,
re-selection, ID-only joins or long-term original-byte retention. No `fresh`,
`stale`, `current`, `reassessment_due` or operational status is persisted. Neither
historical outcome nor roll-ups change with later wall-clock time.

## V4 required evidence and refusal

[ADR 0010](../../docs/adr/0010-required-evidence-status-and-assessment-refusal.md)
applies in the v4 path. Establish plan/composition/evaluator/catalog and snapshot
integrity, explicitly route subject/type, validate every matching candidate, then
apply existing freshness eligibility. Snapshot documents are normalized using the existing JCS representation before
validation, so embedded document values in human validation messages are
canonical-order-independent. Schema-invalid matching evidence produces
attributable `unknown`; no dependent OPA call occurs. Distinct documents at the
greatest eligible collection instant produce `evidence_selection_ambiguity`,
`unknown` and no dependent OPA call. Complete canonical duplicates may coalesce
for selection only. No older fallback, payload merge or ordering precedence exists.
Independent controls remain assessable; any failed required selection blocks its
control. Missing/stale required evidence is unknown, not a completed passing check.

Structured validation diagnostics bind evidence ID/digest, schema reference,
instance/schema pointers, keyword, stable code and human message. Ambiguity
records retain subject, schema/type, requirement, assessment/tied instants and
ordered candidate ID/digest pairs. Human explanations retain these diagnostics.
Invalid-evidence counts belong to unknown. Only underlying fail can be waived;
logical roll-ups preserve fail → error → unknown/missing → waived → pass.

Unverifiable prerequisites, ambiguous routing, inaccessible/unrepresentable
snapshot, validator implementation failure or invalid shared result provenance
refuse the assessment. An identified criterion execution failure or unusable
OPA decision becomes attributable error. Output encoding/validation precedes
atomic publication; refusal/write failure leaves no new result envelope and does
not present an older result as the refused attempt's output. Completing artifact
creation is distinct from assessment pass.

## Evidence snapshot identity

`evidence-document-digest/v1alpha1` hashes the complete RFC 8785/JCS document.
`evidence-set-digest/v1alpha1` hashes the sorted ID/digest entries for the complete
subject snapshot, including rejected, ambiguous, duplicate and nonselected candidates.
The same in-memory snapshot is digested and consumed. Paths are not identity.
The resolved OPA executable is hashed/versioned once and that executable evaluates
the selected evidence. Release-tested OPA metadata is not execution identity.

## Installed and locked validation

Run `scripts/dev gate package` and `scripts/dev gate locked-artifacts` on a clean,
committed candidate. These build/install exact wheel bytes with a verifiable local
receipt and exercise v4 CLI construction, persistence, loading, locked/unlocked
identity equivalence, actual-versus-expected mismatches and no-Git operation.
`composition show/validate` exposes actual composition and optional enforcement;
there is no release-lock reader or release CLI alias.

Generic policy-source release conformance remains `scripts/dev gate policy-release`.
It validates descriptors, archives and materialized content against a successor
composition lock without treating distribution/version/acquisition metadata as
composition identity. Release preparation remains independently validated.

## Historical reproduction

#33 removed project-config v1alpha1/v1alpha2, release-lock v1alpha2, and assessment
plan/results v1/v3 schemas, readers and compatibility fixtures after consumer cutover.
Historical commits, releases, wheels and artifacts remain immutable provenance and
are reproduced with their historical tooling. See the
[retirement inventory](../../docs/history/predecessor-retirement.md).
