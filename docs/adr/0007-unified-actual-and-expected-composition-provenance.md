# ADR 0007: Separate actual composition provenance from expected enforcement

- **Status:** Accepted
- **Original date:** 2026-09-04
- **Destination authority transfer:** 2026-09-04
- **Historical source:** `packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`, `docs/adr/0007-unified-actual-and-expected-composition-provenance.md`

This is the destination-owned normative restatement of accepted workspace ADR 0007. It preserves the accepted contract and updates only ownership/topology references.

[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) clarifies the status/refusal boundary. Its safely attributable schema-invalid required evidence and evidence selection ambiguity → `unknown` corrections are the only accepted exceptions to this ADR’s preservation of current semantic meaning, implemented by #32 after #31; the superseded tooling → `error` and traversal-order selection rules are not preserved, and historical results are not reinterpreted.

## Context

Pre-freeze development currently has unlocked project-config/assessment v1 and locked project-config/release-lock/assessment v3 paths. Provenance completeness must not depend on whether a composition was predeclared. ADR 0005 separates **actual provenance**—what really produced an artifact—from optional **expected enforcement**—what a caller required before execution. ADR 0006 removes configuration-generation artifacts, leaving assessment plans/results as the core generated artifact line and the resolved plan as the external-adapter handoff.

There are no external compatibility consumers and none of the successor identifiers in this ADR are frozen by this decision.

## Decision

### One successor line

Introduce the current development contracts:

```text
compliance.example/project-config/v1alpha3
compliance.example/composition-lock/v1alpha1
compliance.example/assessment-provenance/v1alpha1
compliance.example/assessment-plan/v4
compliance.example/assessment-results/v4
```

and provisional identity algorithms:

```text
compliance.example/composition-digest/v1alpha1
compliance.example/composition-lock-digest/v1alpha1
compliance.example/assessment-plan-digest/v1alpha1
compliance.example/assessment-results-digest/v1alpha1
```

Existing provisional tooling-source, policy-source, evidence-document, and evidence-set digest algorithms remain unchanged. No algorithm is promoted to `/v1` here.

After consumer migration, plan/results v4 are the only current generated assessment artifact line for both unlocked and locked execution. They preserve current semantic assessment meaning while adding one provenance envelope.

### Project configuration v1alpha3

`project-config/v1alpha3` owns materialization locations and optional enforcement selection, not canonical runtime identity.

It requires:

- a stable unique name and materialized path for every policy source;
- project paths for inventory, assignments, evidence, plans, results, and waivers;
- no legacy `paths.policies` fallback;
- no authored `paths.resourceSchema`; inventory/assignment schemas come from executing tooling; and
- no source-order precedence.

A source may declare direct `expectedContent`. Tooling calculates the actual source digest and requires equality before planning/evaluation. This is a partial source-local guard, not a claim that the whole composition is locked.

The configuration may select a complete expected composition only through `expectedComposition.path`. The accepted v1alpha3 value is the adjacent filename `compliance.lock.yaml`; it may not be absolute or traverse a parent. File location is nonsemantic.

Direct source expectations and a composition lock may coexist only when they agree exactly. The lock must name exactly the configured source-name set. A disagreement is a configuration error; neither expectation has precedence.

### Actual tooling identity

Every planning and evaluation run resolves actual tooling identity with three layers:

1. canonical tooling source identity;
2. execution representation (`source` or `installed-wheel`); and
3. descriptive metadata such as observed distribution/version.

For source/editable execution, tooling calculates the canonical source-tree digest on every run and records `execution.kind=source`. There is no wheel identity. No placeholder, lock value, Git SHA, or invented digest may fill that absence.

For installed-wheel execution, actual provenance includes the exact wheel SHA-256 only when acquisition/installation supplied a locally verifiable receipt for those wheel bytes, bound to the installed distribution, and installed files are revalidated through wheel `RECORD` data. A lock value alone is expected identity and cannot be relabeled as actual. If an installed-wheel run lacks valid receipt/provenance, v4 artifact generation fails rather than falling back to Git or expected values.

Distribution/version, repository coordinates, tags, URLs, and invocation details are descriptive/acquisition metadata, not canonical tooling composition identity.

### Actual policy-source identity

Before planning and again before evaluation, tooling calculates every configured policy source's `policy-source-tree-digest/v1alpha1` identity. The actual set is represented as source-name/content pairs sorted by source name.

The source name is semantic because it disambiguates independently composed sources. Materialized path, repository, Git revision, release coordinate, provider, archive representation, and download location are not canonical composition identity.

Source/file order never grants precedence. Identical-only coalescing remains permitted only for exact-identical same-identity definitions; divergence remains a hard failure.

### Actual composition and stage boundaries

Actual composition is exactly actual tooling identity plus the sorted actual policy-source identities. `composition-digest/v1alpha1` is SHA-256 over RFC 8785/JCS bytes of that canonical projection. Tooling/policy descriptive metadata, paths, acquisition data, and expected enforcement are excluded.

A plan records `planningComposition`, the actual composition that resolved its subject/policy/controls. A result copies the validated plan's planning composition and records a newly calculated `evaluationComposition`.

Even in unlocked mode, evaluation policy-source names, algorithms, and digests must exactly equal the persisted plan's policy-source set. Changed policy content requires regenerating the plan. Evaluation may use a different provenance-complete tooling build that supports the contract; the result records the actual evaluation tooling identity.

Locked evaluation additionally requires the relevant actual compositions to equal the selected expected composition.

### Composition lock v1alpha1

`composition-lock/v1alpha1` is an **expected identity set**. It is not a record of what executed and is not an acquisition manifest.

It contains expected tooling source/execution identity plus a name-keyed expected policy-source content set. A source-development lock uses `execution.kind=source`; an installed-release lock may require exact wheel bytes.

`composition-lock-digest/v1alpha1` is SHA-256 over RFC 8785/JCS bytes of the normalized schema+expected projection. Metadata and YAML presentation are excluded.

Locked enforcement requires exact equality between actual composition and normalized expected composition before domain execution. Missing/additional sources, algorithm changes, digest changes, source-vs-wheel representation changes, or wheel digest changes fail closed.

### Assessment provenance envelope

Plan/results v4 record actual planning composition and the enforcement actually performed. Direct expected-source enforcement and complete lock enforcement are recorded separately. An expected identity is never labeled as actual.

Results additionally record:

- actual `evaluationComposition` and evaluation enforcement;
- exact evaluator identity, including executable SHA-256; and
- a snapshotted subject-scoped evidence set with document and set digests.

The evaluator executable is resolved/hashed once and then used for evaluation. Evidence is snapshotted before evaluation; the same snapshot is digested and consumed. Filesystem paths are not provenance identity.

Future typed manual/procedural assurance evidence defined by destination #37 uses the same actual evidence provenance when it becomes an evaluator input; this ADR does not decide which assurance documents qualify or how objective states roll up.

### Plan and results identity

Assessment plan/results v4 retain the semantic payload needed for technical assessment, requirement/realization lineage, waivers, policy diff, explanation, and external-adapter handoff. Their identity includes the applicable semantic payload plus actual provenance under the contract-specific normalized/JCS projection.

Enforcement metadata and descriptive/acquisition/location metadata are validated and persisted where useful but excluded from semantic artifact identity. Two runs with identical actual semantic/runtime inputs must not get different semantic identities merely because one was pre-locked and the other was not.

Waivers remain distinct from desired state and evidence. Result identity binds the waiver revision/application actually used where applicable.

### No configuration-artifact successor

There is no ADR 0007 successor for removed configuration plans, render results, configuration explanations, backend renderers, or a second adapter-input artifact. The assessment plan remains the external-adapter handoff.

## Migration and compatibility

Current `project-config/v1alpha1`, `project-config/v1alpha2`, `release-lock/v1alpha2`, assessment v1, and assessment v3 are unfrozen migration inputs. Historical Git/releases/artifacts remain immutable but current tooling need not be a universal reader after bounded consumer cutover.

Destination implementation sequencing is owned by:

- #31 — actual composition, project-config v1alpha3, composition lock;
- #32 — provenance-bearing assessment plan/results v4;
- #34 — ordinary project consumer migration;
- #35 — IAM/private-source consumer migration;
- #36 — canonical scenario consumer migration; and
- #33 — old-reader retirement after all consumers are migrated.

## Invariants retained

This ADR does not change JCS/domain normalization rules, policy-source conflict semantics, pass/fail/unknown meaning, waiver semantics, requirement/realization semantics, evaluator/evidence identity, private-source boundaries, release coordinates, or firewall/network-policy architecture.
