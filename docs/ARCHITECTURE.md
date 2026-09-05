# System architecture

This document defines the current system-level architecture for `packetlss/compliance`. The accepted architecture decisions are ADRs 0005–0008 in `docs/adr/`.

Historical `packetlss-labs/compliance-workspace` architecture remains migration/design provenance. After this documentation-authority transfer, this repository owns current normative system architecture.

## Semantic composition

The product composition model is:

```text
tooling + N named policy sources + project inputs
```

A policy source is an independently named/materialized semantic input. Repository names, Git revisions, checkout paths, source roles, acquisition URLs, and source/file order are not policy identity or precedence.

Canonical runtime/generated-artifact provenance is content-addressed. Preserve the applicable tooling source/distribution identity, policy-source content digests, actual composition identity, evaluator executable identity, evidence snapshot identity, and artifact-specific semantic identities. Git metadata remains useful review/navigation provenance but is not required after runtime inputs are materialized.

ADR 0007 accepts the successor line `project-config/v1alpha3`, `composition-lock/v1alpha1`, `assessment-provenance/v1alpha1`, and assessment plan/results v4. Its destination implementation packets are #31–#36. Current v1alpha1/v1alpha2/release-lock v1alpha2 and assessment v1/v3 contracts are unfrozen migration inputs until that cutover completes.

Actual composition provenance and expected enforcement are separate: every successor run records what actually executed; direct expected-source identities or a complete composition lock may additionally refuse mismatches. Expected identity never substitutes for missing actual identity.

## First-core policy and assurance model

The first core has two complementary paths.

Technical assessment:

```text
subject / group assignment
  -> Baseline / BaselineOverlay
      -> technical Control instances
          -> typed evidence
          -> pass / fail / unknown
```

A project may use technical baselines without any requirement/realization wrapper.

Objective/regulatory assurance:

```text
subject / group assignment
  -> RequirementBaseline
      -> internal desired requirement
          -> applicable realization
              -> technical controls
              -> required manual/procedural assurance evidence, if any
          -> objective result
      -> explicit framework/regulatory mapping and coverage claim
```

Requirements are desired assurance objectives. Realizations are design-time mappings, not proof of implementation. Authored adoption/implementation labels cannot create pass. Missing, stale, invalid, or inconclusive required evidence is `unknown`. Realization selection is deterministic and fail-closed; source order is never precedence. Technical results remain independently attributable. Framework mappings are bounded claims and do not imply certification/legal compliance beyond evaluated evidence.

Detailed successor terminology, evidence authority, N/A semantics, mapping/result model, identity, and migration remain owned by destination #37.

## External-adapter boundary

The core ends at provenance-bearing assessment plans/results. It does not own backend configuration compilation, Ansible/cloud-init/Terraform/MDM rendering, backend capability registration, provider credentials/state, approval, execution/apply behavior, or an executable adapter/plugin runtime.

The resolved assessment plan is the external-adapter handoff. It preserves subject/plan identity, actual named source digests, stable control instance and implementation IDs, resolved parameters, definition fingerprints, disposition, derivations, deviations, lineage, source provenance, and requirement/realization lineage where applicable.

An external adapter may consume the complete plan or a documented lossless projection and may emit its own adapter/version/output provenance. Adapter output is not evidence that configuration was approved, applied, persistent, or compliant. Assessment remains valid without an adapter installed.

Removed configuration artifact/compiler/renderer families have no ADR 0007 successor.

## Current development repository

All non-sensitive compliance development source whose information-sharing boundary permits co-location now lives in `packetlss/compliance`:

```text
packetlss/compliance
├── tooling/
├── policy-sources/
│   ├── control-library/policies/      # shared-library
│   └── verification-policy/policies/  # verification-policy
├── projects/
│   ├── mock-fleet/
│   └── server-personas/
├── verification/
│   ├── scenarios/
│   └── fixtures/iam-private-boundary/
├── docs/
├── toolchain/
├── scripts/
├── tests/
└── .github/
```

`tooling/` is the explicit Python/build root; the distribution remains `compliance-tooling`. Repository root is not a Python package root.

The policy roots remain independently named/digested. Co-location does not merge their catalogs. Same-kind/same-identity resources coalesce only when complete definitions are identical; divergence is a hard error.

Each ordinary project remains logically isolated with its own inventory, assignments, fixtures, waivers, and generated-state paths.

Canonical verification scenarios are under `verification/scenarios/` and own the complete composed integration/feature suite: all 20 retained public CLI leaves and 18 retained domain features.

## Private-source boundary

Real need-to-know environments remain in separate authorized repositories/workspaces and execution contexts. Central development must not require restricted inventory, evidence, realizations, parameters, credentials, secrets, provider state, or private full results.

`verification/fixtures/iam-private-boundary/` is a synthetic proof only. Its private `policy/` subtree is physically copied to a distinct temporary `environment-private` source root before execution. Validation rejects symlink/same-inode shortcuts and removes the fixture-side policy from the execution assembly so success cannot depend on recursive central-checkout traversal.

The runtime source set remains explicitly named `shared-library`, `verification-policy`, and `environment-private`; no source has order precedence.

## Policy-source assembly

Projects declare stable named policy sources. Source content identity is calculated from the explicitly supplied semantic root, not from repository/path location.

Source list/file order is nonsemantic. Exact-identical same-identity resources may coalesce with provenance; divergent definitions fail. Customization uses explicit typed resources such as overlays or complete alternative realizations, not last-source-wins merging.

Unlocked development records actual source identities. Expected source guards and locks additionally enforce predeclared identities. These are separate concerns.

## Runtime boundary

Runtime must not require:

- `.git` metadata;
- Git submodule commands;
- mutable branch resolution;
- GitHub access after inputs are acquired; or
- the historical workspace layout.

Generated evidence, plans, results, caches, credentials, adapter outputs, and backend state are runtime/generated state, not authoritative source.

## Release ownership

An independently releasable artifact does not require an independent source repository.

- `tooling/` owns the `compliance-tooling` Python distribution, source/wheel provenance, generic policy-source release validation, and installed/no-Git release gates.
- `policy-sources/control-library/` remains an independently releasable/digestible policy source with provider-neutral descriptor/archive construction.
- `policy-sources/verification-policy/` is source-only with no current independent version/archive/publisher lane.
- Historical releases/tags/assets remain in original historical repositories.

No new publisher, tag namespace, signing/attestation system, registry, or release coordinate is implied by consolidation.

## Validation architecture

Validation has three stable owners:

1. **`component-validation`** — repository/tooling/policy/project/IAM focused gates.
2. **`verification-scenarios`** — canonical non-Git composed integration and complete 20/18 feature coverage.
3. **`installed-release-provenance`** — standalone installed package, locked artifacts, release preparation/tag behavior, and generic policy-source release conformance.

Normal validation uses one repository checkout. It does not use migration-era sibling repository App credentials, PAT fallback, sibling `repository:` checkouts, or repository-coordinate integration manifests.

## Development authority and historical provenance

`packetlss/compliance` owns current non-sensitive development source. Source-domain cutover commits and semantic digests are recorded in `docs/history/pre-consolidation.md`.

Historical `packetlss-labs` component repositories and `compliance-workspace` preserve prior commits, issues, PRs, tags, Releases, assets, architecture, and migration evidence. They are retirement/provenance surfaces, not runtime identity or future implementation authority.

Repository retirement and archival are complete. Active ADR 0007 implementation is routed to #31–#36; detailed assurance design to #37; dormant product-DNA review to #38.

## Compatibility/freeze model

The project remains pre-freeze with no external compatibility consumers. A contract becomes compatibility-bound only through an explicit reviewed freeze. Version-like names and historical artifacts do not themselves create permanent current-reader obligations.

Semantic JSON identity uses contract-specific normalization followed by RFC 8785/JCS where specified. Raw source-tree/artifact identities retain their exact-byte/path construction. Provisional algorithm identifiers remain alpha until explicitly frozen.

## Out of scope

Firewall/network-policy repositories and product work remain outside this project unless explicitly reopened. Consolidation does not authorize cross-product coupling.
