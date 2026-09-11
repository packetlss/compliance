# Tooling Release and Distribution Boundary


The ADR 0007 actual composition and v4 assessment contracts are documented
in [Actual composition and expected enforcement](composition.md). All maintained
consumers use successor contracts; historical artifacts require historical tooling.

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
identity recorded by package metadata and descriptive generated-artifact
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

The PEP 517 backend is selected exactly by the identity-bearing
`pyproject.toml` (`uv_build==0.12.5`). Independent builds therefore use the
accepted backend version rather than resolving a newer version from a range.

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
checksum, source identity, wheel identity, and downstream expected composition values.

## Tooling-owned schemas in the wheel

The installed tooling package supplies the generic platform contracts required
by its CLI and generated artifacts. The wheel contains the schemas currently
owned below `tools/schemas/`, including:

- project configuration `v1alpha3`;
- project-registry configuration;
- composition and composition lock `v1alpha1`;
- provider-neutral tooling release manifest `v2`;
- generic policy-source release manifest `v1`;
- assessment plan/results v4 and their provenance definitions;
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
`compliance.example/policy-source-tree-digest/v1alpha1`. Composition consumes only the named materialized `content` identity; release
distribution/version, source-navigation metadata and archive representations do not
enter the composition projection.

The tree digest evaluates generated-directory exclusions relative to the
explicitly supplied policy-source root. A root named `build` or `__pycache__`,
or a root beneath an ancestor with either name, is therefore ordinary source
content; only matching components inside that root are excluded. Artifacts
created by the earlier path-dependent implementation with an erroneous empty
content digest must be regenerated. Consumers do not accept that identity as a
compatibility alias.

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
System-level identity layering is governed by destination
[ADR 0005](../../docs/adr/0005-content-addressed-development-boundaries.md);
the provider-neutral tooling-release decision is retained in the local
[release ADR](adr/2026-08-30-provider-neutral-tooling-release.md).

## Successor composition and generated artifacts

Current projects use `project-config/v1alpha3` and optional `composition-lock/v1alpha1`.
The lock is an expected tooling source/execution identity and name-keyed policy
content set. It is neither acquisition metadata nor proof of actual execution.
See [composition](composition.md) for construction and strict enforcement, and
[assessment provenance](artifact-provenance.md) for v4 planning/evaluation,
verified installed-wheel receipts, evaluator and complete evidence provenance.

`composition show/validate` diagnoses the current actual and expected composition.
The predecessor `release show/validate` commands and release-lock reader are removed.

## Materialization is separate from acquisition

Composition enforcement begins **after** immutable artifacts have been
acquired and policy bundles have been materialized into local directories. It
does not download, clone, fetch, extract, update, or resolve releases.

Historical hosted releases are acquisition surfaces for their immutable wheel
bytes. A future publisher or artifact store may expose validated bytes elsewhere.
Runtime identity remains the version/source/artifact values recorded in the
release manifest and expected composition, not the acquisition URL.

After immutable inputs exist, lock validation and normal runtime processing
require neither:

- `.git` metadata;
- a Git executable;
- submodule commands;
- sibling repositories;
- mutable branch or tag resolution; nor
- GitHub access.

The package gates install a release-style wheel, construct a locked `v1alpha3`
project with a local materialized policy tree, shadow `git` with a deliberately
failing executable, validate the lock, and exercise v4 generated-artifact
provenance. This is the downstream runtime boundary.

## Composed integration boundary

Component validation and the canonical composed scenario gate run from the same
committed destination revision. A downstream or private deployment composition
may remain a leaf integration boundary. Repository paths and Git links are not
runtime or artifact identity. Development topology is governed by destination
[ADR 0005](../../docs/adr/0005-content-addressed-development-boundaries.md),
with current ownership in the local [architecture](../../docs/ARCHITECTURE.md)
and [repository map](../../docs/REPOSITORIES.md).

## Identity summary

The first locked composition distinguishes all of these values:

| Value | Owned by | Meaning |
|---|---|---|
| tooling distribution | tooling release | canonical package identity (`compliance-tooling`) |
| tooling semantic version | tooling release | human tooling version |
| optional tooling Git metadata | tooling release | noncanonical human/source navigation |
| tooling source digest | tooling release + lock | canonical runtime/build source identity |
| tooling wheel SHA-256 | release manifest + composition lock | exact acquired tooling bytes |
| tooling release manifest | tooling release | provider-neutral release metadata |
| policy semantic version | policy release | human policy release selection |
| policy archive SHA-256 | generic release representation | acquired policy artifact bytes |
| policy source SHA-256 | generic release + lock + project | runtime materialized policy identity |
| composition-lock SHA-256 | tooling | normalized expected composition identity |
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
the removed formats or the current v2 tooling, composition-lock v1alpha1, and
v4 assessment contracts.

## Python and OPA support statement

The Python package metadata declares `>=3.13,<3.14`. CPython 3.13 is the only
supported minor during pre-freeze development. The exact canonical development
and CI interpreter is Python 3.13.15, as recorded in
root `toolchain/versions.env`.

Supporting another Python minor requires an explicit package-metadata decision
and CI evidence. Historical releases retain their original metadata and are not
republished to adopt the current support range.

OPA is not a Python dependency and is not downloaded or installed by the wheel.
The current tooling release metadata records OPA `1.18.2` as the tested
evaluator version, matching root `toolchain/versions.env`. Commands that require OPA
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

Each installed-runtime gate derives its dependency requirements from
`uv.lock` with `uv export --frozen --no-dev --no-emit-project`. The exported
requirements retain the lock's exact versions, platform artifact choices, and
hashes. Validation installs those dependencies with hash enforcement into a
fresh external environment, then installs the candidate wheel with `--no-deps`.
The source project is never installed into that environment. An unavailable or
hash-mismatched locked artifact is therefore a hard failure rather than an
invitation to resolve another compatible version. The standalone package gate
performs the same install first with an empty dedicated cache and then in a new
runtime environment with that populated cache, proving cache state does not
change selected identities.

The lock and validation helper are test inputs, not artifact-construction
inputs, and remain outside the established tooling source-tree digest. The exact
backend requirement in `pyproject.toml` and `scripts/build-wheel.py` remain
inside that digest boundary, so this change intentionally changes tooling
source and subsequently built wheel identities without changing the digest
algorithm.

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
