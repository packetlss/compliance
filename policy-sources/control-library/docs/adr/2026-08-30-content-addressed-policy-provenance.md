# ADR: Content-addressed shared-policy provenance

Date: 2026-08-30

Status: Accepted

> Historical scope: this decision records the immutable `compliance-policy
> v0.2.0` producer contract and the canonical content-addressed provenance rule.
> The forward `compliance-control-library` line retains that content identity and
> uses the generic manifest/archive contract from workspace ADR 0004. Historical
> names and schema identifiers below are intentionally unchanged. Workspace ADR
> 0005 and the pre-freeze compatibility deletion decision supersede only this
> ADR's current-code compatibility requirement: reproduction of v0.2.0 now uses
> its historical source and tooling revisions, while current source supports only
> the generic policy-source release/archive contract.
>
> Transition update (2026-09-03): issue #24 retired hosted publication from the
> pre-consolidation control-library repository. Provider-neutral local generic
> descriptor/archive construction and verification remain active. Existing tags,
> GitHub Releases, and assets remain immutable historical records; the references
> to the former publisher below describe its noncanonical role at the time of this
> decision, not a current maintainer path.
>
> Boundary update (2026-09-04): workspace ADR 0006 removed configuration intents,
> policy configuration facets, and in-core rendering from the active contract. The
> assessment plan is now the external-adapter handoff. Historical configuration
> references below remain part of this ADR's original provenance context and do not
> describe the current control-library surface.

## Context

`compliance-policy` is primarily semantic content: Rego modules, control manifests,
parameter schemas, policy/evidence schemas, and backend-neutral configuration-intent
schemas. Unlike `compliance-tooling`, its source tree is directly consumed by the
runtime after materialization; it does not require a compilation/package build step
to become policy.

The first-alpha bundle work established a deterministic `policy-bundle/v1` archive,
a canonical policy-source tree digest, and Git source metadata. During publication
design, the product provenance requirement was refined: an assessment or generated
artifact must remain traceable to the exact semantic inputs even if the original Git
repository, Git metadata, hosting provider, or acquisition mechanism is unavailable.

Git is expected to remain the prevalent way operators acquire shared policy, while
deterministic archives remain useful for air-gapped transfer, artifact stores, and
non-Git acquisition. Acquisition prevalence must not determine semantic identity.

## Decision

Canonical shared-policy provenance is **content-addressed**.

The authoritative identity of materialized shared policy is the existing digest:

```text
compliance.example/policy-source-tree-digest/v1
sha256:<64 lower-case hexadecimal characters>
```

The digest is computed over the exact relative paths and bytes beneath the policy
source root. The source-root directory name itself is not part of the digest. Thus a
repository `policies/` tree and an archive-extracted `policy/` tree have the same
identity when their relative contents are byte-identical.

A semantic policy release is named by distribution and version, but provenance
resolves to the policy content digest:

```yaml
distribution: compliance-policy
version: 0.2.0
content:
  digest: sha256:<...>
  digestAlgorithm: compliance.example/policy-source-tree-digest/v1
```

### Git is source metadata, not canonical identity

Git tags and commits answer where the release was reviewed and how a human can
navigate source history. They do not answer what policy bytes are being evaluated.

A release descriptor may therefore include:

```yaml
sourceMetadata:
  gitTag: v0.2.0
  gitCommit: <40-hex commit>
```

Changing only Git history or commit identity while preserving the exact policy tree
must not change canonical policy content identity.

While hosted publication was active, its annotated release tag was a
release-manager control. The former publisher validated that the tag was annotated
and pointed to the checked-out commit, but this protected release intent and source
navigation rather than defining semantic policy provenance. That Git-only gate was
retired with the hosted publisher.

### Acquisition representations are separate

A deterministic archive is an optional acquisition representation:

```yaml
representations:
  - kind: archive
    format: compliance.example/policy-bundle/v1
    contentRoot: policy
    filename: compliance-policy-0.2.0.tar.gz
    sha256: sha256:<archive bytes>
```

The archive SHA-256 identifies those exact transported bytes. It is not equivalent to
and must not replace the canonical policy content digest.

The existing bundle-v1 internal manifest continues to record `source_git_sha` for
format compatibility. That field is representation/source metadata. Its
`source_digest` is the link from the representation back to canonical policy content.

Two bundle-v1 archives may therefore have different archive hashes because they carry
different Git metadata while extracting to policy trees with the same canonical
content digest.

### Git acquisition is expected but not privileged

The expected normal path is:

```text
git clone/fetch
  -> select release/tag/commit
  -> use or copy policies/
  -> compute policy-source digest
  -> require expected canonical digest
  -> evaluate
```

After materialization and digest verification, runtime evaluation must not require
`.git`, a remote, submodules, GitHub, or network access.

An archive, mirror, object store, filesystem copy, or other acquisition mechanism is
acceptable when it materializes the same digest.

### Provider-neutral release descriptor

`compliance.example/policy-release-manifest/v1` separates:

1. distribution/version release naming;
2. canonical `content` digest identity;
3. optional `sourceMetadata`;
4. optional acquisition `representations`.

Hosted-provider IDs, URLs, workflow IDs, credentials, mutable branches, and `latest`
references are excluded.

The retired GitHub Release workflow was only a publisher adapter. A future publisher
may expose the same descriptor and representations without changing canonical policy
identity.

## Provenance-chain consequence

Policy provenance should be reconstructable without Git:

```text
policy content digest(s)
        |
        v
release composition / lock digest
        |
        v
assessment or configuration plan identity
        |
        v
evaluator/runtime identity + exact runtime inputs
        |
        v
result / rendered artifact identity
```

Git annotations and acquisition records may be attached to this chain, but loss of
those annotations must not break the content-addressed derivation path.

Executable tooling differs: exact wheel bytes participate in installation/execution,
so the wheel SHA-256 remains an important artifact identity. The already-released
tooling v0.2.0 Git-centric alpha contracts remain immutable; later alpha evolution can
add a tooling source-content digest without rewriting history.

## Release-lock consequence

`compliance-tooling` release-lock `v1alpha1` is already released and remains
immutable. Before publishing a real downstream locked composition, a later alpha
revision should make policy canonical identity depend on release naming plus the
policy content digest, with Git source metadata and archive/acquisition digests
modeled separately.

A policy archive SHA or Git commit must not be required merely to prove semantic
policy identity when the materialized policy digest is already known and verified.

## Rejected alternatives

### Git commit as canonical policy identity

Rejected because identical policy content can exist under different Git histories,
mirrors, or providers. It also makes provenance depend unnecessarily on VCS metadata.

### Archive SHA as canonical policy identity

Rejected because the archive is a transport representation, not the semantic input to
OPA. Bundle metadata can change archive bytes without changing extracted policy
content.

### Git-only distribution/provenance

Rejected because air-gapped and non-Git acquisition remain valid use cases and
runtime must stay independent of Git after materialization.

### Removing deterministic archives

Rejected. Deterministic archives remain useful as optional, verifiable transport
representations and provide exact byte identity when those bytes are acquired.

## Consequences

- The canonical content identity is stable across Git/provider/acquisition changes.
- Git remains convenient and auditable without becoming a runtime dependency.
- Archive and content digests have explicit, non-overlapping meanings.
- Release descriptors can represent Git and non-Git acquisition consistently.
- Downstream provenance can be reconstructed from cryptographic content identities.
- Existing bundle-v1 compatibility is preserved.
- Release-lock and generated-artifact provenance will require later alpha evolution;
  existing released schemas are not mutated.
