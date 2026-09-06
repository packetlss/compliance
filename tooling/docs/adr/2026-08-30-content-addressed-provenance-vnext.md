# ADR: Content-addressed provenance vNext

Status: **Accepted**

Date: 2026-08-30

Amended: 2026-08-31 — RFC 8785/JCS canonicalization and pre-freeze digest identifier lifecycle

Compatibility note (2026-09-03): issue #59 completed the deletion anticipated
by this ADR. Current tooling accepts only release-lock/release-validation
v1alpha2 and content-addressed locked artifacts v3; the v1alpha1 lock and
Git-provenance v2 artifact statements below are retained as historical context.

Product-boundary note (2026-09-04): issue #67 removed the v1 and v3
configuration artifact families and in-core rendering. References below to
configuration plans, render results, and explanations are historical; current
v3 artifacts comprise assessment plans and results.

## Context

The first-alpha release and locked-artifact contracts used Git source revisions as part of tooling and policy provenance. During shared-policy publication, the project adopted the stronger product rule that canonical provenance is defined by cryptographic identity of the actual semantic/runtime content. VCS, provider, location, and transport identifiers are metadata unless those exact bytes are themselves consumed.

The system must be able to explain an output back to the exact tooling, policy, evaluator, and authored/runtime inputs that produced it without requiring Git metadata to make that chain valid.

The project is still in development and has no external compatibility consumers. Existing development releases, generated artifacts, and digest algorithm labels therefore do not by themselves establish a supported compatibility promise. This development window should be used to settle the identity contracts before their first frozen versions are declared.

## Decision

### Development compatibility and identifier lifecycle

Digest algorithm identifiers are provisional until an explicit compatibility freeze. An unqualified `/v1` suffix is reserved for the first frozen, immutable version of an identity algorithm. Before that freeze, the corresponding development identifier uses an alpha revision such as `/v1alpha1`.

Development artifacts produced before the freeze may be invalidated or regenerated. Repository and Git history remain review/provenance records, but tooling is not required to preserve runtime verification compatibility for discarded development digest values or pre-freeze algorithm labels.

Once an algorithm is frozen as `/v1`, all identity-affecting parts of that contract are immutable, including:

- the domain normalization that determines the semantic value to identify;
- the canonical byte representation;
- the digest construction and cryptographic hash;
- ordering and inclusion/exclusion rules; and
- normative conformance vectors.

A later change that can alter identity for the same semantic input requires a new major algorithm identifier such as `/v2`; it must not silently redefine `/v1`.

Before an algorithm graduates to `/v1`, its freeze gate must include at least:

- settled domain normalization semantics;
- normative algorithm prose;
- fixed conformance vectors, including relevant Unicode and numeric edge cases;
- independent reproducibility from the specification rather than only the reference implementation; and
- an explicit durable compatibility declaration.

The implementation still contains some pre-amendment development identifiers ending in `/v1`. They are provisional labels, not frozen contracts. A separate implementation issue will rename the affected development algorithms and regenerate development artifacts after this design change is accepted.

### Canonical semantic JSON

When an identity algorithm hashes a semantic JSON value, the canonical JSON-to-bytes representation is RFC 8785, JSON Canonicalization Scheme (JCS), encoded as UTF-8 as specified by JCS.

Domain normalization and JCS canonicalization are separate layers:

```text
domain input
  -> domain-specific semantic normalization
  -> JSON-compatible semantic value
  -> RFC 8785 / JCS bytes
  -> cryptographic digest
```

JCS does not decide whether an array is semantically ordered, which fields participate in identity, whether two resources coalesce, or any other domain rule. Those decisions remain owned by the corresponding provenance contract and happen before JCS serialization.

This rule applies to semantic JSON digest algorithms such as release-lock, evidence-document, and evidence-set identity. It does not convert raw path+byte or file-tree identities into JSON identities. Algorithms that intentionally hash paths and raw file bytes continue to define their own byte-level construction.

Schemas and normalization rules for identity-bearing JSON must remain compatible with JCS requirements. The freeze gate must exercise edge cases that can otherwise differ across language runtimes, especially Unicode/property ordering and JSON number serialization.

### Tooling source identity

Define the provisional tooling source identity as:

```text
compliance.example/tooling-source-tree-digest/v1alpha1
```

The digest hashes path + bytes for the tooling runtime/build contract:

- `pyproject.toml`, including the declared Python/runtime dependency contract;
- `scripts/build-wheel.py`, because it defines the source-to-wheel transformation;
- the `tools/` runtime and tooling-owned schema tree;
- `package-data/`; and
- the canonical repository-level inventory and waiver schema sources mirrored into the package.

`tools/release-metadata.json` is excluded because release builds inject the source digest there. Git metadata, docs, tests, `uv.lock`, CI state, build outputs, caches, and repository location are not canonical tooling content.

The exact wheel bytes remain independently identified by SHA-256. Source digest and wheel digest answer different provenance questions and must not be collapsed.

The source-tree digest is a path+raw-byte algorithm; RFC 8785/JCS does not participate in this identity.

### Release metadata and publication

`tooling-release-metadata/v2` embeds source digest + digest algorithm and tested OPA compatibility version. It no longer requires a Git SHA.

`tooling-release-manifest/v2` records canonical source identity and exact wheel identity. Optional `sourceMetadata.gitTag` / `sourceMetadata.gitCommit` may be attached by a publisher or release manager for source navigation. They do not alter canonical source identity or wheel identity.

Generic release preparation must succeed with Git unavailable. At the time of
this decision, the repository's GitHub publisher was a thin adapter that
validated an annotated release tag and attached that Git information as
noncanonical metadata. Issue #66 later retired that old-repository publisher
during consolidation; provider-neutral release preparation remains current,
and any future publisher stays outside canonical release identity.

Existing development manifests and installed release metadata remain useful historical records, but their presence does not create a public compatibility commitment before the project explicitly freezes those contracts.

### Release lock

`release-lock/v1alpha2` is the first content-addressed composition lock.

Tooling is pinned by distribution, semantic version, canonical source digest/algorithm, and exact Python wheel SHA-256. Policy sources are pinned by distribution, semantic version, and canonical policy source-tree digest/algorithm.

Git tags/commits, repository/provider URLs, archive representation hashes, mutable refs, and acquisition locations do not enter v1alpha2 semantic identity.

`release_lock_digest` uses the provisional algorithm identifier:

```text
compliance.example/release-lock-digest/v1alpha1
```

Its domain normalization produces the canonical semantic lock document, including order-independent policy-source composition. The digest is SHA-256 over the RFC 8785/JCS representation of that normalized semantic document.

`project-config/v1alpha2` can load either release-lock alpha revision; a new project-config revision is not introduced merely for lock provenance evolution.

`release-lock/v1alpha1` retains its original Git-oriented semantics as development history. Pre-freeze runtime compatibility with superseded development artifacts is not a product requirement.

### Generated artifacts

Legacy `release-lock/v1alpha1` projects currently generate the existing v2 artifact schemas.

`release-lock/v1alpha2` projects generate v3 revisions for assessment plan/results and configuration plan/render-result/explanation. Their generator identity contains:

- `compliance-tooling` distribution;
- semantic version;
- canonical tooling source digest + algorithm;
- exact tooling wheel SHA-256 from the validated lock; and
- canonical release-lock digest.

Git SHA is absent from v3 artifact identity.

Configuration remains derived from the persisted assessment plan, never assessment results. Plan/configuration stages do not invent evaluator or evidence-execution provenance.

These generated-artifact schema revisions are still development contracts unless separately frozen. Regenerating them as a consequence of a reviewed pre-freeze identity-algorithm change is acceptable.

### Evaluator identity

OPA is selected independently at assessment execution time and therefore is part of execution provenance rather than tooling release compatibility metadata.

Before v3 assessment execution, the selected OPA executable is resolved once. That same resolved path is used both to:

1. read the actual OPA version and SHA-256 the executable bytes; and
2. perform `opa eval`.

The persisted v3 assessment result records only:

```json
{
  "name": "opa",
  "version": "<actual semantic version>",
  "executableSha256": "sha256:<exact executable bytes>"
}
```

The filesystem path is not canonical provenance.

`testedOpaVersion` remains release compatibility metadata and does not claim which evaluator produced an individual result.

### Evidence input identity

Evidence is a runtime input and must be cryptographically bound to a provenance-complete result. Evidence IDs alone are insufficient because collection metadata, subject binding, timestamps, and other document fields can affect evaluation independently of the ID.

Define the provisional algorithms:

```text
compliance.example/evidence-document-digest/v1alpha1
compliance.example/evidence-set-digest/v1alpha1
```

The document digest is SHA-256 over the RFC 8785/JCS representation of the complete semantic JSON evidence document.

The evidence-set domain normalization produces a sorted list of `{id, digest}` entries for the assessed subject. Sorting is a domain rule and remains independent of JCS. The set digest is SHA-256 over the RFC 8785/JCS representation of that normalized list.

For v3 assessment execution, tooling first copies the evidence JSON files into an isolated temporary snapshot. It derives the subject-scoped evidence identities from that snapshot and passes the same snapshot directory to the unchanged v1 evaluator. This removes path/order dependence and ensures the bytes recorded in result provenance are the bytes made available to evaluation rather than a separately re-read mutable directory.

The v3 assessment result records the evidence document digest algorithm, set digest algorithm, set digest, and each subject evidence ID + full-document digest. Local source paths are not canonical provenance.

Successor [issue #84](https://github.com/packetlss/compliance/issues/84) removes
the unverified collector-supplied `integrity.digest` from the normative envelope.
The evidence document digest remains unchanged and covers the entire evidence
document used by runtime.

### Python runtime environment

For this vNext slice, `pyproject.toml` is the declared Python runtime/dependency contract. No installed dependency inventory, lockfile digest, interpreter executable digest, or environment snapshot is added absent a demonstrated need.

The exact wheel SHA identifies the executable distribution artifact; the embedded source digest links it to canonical source content. An installed Python environment cannot reconstruct the original wheel bytes, so runtime validation verifies installed distribution/version/source identity and carries the wheel SHA from the validated release lock. Acquisition/release verification is responsible for checking wheel bytes before installation.

## Consequences

A provenance-complete v3 assessment can be traced through:

```text
assessment result
  -> assessment plan identity
       -> inventory revision
       -> assignment revision
       -> policy content/revision identities
  -> exact evidence document digests + evidence-set digest
  -> waiver revision
  -> actual OPA version + executable SHA-256
  -> release-lock digest
       -> policy content digest(s)
       -> tooling source digest
       -> tooling wheel SHA-256
```

The assessment timestamp is persisted as part of the result and continues to determine freshness and waiver applicability.

Git may still explain where reviewed source history lived, but deleting `.git` does not invalidate the cryptographic provenance chain.

The source digest intentionally does not claim to hash every repository file. It identifies the tooling runtime/build contract. Documentation and tests remain important governance evidence, but changing them alone does not create a different executable source identity.

RFC 8785/JCS removes Python JSON serialization behavior from the intended cross-language semantic-JSON digest contract. Independent implementations can reproduce the same canonical bytes when they implement the same domain normalization and JCS rules.

No pre-freeze digest value is promoted to compatibility status merely because a development release or generated artifact recorded it. The first frozen `/v1` algorithms will be declared only after their freeze gates are satisfied. After that declaration, identity-affecting changes require a new major algorithm identifier.

## Deferred

This ADR does not introduce signing, transparency logs, SLSA attestations, OCI/PyPI publication, automatic acquisition, environment snapshots, starter-workspace generation, assurance export, external inventory adapters, or firewall work.
