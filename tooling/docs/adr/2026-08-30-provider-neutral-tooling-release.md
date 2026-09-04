# ADR: Separate tooling release identity from publication provider

- **Date:** 2026-08-30
- **Status:** Accepted
- **Issue:** `packetlss-labs/compliance-tooling#20`

Compatibility note (2026-09-03): this ADR records the historical v1 manifest
decision. Issue #59 removed that unfrozen Git-oriented format and its installed
metadata reader from current tooling. Provider neutrality survives in the
content-addressed tooling release manifest/metadata v2 contracts; historical
reproduction uses the corresponding historical tooling revision.

Transition note (2026-09-04): issue #66 retired the old repository's hosted
publisher during consolidation. The provider-neutral identity, preparation, and
verification decision remains accepted; the paragraphs below that describe the
GitHub adapter and release-manager sequence are retained as historical context,
not current publication instructions.

## Context

The tooling package now has a permanent distribution identity, exact installed
source provenance, a locked downstream composition contract, and generated
artifact provenance. The next requirement is to publish immutable tooling
artifacts so downstream consumers can acquire the exact wheel bytes named by a
release lock.

The repositories currently use GitHub for source hosting, CI, tags, and hosted
release assets. Treating a GitHub Release as the semantic definition of a
compliance release would unnecessarily couple release identity and downstream
contracts to one publication service. The durable identities already accepted
by the platform are distribution, semantic version, immutable Git tag, exact
source Git SHA, and artifact SHA-256.

## Decision

Tooling release semantics are provider-neutral.

A tooling release is the immutable set of:

- distribution `compliance-tooling`;
- semantic package version;
- immutable annotated Git release tag;
- exact source Git SHA named by that tag;
- one release-style Python wheel;
- the wheel SHA-256;
- provider-neutral `tooling-release-manifest.json`; and
- `SHA256SUMS` covering the wheel and manifest.

The release manifest schema is
`compliance.example/tooling-release-manifest/v1`. It contains no publication
provider, repository URL, hosted-release ID, workflow/run ID, credential,
download URL, or mutable selector.

Reusable source-local preparation and verification code builds and validates the
complete three-file release payload without invoking a hosting-provider API.
Given the immutable tag string and source Git SHA, it also requires the tag
version to equal the source package version and the built wheel to embed the
same distribution, CLI, version, source SHA, and tested OPA version.

GitHub is the current publication adapter. A tag-only GitHub Actions workflow
validates GitHub's representation of the existing annotated tag, refuses an
already-existing hosted release, prepares the provider-neutral payload, reruns
release package gates, and uploads those exact files. It does not define a
second manifest or introduce GitHub identity into release semantics.

Tag creation remains a deliberate release-manager action after the version and
publication PR is merged. The publisher consumes an existing tag and must not
synthesize, move, or reuse one.

## Consequences

- The same wheel, manifest, and checksum payload can be published by another
  provider without changing downstream release identity.
- Release locks can continue to record semantic version, source SHA, and wheel
  SHA without storing a GitHub release ID or URL.
- GitHub-specific permissions and API behavior are isolated to one publisher
  workflow rather than the reusable release preparation layer.
- The first publishable tooling version advances to `0.2.0`; the old `v0.1.0`
  tag remains immutable and is never moved or reused.
- The hosted publication step can be replaced later without changing the
  manifest schema, wheel identity, generated-artifact provenance, or runtime
  contracts.
- Signing, transparency, OCI, PyPI, automatic acquisition, and compatibility
  solving remain separate future decisions.

## Alternatives rejected

### Make GitHub Release the canonical release identity

Rejected because hosted-release IDs, URLs, and provider state are transport
metadata rather than properties of the released tooling bytes.

### Put provider URLs in the release manifest

Rejected because relocation or republication of identical bytes would then
change or duplicate semantic release metadata.

### Let CI create the release tag automatically

Rejected because the tag is an immutable reviewed source name. It is created
only after the final merged source commit exists and is then consumed by the
publisher.

### Publish directly from `main`

Rejected because a mutable branch does not provide an immutable human release
name and makes source provenance less auditable.

## Detailed contract

See [`../release-distribution.md`](../release-distribution.md).
