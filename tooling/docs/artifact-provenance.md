# Assessment Artifact Provenance


`project-config/v1alpha3` produces assessment plan/results v4 in unlocked,
direct-expected and composition-locked execution. All current consumers use this successor line. Historical artifacts require their historical tooling.

Status: **Current experimental artifact provenance contract; exact plan/result pair
implemented by [#90](https://github.com/packetlss/compliance/issues/90), not frozen**

## Exact-plan/result contract

The current pre-freeze contract replaces the duplicated self-contained result
with an explicit retained `{exact bound plan, assessment result}` historical pair.
The plan owns the complete resolved member intent, frozen operation relationship,
planning composition/enforcement, parameters, stable evidence dependencies,
mappings, and all other plan semantics. The result references only the exact
`plan_id` and direct `subject_id` and owns what evaluation concluded under that plan.

The minimum result retains its explicit schema/version and identity discriminator,
`plan_id`, `subject_id`, `evaluated_at`, immutable outcome, actual evaluation
composition plus evaluation enforcement, exact evaluator, complete subject evidence
snapshot descriptor/evidence-set identity, exact successful selections, technical
outcomes, compact requirement/baseline outcomes, and exact applied-waiver snapshots.
It does not copy the operation, resolved policy, planning composition, summary
counts, or whole-catalog waiver revision. Evaluation enforcement remains validated
non-identity-bearing provenance; changing only enforcement cannot change result
identity when actual semantic composition is identical.

Each successful selection is equivalent to:

```json
{
  "instance_id": "host.setting",
  "dependency_id": "settings",
  "evidence_id": "evidence:observation",
  "evidence_digest": "sha256:<complete-document digest>",
  "collected_at": "2026-09-05T10:00:00.123456Z"
}
```

The assessed plan, not the result, supplies the dependency body and effective
`max_age`. List position, filename, source order, and traversal order are not
dependency identity. Successful selections sort by `(instance_id, dependency_id)`;
technical results sort by `instance_id`; requirement and baseline outcomes sort by
their stable references. Duplicate semantic identities fail. The complete snapshot
descriptor and successful-selection table remain separate facts.

The explicit result-domain projection commits to exact plan and subject IDs,
evaluation instant and stored outcome, evaluation-composition identity, evaluator
identity, evidence-set identity, successful selections, compact outcomes, and exact
applied-waiver facts. Contract-specific domain normalization/ordering precedes RFC
8785/JCS. Embedded descriptors remain self-validating where necessary, while the
projection references their owning domain identities and adds no meaningless
digest-of-digest wrapper.

Intrinsic validation covers result schema/version/order/identity, evaluation
composition and enforcement structure, evaluator shape, evidence snapshot identity,
successful-selection uniqueness and snapshot references, waiver snapshot integrity,
and outcome uniqueness. Publication and full historical interpretation additionally
require exact relational validation against the plan: plan/subject equality,
evaluation policy sources authorized by planning composition, exact active-control
and stable-dependency correspondence, selected documents in the complete snapshot,
valid compact roll-ups, and exact evaluation-time fail-only waiver application.
Failure refuses publication. An orphaned result may expose raw recorded facts but
cannot establish full policy interpretation, historical timeliness, requirement
meaning, or plan alignment.

Whole-catalog `waiver_revision` is deliberately absent. A waived outcome binds the
exact normalized applied snapshot, identity/digest, subject/control target,
evaluation-time applicability, and underlying `fail`. No applied waiver requires no
catalog proof; unrelated waiver content cannot perturb result identity. Historical
waived and later window qualification remain immutable/derived respectively.

Historical tooling resolves the assessed plan solely by exact `plan_id` from an
explicit plan file or bounded plan directory/set and validates the pair before
interpretation. Filename, traversal order, subject-only matching, latest, current-plan
substitution, and approximate equality are forbidden. This is ordinary artifact input
resolution, not a history store, index, run object, retention service, latest-result
database, or discovery subsystem.

## Required evidence and refusal

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
Every declared evidence dependency is required by definition; plan and result
representations contain no optionality discriminator.

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
The normative evidence envelope has no collector-supplied `integrity.digest`.
No replacement payload checksum or second evidence identity is introduced;
opaque extensions remain ordinary complete-document content.

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
