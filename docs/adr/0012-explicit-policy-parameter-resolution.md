# ADR 0012: Explicit policy-parameter resolution and policy-owned evidence freshness

- **Status:** Implemented under #73; additive-set extension implemented under #129; amended by [ADR 0020](0020-governed-policy-composition-without-sealing.md); experimental, not frozen
- **Date:** 2026-09-05
- **Promotion history:** [#37](https://github.com/packetlss/compliance/issues/37)
- **Runtime/schema migration:** [#73](https://github.com/packetlss/compliance/issues/73); no runtime change in this promotion
- **Result ownership alignment:** Implemented under [#90](https://github.com/packetlss/compliance/issues/90); parameter semantics unchanged
- **Additive-set extension:** Accepted under [#127](https://github.com/packetlss/compliance/issues/127), implemented under [#129](https://github.com/packetlss/compliance/issues/129)

ADRs 0013–0015 were subsequently superseded by ADR 0016. #73 completed this ADR's
parameter identity, resolution, direct typed consumption and unresolved-policy
boundary independently; #37 is the completed promotion history that led to the
bounded #78 successor. Historical deferrals below describe this ADR's original
scope rather than current work routing.

The initial-current descriptions and migration table below record the pre-#73
starting point. [The implementation contract](../../tooling/docs/policy-parameters.md)
specifies the resulting experimental representation and implemented additive-set
extension.

> **Current amendment.** ADR 0020 deletes parameter sealing and replaces only the
> former fixed/sealed additive-set closure clauses with monotonic governed
> contribution composition. The declaration/binding/tailoring/consumption model of
> this ADR remains current; references below to seals, sealed state, or fixed-slot
> contribution rejection are historical except where this amendment updates them.

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
- applicable structural restrictions;
- required deviation rationale/governance metadata; and
- complete derivation/source provenance.

A descendant gains no override authority merely because it is more specific.
A stale parent pin, target, fingerprint or from-value is a failure requiring an
explicit reviewed update, not permission to rebase silently. Restrictions remain
effective along the derivation. Open binding cannot be used as an
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
objects are assigned atomically, with no implicit list union or object merge. The
only accepted exception is the explicitly declared additive-set contract below.
Durations use fixed `s`, `m`, `h`, `d`; one `d` is exactly 24 hours. Exact fixed
duration normalization to seconds may be used for semantic comparison/identity
where specified; retain authored representation in provenance where useful.
Such exact canonicalization is representation, not transformed consumption.
The migration must specify its normalization projection and conformance vectors.

There are no calendar durations, coercion, rounding, interpolation,
environment-variable substitution or expression evaluation. A constraint does
not create an absent binding, and default annotations do not change that rule.

### Explicit additive-set exception

ADR 0012's complete-value semantics remain the default. Scalars, objects,
ordinary arrays and direct technical `Baseline` / `BaselineOverlay` values remain
atomic. `uniqueItems: true` alone does not enable composition. Only a technology-
neutral requirement parameter whose current declaration explicitly opts in may
use bounded additive-set composition, conceptually:

```yaml
composition:
  kind: additive-set
```

For such a slot:

```text
exactly one compatible applicable base binding after valid base tailoring
    + zero or more independently applicable additive contributions
    -> canonical effective set
```

The initial member domain is strings only. Member equality is exact JSON-string
value equality, with no case folding, normalization, coercion or transformation.
After duplicate elimination, the semantic array representation is ordered by the
lexicographic order of each member's UTF-8 bytes. Authored base, contribution,
source, file, group, assignment, feature and traversal order are nonsemantic.
The canonical effective array is then validated against the complete current
parameter contract; canonicalization never drops an invalid member to make the
set valid.

An additive contribution is ordinary policy composition. It is not a `bind` or
`tailor` `parameter_operation`; it is not a deviation, overlay mutation,
inheritance edge, precedence rule or parent-state mutation. Conceptually:

```yaml
parameter_contributions:
  - id: database-software
    target:
      requirement: company.authorized-software
      slot: allowed_software
    members:
      - postgresql
      - pgbouncer
```

Its authored target is only the stable semantic slot identity:

```text
(ControlRequirement metadata.id, slot name)
```

The contribution carries no requirement revision or document digest, declaration
or schema digest, base `RequirementBaseline` identity/revision/digest, base-state
fingerprint, `from` value or deviation metadata. Current-policy resolution binds
that stable target to the exact current governed declaration supplied for the
operation. This bounded loose coupling allows an unrelated requirement revision,
requirement-text change, compatible declaration change or base-member addition to
proceed without reauthoring the contribution. It does not weaken the exact pins
used where correctness depends on prior state or interface, including existing
bind/tailor derivation and realization consumption.

### Additive-set resolution and failure boundary

For each stable semantic slot, resolution must:

1. resolve the current inventory, groups and applicable assignments using existing
   semantics;
2. collect every current applicable requirement declaration and additive
   contribution;
3. resolve each contribution target against `(requirement ID, slot name)`;
4. require exactly one compatible current semantic declaration, without using
   source order, revision recency, specificity or another precedence rule;
5. require that declaration to opt explicitly into additive-set composition;
6. validate every string member against the current declaration's item contract
   without coercion or transformation;
7. require exactly one compatible base binding under existing ADR 0012 rules,
   whether fixed or produced by ordinary bind/tailor derivation;
8. form the canonical set union of the selected base after any valid base tailoring
   and every independently applicable contribution;
9. coalesce duplicate members while retaining every base/contribution origin and
    every applicability path;
10. validate the complete canonical union against the current parameter contract;
11. materialize that value through the existing exact realization-consumption
    edges; and
12. fail closed before an assessable plan for any missing, ambiguous, atomic,
    incompatible, invalid-member, invalid-final-set or consumer-
    resolution state.

The same authored contribution reached through several membership or assignment
paths is one semantic contribution with every path retained. Its stable identity is
`(owning RequirementBaseline identity, local contribution ID, target requirement
ID, target slot)`. Separate contributions remain separately attributable even when
they supply equal members.

Tailoring continues to operate only on the selected base:

```text
effective set = tailored base ∪ independently applicable contributions
```

Tailoring cannot suppress, remove or override a contribution. Removal, denial,
suppression, exclusion, priority, override, subtraction, structured/keyed/numeric/
mixed members, generic merge,
reducer or expression behavior require new architecture review. Unsupported author
syntax for those behaviors is an authoring failure, not an ignored extension.

### RequirementBaseline and inventory authority

A contribution does not import, select or make its target requirement applicable.
The target declaration and exactly one base must already be made applicable by
governed current policy. Consequently, the runtime/schema contract allows:

- a contribution target absent from the contribution-owning baseline's exact
  `spec.requirements` membership;
- attachment only to a unique declaration/base made applicable by other governed
  policy;
- a contribution-only `RequirementBaseline` without fake exact requirement
  membership; and
- structural validity when a baseline owns at least one genuine requirement or at
  least one contribution.

Inventory remains authoritative for supplied governed facts and applicability,
such as `feature.database = "true"`. Policy owns the implication that such a fact
causes members to be contributed to technical intent. Inventory must not carry
policy-resource IDs, contribution operations or parameter members. Overlapping
factual classifications and assignments continue to accumulate without precedence.

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

- stable semantic slot identity and the exact resolved `ControlRequirement`
  revision, complete document and digest;
- exact declaration/composition/schema documents and digests;
- exact base binding, binding mode/origin, selected derivation, and existing parent-
  state operations/tailoring;
- parent pins, explicit tailoring operations, before/after values, expected
  fingerprints, restrictions and governance/deviation provenance;
- for every contribution, the exact owning resource revision/document/digest,
  authored members and identity `(owning RequirementBaseline identity, local
  contribution ID, target requirement ID, target slot)`;
- subject/scope, every group/assignment/policy applicability path and named policy-
  source content identity;
- canonical effective set and deterministic member-to-base/contribution
  attribution;
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
For additive-set resources, that contract-specific projection canonicalizes fixed
additive values, additive bind/tailor member arrays, contribution member arrays,
and contribution entries before the existing resource digest and frozen document
are produced. Named policy-source content identity continues to preserve the
acquired input bytes; atomic arrays and unrelated fields retain their existing
meaning.

The assessment plan remains the sole external-adapter handoff and retains the
complete resolved parameter/linkage/freshness facts. Attributable results reference
the exact plan and retain only evaluation-owned outcome/provenance facts. There is no second
adapter-input artifact or separate authorization artifact. Evaluation still
verifies applicable composition and plan integrity; consuming resolved values
does not bypass ADR 0007's actual-versus-expected checks.

These additive-set facts extend the existing plan-owned parameter records and
their provisional identity projections. They introduce no new resource, artifact,
cache, digest family or identity family. Persisted validation must detect tampering
with the frozen declaration, contribution, applicability/attribution, effective
value or exact consumer. Historical explanation consumes only the exact retained,
relationally validated plan/result pair; it never re-resolves current policy.

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

The additive-set extension accepted under #127 and implemented under #129 is part
of the current executable contract. Its coordinated schema/runtime/frozen-plan/
Coverage cutover preserves the table above while adding only the bounded
declaration opt-in, contributions, union, attribution and frozen-plan validation
defined here.

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
| Stale declaration/schema/parent/fingerprint/from-value; missing target or restricted operation | Resolution failure; no implicit rebase |
| Fixed external value silently rebound, or open binding outside declared scope | Resolution failure |
| Wrong type, violated pinned constraint, implicit merge/default, expression or transformed consumption | Resolution failure |
| Missing required consumption edge; copied equal literal only; absent/ambiguous or stale post-substitution destination | Resolution failure |
| One slot explicitly consumed by several required destinations; binding changes | Every destination materializes the new value without editing realization |
| Policy freshness explicitly tailored `4h -> 1h` | Exact targeted dependency receives `1h`; no `min()` selection |
| Parameters resolved but no matching realization | Existing separate coverage/`not_implemented` behavior; not automatically `unknown` |
| Resolution successful, required evidence missing/stale/invalid/inconclusive | ADR 0010 `unknown`, preserving its refusal prerequisites |
| Company `45m`, external condition `<= 30m` | Internally valid company assessment possible; external condition false; no framework claim from company pass |
| Historical result after effective policy/freshness changes | Preserve exact assessed values and evidence-selection attribution; no historical rewrite |
| One additive-set base and no contributions | Canonical effective value equals the base |
| One or several independently applicable contributions | Canonical union of the base and all contribution members |
| A member appears in the base and/or several contributions | One effective member; retain every base/contribution origin |
| The same authored contribution is reached through several paths | One semantic contribution; retain every applicability path |
| Unrelated requirement text/revision changes with a compatible stable slot | Existing contribution continues without reauthoring and resolves against the exact current declaration |
| Unrelated base member is added | Existing contributions continue and union with the changed base |
| Current declaration changes but still admits a member | Contribution applies under the exact current contract |
| Current declaration rejects a contributed member | Resolution failure; do not drop or transform the member |
| Slot is removed, renamed or becomes atomic | Resolution failure |
| Several applicable requirement revisions own the same stable slot | Ambiguity/conflict; no newest-revision selection |
| Contribution has no applicable declaration or base | Resolution failure; it does not import policy |
| Fixed or open-bound slot has an applicable contribution | Canonical union; fixed owns the base, not contribution authority |
| Valid base tailoring plus contribution | Canonical union of the tailored base and contribution |
| Tailoring attempts to suppress a contribution | Authoring/resolution failure; contribution remains independently applicable |
| Combined set violates the complete schema | Resolution failure without dropping members |
| Source/file/assignment/traversal order changes | Identical semantic result and attribution set |
| Removal/deny/priority/reducer or other unsupported syntax | Authoring failure |
| Frozen declaration/contribution/attribution/effective value/consumer is altered | Persisted-plan validation failure |

## Consequences, validation and deferred work

One explicit model makes company intent explainable through both technical-only
and objective paths. Policy authors must supply values and acknowledge changes;
realization authors must declare the semantic connections that literal copying
cannot preserve. Resolution failures are visible before assessment, while missing
evidence remains a separate epistemic outcome. Moving freshness ownership requires
an atomic maintained-consumer migration rather than a reusable-control fallback.

For the accepted additive-set successor, Coverage owns the ephemeral deterministic
projection of **current** effective parameter values and derivation through the
existing resolver. Coverage adds no second resolver, persistence layer or cache and
this decision does not freeze CLI spelling or output shape. Historical assessment
explanation continues to consume only the exact frozen plan/result pair.

The #127 promotion requires a documentation-only diff, coherent links and routing,
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
