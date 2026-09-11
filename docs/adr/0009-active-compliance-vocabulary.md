# ADR 0009: Converge active compliance vocabulary

- **Status:** Accepted
- **Date:** 2026-09-05
- **Implementation contract:** [#57](https://github.com/packetlss/compliance/issues/57)

## Context

Before ADR 0007 successor provenance establishes new composition fixtures, #57
accepts explicit vocabulary convergence. The earlier `shared-library` identity
was intentional, including at ADR 0008 consolidation; it was not an erroneous
spelling. Historical releases, locks, artifacts, and migration evidence retain
that identity. The project remains pre-freeze without external compatibility
consumers.

## Decision

### Reusable policy source

The maintained reusable policy-source semantic identity changes from
`shared-library` to `control-library`.

| Namespace | Maintained value |
| --- | --- |
| Explicit semantic source name | `control-library` |
| Component path | `policy-sources/control-library/` |
| Semantic root | `policy-sources/control-library/policies/` |
| Release distribution | `compliance-control-library` |

These are distinct namespaces. Tooling must receive the source name explicitly,
never derive it from a path or distribution. `control-library` confers no
precedence, trust, mandatory dependency, or globally reserved source role.
Generic tooling continues to accept arbitrary valid explicit source names.

The rename affects identity: source names participate in current and successor
composition/provenance identity. Current development expectations and generated
plans/locks/results must be regenerated when affected. Existing persisted or
historical artifacts must not be rewritten to claim the new name. No
`shared-library` compatibility alias is added: configurations, plans, and locks
using the two names remain semantically distinct, and source-name mismatches
fail closed.

The policy-tree bytes and canonical content digest remain unchanged. Resource
IDs, control implementation and instance IDs, requirement/revision pins,
definition fingerprints, control parameters, technical outcomes, distribution
identity, and release construction/archive semantics are preserved. Names do not
change the content-digest algorithm or make acquisition topology semantic.

The synthetic IAM composition remains exactly three independently named and
materialized sources: `control-library`, `verification-policy`, and
`environment-private`. The private source remains physically separately
materialized with the existing trust-boundary checks. Source/file order remains
nonsemantic; identical definitions alone may coalesce, and divergence fails.

### Expected composition

ADR 0007 `composition-lock` is the sole forward complete expected-composition
abstraction: complete expected tooling source/execution identity plus an exact
name-keyed set of expected policy-source content identities, enforced against
independently resolved actual composition before domain execution.

It is not actual provenance, an acquisition manifest, a release catalog, a
repository manifest, or a source of missing runtime identity. Release versions,
distributions, and representations retain their release/acquisition purposes.
`release-lock/v1alpha2` was a temporary migration contract. #33 removed it and the
other predecessor readers after consumer cutover.

### Project selection and assurance vocabulary

#57 accepts `workspace-config` → `project-registry` for the named project
selection registry. It selects project configuration locations and an optional
default; it does not compose policy, merge project state, acquire components, or
define a development workspace. Its implementation is deferred to Tranche 2,
not implemented in the Tranches 0–1 PR. Current schemas, fields, selection, and
CLI remain unchanged here.

Technical control/assurance resource and wire names remain unchanged by this
vocabulary decision, including `Control`, `Baseline`, `BaselineOverlay`,
`ControlRequirement`, `ControlRealization`, `RequirementBaseline`, `implementation`,
`instance_id`, and `control_id`. Subsequent #37 promotion history does not change
these names.
Technical assessment and optional objective assurance retain their existing
semantics; missing or inconclusive required evidence remains `unknown`.

## Sequencing and non-goals

Tranches 0–1 recorded this decision and migrated maintained semantic compositions
before #31 established successor fixtures. #31 implemented actual composition,
project-config v1alpha3, composition digest/lock, and installed-wheel provenance;
#32 and #34–#36 completed artifact/consumer cutover, while #33 retired release-lock
and old readers. Those successor consumers use the new vocabulary from their first
artifacts.

This tranche implements no project-registry schema/model/CLI changes, ADR 0007
successors, assessment v4, release/composition CLI rename, assurance redesign,
release publication/coordinate change, digest algorithm change/freeze,
configuration artifacts, adapters, or firewall/network-policy work.

Historical repository descriptions, cutover evidence, ADR context, release/tag
records, `compliance-policy v0.2.0`, and historical `compliance-control-library`
releases remain immutable provenance. Current authority explains supersession
without relabeling historical identity.
