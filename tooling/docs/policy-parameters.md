# Explicit policy parameters

Implementation contract: [#73](https://github.com/packetlss/compliance/issues/73),
under [ADR 0012](../../docs/adr/0012-explicit-policy-parameter-resolution.md).
This document specifies the experimental representation for that migration.

Requirement declarations use a `parameters` object keyed by slot name. Each
declaration contains `required`, `binding_mode` (`open` or `fixed`), an inline
`schema` with its own `$id`, and `schema_digest`. Fixed declarations contain an
explicit `value`. Open declarations name permitted baseline identities in
`binding_scope`; those identities constrain structure, not issuer authority.
An optional `representation: duration` validates fixed positive integral
`s`, `m`, `h`, or `d` values. A day is exactly 86400 seconds.

A slot reference contains the requirement reference and document digest, slot
name, declaration digest and schema digest. Semantic slot identity is requirement
metadata ID plus slot name; revision and content pins remain separately checked.
Constraints and defaults never populate absent values. JSON arrays and objects
are atomic. Duration values normalize to an integral seconds string, retaining
authored values in declarations and operations: `1d`, `24h`, `1440m`, and `86400s`
all materialize `86400s`; `1.5h`, `P1D`, and `1M` fail.

Requirement baselines retain an explicit, unchanged requirement membership list.
An optional exact `extends` parent pin permits parameter-only derivation. Each
operation has an `id`, exact `target` slot reference, `expected_parent_fingerprint`,
and `op` of `bind`, `tailor`, or `seal`. Binding requires open unbound state;
tailoring requires explicit `from`, `to`, and the existing complete deviation
record. A seal cannot be removed by descendants. Multiple operations targeting
one slot in a single baseline fail. Operations have no list-order precedence.

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

Identity uses the existing provisional digest contracts and JCS. Object keys are
canonicalized; operations and consumption records are ordered by their explicit
identities, never used as precedence. Duration effective values use canonical
seconds while authored representations remain provenance-bearing. Atomic JSON
arrays retain value order. Acquisition paths and Git metadata add no parameter
authority. Independently assigned divergent slot states conflict; equality of
copied literals cannot erase declaration or linkage differences.

`policy_inputs` contains the resolved authored instance, Control manifest, parameter
schema and sorted content digests of implementation-local non-test Rego modules.
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
