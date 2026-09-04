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
| reusable control-library policy source | `packetlss-labs/compliance-control-library` | `7e563657de47f4ce9774854c95bcd00dc26f13be` | not moved |
| verification-only policy source | `packetlss-labs/compliance-verification-policy` | `18e2b91751c53f5e78fd73edb552b7a4c32c762c` | not moved |
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
