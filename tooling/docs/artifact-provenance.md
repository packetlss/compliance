# Locked Generated-Artifact Provenance


`project-config/v1alpha3` produces assessment plan/results v4 in unlocked,
direct-expected and composition-locked execution. The predecessor v1/v3 workflows
below remain available pending consumer migration (#34–#36) and retirement (#33).

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
apply existing freshness eligibility. Schema-invalid matching evidence produces
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

## Content-addressed locked artifacts

Content-addressed `release-lock/v1alpha2` projects use these v3 artifact schemas:

```text
compliance.example/assessment-plan/v3
compliance.example/assessment-results/v3
```

Their generator provenance is content-addressed:

```json
{
  "generator": {
    "distribution": "compliance-tooling",
    "version": "<installed semantic version>",
    "source_digest": "sha256:<canonical tooling source>",
    "source_digest_algorithm": "compliance.example/tooling-source-tree-digest/v1alpha1",
    "artifact_sha256": "sha256:<exact released wheel bytes>"
  },
  "release_lock_digest": "sha256:<canonical composition>"
}
```

Git revision is deliberately absent. The installed tooling verifies its embedded
source digest against the v1alpha2 lock; the wheel SHA comes from that validated
lock because an installed Python environment cannot reconstruct the original
wheel archive bytes after installation. Release/acquisition validation is
responsible for verifying those wheel bytes before installation.

Only `assessment-results/v3` adds execution-specific evaluator and evidence
provenance:

```json
{
  "evaluator": {
    "name": "opa",
    "version": "<actual OPA semantic version>",
    "executableSha256": "sha256:<exact executable bytes>"
  },
  "evidence": {
    "documentDigestAlgorithm": "compliance.example/evidence-document-digest/v1alpha1",
    "setDigestAlgorithm": "compliance.example/evidence-set-digest/v1alpha1",
    "setDigest": "sha256:<subject evidence set>",
    "documents": [
      {"id": "<evidence id>", "digest": "sha256:<complete evidence document>"}
    ]
  }
}
```

The selected OPA executable is resolved once; the same resolved executable is
hashed/versioned and used for `opa eval`. Its filesystem path is not canonical.
`testedOpaVersion` remains release compatibility metadata, not proof of the
executable that produced an assessment.

Evidence IDs alone are not sufficient provenance. Before a v3 assessment, the
runtime copies the evidence JSON files into an isolated snapshot, computes
complete-document digests for the assessed subject, and evaluates against that
same snapshot. Thus collection metadata, subject binding, timestamps, payload,
integrity fields, and any other JSON fields actually presented to runtime are
bound to the result without making local evidence paths semantic.

The v3 assessment-plan ID continues to hash the full persisted plan excluding
only `id`; therefore generator and release-lock provenance participate in plan
identity.

Together with the existing plan inventory/assignment/policy revisions,
`waiver_revision`, `evaluated_at`, evaluator identity, and evidence snapshot,
an assessment result can be walked back through the runtime inputs that actually
produced it.

The governing decision and tooling source-digest boundary are recorded in
[`docs/adr/2026-08-30-content-addressed-provenance-vnext.md`](adr/2026-08-30-content-addressed-provenance-vnext.md).

### Local generic policy-source conformance

Content-addressed compatibility between tooling and policy sources is treated as
an executable contract, not as a schema-shape assumption. The current procedure
is implemented by
[`scripts/validate-policy-release-compatibility.sh`](../scripts/validate-policy-release-compatibility.sh).

The validation builds and installs the current tooling wheel, then uses a
tooling-owned minimal synthetic source with an arbitrary distribution name. It
constructs a generic `policy-source-release-manifest/v1` descriptor and
normalized `policy-source-archive/v1` representation entirely in a temporary
directory. No producer repository, hosted asset, provider credential, or
authoritative policy content is involved.

The gate performs the following checks in order:

1. build the current wheel with its canonical source digest and install it in a
   fresh environment;
2. construct the minimal generic descriptor, archive, and `SHA256SUMS`, then
   verify every exact representation byte;
3. read the manifest through the installed `tools.policy_source_release`,
   validate archive metadata, ordering, paths, and exact-byte SHA-256, and
   materialize its `policy/` content tree;
4. require the descriptor and materialized tree to use and reproduce
   `compliance.example/policy-source-tree-digest/v1alpha1` exactly;
5. project that source into an active `compliance.example/release-lock/v1alpha2`
   beside the installed tooling identity;
6. validate the lock against the materialized policy tree and installed wheel;
7. disable Git, provider/download commands, and network connections throughout
   the installed-runtime proof; and
8. assert that Git tag/commit, policy archive SHA, repository/provider location,
    representation metadata, and download/acquisition metadata are absent from
    the canonical semantic lock document.

The policy archive SHA and policy content digest intentionally have different
roles. The archive SHA verifies exact transport bytes; the policy content digest
identifies the semantic/runtime tree after materialization. For tooling, the
source-tree digest identifies canonical source content while the wheel SHA
identifies the exact distribution bytes that are installed. These identities are
kept separate rather than collapsed into a single provenance value.

A passing gate proves the current provider-neutral producer/consumer contract
without conflating hosted transport availability with semantic compatibility.
The producer-specific pre-freeze manifest formats remain in immutable history
but are unsupported by current tooling; reproduction uses the corresponding
historical tooling and release state.

This proof runs in `.github/workflows/tooling-package-validation.yml` in the
designated package-validation lane before a tooling release-contract change can
merge. The script and package workflow gate are the executable specification.
Individual workflow run IDs are historical evidence, not part of the
compatibility contract. Hosted publication is paused during repository
consolidation; removing its provider-specific adapter does not remove or weaken
this local proof.

## Current locked-artifact contract

This contract binds generated assessment artifacts to the exact
released tooling and release-lock composition that produced them. It applies to
projects using `compliance.example/project-config/v1alpha2` and the adjacent
`compliance.example/release-lock/v1alpha2` contract.

Current development/workspace projects using `project-config/v1alpha1` continue
to use the existing v1 generated-artifact schemas. This change does not widen or
redefine any existing v1 schema identifier.

### Provenance-bearing artifact revisions

Locked projects persist the v3 revisions listed above. Each artifact adds
content-addressed generator and composition provenance:

```json
{
  "generator": {
    "distribution": "compliance-tooling",
    "version": "<installed semantic version>",
    "source_digest": "sha256:<canonical tooling source>",
    "source_digest_algorithm": "compliance.example/tooling-source-tree-digest/v1alpha1",
    "artifact_sha256": "sha256:<exact released wheel bytes>"
  },
  "release_lock_digest": "sha256:<64-hex>"
}
```

The generator identity comes from installed package metadata and the validated
lock. Runtime Git inspection is not a fallback. Development/editable tooling
with an unrecorded source digest cannot produce provenance-complete v3 locked
artifacts.

`compliance-tooling` is the accepted distribution identity. The earlier
`opa-compliance-prototype` name was temporary and is not a valid current
generator identity.

`release_lock_digest` is the canonical path-independent digest of the checked-in
`compliance.lock.yaml`. It identifies the exact tooling + policy release
composition. It is not a download URL, local materialization path, policy-source
digest, or replacement for the full lock file.

### Validation model

The v1 schemas are closed contracts. V3 validators therefore use two
independent checks rather than modifying them:

1. remove locked-provenance fields, substitute the corresponding v1 schema
   identifier, and validate against the unchanged closed v1 contract;
2. validate the original locked document against its v3 provenance
   overlay.

For content-addressed plans, the locked `id` is recomputed over the complete
persisted document excluding only `id` itself. Consequently generator and lock
provenance participate in immutable artifact identity.

Arbitrary additional top-level fields remain rejected by the projected closed v1
contract.

### Assessment chain

A locked assessment plan records the current validated generator and lock before
it is persisted. Existing `policy_revision` and per-source `policy_sources`
continue to describe materialized policy bytes selected by the planner. Those
policy identities are not replaced by the release-lock digest.

Before a locked plan is evaluated, its stored generator and lock must match the
currently validated locked project. A mismatch is a refusal, not a warning.
Assessment results record the same composition identity and reference the stored
locked `plan_id`.

Waiver behavior is unchanged. Waivers alter reporting state, not desired policy
or generator provenance.

### External adapter handoff

The assessment plan is the complete core handoff. External programs may consume
its stable control IDs, fingerprints, resolved parameters, lineage, deviations,
subject and plan identity, and policy-source content digests. They own their
output provenance and must reference the source assessment plan when recording
it. External output is neither proof of execution nor compliance evidence.

### Policy comparison

`policy diff` separates effective-policy change from plan context. Generator or
release-lock-only churn changes the content-addressed plan ID, so it is visible
as context/provenance change. It does not create fabricated scope, requirement,
or control changes when effective policy is otherwise identical.

The full release lock remains the authoritative composition record. Policy diff
artifacts do not embed another copy of it.

### Runtime independence

After the wheel, lock, project configuration, and materialized inputs exist,
locked artifact generation/validation requires no `.git`, Git commands,
submodules, mutable branch/tag resolution, or GitHub access. Installed-wheel
gates shadow `git` with a failing executable while exercising the locked runtime.

### Deferred

This contract does not add artifact acquisition/download behavior, registry
publication, signing/transparency, automatic compatibility solving, starter
workspace generation, external inventory adapters, assurance export, or firewall
work.

### Historical reproduction

The Git-provenance v2 assessment artifacts, every v1/v2/v3 configuration
artifact family, and the v1alpha1 release lock are historical pre-freeze
formats. Current tooling does not construct, load, validate, or execute them.
Historical reproduction uses
the corresponding historical tooling release or commit and its immutable
assets; current `main` is not a universal historical reader. Removing current
reader code does not rewrite or freeze any historical or surviving contract.

The historical identifiers are `compliance.example/release-lock/v1alpha1`,
`compliance.example/assessment-plan/v2`,
`compliance.example/assessment-results/v2`,
`compliance.example/configuration-plan/v1`,
`compliance.example/configuration-plan/v2`,
`compliance.example/configuration-plan/v3`,
`compliance.example/configuration-render-result/v1`,
`compliance.example/configuration-render-result/v2`, and
`compliance.example/configuration-render-result/v3`,
`compliance.example/configuration-explanation/v1`,
`compliance.example/configuration-explanation/v2`, and
`compliance.example/configuration-explanation/v3`.
