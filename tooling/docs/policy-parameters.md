# Explicit policy parameters

> **Successor routing:** [ADR 0024](../../docs/adr/0024-objective-assurance-and-parameter-policy.md)
> is accepted design under #192, not yet implemented. It separates Objective
> implementation gaps from Assessment outcomes, simplifies required Check membership,
> moves parameter ownership to explicitly assigned ParameterPolicy, supports both
> Check-authoring consumption paths and reconstructs frozen summaries. This document
> describes the current experimental runtime until coordinated migration; its
> superseded representations are not the successor implementation contract.

Current implementation contract: [#73](https://github.com/packetlss/compliance/issues/73),
as amended by [ADR 0020](../../docs/adr/0020-governed-policy-composition-without-sealing.md)
and implemented under [#144](https://github.com/packetlss/compliance/issues/144).
The complete contract remains experimental and pre-freeze.

## Current implemented representation

Requirement declarations use a `parameters` object keyed by slot name. Each
declaration contains `required`, `binding_mode` (`open` or `fixed`), an inline
`schema` with its own `$id`, and `schema_digest`. Fixed declarations contain an
explicit `value`. Open declarations require permitted baseline identities in
`binding_scope`; fixed declarations may also use `binding_scope` to permit explicit
governed descendant tailoring. Those identities constrain structure, not issuer
authority.
An optional `representation: duration` validates fixed positive integral
`s`, `m`, `h`, or `d` values. A day is exactly 86400 seconds.

A slot reference contains the requirement reference and document digest, slot
name, declaration digest and schema digest. Semantic slot identity is requirement
metadata ID plus slot name; revision and content pins remain separately checked.
Under [ADR 0019](../../docs/adr/0019-typed-identifier-namespaces-and-schema-uri-ownership.md),
the stable identity is structurally `(requirement ID, owner-local snake_case slot)`;
the exact declaration additionally includes the exact requirement reference and
resource/declaration/schema digests. Nested schema properties remain schema-local
fields rather than a global parameter namespace.
Constraints and defaults never populate absent values. JSON arrays and objects
are atomic unless a requirement slot explicitly opts into the string-only
additive-set contract below. Duration values normalize to an integral seconds string, retaining
authored values in declarations and operations: `1d`, `24h`, `1440m`, and `86400s`
all materialize `86400s`; `1.5h`, `P1D`, and `1M` fail.

Requirement baselines retain an explicit, unchanged requirement membership list.
An optional exact `extends` parent pin permits parameter-only derivation. Each
operation has an `id`, exact `target` slot reference, `expected_parent_fingerprint`,
and `op` of `bind` or `tailor`. Binding requires open unbound state; tailoring
requires explicit `from`, `to`, and the existing complete deviation record. Fixed
base ownership is not descendant authority: a valid governed descendant may tailor
an inherited fixed value. Multiple operations targeting one slot in a single
baseline fail. Operations have no list-order precedence.

Realization consumption links target one named control instance, exact
implementation ID/version/content fingerprint, and a JSON object path in its
technical parameters or named evidence dependency. Paths never address array
positions. Links materialize direct typed values; they do not evaluate expressions
or convert units. The final interface is checked after any implementation choice.
Every required slot in an implemented realization must have a required dependency
consumer. Missing realization retains the existing independent coverage behavior.

Technical instance `evidence` bindings explicitly name dependencies and their
effective `max_age`. Control manifests declare dependency IDs, types and required
flags, but no effective freshness. There is no fallback. Objective links may
supply freshness instead of literal instance bindings.

Frozen plan facts retain declaration documents, exact pins, source locators,
selected baseline ancestry, authored operations, intermediate state fingerprints,
effective values, authored links, implementation interfaces and destinations.
Persisted validation checks the frozen derivation and materialization, independently
of the outer artifact digest. Under
[#90](https://github.com/packetlss/compliance/issues/90), results reference
the exact plan rather than retaining corresponding resolved facts; historical
evidence selection identifies the exact assessed dependency by stable
`(instance_id, dependency_id)`.

An inline parameter schema `$id` identifies its schema contract and URI base, not
the owning requirement slot or exact schema bytes. The separately retained
`schema_digest` commits exact content. ADR 0019's canonical absolute HTTPS URI layout
and schema-version evolution rules are implemented under #136; runtime schema
resolution remains document-local and offline.

Identity uses the existing provisional digest contracts and JCS. Object keys are
canonicalized; operations and consumption records are ordered by their explicit
identities, never used as precedence. Duration effective values use canonical
seconds while authored representations remain provenance-bearing. Atomic JSON
arrays retain value order. Acquisition paths and Git metadata add no parameter
authority. Independently assigned divergent slot states conflict; equality of
copied literals cannot erase declaration or linkage differences.

The additive-set contract supplies its own narrow semantic normalization before
those existing JCS digests are calculated: fixed additive values, additive
`bind`/`tailor` `from` and `to` members, contribution members, and contribution
entries are canonicalized by their defined set/identity order. Frozen requirement
and baseline documents retain that normalized semantic document and its existing
resource digest; named policy-source content identity still records the acquired
source bytes. Atomic values and unrelated resource fields are not normalized by
this rule, and no second digest algorithm or identity family is introduced.

`policy_inputs` contains the resolved authored instance, Control manifest, parameter
schema and sorted content digests of implementation-local non-test Rego modules.
The exact plan separately projects the Control-owned title and purpose for both
active and excluded checks and validates those fields against this frozen manifest.
The prose is identity-bearing context, never a parameter or other executable input.
The implementation fingerprint hashes these manifest/interface/module facts with
JCS; source composition independently binds shared helpers. Changes in local module
content or version invalidate destination pins. `parameter_facts` contains the
requirement document, resolved slot states, selected realization and consumption
records. `parameter_derivation` freezes the selected baseline ancestry and states.
The exact relationally validated plan owns these records; results do not copy them.
ADR 0011 successful selections retain stable dependency attribution. Stored policy
diff compares the plan-owned fields;
subject explanation prints effective ages and complete slot/link provenance.

The canonical private-source scenario exercises explicit 24h → 1h tailoring with
unchanged realization bytes, four-way freshness fan-out, conflicting independent
ancestor/descendant assignment, required-evidence unknown, missing realization and
independent frozen-fact tampering. Focused resolver vectors exercise 30d → 15d
fan-out into technical, evidence-input and freshness destinations.

## Implemented additive-set extension

ADR 0012 keeps scalars, objects, ordinary arrays and all direct technical
`Baseline` / `BaselineOverlay` values atomic. `uniqueItems: true` has no composition
meaning. The only accepted exception is a string-array requirement slot that
explicitly opts into additive-set composition:

```yaml
composition:
  kind: additive-set
```

Its current effective value is:

```text
canonical(tailored base ∪ every independently applicable contribution)
```

Exactly one compatible current declaration and exactly one compatible applicable
base are required. The base uses the exact bind/tailor contract. Every compatible,
independently applicable contribution participates after valid base tailoring,
including for a fixed base. With no contributions, the canonical effective value
is the selected base.

Members are strings and are compared by exact JSON-string value, without case
folding, Unicode normalization, coercion or transformation. Duplicates coalesce.
The canonical effective array sorts the surviving strings lexicographically by
their UTF-8 bytes before complete current-schema validation and ordinary JCS-based
identity projection. Authored order in a base or contribution and source, file,
group, assignment, feature or traversal order have no semantic effect. An invalid
member or invalid final set fails resolution; the resolver must not remove members
to obtain a valid result.

### Contributions and stable targets

A contribution is ordinary applicable policy:

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

This is the current authoring wire syntax. An authored
contribution targets only `(ControlRequirement metadata.id, slot name)`. It does
not carry a requirement revision/document digest, declaration/schema digest, base
baseline pin, base fingerprint, `from` value or deviation metadata. The resolver
binds the target to the unique exact current declaration supplied for the operation.
Compatible unrelated requirement or declaration changes therefore do not require
contribution reauthoring; incompatible current meaning fails closed.

Contributions are not current `parameter_operations`. They do not bind or tailor;
do not mutate a parent or base; and do not create an inheritance, deviation,
overlay, precedence or authority edge. Tailoring affects only the base and cannot
suppress, remove or override independently applicable contributions.

The semantic contribution identity is `(owning RequirementBaseline identity, local
contribution ID, target requirement ID, target slot)`. Reaching the same contribution
through several membership/assignment paths retains one contribution and every path.
Equal members from the base or separate contributions produce one effective member
while every origin remains attributable.

### Applicability and RequirementBaseline structure

A contribution never imports, selects or makes its target requirement applicable.
Exactly one compatible declaration and base must already be applicable through
governed current policy. The schema/runtime contract therefore allows:

- a target not listed in the contribution owner's exact `spec.requirements`;
- attachment to a unique declaration/base made applicable by other policy;
- a contribution-only `RequirementBaseline` without fake requirement membership;
  and
- a baseline with at least one genuine requirement or at least one contribution.

Inventory remains governed-fact and applicability input. Policy, not inventory,
owns the implication that a fact contributes particular members. Inventory must not
carry policy IDs, contribution operations or parameter members. Overlapping factual
classifications and assignments accumulate without precedence.

### Resolution and frozen facts

The implementation collects all applicable declarations, bases and
contributions; resolve each stable target; require the unique compatible opted-in
declaration and base; validate members; apply valid base tailoring; compute and
validate the canonical union; and
materialize it through the current exact realization links. Missing, ambiguous,
atomic, incompatible, invalid-member, invalid-final-set and consumer-resolution
conditions prevent an assessable plan.

The exact plan must retain:

- stable slot identity and the exact requirement revision/document/digest;
- exact declaration/composition/schema documents and digests;
- exact base binding, derivation/operations and tailoring;
- exact contribution owner revision/document/digest, authored members and semantic
  contribution identity;
- every group/assignment/policy applicability path;
- canonical effective set and deterministic member-to-origin attribution; and
- exact realization consumer and materialized value.

These extend current `parameter_facts` / `parameter_derivation` ownership and their
provisional plan identity projections. No new resource, artifact, cache, digest
family or identity family is introduced. Persisted validation must reject tampering
with any frozen declaration, contribution, applicability/attribution, effective
value or consumer.

Each additive slot state retains its canonical effective `value` plus a
`composition` record containing `kind`, canonical `base_value`, every
entry in `base_origins`, semantic `contributions`, and `member_origins`. A contribution
record freezes its semantic identity, exact owner document/digest/source identity,
canonical authored member set, and every applicability path. A contribution-only
selected baseline remains present in `resolved_requirement_baselines` with an empty
`requirements` array and empty resolved state; it does not create a target
requirement record.

Coverage owns an ephemeral deterministic projection of **current** effective values
and derivation through the existing planner/resolver. This does not freeze command
spelling or query shape and creates no second resolver, persistence layer or cache.
Historical assessment explanation uses only the exact retained, relationally
validated plan/result pair and never re-resolves current policy.

Structured/keyed/numeric/mixed members; removal, denial, suppression, override,
priority or subtraction; generic expressions, reducers or merge strategies;
contribution ACL/issuer authority; direct technical-baseline composition; changed
realization selection; evidence redesign; compatibility scaffolding; and new
resource/artifact/digest/identity families are outside #127/#129. Unsupported syntax is
an authoring failure and any demonstrated need for these semantics returns to
architecture.
