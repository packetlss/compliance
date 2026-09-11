# ADR 0007: Separate actual composition provenance from expected enforcement

- **Status:** Accepted
- **Original date:** 2026-09-04
- **Destination authority transfer:** 2026-09-04
- **Result/plan ownership refinement:** Implemented under [#90](https://github.com/packetlss/compliance/issues/90); experimental, not frozen
- **Historical source:** `packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`, `docs/adr/0007-unified-actual-and-expected-composition-provenance.md`

This is the destination-owned normative restatement of accepted workspace ADR 0007. It preserves the accepted contract and updates only ownership/topology references.

[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) clarifies the status/refusal boundary. Its safely attributable schema-invalid required evidence and evidence selection ambiguity → `unknown` corrections are the only accepted exceptions to this ADR’s preservation of current semantic meaning, implemented by #32 after #31; the superseded tooling → `error` and traversal-order selection rules are not preserved, and historical results are not reinterpreted.

[ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md) owns interpretation across wall-clock time and requires #32 to retain validated, result-identity-bound successful-selection and temporal facts in v4. This is a representation clarification, not another assessment-time semantic exception or query-time status implementation.

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

A plan records `planningComposition`, the actual composition that resolved its
subject/policy/controls, and the planning enforcement actually performed. A result
references that exact bound plan by `plan_id`; it does not copy the planning stage.
The result records a newly calculated `evaluationComposition`, including its actual
composition, digest algorithm/digest, and the evaluation enforcement actually
performed. Planning and evaluation enforcement remain non-identity-bearing
provenance. Removing the copied planning stage does not remove evaluation enforcement
or collapse actual composition into expected enforcement.

Even in unlocked mode, evaluation policy-source names, algorithms, and digests must exactly equal the persisted plan's policy-source set. Changed policy content requires regenerating the plan. Evaluation may use a different provenance-complete tooling build that supports the contract; the result records the actual evaluation tooling identity.

Locked evaluation additionally requires the relevant actual compositions to equal the selected expected composition.

### Composition lock v1alpha1

`composition-lock/v1alpha1` is an **expected identity set**. It is not a record of what executed and is not an acquisition manifest.

It contains expected tooling source/execution identity plus a name-keyed expected policy-source content set. A source-development lock uses `execution.kind=source`; an installed-release lock may require exact wheel bytes.

`composition-lock-digest/v1alpha1` is SHA-256 over RFC 8785/JCS bytes of the normalized schema+expected projection. Metadata and YAML presentation are excluded.

Locked enforcement requires exact equality between actual composition and normalized expected composition before domain execution. Missing/additional sources, algorithm changes, digest changes, source-vs-wheel representation changes, or wheel digest changes fail closed.

### Assessment provenance envelope

Plan v4 records actual planning composition and the planning enforcement actually
performed. Direct expected-source enforcement and complete lock enforcement are
recorded separately. An expected identity is never labeled as actual.

The accepted result successor records:

- the exact bound `plan_id` and direct `subject_id`;
- actual `evaluationComposition`, its algorithm/digest, and evaluation enforcement;
- exact evaluator identity, including executable SHA-256;
- a complete snapshotted subject evidence descriptor with document and set digests;
- exact successful stable-dependency-to-document selections captured by trusted
  orchestration; and
- immutable technical, compact requirement/baseline, and exact applied-waiver
  outcome facts.

The evaluator executable is resolved/hashed once and then used for evaluation.
Evidence is snapshotted before evaluation; the same snapshot is digested and
consumed. Filesystem paths are not provenance identity. Evaluator-reported evidence
IDs do not replace orchestration-owned successful selections.

Typed manual/procedural assurance evidence promoted through #37 and implemented
under #78 uses the same actual evidence provenance when it becomes an evaluator
input; this ADR does not decide which assurance documents qualify or how objective
states roll up.

### Exact plan/result historical record and validation

The accepted historical representation is an explicit retained pair:

```text
exact valid bound plan + intrinsically valid result
    + successful relational validation
    = trustworthy historical assertion
```

The plan owns resolved policy intent, the operation relationship, planning
composition/enforcement, parameters, evidence dependencies, mappings, and other
plan semantics. The result owns what evaluation actually concluded under that exact
plan. It does not retain a complete operation, complete resolved policy, copied
planning composition, `assessment_id`, summary-count objects, or plan-owned facts
repeated in children. An orphaned result may expose raw recorded facts, but without
its exact valid plan it cannot establish validated policy interpretation, historical
timeliness, requirement meaning, or plan alignment.

Intrinsic result validation covers its schema/version, canonical order, identity,
evaluation composition and enforcement structure, evaluator identity, complete
evidence snapshot, successful-selection references, applied-waiver snapshots, and
unique outcome identities. Before publication or full historical interpretation,
mandatory relational validation additionally requires exact plan/subject equality,
evaluation source authorization by planning composition, exact active control and
stable evidence-dependency correspondence, selected documents present in the
complete snapshot, valid compact roll-ups, and exact evaluation-time waiver
applicability. Failure refuses publication.

### Plan and results identity

Assessment plan v4 retains the semantic payload needed for technical assessment,
requirement/realization lineage, policy diff, explanation, and external-adapter
handoff. The plan identity includes that resolved semantic payload plus planning
provenance under its contract-specific normalized/JCS projection.

The result domain has its own explicit semantic projection. Domain normalization
and ordering precede RFC 8785/JCS serialization. It commits to independently
meaningful result facts: exact `plan_id`, `subject_id`, `evaluated_at`, stored
historical outcome, evaluation-composition identity, evaluator identity,
evidence-set identity, exact successful-selection records, technical outcomes,
compact requirement/baseline outcomes, and exact applied-waiver application facts.
Self-validating descriptors remain where needed, but the result references their
owning domain identities instead of wrapping or reinventing their projections.

Successful selections order by `(instance_id, dependency_id)`, technical outcomes
by `instance_id`, requirement outcomes by stable requirement reference, and
requirement-baseline outcomes by stable baseline reference. Duplicate semantic
identities fail. Evidence dependency identity is stable and authored; list position,
filename, source order, and traversal order are not identity.

Enforcement metadata and descriptive/acquisition/location metadata are validated
and persisted where useful but excluded from semantic artifact identity. Two runs
with identical actual semantic/runtime inputs must not get different semantic
identities merely because one was pre-locked and the other was not.

Waivers remain distinct from desired state and evidence. Result identity binds only
an exact normalized applied-waiver snapshot and its exact subject/control,
evaluation-time applicability, digest/identity, and underlying failure. A whole
waiver-catalog revision is not result identity or historical assertion semantics;
an unrelated waiver and the absence of any applied waiver do not perturb identity.

### No configuration-artifact successor

There is no ADR 0007 successor for removed configuration plans, render results, configuration explanations, backend renderers, or a second adapter-input artifact. The assessment plan remains the external-adapter handoff.

## Migration and compatibility

Predecessor `project-config/v1alpha1`, `project-config/v1alpha2`,
`release-lock/v1alpha2`, assessment v1, and assessment v3 were unfrozen migration
inputs. They are removed from current tooling; historical Git/releases/artifacts
remain immutable and require historical tooling.

Destination implementation sequencing was:

- #31 — actual composition, project-config v1alpha3, composition lock;
- #32 — provenance-bearing assessment plan/results v4;
- #34 — ordinary project consumer migration;
- #35 — IAM/private-source consumer migration;
- #36 — canonical scenario consumer migration; and
- #33 — old-reader retirement after all consumers migrated.

[#90](https://github.com/packetlss/compliance/issues/90) implements the later pre-freeze
result/plan ownership cutover, including intrinsic and relational validation and
the result-domain identity projection. It introduces no compatibility reader.

## Invariants retained

This refinement does not change JCS serialization, policy-source conflict semantics,
pass/fail/unknown/error/refusal boundaries, fail-only waiver application,
requirement/realization semantics, evaluator/evidence identities, private-source
boundaries, release coordinates, or firewall/network-policy architecture. It does
not introduce core history/retention, a run artifact, a result graph, mutable waiver
substitution, query-time roll-up rewriting, or compatibility with pre-freeze results.
