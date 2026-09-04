# Tooling Release and Distribution Boundary

Status: **Current pre-freeze package, release, and locked-composition contract**

This document defines the standalone Python package, immutable tooling release,
and locked downstream composition boundaries for `compliance-tooling`. They are
tooling-owned development contracts. None is frozen by its version-like suffix.
Historical releases remain immutable, but current tooling reads only the active
content-addressed formats documented here.

## First-alpha distribution identity

The accepted Python distribution name is:

```text
compliance-tooling
```

The operator-facing command remains:

```text
compliance
```

Python packaging normalizes the wheel filename to a form such as
`compliance_tooling-<version>-py3-none-any.whl`; the canonical distribution
identity recorded by package metadata, release locks, and generated-artifact
provenance is `compliance-tooling`.

The earlier `opa-compliance-prototype` distribution name was a temporary
development compatibility constraint while the workspace root directly depended
on the child package key. `compliance-workspace#27` / PR #28 removed that
coupling by selecting the pinned child project by repository path. The prototype
name is therefore superseded before the first actual tooling release and must
not be used in a new released lock or durable generated artifact.

The current source repository happens to be named `compliance-tooling`, but its
repository coordinate is transitional metadata rather than contract identity.
The Python distribution remains `compliance-tooling`, the import package remains
`tools`, and the operator command remains `compliance`; these are distinct
package/runtime interfaces and do not require a same-named source repository.
PyPI or another Python registry is not part of this first contract.

## Tooling release identities

A tooling release has distinct identities:

| Identity | Purpose |
|---|---|
| distribution | canonical package/product identity (`compliance-tooling`) |
| semantic package version | human release/version selection |
| tooling source digest | canonical runtime/build source identity |
| wheel SHA-256 | immutable distributed wheel bytes |
| optional Git tag/commit | noncanonical release navigation metadata |

The publication provider is deliberately **not** a release identity. A hosted
release ID, provider URL, CI run ID, or download URL may describe where a copy
was published, but it does not change what was released.

The package version comes from normal Python distribution metadata. The wheel
also contains `tools/release-metadata.json` using
`compliance.example/tooling-release-metadata/v2`, with the canonical source
digest and algorithm plus the tested OPA version. Editable/source development
installations report `build_kind: development` and a null source digest. Release
wheels embed the canonical source digest and report `build_kind: release`.

The installed identity is available without parsing presentation text:

```sh
compliance version --format json
```

A compact human form is available as:

```sh
compliance --version
compliance version
```

Release acquisition URLs, repository branches, publication-provider IDs, and
registry credentials are deliberately absent from this runtime identity.

## Canonical wheel build boundary

`scripts/build-wheel.py` builds from a temporary clean source copy. It may embed
the canonical source digest without changing or dirtying the authoritative
source checkout.

Example release-style build:

```sh
python scripts/build-wheel.py \
  --source-digest sha256:<64-hex> \
  --output-dir dist
```

A raw local build may omit `--source-digest`; that produces development
metadata and must not be represented as a provenance-complete release.

The release-preparation layer computes the source digest, wraps this builder,
and requires the built wheel to embed exactly that digest. Optional Git tag and
commit metadata may be supplied together for navigation; it is excluded from
canonical source and wheel identity.

## Provider-neutral release payload

The first provider-neutral tooling release was version `0.2.0`, with immutable
annotated Git tag `v0.2.0` retained as optional source-navigation metadata.

A prepared tooling release is exactly this custom payload:

```text
compliance_tooling-0.2.0-py3-none-any.whl
tooling-release-manifest.json
SHA256SUMS
```

The reusable source-local interface is:

```sh
python scripts/tooling-release.py prepare \
  --output-dir dist/release

# Optional noncanonical source-navigation metadata:
python scripts/tooling-release.py prepare \
  --git-tag v0.2.0 \
  --git-commit <exact-40-hex-source-sha> \
  --output-dir dist/release

python scripts/tooling-release.py verify \
  --release-dir dist/release
```

Preparation and verification do not call a hosting-provider API and do not
choose a publication provider. They:

1. compute the canonical tooling source identity;
2. validate optional strict `v<SemVer>` tag/commit metadata when supplied;
3. build exactly one release-style wheel through the canonical builder;
4. require the normalized wheel name for `compliance-tooling` and that version;
5. inspect wheel distribution/version, `compliance` entrypoint, embedded source
   digest/algorithm, and tested OPA version;
6. write and validate the release manifest;
7. write `SHA256SUMS` for the wheel and manifest; and
8. require that the release directory contain exactly the three contracted
   files.

The generic preparation gate is tested with a deliberately failing `git`
executable. Release payload construction does not discover canonical identity
from `.git` or a hosting service.

### Tooling release manifest v2

`tooling-release-manifest.json` uses schema:

```text
compliance.example/tooling-release-manifest/v2
```

Its shape is:

```json
{
  "schema": "compliance.example/tooling-release-manifest/v2",
  "distribution": "compliance-tooling",
  "cli": "compliance",
  "version": "0.2.0",
  "source": {
    "digest": "sha256:<64-hex>",
    "digestAlgorithm": "compliance.example/tooling-source-tree-digest/v1alpha1"
  },
  "artifact": {
    "kind": "python-wheel",
    "filename": "compliance_tooling-0.2.0-py3-none-any.whl",
    "sha256": "sha256:<64-hex>"
  },
  "testedOpaVersion": "1.18.2",
  "sourceMetadata": {
    "gitTag": "v0.2.0",
    "gitCommit": "<optional-40-hex>"
  }
}
```

The manifest is a closed provider-neutral contract. It contains no publisher,
hosted-release ID, repository URL, download URL, CI run ID, credential, mutable
branch, `latest` selector, workspace path, policy pin, or signing identity.

`SHA256SUMS` contains exactly the wheel and manifest entries. Its wheel digest
must equal `artifact.sha256` in the manifest. The checksum file does not include
itself, avoiding a self-referential identity.

## Publication pause during repository consolidation

No new hosted tooling release should be cut from this repository before
consolidation. The former tag-triggered GitHub publisher and its repository-write
permission have been retired; this repository has no active hosted-publication
workflow or release-manager sequence.

Existing tags, GitHub Releases, wheels, manifests, and checksums remain immutable
historical records. Reproducing one uses its corresponding historical source and
tooling state; those artifacts are not republished through the current branch.

Provider-neutral local release preparation and verification remain supported for
provenance validation. The optional annotated-tag contract also remains useful
for local source navigation and is exercised by package validation, but pushing a
tag does not publish a release. A publisher may be established in the
consolidated repository when a concrete downstream release need exists. That
future transport choice must preserve the provider-neutral wheel, manifest,
checksum, source identity, wheel identity, and downstream release-lock values.

## Tooling-owned schemas in the wheel

The installed tooling package supplies the generic platform contracts required
by its CLI and generated artifacts. The wheel contains the schemas currently
owned below `tools/schemas/`, including:

- project configuration `v1alpha1` and locked project configuration `v1alpha2`;
- workspace configuration;
- release lock `v1alpha2`;
- provider-neutral tooling release manifest `v2`;
- generic policy-source release manifest `v1` and the two immutable legacy
  policy-source manifest compatibility schemas;
- assessment plan/result semantic v1 and content-addressed locked v3 revisions;
- policy diff and diff-set outputs.

Inventory/assignment and waiver schemas historically live at repository-level
paths under `schemas/`. The package contract preserves those source paths for
the development workspace while installing exact package-data mirrors at:

```text
<site-packages>/schemas/inventory/resource.schema.json
<site-packages>/schemas/waivers/resource.schema.json
```

The canonical wheel builder refuses to build if either packaged mirror differs
byte-for-byte from its repository source schema.

Policy resource, control parameter, and evidence payload schemas remain owned
and distributed by policy artifacts. They are not copied into the tooling
wheel.

## Generic policy-source release contract

The current producer-neutral policy-source descriptor is:

```text
compliance.example/policy-source-release-manifest/v1
```

Its semantic identity is exactly the case-sensitive `distribution`, SemVer
`version`, and `content` identity using
`compliance.example/policy-source-tree-digest/v1alpha1`. The normalized semantic
document is already the complete shape of one
`release-lock/v1alpha2.policySources[*]` value; source-navigation metadata and
representations do not enter that projection.

The packaged `tools.policy_source_release` module validates and normalizes only
this generic schema. The producer-specific pre-freeze
`policy-release-manifest/v1` and `verification-policy-release-manifest/v1`
formats are immutable historical records but are not read by current tooling.
Reproducing those releases requires the corresponding historical tooling and
release state. New generic distributions are not constrained by a producer role
or hard-coded distribution taxonomy.

The initial generic representation is
`compliance.example/policy-source-archive/v1`: a tar/gzip archive containing
only regular files and directories below an explicit `policy/` root. Entries
use normalized POSIX names in lexical order after that root. Gzip metadata has a
zero timestamp, no optional header fields, and the portable unknown-OS value;
tar members have zero timestamps and numeric ownership, empty owner/group
names, and modes `0755` for directories and `0644` for regular files. The gzip
compression level may vary and therefore remains part of representation bytes,
not semantic content identity. Local archive validation first verifies the
declared exact-byte SHA-256, rejects non-normalized metadata or ordering,
absolute/traversing paths, links, special entries, and `build` or `__pycache__`
components, then recomputes the canonical policy-source tree digest before
optional materialization at a consumer-selected path. The opaque archive
filename is not parsed for distribution or version.

This boundary performs no discovery, download, authentication, caching, lock
generation, or publication. Future producers own construction and publication
of their releases while reusing the generic descriptor and archive profile.
System-level rationale and identity layering are governed by
[workspace ADR 0004](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/adr/0004-generic-policy-source-release-contract.md).

## Release lock v1alpha2

A locked downstream project checks in an adjacent:

```text
compliance.lock.yaml
```

with schema:

```text
compliance.example/release-lock/v1alpha2
```

The lock records release **identity, not location**. It contains one exact
tooling identity and a name-keyed set of exact released policy-source
identities. It contains no local materialization paths, download URLs, GitHub
branches, hosted-release IDs, credentials, `latest` selectors, or version
ranges.

Example shape:

```yaml
schema: compliance.example/release-lock/v1alpha2

tooling:
  distribution: compliance-tooling
  version: 0.3.0
  source:
    digest: sha256:<64-hex>
    digestAlgorithm: compliance.example/tooling-source-tree-digest/v1alpha1
  artifact:
    kind: python-wheel
    sha256: sha256:<64-hex>

policySources:
  shared:
    distribution: compliance-policy
    version: 0.2.0
    content:
      digest: sha256:<64-hex>
      digestAlgorithm: compliance.example/policy-source-tree-digest/v1alpha1
```

The tooling artifact SHA-256 identifies exact acquired wheel bytes. Each policy
content digest identifies the materialized policy tree consumed by runtime
evaluation. Generic policy-source archives retain a separate representation
SHA-256 at the acquisition boundary. Content and representation identities must
never be conflated.

An already-installed Python environment cannot reconstruct the original wheel
bytes. Runtime validation therefore carries `tooling.artifact.sha256` as
acquisition provenance but verifies the installed tooling distribution,
semantic version, canonical source digest, and digest algorithm. It does not
pretend to re-verify the original wheel artifact digest after installation.

The obsolete `opa-compliance-prototype` value is not an alias. A lock that names
it while the installed distribution is `compliance-tooling` fails through the
normal tooling-distribution mismatch contract.

## Canonical release-lock identity

A validated lock has a canonical identity named by:

```text
compliance.example/release-lock-digest/v1alpha1
```

`release_lock_digest` is SHA-256 over the RFC 8785/JCS UTF-8 representation of
the validated semantic lock document after lock-specific normalization. The
rendered value is:

```text
sha256:<64 lower-case hexadecimal characters>
```

The digest is independent of:

- YAML comments and whitespace;
- YAML/key ordering;
- policy-source map ordering; and
- local materialization paths.

Relocating the same released composition to another directory or machine does
not change its release-lock identity. Publication-provider metadata is absent
from the semantic lock, so republishing identical release bytes elsewhere also
does not change the lock identity.

Generated artifact v3 contracts record this digest together with the installed
generator distribution/version/source digest and exact locked wheel identity. See
[`artifact-provenance.md`](artifact-provenance.md).

## Locked project configuration v1alpha2

`compliance.example/project-config/v1alpha1` remains the current development and
workspace-compatible contract. It still supports local/unpinned source
assembly, legacy `paths.policies`, and an authored `paths.resourceSchema`.
Existing projects are not migrated by the release-lock slice.

The downstream locked contract is:

```text
compliance.example/project-config/v1alpha2
```

A `v1alpha2` project:

- requires named `policySources`;
- requires `name`, local materialized `path`, and exact `digest` for every
  source;
- does not support legacy `paths.policies`;
- does not contain `paths.resourceSchema`;
- obtains the inventory/assignment schema from the installed tooling package;
- requires adjacent `compliance.lock.yaml`; and
- retains project paths for inventory, assignments, evidence, plan, results,
  and waivers.

The project config owns **location** while the lock owns **release identity**.
For every configured source, validation requires:

```text
project policySources[].name
    == release lock policy source name
project policySources[].digest
    == release lock sourceDigest
actual digest(materialized local path)
    == release lock sourceDigest
```

All three must agree before a normal `v1alpha2` command can proceed.

Policy source ordering remains semantically irrelevant. The release lock does
not introduce source precedence, override ordering, or last-writer-wins
behavior. Existing identical-only coalescing and divergent-identity hard errors
remain unchanged.

## Installed-tool enforcement

Normal CLI commands load `v1alpha2` through the same config selection layer used
by planning and evaluation. Before the validated config is handed to those
commands, tooling requires:

- installed distribution == locked tooling distribution;
- installed semantic version == locked tooling version; and
- embedded installed source digest == locked source digest; and
- embedded source digest algorithm == the current tooling source algorithm.

A development/editable build with a null source digest cannot silently satisfy
a locked project. It fails release validation explicitly. Runtime validation
does not inspect `.git` to manufacture a missing release identity.

The diagnostic surfaces are:

```sh
compliance --config ./compliance.yaml release show
compliance --config ./compliance.yaml release validate
compliance --config ./compliance.yaml release validate --format json
```

`release show` reports the current state even when invalid. `release validate`
returns failure when the installed tooling or any materialized source does not
match the lock.

For locked projects, runtime overrides that would substitute the policy source
contract (`--policy-source`, `--policies`) or the tooling-owned inventory schema
(`--resource-schema`) are rejected. The same options remain available to
`v1alpha1` development projects.

## Generated-artifact provenance

Locked `project-config/v1alpha2` generation uses the content-addressed v3
artifact revisions. Each v3 artifact records:

```text
generator.distribution = compliance-tooling
generator.version = installed semantic version
generator.source_digest = embedded canonical tooling source digest
generator.source_digest_algorithm = canonical tooling source algorithm
generator.artifact_sha256 = exact locked wheel identity
release_lock_digest = canonical digest of compliance.lock.yaml
```

The assessment plan content ID includes this provenance. A stored v3 plan
cannot be evaluated under a different current lock composition; the mismatch
is a hard refusal. Current `v1alpha1` development projects retain the existing
v1 assessment artifact behavior.

## Materialization is separate from acquisition

The release-lock contract begins **after** immutable artifacts have been
acquired and policy bundles have been materialized into local directories. It
does not download, clone, fetch, extract, update, or resolve releases.

Historical hosted releases are acquisition surfaces for their immutable wheel
bytes. A future publisher or artifact store may expose validated bytes elsewhere.
Runtime identity remains the version/source/artifact values recorded in the
release manifest and release lock, not the acquisition URL.

After immutable inputs exist, lock validation and normal runtime processing
require neither:

- `.git` metadata;
- a Git executable;
- submodule commands;
- sibling repositories;
- mutable branch or tag resolution; nor
- GitHub access.

The package gates install a release-style wheel, construct a locked `v1alpha2`
project with a local materialized policy tree, shadow `git` with a deliberately
failing executable, validate the lock, and exercise v3 generated-artifact
provenance. This is the downstream runtime boundary.

## Workspace integration boundary

Component validation is repository-local. The canonical composed scenario gate
consumes explicit component revisions; an optional workspace remains a leaf
integration/deployment composition. Repository paths and workspace gitlinks are
not runtime or artifact identity. Development topology is governed by workspace
[ADR 0005](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/adr/0005-content-addressed-development-boundaries.md),
with current ownership in the workspace
[architecture](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/ARCHITECTURE.md)
and [repository map](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/REPOSITORIES.md).

## Identity summary

The first locked composition distinguishes all of these values:

| Value | Owned by | Meaning |
|---|---|---|
| tooling distribution | tooling release | canonical package identity (`compliance-tooling`) |
| tooling semantic version | tooling release | human tooling version |
| optional tooling Git metadata | tooling release | noncanonical human/source navigation |
| tooling source digest | tooling release + lock | canonical runtime/build source identity |
| tooling wheel SHA-256 | release manifest + release lock | exact acquired tooling bytes |
| tooling release manifest | tooling release | provider-neutral release metadata |
| policy semantic version | policy release | human policy release selection |
| policy archive SHA-256 | generic release representation | acquired policy artifact bytes |
| policy source SHA-256 | generic release + lock + project | runtime materialized policy identity |
| release-lock SHA-256 | tooling | portable tooling + policy composition identity |
| local materialized path | project config | machine/directory-specific location only |

Hosted-release IDs and download URLs are intentionally absent from the identity
table because they describe publication/acquisition locations rather than the
released bytes.

## Historical pre-freeze formats

Tooling release manifest v1, installed tooling metadata v1alpha1, release lock
and validation v1alpha1, assessment artifacts v2, and configuration artifacts
v1/v2/v3 are historical pre-freeze formats. Current tooling does not construct,
load, or validate them. To reproduce a historical development release or artifact, use
the corresponding historical tooling release or commit in an isolated
environment and verify its immutable release assets under that revision's
rules. Current `main` is not a universal historical reader.

The removed identifiers are:

```text
compliance.example/tooling-release-manifest/v1
compliance.example/tooling-release-metadata/v1alpha1
compliance.example/release-lock/v1alpha1
compliance.example/release-validation/v1alpha1
compliance.example/assessment-plan/v2
compliance.example/assessment-results/v2
compliance.example/configuration-plan/v1
compliance.example/configuration-plan/v2
compliance.example/configuration-plan/v3
compliance.example/configuration-render-result/v1
compliance.example/configuration-render-result/v2
compliance.example/configuration-render-result/v3
compliance.example/configuration-explanation/v1
compliance.example/configuration-explanation/v2
compliance.example/configuration-explanation/v3
```

Historical commits, tags, releases, hosted assets, manifests, archives, and
checksums remain immutable. Their continued existence does not freeze either
the removed formats or the surviving v2 tooling, v1alpha2 lock/validation, and
v3 locked-artifact contracts.

## Python and OPA support statement

The Python package metadata declares `>=3.13,<3.14`. CPython 3.13 is the only
supported minor during pre-freeze development. The exact canonical development
and CI interpreter is Python 3.13.15, as recorded in
`scripts/ci-versions.env`.

Supporting another Python minor requires an explicit package-metadata decision
and CI evidence. Historical releases retain their original metadata and are not
republished to adopt the current support range.

OPA is not a Python dependency and is not downloaded or installed by the wheel.
The current tooling release metadata records OPA `1.18.2` as the tested
evaluator version, matching `scripts/ci-versions.env`. Commands that require OPA
continue to use an externally supplied executable. Package installation and
release/config/inventory/waiver validation perform no OPA network acquisition.

## Standalone acceptance boundary

`scripts/validate-package.sh`, `scripts/validate-locked-artifacts-package.sh`,
`scripts/validate-release-preparation.sh`, and the
`tooling-package-validation` workflow prove that the wheel and locked project
can be consumed without any workspace checkout and that a complete
provider-neutral release payload can be prepared without a hosted-release API.
The single Python 3.13 package job runs installed-wheel, locked-artifact,
annotated-tag, provider-neutral release-preparation, and local generic
policy-source conformance validation exactly once.

This package gate complements rather than replaces the canonical composed
scenario integration gate.

## Deferred from this slice

This contract does not define or implement:

- PyPI or OCI publication;
- a replacement publisher adapter before a concrete downstream need is defined
  for the consolidated repository;
- automatic artifact acquisition or materialization;
- wheel/artifact signing;
- Sigstore, transparency logs, or SLSA attestations;
- automatic compatibility solving or version-range selection;
- `compliance init` or scaffolding;
- external inventory adapters; or
- assurance export.

No firewall-policy or `firewall-compiler` work is part of this contract.

## Decision record

The release/publisher separation is recorded in
[`adr/2026-08-30-provider-neutral-tooling-release.md`](adr/2026-08-30-provider-neutral-tooling-release.md).
The publisher-retirement transition and pre-freeze CPython 3.13-only support
decision are recorded in the
[architecture decision log](architecture.md#11-decision-log).
