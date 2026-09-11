# Compliance control library

This component is the system's standard control library and reusable control
capability library. It is co-located at `policy-sources/control-library/`, while its
independent semantic policy source is named `control-library` and rooted at
`policy-sources/control-library/policies/`. The release distribution identity
remains `compliance-control-library`.

[ADR 0009](../../docs/adr/0009-active-compliance-vocabulary.md) intentionally
renames the previous `shared-library` identity. Historical provenance keeps the
old name; policy-tree bytes and content identity are unchanged, with no alias.

The library owns reusable OPA controls and helpers, control parameter schemas,
evidence and policy schemas, and technology-neutral requirement contracts. It is
a recommended reusable policy source, not a globally mandatory platform
component and not an adopter's authoritative desired policy. The platform remains:

```text
compliance-tooling + N named policy sources + project inputs
```

A self-contained policy source can operate without this library. Consumers depend
on library capabilities only through explicit semantic references and validation,
not through repository naming or a required source hierarchy.

The library's package, sysctl, AWS S3, macOS, SaaS, and other controls remain
technical assessment capabilities with stable IDs, parameter schemas, Rego
entrypoints, typed evidence requirements, and required authored title/purpose.
The title and purpose are intrinsic, identity-bearing Control meaning; instances,
overlays, and realizations cannot override them, and tooling never interprets them
as executable input. They do not define an in-core
configuration-generation contract.

The provenance-bearing resolved assessment plan is the handoff to separately
versioned external adapters. Such programs may map stable control IDs, definition
fingerprints, resolved parameters, and provenance to IaC, PaC, MDM, ticketing, or
configuration-management output. Adapter code, backend templates, source
precedence, and a duplicate configuration-plan abstraction do not belong here.

## Releases and provenance

The current forward release candidate is `compliance-control-library v0.4.0` and
uses the tooling-owned generic contracts:

```text
manifest: compliance.example/policy-source-release-manifest/v1
archive:  compliance.example/policy-source-archive/v1
content:  compliance.example/policy-source-tree-digest/v1alpha1
```

The canonical provenance identity is the digest of the materialized policy tree.
Distribution plus version plus that content identity names the semantic release;
Git metadata is optional source navigation, and an archive SHA-256 identifies only
the exact representation bytes. The generic archive contains the exact semantic
tree below `policy/` and has no required embedded manifest.

Hosted publication remains retired. Existing tags, GitHub Releases, and assets in
`packetlss-labs/compliance-control-library` remain immutable historical records.
Provider-neutral local descriptor/archive preparation and verification remain the
current release-contract proof. A new publisher requires separate reviewed work
when a real downstream release is needed.

[`docs/release-distribution.md`](docs/release-distribution.md) defines the current
producer boundary. The original content-addressed provenance decision remains in
[`docs/adr/2026-08-30-content-addressed-policy-provenance.md`](docs/adr/2026-08-30-content-addressed-policy-provenance.md),
and the generic cross-producer contract is governed by workspace ADR 0004.

The published `compliance-policy v0.2.0` release is immutable historical identity.
Its distribution, producer-specific descriptor, bundle format, tag, hosted assets,
checksums, and canonical content digest are not renamed, rewritten, or republished.
Current source no longer constructs, reads, or validates those producer-specific
formats. Reproduction uses the historical tag's source and tooling in an isolated
environment and verifies its assets under their historical checksum rules.

## Component role

[ADR 0012](../../docs/adr/0012-explicit-policy-parameter-resolution.md) accepts
explicit policy parameters and policy-owned effective evidence freshness.
Controls retain reusable evidence dependency contracts and optional capability
restrictions; adopter policy chooses effective `max_age`. Current manifests
still own those ages until the coordinated migration in
[#73](https://github.com/packetlss/compliance/issues/73). This documentation
promotion changes no policy/schema bytes or effective values.

Synthetic baselines, illustrative benchmark mappings, and the example IAM
requirement chain live in `compliance-verification-policy`. Restricted
realizations, environment parameters, inventory, assignments, evidence, plans,
results, and any externally generated configuration remain in their owning
project or adapter boundaries.

Current source-boundary tests derive their inventory directly from `policies/`.
They require complete reusable controls and shared schemas, reject
adoption-specific resources and external mappings, and validate identities,
references, and Rego entrypoints without a historical role taxonomy.

The destination materializes this producer at `policy-sources/control-library/`.
Its outer path, GitHub repository, semantic source name, and release distribution
identity remain separate concepts.

## Closed-world assurance ownership

[ADR 0016](../../docs/adr/0016-closed-world-policy-assessment.md) supersedes ADRs
0013–0015; its bounded successor is implemented under #78 and remains experimental.
This library owns
reusable policy/evidence schemas and technology-neutral requirement contracts;
tooling owns inventory, planning, qualification, run accounting and results.
Adopter policy/governance owns supplied scope, company requirements, demonstration
choices and external applicability/sufficiency judgments. Synthetic content belongs
to verification policy; real private inputs stay outside this repository.

Selected dependencies identify typed evidence contracts, including explicit assurance
requirements where policy chooses them. No universal certificate schema or generic
recognition/authority subsystem is implied. Authored adoption, issuer/approval/signature
references, mappings and digests cannot establish reality. Exact beneficiary dependencies
and required correlation/integration evidence constrain shared assurance reuse; direct
assessment-result consumption is not required.

Framework mappings remain attributable policy/reporting content, never an authoritative
external obligation universe or engine-established conformity. Preserve ADR 0012 typed
parameter consumption and freshness, existing missing-realization behavior and ADR 0010
qualification/outcomes. Source names/content digests grant no truth, authority or precedence.

#73 and #78 are complete; #37 is their architecture-promotion history. Any new
assurance semantics or common reuse mechanism requires a focused architecture
exploration. No broader assurance subsystem is authorized by this material.

## Component validation

From a clean, committed destination checkout, run:

```sh
./policy-sources/control-library/scripts/validate-shared-policy.sh
```

The co-located tooling input and setup are documented in
[docs/validation.md](docs/validation.md). This checks the library's resources,
schemas, source boundary, content/release/archive identities, and Rego without a
parent workspace, sibling checkout, or adopting project. Destination CI runs it in
`component-validation`.
The complete composed feature suite is owned by `verification/scenarios/` in this
repository.
