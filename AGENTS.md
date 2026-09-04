# Compliance repository instructions

This repository is the selected destination for consolidated non-sensitive compliance development under `packetlss-labs/compliance-workspace` ADR 0008. It becomes authoritative only through the staged cutover coordinated by workspace issue #69; until a source domain is explicitly cut over, its existing `packetlss-labs/*` repository remains authoritative.

## Durable architecture

Before implementation, read the applicable accepted architecture and the bounded GitHub issue. During bootstrap and migration, accepted workspace ADRs 0005 through 0008 are normative and must be copied or linked into this repository before implementation relies on them here.

Preserve these invariants:

- runtime and semantic identity is content-addressed; Git repository, owner, commit, checkout path, workspace pin, URL, and source order are acquisition/review metadata unless a contract explicitly consumes those exact bytes;
- `tooling/` is the explicit tooling source/build root and the Python distribution identity remains `compliance-tooling` unless separately reviewed;
- policy inputs are independently named and materialized semantic roots, including `shared-library`, `verification-policy`, and real environment-private sources;
- repository co-location must not create a merged policy tree or source precedence;
- source/file order is nonsemantic; identical same-identity definitions may coalesce only when exactly identical and divergent definitions fail closed;
- ordinary technical assessment and optional requirement/realization assurance remain complementary paths;
- missing, stale, invalid, or inconclusive required evidence produces `unknown`, never `pass`;
- authored realization/adoption state is not evidence of implementation;
- the provenance-bearing assessment plan is the external-adapter handoff;
- in-core configuration compilation/rendering, backend credentials/state, apply authority, and adapter/plugin runtime remain outside the core;
- verification policy remains source-only and must not regain an independent hosted release lane merely because it is co-located;
- real private inventory, evidence, realizations, credentials, secrets, provider state, generated results, and other need-to-know operational data stay outside this repository;
- generated evidence, plans, results, caches, and backend/external-adapter outputs are not authoritative source and remain untracked;
- firewall-related repositories and product work are out of scope unless explicitly reopened.

## Migration boundary

This repository starts from clean Git history. Historical component repositories, issues, PRs, tags, releases, and assets remain historical provenance and are not imported as active Git history.

Source movement must use bounded migration issues and record the exact source repository/commit plus applicable content digest. A pure enclosing-root relocation must not change tooling or policy-source semantic identity. If it does, stop and return to architecture rather than accepting a refreshed digest mechanically.

The synthetic IAM private-boundary fixture may eventually be co-located only if validation independently materializes its `environment-private` source. Co-location itself is not proof of a real trust boundary.

ADR 0007 successor implementation (`project-config/v1alpha3`, composition lock, assessment provenance and v4 plan/results) may occur after source co-location. Repository migration must preserve explicit semantic roots and current required runtime contracts until the bounded successor cutover. Do not silently absorb workspace #37 semantics into migration work.

## Development workflow

After the single repository-bootstrap commit that created this file, normal work is:

```text
classify/design
  -> bounded GitHub issue
  -> fresh branch from current main
  -> focused implementation
  -> PR
  -> CI on the reviewed revision
  -> review/re-review
  -> human squash merge
```

Do not implement directly on `main` after bootstrap. Implementation-local questions may be resolved when they do not change semantics, architecture boundaries, public/cross-component contracts, release identity, trust boundaries, or issue scope. Architectural findings return to the design loop and must be recorded durably before implementation relies on them.

Normal consolidated CI must eventually operate from this repository checkout without the old sibling-acquisition `compliance-ci` GitHub App credentials. Stable CI evidence must be observed and reviewed before merge. GitHub branch protection, rulesets, required-status-check enforcement, and similar provider controls are optional operational hardening under amended ADR 0008 and are not authority-cutover prerequisites.
