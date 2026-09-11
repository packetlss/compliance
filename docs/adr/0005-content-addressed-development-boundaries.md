# ADR 0005: Content-addressed development boundaries

- **Status:** Accepted
- **Original date:** 2026-09-02
- **Destination authority transfer:** 2026-09-04
- **Historical source:** `packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`, `docs/adr/0005-content-addressed-development-boundaries.md`

This is the destination-owned normative restatement of accepted workspace ADR 0005. The historical file remains immutable decision provenance. This restatement changes repository-state descriptions only; it does not change the accepted semantics.

## Context

The compliance system's semantic composition is:

```text
tooling + N named policy sources + project inputs
```

The project previously duplicated that model with a workspace/submodule graph and child CI that indirectly depended on every sibling pin. That topology was useful while proving migrations and early release contracts but was not semantic identity.

A repository boundary, policy-source boundary, release boundary, and information-security boundary are distinct concepts.

## Decision

### Canonical provenance is content-addressed

Cryptographic identity of actual semantic/runtime content is authoritative. Preserve, as applicable:

- independently identified policy-source trees;
- contract-specific domain normalization;
- RFC 8785/JCS for semantic JSON digest algorithms;
- raw path-and-byte construction for source-tree algorithms that define it;
- exact tooling source/distribution artifact identity;
- evaluator executable version and byte digest;
- evidence document and evidence-set identities;
- release/composition identity; and
- provenance-bearing generated plans and results.

Git commits, tags, repository names, checkout paths, workspace commits, submodule gitlinks, provider/location metadata, URLs, and transport representations are review, navigation, or acquisition metadata unless the applicable runtime contract explicitly consumes those exact bytes.

### Development topology is nonsemantic

Repository layout must not determine policy-source identity, policy precedence, resource coalescing/conflict resolution, runtime behavior, generated-artifact identity, or compatibility status.

Logical policy sources remain independently named and independently digested even when co-located. Non-sensitive components may be developed atomically in one repository. Separate repositories are justified by real ownership, visibility, independently useful lifecycle, or information-sharing boundaries—not merely to simulate source isolation.

### Validation has three owners

Validation is divided into:

1. **Component validation** — focused unit/schema/policy/release-construction/contract tests.
2. **Composed integration validation** — one canonical deterministic scenario/feature suite.
3. **Installed-release provenance validation** — exact acquired artifacts, materialized content, no producer Git requirement, and execution provenance.

The complete feature suite has one canonical integration owner. Whole-workspace gitlink equality and sibling checkout cleanliness are orchestration concerns, not semantic component tests.

### Development compatibility is explicit

A version-like suffix or historical published artifact does not by itself create a frozen compatibility promise. Until a contract is explicitly frozen, current development tooling need not remain a universal reader for superseded alpha locks, artifact revisions, manifests, package identities, path aliases, or migration representations.

Historical Git history, tags, Releases, hosted assets, and generated artifacts remain immutable provenance. Removing active compatibility code never authorizes rewriting those records.

### Pinning follows the identity boundary

Retain pins/digests that identify or verify consumed semantic/runtime content or acquisition bytes, including policy-source digests, tooling source/wheel digests, evaluator identity, evidence identities, composition identity, and representation checksums where applicable.

Do not retain workspace baselines, sibling gitlinks, archived migration-source SHAs, or checkout paths as runtime identity.

Recording actual provenance and enforcing a predeclared expected composition are separate concerns.

## Current implementation state

The transitional multi-repository dependency graph has been consolidated into `packetlss/compliance`. Component, canonical scenario, and installed-release validation now run from the destination checkout. The old workspace and component repositories are archived historical provenance after retirement under destination issue #29.

The accepted provenance successor is ADR 0007. Destination issues #31–#36 are its
completed implementation and consumer-migration history. Pre-freeze compatibility
remains governed by this ADR until explicit freezes are reviewed.

## Consequences

- Cross-component development may be atomic without collapsing semantic roots.
- Policy-source isolation is tested through explicit named/materialized roots rather than Git repository boundaries.
- Runtime remains independent of `.git`, submodule commands, mutable refs, and GitHub after inputs are materialized.
- Historical provenance remains discoverable without becoming a permanent active validation dependency.
- Real need-to-know/private environments remain separate.

## Non-decisions

This ADR does not freeze current contracts, choose signing/registry/SaaS systems, change configuration execution ownership, change detailed assurance semantics, or authorize firewall/network-policy work.
