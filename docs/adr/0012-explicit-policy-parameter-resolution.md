# ADR 0012: Explicit policy-parameter resolution and policy-owned evidence freshness

- **Status:** Implemented under #73; experimental, not frozen
- **Date:** 2026-09-05
- **Promotion history:** [#37](https://github.com/packetlss/compliance/issues/37)
- **Runtime/schema migration:** [#73](https://github.com/packetlss/compliance/issues/73); no runtime change in this promotion
- **Result ownership alignment:** Implemented under [#90](https://github.com/packetlss/compliance/issues/90); parameter semantics unchanged

ADRs 0013–0015 were subsequently superseded by ADR 0016. #73 completed this ADR's
parameter identity, resolution, direct typed consumption and unresolved-policy
boundary independently; #37 is the completed promotion history that led to the
bounded #78 successor. Historical deferrals below describe this ADR's original
scope rather than current work routing.

The initial-current descriptions and migration table below record the pre-#73
starting point. [The implementation contract](../../tooling/docs/policy-parameters.md)
specifies the resulting experimental representation.

## Context and authority

The parameter decision accepted under #37 required durable authority for a common
resolution model. Current technical baselines already validate literal control
parameters and use explicit pinned overlays. Current `ControlRequirement` and
`RequirementBaseline` schemas have no parameter declarations or bindings;
`ControlRealization` embeds literal technical instances. Reusable `Control`
manifests currently supply effective evidence `max_age` to the plan. These are
migration inputs, not evidence that the successor model is implemented.

This ADR accepts explicit policy-parameter semantics for technical controls,
technology-neutral requirements, NIST-style organization-defined parameters
(ODPs), evidence freshness, externally fixed/delegated values and company or
environment specialization. It promotes an accepted design; it does not reopen
broader assurance decisions or implement resource/schema/runtime behavior.
Examples are conceptual semantics, not accepted YAML/JSON resource syntax.

[ADRs 0005](0005-content-addressed-development-boundaries.md),
[0006](0006-regulatory-assurance-and-external-adapter-boundary.md),
[0007](0007-unified-actual-and-expected-composition-provenance.md),
[0008](0008-consolidated-private-development-repository.md) and
[0009](0009-active-compliance-vocabulary.md) retain composition, optional
assurance, private-source, vocabulary and external-adapter boundaries.
[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) retains
assessment-time evidence status/refusal; [ADR 0011](0011-historical-assessment-and-operational-evidence-timeliness.md)
retains immutable historical outcomes and evidence-selection attribution.
The v4 foundation and consumer cutover are implemented on current main; this
successor does not add work to the completed #31–#36 migration or #33 retirement.

## Decision

### Resolve policy before assessment

```text
declaration
    -> explicit binding
    -> optional explicit descendant tailoring
    -> concrete effective value
    -> explicit realization-dependency consumption, where applicable
    -> fully resolved assessment plan
```

Every required security-relevant parameter must resolve deterministically before
an assessment plan is valid. A standalone technical baseline remains first-class
and needs no requirement/realization wrapper.

A reusable declaration may intentionally remain open for later binding. The
completeness obligation applies to the selected effective policy for the assessed
scope; declaration validation must not manufacture a value to make it complete.

```text
required parameter unresolved -> policy-resolution failure -> no assessable plan
independently applicable divergent bindings -> policy-resolution conflict
```

Do not evaluate partially resolved policy. An invalid diagnostic plan may explain
resolution failures under the existing plan/refusal boundary; it is not an
assessable plan. Missing/stale/invalid/inconclusive required evidence **after
successful policy resolution** remains assessment `unknown` under ADR 0010.
A missing realization is neither a missing parameter nor automatically evidence
`unknown`; existing coverage and missing-realization semantics remain unchanged.

### No implicit precedence or manufactured values

Source order, file order, source name, environment specificity, ancestry by
itself, group depth, nearest-scope selection, “strictest wins”, `min()`, `max()`
and arbitrary merge semantics must never choose effective values. Assignment
order likewise grants no precedence. Constraints validate explicitly chosen
values; they do not manufacture values. JSON Schema `default` annotations must
not populate security-relevant parameters.

Exact-identical same-identity definitions may coalesce with all provenance.
Divergent independently applicable definitions fail closed. Mere equality of
copied values does not establish declaration identity or semantic linkage.

### Binding and explicit descendant tailoring

Binding fills an intentionally open parameter slot in a structurally permitted
selected policy derivation:

```text
requirement: inactivity_period required, unbound
selected company policy: bind inactivity_period = 30d
```

Changing an inherited bound value requires explicit descendant tailoring:

```text
company: inactivity_period = 30d
selected derived enclave policy: tailor 30d -> 15d
```

Tailoring must retain and validate, as applicable:

- exact parent policy revision/content pin;
- exact target declaration/definition and expected parent state/fingerprint;
- explicit before/from and after/to values;
- operation identity;
- applicable structural restrictions/seals;
- required deviation rationale/governance metadata; and
- complete derivation/source provenance.

A descendant gains no override authority merely because it is more specific.
A stale parent pin, target, fingerprint or from-value is a failure requiring an
explicit reviewed update, not permission to rebase silently. Restrictions and
seals remain effective along the derivation. Open binding cannot be used as an
alias for replacing a value that is already bound.

### Derivation is distinct from assignment

```text
company policy -> derives enclave policy
assignment selects enclave policy -> one selected effective derivation
```

The selected derivation explicitly carries its ancestor state and permitted
changes. Assigning ancestors independently is a different composition:

```text
company policy independently assigned
    + divergent enclave policy independently assigned
    -> conflict
```

Ancestry does not create assignment precedence. This decision adds only
parameter binding/derivation/tailoring semantics to `RequirementBaseline`;
it does not define general requirement-membership overlays or realization
inheritance. Existing realization `based_on` remains provenance only.

### Requirement slot identity and dependency consumption

A technology-neutral requirement parameter has stable semantic identity
conceptually equivalent to:

```text
(ControlRequirement identity, slot name)
```

An exact declaration reference additionally pins the requirement revision,
requirement/declaration digest and exact type/value-schema identity/content.
A realization references that exact semantic requirement slot, not a copied
value or a matching display name.

**Every security-relevant requirement parameter that affects satisfaction must
have an explicit consumption edge into the required realization dependency whose
semantics use that parameter.** Initial consumers are technical check inputs,
evidence requirement inputs and evidence freshness inputs. The semantic contract
permits future separately defined procedural/manual assurance, external assurance
and certification/review dependency types; this ADR defines none of their
qualification, authority or result semantics.

If effective `inactivity_period` changes from `30d` to `15d`, every required
destination explicitly consuming it must materialize `15d` without editing the
realization. A copied literal equal to the current value does not satisfy the
required linkage. Authored policy retains the symbolic edge; the resolved plan
materializes the concrete value and retains linkage/derivation provenance.
Evaluation consumes those resolved values and does not resolve parameters again.
A broken or absent required edge cannot be repaired by matching equal literals.

Initial consumption is direct and typed. Destination-field renaming and exact
canonical representation are permitted where needed. Arithmetic, lookup tables,
predicates, scaling, rounding, arbitrary unit conversion, expressions and
interpolation are forbidden. A need for transformed consumption requires
architecture escalation, not a local convenience expression language.

### Technical destinations are implementation-local

Do not create a universal stable technical-parameter ontology. A technical
destination is identified by the exact resolved check definition, conceptually:

```text
control instance
    + exact implementation identity/version/fingerprint
    + destination input name/path
```

A requirement slot is a stable technology-neutral semantic identity; a technical
destination is one implementation-local input in an exact resolved check.
`substitute` may preserve control-instance lineage while changing implementation
and interface. A retained instance ID cannot authorize a stale input link after
substitution. Links must resolve and type-check against the selected final check.
Evidence dependencies have unambiguous stable authored `dependency_id` identities.
The result's successful-selection attribution uses the exact control instance plus
that dependency identity; an ambiguous evidence type or incidental file/list
position cannot stand in for the authored destination identity.

### External fixed and delegated/open bindings

Only the structural semantics needed for parameter resolution are accepted:

```text
external declaration: inactivity_period = 30d, binding mode = fixed
    -> local policy may consume it, but cannot silently replace it

external declaration: inactivity_period, binding mode = delegated/open to organization
    -> company policy may bind a concrete value within declared scope/restrictions
```

Whether the external issuer/customer/framework input itself is accepted as
authoritative was deferred during #37 promotion. ADR 0016 now assigns external
applicability and sufficiency to governance. Source identity/content digests prove
what input was consumed; they do not inherently prove authority. This ADR creates
no generic authority, IAM or delegation-verification subsystem.

For company-owned policy, selected provenance-bearing policy defines desired
state. Existing governance metadata such as `approval_ref` remains provenance
unless another accepted contract explicitly grants it runtime authority
semantics. Recording required governance metadata is not approval verification.

### Evidence freshness is policy intent

| Owner | Responsibility |
| --- | --- |
| Reusable `Control` | Evidence dependency identity/type/schema; optional implementation capability restrictions |
| Policy / baseline / requirement | Effective freshness requirement |
| Realization | Requirement-slot-to-evidence-dependency linkage where applicable |
| Evidence | Observed `collected_at` |
| Evaluator | Apply resolved `max_age` at `evaluated_at` |

Effective `max_age` is policy intent, not an intrinsic reusable-Control default.
Technical-only baselines may bind freshness directly. Objective requirements may
declare semantic freshness parameters; realizations may link each to one or more
explicit evidence dependencies.

```text
company: privileged_evidence_max_age = 4h
selected enclave derivation: explicit tailor 4h -> 1h
resolved assessment requirement: max_age = 1h
```

Do not resolve this through `min()`. A capability restriction validates the
explicit value; it cannot supply or silently tighten it. Current Control-owned
ages remain the executable migration contract until coordinated consumer cutover;
removing them requires explicit policy-owned replacement values.

Preserve ADR 0010 assessment-time eligibility/status/selection and ADR 0011
immutable successful `(instance_id, dependency_id)` plus evidence ID/document
digest and `collected_at` attribution. The exact assessed plan supplies the
dependency body and `max_age`; the result does not copy it. Changed policy freshness cannot
rewrite historical selection facts or outcomes. This promotion does **not** decide
`collected_at > evaluated_at`, the subsequently simplified required-only evidence
model, or query-time views.

### Value contract

Values are typed JSON validated against explicit pinned constraints. Arrays and
objects are assigned atomically, with no implicit list union or object merge.
Durations use fixed `s`, `m`, `h`, `d`; one `d` is exactly 24 hours. Exact fixed
duration normalization to seconds may be used for semantic comparison/identity
where specified; retain authored representation in provenance where useful.
Such exact canonicalization is representation, not transformed consumption.
The migration must specify its normalization projection and conformance vectors.

There are no calendar durations, coercion, rounding, interpolation,
environment-variable substitution or expression evaluation. A constraint does
not create an absent binding, and default annotations do not change that rule.

### Company policy and external conformity answer different questions

```text
policy resolution -> determine concrete effective company intent
external conformity -> compare that intent against explicit external conditions
assessment -> determine whether evidence satisfies resolved company intent
```

For an external condition `timeout <= 30m` and selected company `timeout = 45m`,
company policy may be internally well-formed and assessable at `45m` while the
external conformity condition is false. A passing company assessment must not
establish that framework claim. This does not waive a constraint explicitly
adopted into the selected policy's own structural/value contract; that constraint
still validates the chosen binding. External references alone do not import such
constraints or grant desired-state authority. The conformity evaluator and claim
authority contract remain separate work.

### Ordinary sources preserve private composition

No new environment-policy resource family is needed. Ordinary independently
named/digested policy sources such as `control-library`, `company-policy` and
`environment-private` may compose. Environment/private policy may contain
permitted open bindings, explicit derived-policy tailoring, environment-specific
realizations and sensitive effective values. Its name, privacy boundary,
repository, path or position grants no precedence. Names still identify sources
in composition provenance under ADR 0007; that is distinct from precedence.

Real private inputs stay outside this repository. The existing synthetic IAM
fixture remains a proof using a separately materialized `environment-private`
root, not a reason to acquire real private policy or create a merged policy tree.

### Immutable plan and provenance obligations

A valid resolved plan must explain each effective value without reopening mutable
policy. Preserve at minimum, as applicable:

- stable semantic slot identity, exact declaration/revision/schema pins and
  concrete typed effective value;
- binding mode/origin and selected derivation;
- parent pins, explicit tailoring operations, before/after values, expected
  fingerprints, restrictions/seals and governance/deviation provenance;
- subject/scope, assignment provenance and named policy-source content identities;
- selected realization dependency and exact technical/evidence destination;
- authored consumption edge and materialized destination value; and
- resolved evidence dependency and effective `max_age`.

These facts participate in the appropriate semantic plan identities/fingerprints;
persisted validation must detect inconsistent pins, edges, values and destination
attribution, rather than trusting shape alone. Equal effective values do not
justify discarding their distinct semantic linkage/derivation facts. Preserve
contract-specific normalization followed by JCS where specified and the existing
separation of semantic content from acquisition/location and expected-enforcement
metadata. Digests retain evidence of inputs, not proof of external authority.

The assessment plan remains the sole external-adapter handoff and retains the
complete resolved parameter/linkage/freshness facts. Attributable results reference
the exact plan and retain only evaluation-owned outcome/provenance facts. There is no second
adapter-input artifact or separate authorization artifact. Evaluation still
verifies applicable composition and plan integrity; consuming resolved values
does not bypass ADR 0007's actual-versus-expected checks.

## Implemented migration summary

These changes are implemented under #73 and #90. No artifact version or algorithm
is frozen by this summary.

| Surface | Current executable contract | Bounded successor obligation |
| --- | --- | --- |
| `ControlRequirement` | Technology-neutral statement and external references; no parameters | Technology-neutral slot declarations with stable identity and exact declaration/type-schema pins |
| `RequirementBaseline` | Pinned required requirement list | Explicit bindings and parameter-only selected derivation/tailoring |
| `ControlRealization` | Complete embedded literal technical instances, pinned requirement, `allOf`; `based_on` provenance only | Explicit requirement-slot-to-dependency-input links; preserve complete selection and current satisfaction model |
| `Baseline` / `BaselineOverlay` | Literal technical parameters and pinned typed operations | Retain technical role; explicit policy-owned freshness targeting/binding/tailoring where needed |
| `Control` | Parameter schema and evidence contracts requiring effective `max_age` | Retain dependency contracts/capability restrictions; remove effective freshness ownership only after coordinated consumer migration |
| Evidence dependencies | Stable authored IDs, type and effective `max_age` | Exact `(instance_id, dependency_id)` historical attribution with the dependency body and `max_age` owned by the assessed plan |
| Assessment plan/results/provenance | Exact plan retains resolved parameter/linkage/freshness records | Result references `plan_id` and retains only evaluation-owned facts, with mandatory relational validation |
| Fingerprints, validation, explanation and policy diff | Current literal instance fingerprints and frozen derivations | Include applicable slot/schema/operation/linkage/destination/freshness facts; explain and compare frozen facts without mutable-policy resolution |
| Maintained policy/projects/fixtures/scenarios | Current literals, pins and Control-owned ages | Explicit synthetic bindings/edges/freshness, coordinated schema and consumer cutover, deliberate changed expectations and regenerated development artifacts |

The checked current sources include the policy schemas under
[`policy-sources/control-library/policies/schemas/policy/`](../../policy-sources/control-library/policies/schemas/policy/),
[`render_plan.py`](../../tooling/tools/render_plan.py),
[`test_render_plan.py`](../../tooling/tests/test_render_plan.py),
[`test_control_realization.py`](../../tooling/tests/test_control_realization.py) and
[`test_assessment_v4.py`](../../tooling/tests/test_assessment_v4.py). In particular,
the current no-matching-realization test expects a valid assessable plan,
`not_implemented` adoption and failing requirement/baseline results. Preserve this
when required policy parameters resolve; do not recast absence as evidence
`unknown` or use a coverage gap to bypass parameter resolution.

The migration is coordinated across schema owners, planner/validation, provenance,
fingerprints, explanation and maintained consumers. Current experimental contracts
remain until that cutover. Pre-freeze artifacts may need regeneration; historical
artifacts/results/releases remain immutable, and removed predecessor readers are
not restored. See [contract maturity](../CONTRACT_MATURITY.md).

## Conformance and failure matrix

| Condition | Required behavior |
| --- | --- |
| Required slot unbound in selected effective policy, even with a schema default | Resolution failure; no assessable plan |
| Structurally permitted explicit open binding | Concrete typed value, with binding provenance |
| Valid selected descendant tailoring `30d -> 15d` | Resolve `15d` with complete explicit derivation |
| Independently assigned divergent company and enclave values | Conflict, regardless of ancestry or specificity |
| Stale declaration/schema/parent/fingerprint/from-value; missing target or restricted operation | Resolution failure; no implicit rebase or seal bypass |
| Fixed external value silently rebound, or open binding outside declared scope | Resolution failure |
| Wrong type, violated pinned constraint, implicit merge/default, expression or transformed consumption | Resolution failure |
| Missing required consumption edge; copied equal literal only; absent/ambiguous or stale post-substitution destination | Resolution failure |
| One slot explicitly consumed by several required destinations; binding changes | Every destination materializes the new value without editing realization |
| Policy freshness explicitly tailored `4h -> 1h` | Exact targeted dependency receives `1h`; no `min()` selection |
| Parameters resolved but no matching realization | Existing separate coverage/`not_implemented` behavior; not automatically `unknown` |
| Resolution successful, required evidence missing/stale/invalid/inconclusive | ADR 0010 `unknown`, preserving its refusal prerequisites |
| Company `45m`, external condition `<= 30m` | Internally valid company assessment possible; external condition false; no framework claim from company pass |
| Historical result after effective policy/freshness changes | Preserve exact assessed values and evidence-selection attribution; no historical rewrite |

## Consequences, validation and deferred work

One explicit model makes company intent explainable through both technical-only
and objective paths. Policy authors must supply values and acknowledge changes;
realization authors must declare the semantic connections that literal copying
cannot preserve. Resolution failures are visible before assessment, while missing
evidence remains a separate epistemic outcome. Moving freshness ownership requires
an atomic maintained-consumer migration rather than a reusable-control fallback.

Promotion requires a documentation-only diff, coherent links and routing,
`git diff --check`, repository validation, fresh-context exact-head independent
review and all four stable exact-head CI contexts green. Runtime/schema tests
are acceptance obligations of the successor issue, not changes in this PR.
Human final squash-merge authority remains unchanged.

The implementation deferred broader assurance terminology, manual/procedural/
external/certification dependency semantics, external authority and framework
claims, N/A and missing-realization redesign, general requirement/realization inheritance,
transformed consumption, technical-parameter ontology, generic IAM/delegation,
future-timestamp policy, query-time operational views, evidence retention and
collection. This decision authorizes no new result state, artifact family,
environment-policy resource, adapter/apply runtime, release publication, contract
freeze, private-data acquisition or firewall/network-policy work.

Implementation must return to architecture if it requires any deferred semantics,
changes a trust/release/compatibility boundary, or cannot represent the required
immutable values, typed links, identities and historical evidence attribution.
Concrete wire layout may be resolved under the bounded successor contract only
while preserving all these invariants.
