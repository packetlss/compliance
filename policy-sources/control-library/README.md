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
entrypoints, and typed evidence requirements. They do not define an in-core
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

## Accepted scoped-assurance ownership

[ADR 0013](../../docs/adr/0013-scoped-assurance-and-obligation-instances.md),
[ADR 0014](../../docs/adr/0014-attributable-applicability-and-authority-acceptance.md)
and [ADR 0015](../../docs/adr/0015-bounded-external-claims-and-assurance-recognition.md)
are accepted design, not yet implemented under #37. This library retains reusable
policy/evidence schemas and technology-neutral contracts; tooling owns inventory,
planning and results. Adopter sources own company interpretations, desired policy,
applicable governance acceptance decisions and scoped consumption/claim inputs.
Synthetic examples belong to verification policy; real private facts remain outside
this repository. The library's name and content digests establish no issuer or
applicability authority, source precedence or automatic company policy adoption.

Population bases, applicability determinations and recognition rules retain distinct
semantics. Exact claim/obligation accounting and explicit named recognition dependencies
do not turn mappings, authored realizations or broad operational reach into proof.
Missing interpretation/realization and unresolved claim authority remain visible,
distinct from evidence insufficiency and shared assessment-integrity refusal.

Finish #73 / ADR 0012 independently before repository-grounded coordinated migration
planning under #37 across all three ADRs. Their migration tables govern successor
ownership without selecting wire syntax, generic attachments or new resource kinds.
Current policy/schema bytes remain unchanged until an authorized runtime cutover.
Manual/procedural methodology and sampling inference still require architecture.

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
The complete composed feature suite is owned by `compliance-verification-scenarios`.
