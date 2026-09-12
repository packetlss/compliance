# ADR 0019: Typed identifier namespaces and schema URI ownership

- **Status:** Accepted design, not yet implemented; experimental, not frozen
- **Date:** 2026-09-12
- **Architecture contract:** [#134](https://github.com/packetlss/compliance/issues/134)
- **Exploration:** [#132](https://github.com/packetlss/compliance/issues/132)
- **Refines:** [ADR 0005](0005-content-addressed-development-boundaries.md), [ADR 0007](0007-unified-actual-and-expected-composition-provenance.md), [ADR 0009](0009-active-compliance-vocabulary.md), [ADR 0012](0012-explicit-policy-parameter-resolution.md), and [ADR 0017](0017-source-authored-policy-and-check-meaning.md)
- **Implementation:** Deferred to the bounded PR #133 amendment and a separate coordinated pre-freeze namespace migration

## Context and decision boundary

The current experimental system has stable policy identifiers, exact revisions,
content digests, named policy-source provenance, evidence dispatch types, JSON
Schema identifiers, platform wire discriminators, release coordinates, Rego
entrypoints and filesystem paths. Several of these strings look similar or repeat
domain words, but they answer different lookup and provenance questions. Repository
co-location and the placeholder `compliance.example` authority do not make them one
global namespace.

Mixed underscore and hyphen spelling in current semantic resource IDs and several
unrelated JSON Schema URI layouts also make new authoring ambiguous. The project is
pre-freeze, so one canonical direction must be promoted before more identities are
minted. This decision records that direction only. It does not rename a resource or
schema, change a validator or reader, or make the accepted cross-kind collision rule
executable.

The following concepts remain distinct:

| Concept | Meaning and authority |
| --- | --- |
| Semantic resource ID | Stable authored name used in the resource kind's lookup namespace |
| Resource version or revision | Exact interface/history metadata, separate from the stable ID |
| Content digest or fingerprint | Exact content/interface identity under its declared algorithm, not a human name |
| Owner-local name | Slot, property, dependency, operation, link or contribution name interpreted only below its structural owner |
| Evidence type/version | Independent dispatch identity for an observation wire contract |
| JSON Schema `$id` | Schema-contract identifier and base URI, not resource identity or exact schema content |
| Policy-source identity | Named independently materialized composition input plus its exact content digest |
| Platform discriminator | Platform-owned `apiVersion`, evidence-envelope `schema`, artifact schema or digest-algorithm domain |
| Release/distribution identity | Acquisition and release coordinate for tooling or a policy source |
| Rego or filesystem name | Executable linkage or source organization, not semantic policy authority |

## Decision

### Canonical public lexical grammar

Policy-owned externally referenced semantic resources and evidence dispatch types
use these canonical forms:

```text
SEGMENT = [a-z0-9]+(?:-[a-z0-9]+)*
ID      = SEGMENT(?:\.SEGMENT)*
SLOT    = [a-z][a-z0-9]*(?:_[a-z0-9]+)*
REV     = [a-z0-9]+(?:[.-][a-z0-9]+)*
REF     = ID "@" REV
TYPE    = ID "/v" [1-9][0-9]*
DIGEST  = sha256:[0-9a-f]{64}
```

Semantic resource IDs use dot-separated kebab-case segments. Dot punctuation is
organizational only: it creates neither runtime ancestry nor authority. Requirement
slots and authored technical property names remain owner-local snake_case. Evidence
dependency names remain owner-local. Local operation, link and contribution IDs
retain their structural owners rather than becoming public semantic resource IDs.

Runtime performs no case-folding, alias expansion, Unicode normalization or other
identifier normalization. Versions, revisions, digests, policy-source names,
repository coordinates and filesystem paths do not occur inside a stable semantic
resource ID. A revision combines with an ID structurally as `REF`; it is not an ID
segment.

### Typed lookup namespaces, not one global ID space

An identifier is unique in the namespace in which its reference is resolved. The
resource kind or structural field supplies that namespace; authors do not embed a
kind tag or source qualifier in every ID.

| Identity class | Lookup/admission namespace |
| --- | --- |
| `Control` | Control catalog, currently keyed by stable `ID` |
| `Baseline` and `BaselineOverlay` | One shared technical-baseline namespace keyed by `REF` |
| `RequirementBaseline` | Requirement-baseline catalog keyed by `REF`, with the assignment collision admission rule below |
| `ControlRequirement` | Requirement namespace keyed by `REF` |
| `ControlRealization` | Realization namespace keyed by `REF` |
| Technical `instance_id` | Unique within the resolved subject plan across direct technical-baseline and realization paths |
| Evidence `type` | Independent dispatch namespace keyed by `TYPE` |
| Subject, group, assignment, waiver, policy-source and project names | Their existing distinct input or composition namespaces |
| Rego package and entrypoint | Executable namespace, separate from semantic policy identifiers |

Within a typed namespace, definitions with the same identity may coalesce only when
their complete semantic definitions are exact-identical; divergence fails closed
without source or file precedence.

The current Control catalog resolves a Control by stable ID. Its `version` and
definition fingerprint are exact interface metadata checked by pins and frozen
plans, but the current loader does not admit several parallel versions of one
Control ID. This describes current architecture; it is not a permanent prohibition
on a separately explored and promoted future multi-version lookup design.

### No mandatory authority-qualified semantic IDs

No authority prefix is required. Prefixes such as `company`, `verification` or an
adopter-selected organization string are ordinary authored `SEGMENT`s. They can
reduce accidental overlap, but do not prove ownership, confer trust or precedence,
reserve a namespace, or identify the policy source that supplied a definition.

Repository owner, GitHub organization, checkout path, source name, distribution,
release, acquisition URL, Git revision and source/file order remain acquisition,
review or composition provenance unless a separate contract explicitly consumes
their bytes. None is semantic namespace authority. This preserves vendoring and
independent policy-source composition without source-qualified runtime references.

### Kindless assignment references fail closed across baseline catalogs

`PolicyAssignment.spec.baselineRefs` serializes only `name` plus `revision`, which
normalizes to the kindless `REF` shape. A reference therefore cannot distinguish a
technical `Baseline`/`BaselineOverlay` from a `RequirementBaseline` when both occupy
the same `REF`.

For collision admission, the technical-baseline namespace and RequirementBaseline
namespace consequently form one assignment-reference namespace. Any supplied
composition in which the same `REF` is occupied by both a technical baseline and a
RequirementBaseline must be rejected before planning, independently of source,
file or traversal order. The runtime must not prefer one catalog, fall back between
catalogs, infer a kind, or add source qualification.

This fail-closed rule is accepted architecture but is not implemented by this ADR
promotion. The coordinated pre-freeze migration must add its validation and tests;
until then, current executable behavior must not be represented as conforming to the
rule.

### Parameter and other owner-local identity

[ADR 0012](0012-explicit-policy-parameter-resolution.md) structural identity is
unchanged:

```text
stable requirement slot = (requirement ID, slot)
exact declaration = exact requirement reference + resource/declaration/schema digests + slot
technical destination = instance + exact implementation/interface + destination path
```

The stable slot deliberately survives a compatible requirement revision while the
exact resolved declaration remains pinned separately. A realization materializes
the slot through exact typed consumer and destination edges. Nested JSON Schema
properties are schema-local fields, not members of a global parameter ontology.
Likewise, evidence dependencies and local operation/link/contribution IDs gain
identity from their owning resource and structural role.

### Evidence dispatch type and version

Evidence observation contracts remain independent of their consumers. A type such
as `linux.packages/v1` is valid without embedding a Control, policy-source or schema
publisher identity. `/vN` is dispatch-significant wire-contract versioning:

- compatible extensions to an observation may retain the type/version;
- an incompatible wire shape or observation meaning requires a new version; and
- one composition must supply one exact schema definition for each evidence type.

An evidence document ID is an attributable label in the evidence-input namespace,
not global content identity. The unchanged complete-document digest is its exact
content identity for assessment provenance.

### JSON Schema `$id` ownership and evolution

Let `H` be a schema publisher's explicitly selected stable DNS host. Canonical
absolute HTTPS schema-contract identifiers use these predictable layouts:

```text
https://H/schemas/platform/policy/{kind-kebab}/{WIRE}.schema.json
https://H/schemas/platform/{family}/{WIRE}.schema.json
https://H/schemas/evidence/{ID}/v{N}.schema.json
https://H/schemas/controls/{ID}/parameters/v{N}.schema.json
https://H/schemas/controls/{ID}/evidence/{SLOT}/inputs/v{N}.schema.json
https://H/schemas/requirements/{ID}/parameters/{SLOT}/v{N}.schema.json
```

Here `{kind-kebab}` is the policy resource kind rendered in kebab-case, `{family}`
is a platform-owned schema family, `{WIRE}` is that schema contract's explicit wire
version token, and `{ID}`, `{SLOT}` and `{N}` follow the grammar above.

`$id` identifies a schema contract and supplies a URI base. It does not identify a
policy resource, prove publishing or policy authority, or identify exact bytes.
Schema and resource digests plus enclosing provenance commit exact content. Schema
contract version is separate from the owning resource revision: compatible schema
evolution may retain one `$id` while its exact digest changes; incompatible schema
evolution mints a new schema-contract version. `$id` alone is not a global catalog
or composition-admission key. Where an existing resolver selects schemas for one
catalog role, competing candidates must satisfy that resolver's exact-definition
rule; in particular, one composition requires one exact schema definition for an
evidence `TYPE`. Separately digest-pinned, document-local parameter schemas may
retain the same compatible contract `$id` while their exact content changes.

The URI may be resolvable for publisher convenience, but runtime network discovery
is not required. Parameter schema references remain document-local and offline
under ADR 0012. `https://compliance.example` remains the experimental first-party
platform schema host until a separate authority/publishing decision selects a
production host. GitHub coordinates must not be used to infer one.

Platform `apiVersion` values, the evidence-envelope `schema`, artifact
discriminators and digest-algorithm domains remain platform-owned and unchanged.
Their `compliance.example/...` spelling neither grants semantic resource authority
nor requires semantic IDs to carry an equivalent prefix.

## Migration direction and PR #133 disposition

The coordinated pre-freeze migration will rename current authored identities to the
canonical grammar without aliases or compatibility readers. Representative
direction is:

| Current | Canonical |
| --- | --- |
| `macos.system.minimum_version` | `macos.system.minimum-version` |
| `aws.s3.account_public_access_block_required` | `aws.s3.account-public-access-block-required` |
| `linux.packages/v1` | unchanged |
| Owner-local slot `privileged_evidence_max_age` | unchanged |

Open PR [#133](https://github.com/packetlss/compliance/pull/133) is
**amend-before-merge**, bounded to exactly these mappings:

| PR #133 identity | Required disposition |
| --- | --- |
| Control `linux.packages.only_allowed` | Rename to `linux.packages.only-allowed` |
| Requirement `company.authorized-software` | Unchanged |
| Baselines `company.authorized-software-base`, `company.database-software` | Unchanged |
| Realization and technical instance IDs | Unchanged |
| Slot `allowed_software`, local IDs, destination `/allowed`, evidence dependency and `linux.packages/v1` | Unchanged |
| Rego entrypoint | Remains `data.compliance.controls.linux.packages_only_allowed.evaluate` as executable linkage |
| Control parameter schema `$id` | `https://compliance.example/schemas/controls/linux.packages.only-allowed/parameters/v1.schema.json` |
| Requirement parameter schema `$id` | `https://compliance.example/schemas/requirements/company.authorized-software/parameters/allowed_software/v1.schema.json` |

Changing those authored identities naturally recalculates affected resource digests,
definition fingerprints, exact pins and experimental release vectors through the
existing algorithms. This ADR does not amend PR #133. After this promotion merges,
PR #133 must make only the bounded amendment, recompute its affected pins/vectors,
and repeat exact-head validation, CI and review.

A separate coordinated pre-freeze migration issue must then cover existing
maintained resource IDs, schema `$id` values, validators/reference patterns and the
cross-kind assignment collision rule. That broader migration must not be folded
into PR #133.

## Consequences and non-goals

Typed namespaces keep semantic references independent of repositories and policy
sources while allowing short domain-oriented identifiers. This makes the lookup
kind and structural owner important context. URI-shaped schema contract identity
remains separate from content-addressed exactness and platform wire ownership.

This decision does not:

- rename or migrate current resources or schemas;
- change runtime, schema, validator, test, fixture or generated-artifact behavior;
- add aliases, compatibility readers, source-qualified identity or precedence;
- introduce network schema discovery or a namespace registry/service;
- select a production schema authority;
- change evidence qualification or selection, digest algorithms, or identity projections;
- change ADR 0012 stable parameter targeting or create a global parameter ontology;
- implement the technical/RequirementBaseline collision rule; or
- redesign Control multi-version lookup.

Current pre-migration resources and artifacts preserve their exact historical
identity and require the tooling that understands them. New executable conformance
and coordinated identity changes require the separately reviewed implementation
tranches above. Human promotion and merge authority remains unchanged.
