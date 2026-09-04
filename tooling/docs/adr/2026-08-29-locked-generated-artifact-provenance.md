# ADR: Bind locked generated artifacts to release composition

- **Date:** 2026-08-29
- **Status:** Accepted
- **Issue:** `packetlss-labs/compliance-tooling#15`

Compatibility note (2026-09-03): this ADR records the historical first-alpha
decision. Issue #59 removed its unfrozen Git-provenance v2 formats from current
tooling after the content-addressed v3 successor was established. Historical
reproduction uses the corresponding historical tooling revision; no historical
asset or record is rewritten.

Product-boundary note (2026-09-04): issue #67 also removed the v1 and v3
configuration artifact families and all in-core generation. Configuration
statements below are historical. The current interoperability boundary is the
assessment plan consumed by separately implemented external programs.

## Context

The standalone tooling package, deterministic shared-policy bundle, and
`compliance.lock.yaml` contracts now provide independent identities for tooling
bytes, policy bytes, materialized policy sources, and one tested downstream
release composition.

Existing generated assessment and configuration artifacts identify effective
policy, inventory, assignments, waivers, and upstream plans, but their v1
schemas do not identify the released tooling and release-lock composition that
generated them. The v1 schemas are closed contracts and cannot be widened
without redefining an existing schema identifier.

## Decision

Locked `project-config/v1alpha2` projects use new v2 generated-artifact schema
identifiers for assessment plans/results and configuration plans/render results/
explanations. Current `project-config/v1alpha1` development/workspace generation
continues to use v1.

Every locked v2 artifact records:

- generator distribution;
- generator semantic version;
- generator source Git SHA from installed release metadata; and
- canonical `release_lock_digest`.

The full lock is not copied into artifacts. Existing policy-source and policy
revision fields remain independently authoritative for the materialized policy
content selected by planning.

For content-addressed plans, generator and lock provenance participates in the
artifact content ID. A composition-only difference therefore creates a distinct
immutable artifact ID but remains context/provenance rather than an effective
policy change in policy-diff semantics.

The v2 validation model does not alter v1 schemas. A v2 document is projected
back to the corresponding v1 shape by removing the two provenance concepts and
substituting the v1 schema identifier, then validated against the unchanged
closed v1 contract. The original document is separately validated against its
v2 provenance overlay and, for content-addressed plans, its v2 ID is verified.

The existing v1 planner, evaluator, compiler, renderer, and explanation logic
remain the semantic engines. The release-aware locked CLI boundary wraps those
engines, validates the current lock before generation/transformation, and
propagates the stored provenance and persisted upstream v2 IDs through the
artifact chain. Rendering uses the stored configuration-plan identity and does
not create an execution/apply path.

## Consequences

- Historical and current workspace v1 artifacts remain readable without schema
  widening or project migration.
- A locked plan cannot be evaluated or compiled under a different current
  release-lock composition.
- Development/editable tooling with no embedded release source SHA cannot
  produce provenance-complete locked artifacts.
- Configuration render/explanation provenance comes from the stored plan chain;
  it is not silently replaced by a newly resolved composition.
- Rendered files that embed a configuration-plan ID use the persisted v2 ID,
  and render-result artifact digests cover those final bytes.
- Runtime artifact generation and validation still require no Git metadata,
  submodule operations, mutable refs, or GitHub access after immutable inputs
  are materialized.

## Alternatives rejected

### Widen the existing v1 schemas

Rejected because the schemas are closed contracts and changing them in place
would silently alter the meaning of existing identifiers.

### Embed the full release lock in every artifact

Rejected because it duplicates the checked-in composition record, increases
artifact churn, and conflates a compact reference with the authoritative lock.

### Record only tooling version or only policy revision

Rejected because neither alone identifies the released generator composition.
Semantic version does not identify source bytes, while policy revision does not
identify the tooling release that performed the transform.

### Recompute provenance from Git at runtime

Rejected because installed downstream runtime must not depend on `.git`, Git
commands, submodules, mutable branch/tag resolution, or GitHub access.

## Detailed contract

See [`../artifact-provenance.md`](../artifact-provenance.md).
