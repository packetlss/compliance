# Standard control-library release and distribution boundary

Status: **Accepted provider-neutral generic policy-source producer contract**

This document defines the producer-owned release, acquisition, materialization,
and provenance boundary for the standard control library. Workspace ADR 0004 owns
the generic cross-producer contract and identity layering; `compliance-tooling`
owns its schema, normalized model, canonical digest implementation, and archive
validator.

## Forward release identity

The current forward release candidate under the accepted public identity is:

```text
distribution: compliance-control-library
version: 0.4.0
manifest: compliance.example/policy-source-release-manifest/v1
archive: compliance.example/policy-source-archive/v1
content: compliance.example/policy-source-tree-digest/v1alpha1
```

The standard control library is a recommended reusable policy source, not a
globally mandatory component. The platform composition remains
`compliance-tooling + N named policy sources + project inputs`. Repository name,
provider, local materialization path, and archive filename carry no source-role or
semantic dependency meaning.

The semantic release identity is exactly:

```text
distribution + version + canonical policy content identity
```

It projects without loss to one unchanged
`release-lock/v1alpha2.policySources[*]` value. No release-lock revision or policy
source semantics change is part of this producer migration.

## Canonical policy content identity

The canonical content identity remains:

```text
compliance.example/policy-source-tree-digest/v1alpha1
sha256:<64 lower-case hexadecimal characters>
```

SHA-256 is computed over every included regular file under the policy root in
sorted POSIX relative-path order. For each file, the digest receives the UTF-8
path, one NUL byte, the exact file bytes, and one NUL byte. `build` and
`__pycache__` path components are excluded by the established digest contract and
therefore rejected from release archives.

RFC 8785/JCS does not participate in this tree digest. For an unchanged source
tree, the reset changes only the provisional algorithm label; the hashed path and
raw-byte stream and resulting SHA-256 value remain unchanged.

The source-root directory name is not hashed. Repository `policies/` and archive
`policy/` therefore have the same identity when their relative paths and bytes are
identical.

Git tag/commit metadata is optional source navigation. It does not participate in
content identity or the release-lock projection. Runtime validation requires no
Git metadata, network, hosted provider, or repository after content is locally
materialized.

## Generic descriptor and archive

The forward descriptor uses the tooling-owned schema
`compliance.example/policy-source-release-manifest/v1`. An archive-bearing local
payload is shaped as:

```json
{
  "schema": "compliance.example/policy-source-release-manifest/v1",
  "distribution": "compliance-control-library",
  "version": "0.4.0",
  "content": {
    "digest": "sha256:<canonical policy digest>",
    "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1"
  },
  "sourceMetadata": {
    "gitTag": "v0.4.0",
    "gitCommit": "<source object ID>"
  },
  "representations": [
    {
      "kind": "archive",
      "format": "compliance.example/policy-source-archive/v1",
      "contentRoot": "policy",
      "filename": "compliance-control-library-0.4.0.tar.gz",
      "sha256": "sha256:<exact archive bytes>"
    }
  ]
}
```

The generic archive contains only the exact semantic tree below `policy/`. It has
no embedded release manifest. It permits only regular files and directories,
normalizes ordering and tar/gzip metadata, and rejects absolute/traversing paths,
links, devices, FIFOs, other special entries, and digest-excluded generated paths.

The archive SHA-256 identifies exact representation bytes and is intentionally
separate from the canonical policy content digest. The tooling-owned validator
checks the declared representation SHA first, enforces the safe deterministic
profile, materializes `policy/`, and recomputes the canonical content digest.

This producer keeps no copy of the generic schema or validator. The local helper
constructs the distribution-specific payload and archive, then delegates schema,
model, archive-profile, extraction-safety, and content validation to released
`compliance-tooling`.

## Preparation and verification

Release preparation and verification run in a tooling environment:

```sh
uv run --project ../../tooling --frozen python scripts/policy-release.py prepare \
  --version 0.4.0 \
  --output-dir dist/release
```

That Git-independent form emits:

```text
policy-source-release-manifest.json
SHA256SUMS
```

The provider-neutral local path can also ask for the generic archive:

```sh
uv run --project ../../tooling --frozen python scripts/policy-release.py prepare \
  --version 0.4.0 \
  --archive \
  --output-dir dist/release
```

Optional `--git-tag` and `--git-commit` values add noncanonical source-navigation
metadata without changing the content digest or deterministic archive bytes.

Verify either local payload against its checksums, archive safety profile, and the
materialized policy tree:

```sh
uv run --project ../../tooling --frozen python scripts/policy-release.py verify \
  --release-dir dist/release \
  --policy-root policies
```

The archive-bearing local payload is:

```text
compliance-control-library-0.4.0.tar.gz
policy-source-release-manifest.json
SHA256SUMS
```

`SHA256SUMS` covers the descriptor and every representation. It is payload
integrity metadata and does not redefine semantic identity.

## Historical v0.2.0 provenance

The published `compliance-policy v0.2.0` release remains immutable history:

- distribution `compliance-policy` at version `0.2.0`;
- `compliance.example/policy-release-manifest/v1`;
- `compliance.example/policy-bundle/v1` and its embedded manifest;
- tag and source revision `f1f71f703dc788b1e9fd866d9268fbda5d2fe14b`;
- content digest
  `sha256:a956818dd608b70d051e807f173b4e468dabcd505e5e59655542560efbcf8e7d`;
- archive SHA-256
  `sha256:22bd33f0d1bdc78767941f8020aec0c5789ea7b829d4eaa01e433f7340a8dcf0`;
- descriptor SHA-256
  `sha256:f21aa7e423701590025efbba7275d192805b6d11ec2875a98b50aef6b93c21da`;
  and
- existing locks and generated artifacts that name that exact coordinate.

Current source intentionally does not retain producer-specific schemas, fixtures,
bundle helpers, readers, or recurring compatibility checks for this release. To
reproduce it, check out the historical tag and its historical tooling revision in
an isolated environment, then verify the hosted assets under the manifest and
checksum rules from that historical state. Current `main` does not parse,
normalize, validate, rebuild, or republish the retired format.

The published `compliance-control-library v0.3.0` tag, release, and assets likewise
remain unchanged with their former provisional `/v1` label. They are historical
development records, not active `release-lock/v1alpha2` inputs, and the forward
producer does not add compatibility acceptance for that discarded label.

## Hosted publication status

Hosted publication remains retired. The existing tags, GitHub Releases, manifests,
archives, and checksums in `packetlss-labs/compliance-control-library` remain
immutable historical records. Do not create a new control-library tag or hosted
release in the destination without separately reviewed publisher work.

`release/VERSION` and the provider-neutral local prepare/verify commands remain the
current proof that the `v0.4.0` source candidate can produce and validate the generic
descriptor and archive contract. A publisher may be established only when a real
downstream release is needed. Publication, if later required, remains a transport
adapter around these identities rather than their owner.

The destination producer path is `policy-sources/control-library/`, the semantic
source name is `control-library`, and the semantic root is its `policies/` directory.
Those are independent from release distribution identity. Destination CI runs the
gate in `component-validation`.

## Validation invariants

Focused release/archive validation proves:

- descriptor-only preparation needs neither Git nor an archive;
- forward distribution, version, manifest, archive, and digest identifiers are
  exact;
- the generic archive is deterministic and contains only `policy/` semantic
  content with no embedded release manifest;
- different Git metadata leaves content and archive identities unchanged;
- representation SHA and recomputed tree digest are both required;
- provider/location metadata cannot enter semantic identity;
- the semantic model projects exactly to the unchanged release-lock policy-source
  shape; and
- unsafe, excluded, or tampered source/archive inputs are refused.

The repository-required component gate is:

```sh
./policy-sources/control-library/scripts/validate-shared-policy.sh
```

See [validation.md](validation.md) for co-located contract validation. GitHub
Actions reports the stable destination `component-validation` check.

## Content ownership

The standard control library continues to own reusable assessment controls, Rego
helpers, control parameter schemas, policy/evidence schemas, and
technology-neutral requirement contracts. It does not define configuration-intent
schemas or an in-core rendering contract. External adapters consume stable control
IDs, definition fingerprints, resolved parameters, and provenance from the
assessment plan.

Verification-only policy, adopter desired policy, restricted realizations,
environment parameters, inventory, assignments, evidence, generated plans/results,
externally rendered configuration, credentials, and backend state remain outside
this release. This change does not alter source-order invariance, identical-only
coalescing, visible divergence errors, overlay/realization semantics, or the
external-adapter boundary.
