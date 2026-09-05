# System architecture

This document defines the current system-level architecture for `packetlss/compliance`. The accepted architecture decisions are ADRs 0005–0011 in `docs/adr/`.

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

[ADR 0009](adr/0009-active-compliance-vocabulary.md) intentionally renames the maintained reusable semantic source from `shared-library` to `control-library`. The component path `policy-sources/control-library/`, semantic root `policy-sources/control-library/policies/`, and distribution `compliance-control-library` remain distinct namespaces; tooling receives source names explicitly. The name grants no precedence, trust, mandatory dependency, or reserved role. Policy-tree content identity is unchanged, while name-bearing composition/provenance identities change without a compatibility alias.

ADR 0007 `composition-lock` is the sole forward complete expected-composition abstraction. `release-lock/v1alpha2` is only a temporary migration contract pending #33. The #57 `workspace-config` → `project-registry` cutover is implemented: the registry selects one project configuration by explicit name or default without composing policy or merging project state. Registry data/location and repository/workspace topology are nonsemantic; the retired discriminator is unsupported without an alias. The changed tooling source bytes affect only existing tooling provenance; technical control/assurance resource names remain unchanged pending #37.

## Primary intended user jobs

The system preserves decided security intent through policy resolution, technical realization, infrastructure handoff, independent evidence, assessment, and explanation. Infrastructure tooling, repository topology, and evidence-collection mechanisms do not become authoritative for policy meaning.

These jobs describe the intended product scope of the accepted core, not a claim that every operator workflow is complete in the current CLI.

- **Policy owner:** trace a decided policy objective or technical policy to the concrete technical criteria intended to realize it. This includes direct technical policy through `Baseline` / `BaselineOverlay` and optional higher-level objectives through requirement → realization → technical controls, with resolved parameters, lineage, deviations, exclusions, and source provenance. An authored realization describes design intent; it does not prove deployment or effectiveness.
- **Security operator:** determine whether decided technical controls are actually satisfied and understand policy and assessment coverage. Keep a decided criterion's `pass` / `fail` / `unknown` / `error` assessment state distinct from unassigned scope, explicit exclusions or deviations, an absent realization for an assigned objective, missing or stale evidence, and broader security conditions with no identified active criterion. Passing assigned controls does not prove complete security-policy coverage. Discovery of observed-but-unaddressed security conditions is a separate future capability, not an implemented assessment claim.
- **Infrastructure operator:** consume exact resolved, subject-scoped technical intent with provenance and integrate it into independently owned infrastructure tooling. External systems may translate the assessment plan into Ansible, Terraform, MDM, cloud-init, ticketing, configuration-management, or other delivery mechanisms, within the [external-adapter boundary](#external-adapter-boundary). Backend capability selection, configuration compilation, credentials, approvals, execution/apply, and provider state remain outside the core. Generated configuration does not establish that intended state was deployed or remains effective.
- **Auditor / reviewer:** obtain attributable evidence and explanations of whether decided controls were satisfied, failed, unknown, waived, or otherwise qualified, with the provenance needed to understand the conclusion. Provenance identifies the inputs and execution used; it does not itself authenticate observation truth or approval authority. A point-in-time assessment is not automatically proof of continuous effectiveness. Framework mappings are bounded assurance claims, not automatic certification or legal-compliance claims.
- **Evidence operator:** understand evidence demand and health: required evidence types, the subjects and controls requiring them, freshness requirements, missing/stale/invalid/otherwise unusable evidence, and the assessment outcomes blocked by those problems. This is an intended product job even though the current CLI does not provide a complete evidence-operator workflow. It does not introduce a new evidence resource or collection-failure taxonomy.

These jobs do not themselves settle evidence or temporal interpretation. [ADR 0010](adr/0010-required-evidence-status-and-assessment-refusal.md) owns assessment-time evidence validity/status/refusal, and [ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md) owns immutable history, exact plan alignment and derived operational evidence timeliness. Detailed manual/procedural assurance and N/A remain with #37; policy-gap discovery, evidence-operator CLI design, collector failure taxonomy and durable evidence retention remain separate work. Point-in-time assessments cannot establish continuous effectiveness.

### Assessment-plan meaning

`assessment-plan` remains the artifact name and responsibility boundary. Semantically, it carries resolved, subject-scoped security intent for decided, modeled policy, together with the assessment-specific information required to evaluate that intent. This is why the same plan is the external-adapter handoff described below. [ADR 0006](adr/0006-regulatory-assurance-and-external-adapter-boundary.md) and [ADR 0007](adr/0007-unified-actual-and-expected-composition-provenance.md) retain one plan responsibility: no rename, split, or second in-core adapter-input/configuration artifact is implied.

The plan is not:

- a complete inventory of all security concerns or proof that all meaningful security decisions have been made;
- a backend configuration specification or authorization to apply changes; or
- evidence that settings were deployed or remain effective at the present moment.

This clarifies existing artifact meaning, not a new payload or readiness claim: #31 establishes the composition foundation, while v1alpha3 assessment artifact generation remains unavailable until the v4 implementation owned by #32.

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

[ADR 0010](adr/0010-required-evidence-status-and-assessment-refusal.md) owns the common required-evidence `unknown`, attributable execution `error`, and assessment-wide refusal boundary. It clarifies ADRs 0006/0007; #32 implements its schema-invalid-evidence and evidence selection ambiguity corrections as the only semantic preservation exceptions after #31. This is accepted design, not yet runtime behavior. #31 remains independent and unblocked; broader assurance design remains with #37.

## Historical assessment and operational interpretation

[ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md) is **accepted design, not yet implemented**. Historical outcomes remain immutable at `evaluated_at` under their exact plan, evidence snapshot, evaluator, planning/evaluation composition and waiver revision/application. Exact current `plan_id` equality means only **Plan-aligned**; a mismatch, including provenance-only differences, means **Different plan**.

At query instant `q`, evidence timeliness is derived from the historical successful selections and the assessed plan's recorded requirements (`q - collected_at <= max_age`, equality included). No mutable evidence substitution, query-time re-selection or historical roll-up recomputation is allowed. Historical `waived` remains waived after expiry; recorded waiver validity is qualified separately. Outcome, alignment, timeliness, waiver validity and coverage/applicability aggregate independently under ADR 0011's state matrix. Neither plan alignment nor timely evidence establishes present-state certainty, absence of drift, or continuous effectiveness.

#32 must retain validated, identity-bound selection references (evidence ID plus complete-document digest), selected `collected_at`, and unambiguous assessed-plan requirement associations resolving `max_age`, with references into the complete snapshot and successful selections distinguished from nonselected candidates. Existing evidence identity and ADR 0010 assessment semantics are unchanged. #32 owns this representation obligation, not query-time judgments. A later separately authorized operational view depends on #32; no runtime implementation or new artifact family is authorized by #66.

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
│   ├── control-library/policies/      # control-library
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

The runtime source set remains explicitly named `control-library`, `verification-policy`, and `environment-private`; no source has order precedence.

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
