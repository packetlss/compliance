# ADR 0020: Governed policy composition without sealing

- **Status:** Accepted design, not yet implemented; implementation tracked by [#144](https://github.com/packetlss/compliance/issues/144); experimental, not frozen
- **Date:** 2026-09-13
- **Amends:** [ADR 0012](0012-explicit-policy-parameter-resolution.md)
- **Refines:** [ADR 0019](0019-typed-identifier-namespaces-and-schema-uri-ownership.md)
- **Supersedes:** Only the technical-seal, parameter-seal, and fixed/sealed additive-set-closure clauses in ADR 0012 and their implementation/promotion records [#127](https://github.com/packetlss/compliance/issues/127) and [#129](https://github.com/packetlss/compliance/issues/129)

## Context

The prior experimental contracts supplied two mechanisms that prevent a governed
descendant from changing inherited policy: technical `BaselineOverlay.seal` and
RequirementBaseline parameter `seal`. They also treated fixed or sealed
additive-set bases as closed to independently applicable contributions. Those
mechanisms imply an ancestry-based policy-authority or delegation relationship.
The accepted architecture contains no such hierarchy: governed policy is
authoritative policy.

Exact parent pins, target fingerprints, expected from/to values, required
deviation/governance provenance, named policy-source provenance, and fail-closed
conflict admission remain valuable evidence of an explicit valid derivation. They
do not establish a higher-policy veto. The existing architecture already rejects
independently applicable divergent definitions without source, issuer, ancestry,
or traversal precedence.

## Decision

### Delete sealing rather than replace it

Delete technical `BaselineOverlay.seal`, technical `overlay_policy`, sealed-control
and blocked-operation enforcement, technical seal lineage, and their frozen-plan,
explanation, and validation facts. An accepted descendant overlay may explicitly
tailor, exclude, substitute, or annotate inherited policy through the existing
exact parent pins, target fingerprints, from/to values, deviation/governance
provenance, and lineage.

Delete RequirementBaseline parameter `seal`, parameter sealed state, seal
operations/history, fixed-declaration sealed initialization, and all
sealing-specific ancestry/reference validation and presentation. ADR 0012's
declaration, binding, explicit descendant tailoring, exact realization consumption,
and unresolved/conflict boundaries otherwise remain in force.

`fixed` means that the `ControlRequirement` declaration supplies the base value.
It is base-value ownership and provenance, not higher-policy authority and not an
immutability barrier against a valid governed descendant tailoring. `open` still
requires applicable governed policy to bind the base. `tailor` remains explicit
descendant derivation of an inherited base using the existing exact parent,
fingerprint, from/to, and deviation semantics.

No replacement authority mechanism is introduced: no unseal, allow/deny mutation
ACL, policy/source/issuer ranking, central-versus-local authority, override right,
or ancestry precedence.

### Additive-set is monotonic governed composition

Atomic complete-value semantics remain the default for scalars, objects, ordinary
arrays, and direct technical values. An author needing one exact complete array
must use ordinary atomic array semantics. Contributions targeting an atomic slot
remain incompatible failures.

For a requirement declaration explicitly opting into:

```yaml
composition:
  kind: additive-set
```

the invariant is:

```text
effective set = selected base after valid base tailoring
                union every compatible independently applicable contribution
```

Every applicable governed contribution participates. A fixed base, an open-bound
base, and either base after valid tailoring may receive contributions. There is no
closed contribution state, suppression, denial, subtraction, priority, override,
source/issuer authority, or ancestry precedence.

Preserve the existing string-member domain, canonical member ordering, duplicate
coalescence, complete member/contribution/applicability-path attribution, exactly
one compatible declaration and base, final schema validation, exact realization
consumption, and fail-closed missing, ambiguous, incompatible, divergent-base,
invalid-member, invalid-final-set, and consumer behavior. Tailoring changes only
the selected base; it cannot suppress an independently applicable contribution.

### Pre-freeze schema-contract evolution

Before explicit compatibility freeze, schema-contract identifiers and versions are
provisional and may be replaced in place by a coordinated reviewed semantic
migration. Historical artifacts retain their historical meaning and require
historical tooling. After a schema contract is explicitly frozen, compatible
evolution may retain its identifier while incompatible evolution requires a new
schema-contract version.

This is a general pre-freeze rule, not a seal-specific exception. The coordinated
cutover changes affected authoring and frozen-plan schemas in place while retaining
their current `$id` values. It creates no compatibility reader, alias, dual
representation, deprecated-but-accepted seal form, predecessor support, identity
algorithm, or artifact family.

## Consequences and implementation boundary

The coordinated implementation in #144 will remove sealing from authoring, runtime,
frozen-plan admission/validation, current operator/explanation surfaces, maintained
synthetic policy, and seal-only verification. It regenerates naturally affected
provisional state/resource/source/content/composition/member-plan/operation/plan/
result/release inputs with existing algorithms. Technical Control definition
fingerprints do not change solely because `overlay_policy` is removed, because it
is already outside their definition-fingerprint projection.

The implementation preserves source/file/group/assignment/traversal invariance,
exact recomputation of the remaining derivation/contribution/attribution/effective
value/consumer facts, and fail-closed independently applicable divergence. It does
not add direct technical additive composition, generic reducer/merge/expression
semantics, negative contributions, compatibility scaffolding, or Stage 9 work
beyond a minimal regression adjustment necessary for this cutover.

Return to architecture if a retained product use genuinely needs runtime
policy-author authority, an external compatibility consumer exists, exact arrays
cannot use atomic semantics, suppression or negative contributions are needed, an
identity algorithm must change rather than receive regenerated inputs, or a
separate parent-order defect is found that does not depend on removed seal state.
