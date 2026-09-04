# Retirement readiness evidence

This document records the one-time readiness evidence for declaring `packetlss/compliance` the sole authoritative non-sensitive compliance development and documentation repository under retirement controller #29 and cutover issue #40.

It is migration/retirement provenance, not a permanent compatibility contract. Historical migration digests below identify the accepted source snapshots and must not become future development pins after retirement.

## Authority prerequisites

Completed before this cutover candidate:

- all six non-sensitive source domains were migrated and have explicit destination authority records in `docs/history/pre-consolidation.md`;
- canonical scenario authority was reconciled after PR #28;
- accepted ADRs 0005–0008 and current system/workflow/repository/maturity documentation transferred to destination authority in #39 / PR #44;
- historical ADR 0007 implementation issues were routed to destination #31–#36;
- detailed assurance design was routed to destination #37;
- dormant product-DNA follow-up was routed to destination #38 with firewall work explicitly excluded;
- stale workspace productization issue #26 was closed rather than copied with obsolete topology/configuration assumptions.

## Preserved migration identities

The migration ledger and completed source-relocation validation established these content identities:

| Source | Algorithm | Migration identity |
| --- | --- | --- |
| tooling | `compliance.example/tooling-source-tree-digest/v1alpha1` | `sha256:93dce066b7eae3b63518d3011e21c977a4d52f5aa6963a48ea34161ef37c9f22` |
| `shared-library` | `compliance.example/policy-source-tree-digest/v1alpha1` | `sha256:75f88e26b0e941d93cc993fa40fd8bea96594254c5c6c0c46f39f3237a6d13c1` |
| `verification-policy` | `compliance.example/policy-source-tree-digest/v1alpha1` | `sha256:4e4bec94fa7b73056989074ae51c03671bd254fa63c89d4e7d324d13a4313da4` |
| synthetic `environment-private` | `compliance.example/policy-source-tree-digest/v1alpha1` | `sha256:f94aea8ac3259219c8a745a9bcd057f7ccdb80c97bed36a923f4f2522e3644aa` |

The IAM fixture validation proves the private policy is physically copied to a distinct temporary `environment-private` root, rejects symlink/same-inode shortcuts, removes the fixture-side policy before execution, and then composes the project. Real private environment data remains outside this repository.

## Canonical integration

`verification/scenarios/` is the canonical composed integration owner. The historical five-repository `integration/components.json` acquisition authority was removed during PR #28 without adding a replacement semantic composition abstraction.

The canonical gate uses committed destination roots in a temporary non-Git assembly and retains:

- exactly 20 public CLI leaves;
- exactly 18 domain features;
- fixed-time deterministic assessment behavior;
- pass/fail/unknown/waiver/conflict assertions;
- independently materialized IAM private source;
- named policy-source provenance;
- evaluator/evidence and assessment-plan external-adapter handoff assertions; and
- generated-state cleanup / checkout cleanliness.

## Active validation and topology

The sole active stable CI contexts are:

- `component-validation`
- `verification-scenarios`
- `installed-release-provenance`

The destination repository validator rejects restoration of root Python-project ambiguity, submodules, workflow path filtering, old `COMPLIANCE_CI_*`/PAT acquisition, historical component repository checkout, and repository-coordinate normal-development topology.

Normal development uses one destination checkout. There is no active `.gitmodules` file, sibling repository acquisition manifest, or old GitHub App/PAT path in normal destination validation.

## Historical work routing

| Historical issue | Destination successor |
| --- | --- |
| `packetlss-labs/compliance-tooling#77` | `packetlss/compliance#31` |
| `packetlss-labs/compliance-tooling#78` | `packetlss/compliance#32` |
| `packetlss-labs/compliance-tooling#79` | `packetlss/compliance#33` |
| `packetlss-labs/compliance-development-projects#19` | `packetlss/compliance#34` |
| `packetlss-labs/compliance-project-iam-realization#5` | `packetlss/compliance#35` |
| `packetlss-labs/compliance-verification-scenarios#13` | `packetlss/compliance#36` |
| `packetlss-labs/compliance-workspace#37` | `packetlss/compliance#37` |
| `packetlss-labs/compliance-workspace#21` | `packetlss/compliance#38` (dormant; no firewall implementation) |

Historical workspace #26 was closed as stale/superseded because its workspace-authority, no-consolidation, and removed configuration/rendering assumptions conflict with accepted current architecture.

Workspace #65 and #69 remain open only as final retirement/migration coordinators until the archive boundary.

## Historical provenance preservation

Historical component/workspace repositories retain their Git history, issues, pull requests, tags, Releases, hosted assets, and prior validation/migration evidence. Retirement archives rather than deletes them and does not rewrite or republish historical artifacts.

Historical release discoverability is checked through GitHub before archive actions. Release existence never becomes a current compatibility promise by itself.

## Sole-authority cutover

Destination PR #45 was reviewed as a documentation/readiness/authority-only change and all three stable CI contexts succeeded on exact PR head `433bdd3edd23683800f4ab2e8ce9a2c9bb95f037` before merge.

The sole-authority cutover became effective when PR #45 was squash-merged as:

- `packetlss/compliance@c1f9584263ea39d012a832f61b33c9643e3d60be`

From that commit onward, `packetlss/compliance` is the sole authoritative non-sensitive compliance development and documentation repository. Historical component repositories and `packetlss-labs/compliance-workspace` are provenance-only retirement surfaces; real private environment repositories remain separate.

This commit is Git/review provenance for the authority transition, not semantic runtime identity.