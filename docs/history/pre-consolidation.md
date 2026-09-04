# Pre-consolidation migration provenance

This file records navigation and migration provenance for the clean-history consolidation into `packetlss/compliance`.

These Git revisions identify reviewed source snapshots used to plan migration. They are **not** semantic runtime identities and do not replace tooling source digests, policy-source content digests, evaluator/evidence identity, assessment provenance, or future release acquisition provenance.

## Destination bootstrap

- destination repository: `packetlss/compliance`
- GitHub repository ID: `1357405090`
- visibility at bootstrap: private
- initial bootstrap commit: `e1efe1c8b72b757dd392a8630b9bac48779e6d1d`
- initial commit contents: root `AGENTS.md` only
- destination authority: not yet transferred for all source domains; staged cutover is coordinated by `packetlss-labs/compliance-workspace#69`

## Accepted architecture migration source

- repository: `packetlss-labs/compliance-workspace`
- accepted source commit including the ADR 0008 governance amendment: `098ef18c1384b34c532f705b3f5b3d1a25bd638f`
- historical architecture/issues/PRs remain in the original workspace repository until it is archived after cutover

## Component source snapshots

| Logical source domain | Historical repository | Reviewed pre-consolidation source commit | Migration status |
| --- | --- | --- | --- |
| tooling/runtime and tooling-owned schemas | `packetlss-labs/compliance-tooling` | `bf9d71037a494f0f0a991003193f669aa811b94c` | moved by `packetlss/compliance#5` / PR #6; `packetlss/compliance@e1a0a0ccf472528ef027f8a2f6464bc7cf17a7d6` is authoritative for tooling |
| reusable control-library policy source | `packetlss-labs/compliance-control-library` | `7e563657de47f4ce9774854c95bcd00dc26f13be` | moved by `packetlss/compliance#9` / PR #11; `packetlss/compliance@a0b94b5a175816252a36e6c7f0e067c0e4ddf79e` is authoritative for `shared-library` |
| verification-only policy source | `packetlss-labs/compliance-verification-policy` | `18e2b91751c53f5e78fd73edb552b7a4c32c762c` | moved by `packetlss/compliance#10` / PR #14; `packetlss/compliance@33bbcf7b5ca71f83c46dae4ecd16ccc5a8840244` is authoritative for `verification-policy` |
| ordinary development projects | `packetlss-labs/compliance-development-projects` | `fa0eb99dc472a041e57c38103913c81753b963ab` | not moved |
| synthetic IAM/private-boundary proof | `packetlss-labs/compliance-project-iam-realization` | `9d75575989031e06484629ee6a68e90497c1f5d9` | not moved |
| canonical verification scenarios/integration | `packetlss-labs/compliance-verification-scenarios` | `92876dee8c081d6f51976391114c84dbdfd34f81` | not moved |

## Historical provenance rule

The original repositories retain their pre-consolidation commits, issues, pull requests, tags, GitHub Releases, and hosted assets. Complete historical Git graphs are intentionally not imported into this repository.

For each later source migration, update this ledger with:

- source repository and exact final authoritative source commit;
- applicable semantic/content digest before migration;
- destination migration issue and PR;
- semantic/content digest after relocation where applicable;
- first destination commit that becomes authoritative for that source domain;
- old repository archival/closure treatment; and
- historical release location when that component has published releases.

A pure enclosing-root relocation must preserve the applicable tooling or policy-source content identity. If it does not, the migration must stop and return to architecture rather than treating a new digest as routine migration metadata.

## Tooling relocation

- source repository: `packetlss-labs/compliance-tooling`
- final source revision: `bf9d71037a494f0f0a991003193f669aa811b94c`
- destination issue: `packetlss/compliance#5`
- destination pull request: `packetlss/compliance#6`
- destination root: `tooling/`
- digest algorithm: `compliance.example/tooling-source-tree-digest/v1alpha1`
- source digest before relocation: `sha256:93dce066b7eae3b63518d3011e21c977a4d52f5aa6963a48ea34161ef37c9f22`
- source digest after relocation: `sha256:93dce066b7eae3b63518d3011e21c977a4d52f5aa6963a48ea34161ef37c9f22`
- equality result: exact equality; the same root-relative canonical paths and bytes produce the same digest under the old repository root and destination `tooling/` root
- destination authority commit: `e1a0a0ccf472528ef027f8a2f6464bc7cf17a7d6`
- current tooling authority: `packetlss/compliance` under `tooling/`
- historical source/release repository: `packetlss-labs/compliance-tooling`; its Git history, tags, GitHub Releases, wheels, manifests, checksums, and hosted assets remain pre-consolidation provenance and it is no longer the active tooling source authority

## Control-library relocation

- historical source repository: `packetlss-labs/compliance-control-library`
- final source revision: `7e563657de47f4ce9774854c95bcd00dc26f13be`
- source-main re-verification: GitHub `main` resolved to the same revision immediately before relocation on 2026-09-04
- destination issue: `packetlss/compliance#9`
- destination pull request: `packetlss/compliance#11`
- destination producer root: `policy-sources/control-library/`
- semantic source name: `shared-library`
- semantic policy root: `policy-sources/control-library/policies/`
- digest algorithm: `compliance.example/policy-source-tree-digest/v1alpha1`
- source digest before relocation: `sha256:75f88e26b0e941d93cc993fa40fd8bea96594254c5c6c0c46f39f3237a6d13c1`
- source digest after relocation: `sha256:75f88e26b0e941d93cc993fa40fd8bea96594254c5c6c0c46f39f3237a6d13c1`
- equality result: exact equality; the same policy-root-relative paths and bytes produce the same digest under the historical repository `policies/` root and destination `policy-sources/control-library/policies/` root
- destination authority commit: `a0b94b5a175816252a36e6c7f0e067c0e4ddf79e`
- current `shared-library` authority: `packetlss/compliance` under `policy-sources/control-library/policies/`
- historical source/release repository: `packetlss-labs/compliance-control-library`; its Git history, tags, GitHub Releases, descriptors, archives, manifests, checksums, and hosted assets remain pre-consolidation provenance and it is no longer the active `shared-library` source authority

## Verification-policy relocation

- historical source repository: `packetlss-labs/compliance-verification-policy`
- final source revision: `18e2b91751c53f5e78fd73edb552b7a4c32c762c`
- source-main re-verification: GitHub `main` resolved to the same revision immediately before relocation on 2026-09-04
- destination issue: `packetlss/compliance#10`
- destination pull request: `packetlss/compliance#14`
- destination producer root: `policy-sources/verification-policy/`
- semantic source name: `verification-policy`
- semantic policy root: `policy-sources/verification-policy/policies/`
- digest algorithm: `compliance.example/policy-source-tree-digest/v1alpha1`
- source digest before relocation: `sha256:4e4bec94fa7b73056989074ae51c03671bd254fa63c89d4e7d324d13a4313da4`
- source digest after relocation: `sha256:4e4bec94fa7b73056989074ae51c03671bd254fa63c89d4e7d324d13a4313da4`
- equality result: exact equality; the same policy-root-relative paths and bytes produce the same digest under the historical repository `policies/` root and destination `policy-sources/verification-policy/policies/` root
- destination authority commit: `33bbcf7b5ca71f83c46dae4ecd16ccc5a8840244`
- current `verification-policy` authority: `packetlss/compliance` under `policy-sources/verification-policy/policies/`
- historical source/release provenance: `packetlss-labs/compliance-verification-policy`; its Git history, tags, GitHub Releases, manifests, archives, checksums, and hosted assets remain immutable pre-consolidation records and it is no longer the active `verification-policy` source authority
- current lifecycle: source-only; no independent version or release cadence, descriptor/archive producer, tag validator, hosted publisher, or replacement release ceremony
