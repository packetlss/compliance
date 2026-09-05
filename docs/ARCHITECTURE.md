# System architecture

This document defines the current system-level architecture for `packetlss/compliance`. The accepted architecture decisions are ADRs 0005–0015 in `docs/adr/`.

Historical `packetlss-labs/compliance-workspace` architecture remains migration/design provenance. After this documentation-authority transfer, this repository owns current normative system architecture.

## Semantic composition

The product composition model is:

```text
tooling + N named policy sources + project inputs
```

A policy source is an independently named/materialized semantic input. Repository names, Git revisions, checkout paths, source roles, acquisition URLs, and source/file order are not policy identity or precedence.

Canonical runtime/generated-artifact provenance is content-addressed. Preserve the applicable tooling source/distribution identity, policy-source content digests, actual composition identity, evaluator executable identity, evidence snapshot identity, and artifact-specific semantic identities. Git metadata remains useful review/navigation provenance but is not required after runtime inputs are materialized.

ADR 0007 accepts the successor line `project-config/v1alpha3`, `composition-lock/v1alpha1`, `assessment-provenance/v1alpha1`, and assessment plan/results v4. Its destination implementation packets are #31–#36. Consumer cutover is complete; #33 retires the predecessor config, release-lock, and assessment readers. Historical artifacts require historical tooling.

Actual composition provenance and expected enforcement are separate: every successor run records what actually executed; direct expected-source identities or a complete composition lock may additionally refuse mismatches. Expected identity never substitutes for missing actual identity.

[ADR 0009](adr/0009-active-compliance-vocabulary.md) intentionally renames the maintained reusable semantic source from `shared-library` to `control-library`. The component path `policy-sources/control-library/`, semantic root `policy-sources/control-library/policies/`, and distribution `compliance-control-library` remain distinct namespaces; tooling receives source names explicitly. The name grants no precedence, trust, mandatory dependency, or reserved role. Policy-tree content identity is unchanged, while name-bearing composition/provenance identities change without a compatibility alias.

ADR 0007 `composition-lock` is the sole forward complete expected-composition abstraction. The #57 `workspace-config` → `project-registry` cutover is implemented: the registry selects one project configuration by explicit name or default without composing policy or merging project state. Registry data/location and repository/workspace topology are nonsemantic; the retired discriminator is unsupported without an alias. The changed tooling source bytes affect only existing tooling provenance; technical control/assurance resource names remain unchanged pending #37.

## Primary intended user jobs

The system preserves decided security intent through policy resolution, technical realization, infrastructure handoff, independent evidence, assessment, and explanation. Infrastructure tooling, repository topology, and evidence-collection mechanisms do not become authoritative for policy meaning.

These jobs describe the intended product scope of the accepted core, not a claim that every operator workflow is complete in the current CLI.

- **Policy owner:** trace a decided policy objective or technical policy to the concrete technical criteria intended to realize it. This includes direct technical policy through `Baseline` / `BaselineOverlay` and optional higher-level objectives through requirement → realization → technical controls, with resolved parameters, lineage, deviations, exclusions, and source provenance. An authored realization describes design intent; it does not prove deployment or effectiveness.
- **Security operator:** determine whether decided technical controls are actually satisfied and understand policy and assessment coverage. Keep a decided criterion's `pass` / `fail` / `unknown` / `error` assessment state distinct from unassigned scope, explicit exclusions or deviations, an absent realization for an assigned objective, missing or stale evidence, and broader security conditions with no identified active criterion. Passing assigned controls does not prove complete security-policy coverage. Discovery of observed-but-unaddressed security conditions is a separate future capability, not an implemented assessment claim.
- **Infrastructure operator:** consume exact resolved, subject-scoped technical intent with provenance and integrate it into independently owned infrastructure tooling. External systems may translate the assessment plan into Ansible, Terraform, MDM, cloud-init, ticketing, configuration-management, or other delivery mechanisms, within the [external-adapter boundary](#external-adapter-boundary). Backend capability selection, configuration compilation, credentials, approvals, execution/apply, and provider state remain outside the core. Generated configuration does not establish that intended state was deployed or remains effective.
- **Auditor / reviewer:** obtain attributable evidence and explanations of whether decided controls were satisfied, failed, unknown, waived, or otherwise qualified, with the provenance needed to understand the conclusion. Provenance identifies the inputs and execution used; it does not itself authenticate observation truth or approval authority. A point-in-time assessment is not automatically proof of continuous effectiveness. Framework mappings are bounded assurance claims, not automatic certification or legal-compliance claims.
- **Evidence operator:** understand evidence demand and health: required evidence types, the subjects and controls requiring them, freshness requirements, missing/stale/invalid/otherwise unusable evidence, and the assessment outcomes blocked by those problems. This is an intended product job even though the current CLI does not provide a complete evidence-operator workflow. It does not introduce a new evidence resource or collection-failure taxonomy.

These jobs do not themselves settle evidence or temporal interpretation. [ADR 0010](adr/0010-required-evidence-status-and-assessment-refusal.md) owns assessment-time evidence validity/status/refusal, and [ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md) owns immutable history, exact plan alignment and derived operational evidence timeliness. ADRs 0013–0015 below own accepted scoped-claim, applicability/N/A authority and recognition semantics; manual/procedural methodology and sampling inference remain with #37; policy-gap discovery, evidence-operator CLI design, collector failure taxonomy and durable evidence retention remain separate work. Point-in-time assessments cannot establish continuous effectiveness.

### Assessment-plan meaning

`assessment-plan` remains the artifact name and responsibility boundary. Semantically, it carries resolved, subject-scoped security intent for decided, modeled policy, together with the assessment-specific information required to evaluate that intent. This is why the same plan is the external-adapter handoff described below. [ADR 0006](adr/0006-regulatory-assurance-and-external-adapter-boundary.md) and [ADR 0007](adr/0007-unified-actual-and-expected-composition-provenance.md) retain one plan responsibility: no rename, split, or second in-core adapter-input/configuration artifact is implied.

The plan is not:

- a complete inventory of all security concerns or proof that all meaningful security decisions have been made;
- a backend configuration specification or authorization to apply changes; or
- evidence that settings were deployed or remain effective at the present moment.

This clarifies existing artifact meaning, not a new payload or readiness claim: #31 establishes the composition foundation, and #32 implements v1alpha3 assessment generation through provenance-bearing v4 plans/results.

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

Destination [#37](https://github.com/packetlss/compliance/issues/37) remains the open parent assurance architecture effort. ADR 0012 and bounded successor #73 own parameter/freshness resolution; ADRs 0013–0015 below own accepted scoped assurance, applicability authority and external claims. Residual methodology and repository-grounded migration planning remain with #37; promotion does not complete that issue.

[ADR 0010](adr/0010-required-evidence-status-and-assessment-refusal.md) owns the common required-evidence `unknown`, attributable execution `error`, and assessment-wide refusal boundary. It clarifies ADRs 0006/0007; #32 implements its schema-invalid-evidence and evidence selection ambiguity corrections as the only semantic preservation exceptions after #31. These corrections are implemented in the sole supported v4 path. #31 is complete; broader assurance design remains with #37.

## Explicit policy parameters and freshness

[ADR 0012](adr/0012-explicit-policy-parameter-resolution.md) is **accepted design, not yet implemented** under #37; [#73](https://github.com/packetlss/compliance/issues/73) owns the coordinated schema/runtime/consumer migration. Its common model is declaration → explicit binding → optional explicit descendant tailoring → concrete effective value → explicit dependency consumption → resolved assessment plan. Required unresolved parameters and independently applicable divergent bindings prevent an assessable plan. Source/file order, ancestry, assignment scope or specificity, strictness and min/max never choose values; constraints and JSON Schema defaults cannot manufacture them.

Requirement slots have stable technology-neutral identity with exact declaration/revision/type-schema pins. Realizations retain explicit typed links into required dependency inputs; plans materialize every linked value with immutable provenance, and evaluation does not resolve parameters again. Technical destinations belong to an exact resolved implementation/interface, including after substitution. Selected derivation permits explicit tailoring; independently assigning divergent ancestor and descendant policies is a conflict.

Effective evidence `max_age` belongs to policy/baseline/requirement intent. Controls retain evidence dependency contracts and optional capability restrictions; realizations link semantic freshness slots where applicable. Current Control-owned ages and literal-input schemas remain executable migration inputs until #73 cuts over all affected consumers. ADR 0010 still owns assessment-time evidence semantics and ADR 0011 immutable historical selection attribution; the future-timestamp question is unchanged.

Policy resolution determines company intent; external conformity compares it with explicit external conditions; assessment tests evidence against that company intent. Passing company policy does not establish an external framework claim. Fixed/open external binding restrictions do not authenticate issuer authority; ADR 0014 owns the accepted narrow authority-consumption contract, outside #73. Missing realization/coverage gaps remain distinct from unresolved parameters and missing evidence. Ordinary named private policy sources need no new resource family or precedence. ADR 0012 extends the existing provenance-bearing plan, not the adapter or authorization artifact surface.

## Scoped assurance, applicability and bounded external claims

[ADR 0013](adr/0013-scoped-assurance-and-obligation-instances.md),
[ADR 0014](adr/0014-attributable-applicability-and-authority-acceptance.md) and
[ADR 0015](adr/0015-bounded-external-claims-and-assurance-recognition.md) are
**accepted design, not yet implemented**, promoted under #37. Their conceptual
vectors and migration tables are normative successor obligations, not current
schema/runtime support.

Operational scope, assessment/beneficiary coverage and claim population are
distinct. Broad operations do not enlarge a claim. Population completeness needs
an exact enumeration and an attributable basis establishing it as exhaustive for
the claimed domain at one explicit assessment instant `t`. An explicitly named-set
claim speaks only for that set. Existing Subject/InventoryGroup/PolicyAssignment
remain the foundation: union overlap over stable identities, retain all paths,
and fail closed on cycles, unresolved references or ambiguous correlations.
Entity identity does not enumerate owned assets. Accepted basis semantics must
establish state at `t`, without requiring physical snapshot capture exactly then.
Direct local assessments share `t`; imported cross-time results need separately
qualified semantics. Historical membership changes never rewrite claims.

```text
attributable fact/determination + accepted applicability basis
    -> exact applicability decision
external/company obligation + exact governed scope + resolved applicability
    -> exact obligation instance
```

The completeness denominator is the exact resolved set of obligation instances,
not all requirements multiplied by all members. Host, system and entity obligations
retain their actual quantification. Common assurance contributes only through
explicit scoped consumption and admissible integration evidence where needed.

Applicability is distinct from satisfaction and from company policy adoption.
Determinations preserve exact assertion/revision/content (including an assertion
within a document), source-owned vocabulary/schema, issuer/provenance, scope and
quantification, validity/conditions, pinned destination acceptance basis,
consuming decision/obligations and rationale/conflicts/rejected or unresolved facts.
The core consumes an exact governance/policy acceptance decision; names, digests,
issuer labels, approval references and signatures alone do not establish authority.
Compatible determinations may accumulate obligations; contradictory overlap stays
unresolved without an exact accepted replacement relation. Missing, expired,
narrower or unavailable authority never establishes N/A. There is no generic
IAM/reviewer verifier or unified Determination abstraction for population,
applicability and recognition.

An external claim requires both an established population and exhaustive accounting
of every applicable instance. Pin scheme/revision, profile/target, authoritative
external obligation denominator or exact accepted basis, population proposition,
`t` and permitted qualifications/exclusions. Outside-claim follows only that explicit
target. Retain every relevant obligation through applicability, company interpretation,
exact requirements, mapping/conformity, realization/dependencies and residual gaps.
Passing existing checks or accumulating partial mappings cannot establish completeness.
A legitimate empty applicable set establishes no positive conformity/certification.

Alignment means correspondence; evidence support is independently judged by the
consuming dependency; required external assurance requires qualifying possession;
authoritative recognition grants an exact external result a defined effect under
a pinned accepted destination rule. Recognition satisfies a named dependency before
normal roll-up, never overwrites an objective/framework result. No automatic
transitivity, equivalence, fallback/anyOf, ID matching or min/max recognition follows.
Qualified external statements retain exact assertion/result, issuer/scheme/revision,
holder/scope/exclusions, time/qualifications, local correlation, provenance and
acceptance. Unknown scope and corporate relationships cannot broaden certification.
Exact normalized assertion and relevant source-byte attribution suffice; no generic
attachment family is required.

### Claim inability, evidence outcomes and refusal

Safely attributable inability to establish a particular population, applicability
decision, obligation denominator, mapping/coverage or recognition effect leaves
the bounded claim unestablished. Independently valid technical/objective assessment
remains publishable where its own plan is valid. This is not automatically ADR 0010
refusal and must not silently become evidence `unknown`.

Evidence insufficiency after valid dependency resolution follows ADR 0010. Shared
plan/routing/composition/provenance/snapshot/evaluator/result-envelope integrity
failures preventing trustworthy publication require ADR 0010 refusal. ADR 0012's
unresolved required-policy boundary remains unchanged. Missing interpretation and
missing realization remain distinct; preserve design-time realizations, exactly-one
selection, conservative roll-up, fail-only waivers and standalone technical baselines.

### Sequencing and remaining architecture

Complete #73 independently, then plan ADRs 0013–0015 together against the actual
post-#73 representation under #37. Default to one coordinated successor migration
across shared plans/results, dependencies, evidence, mapping and claims. Split
implementation issues only when investigation proves independently complete cutovers
without transient schemas, duplicated migration or compatibility scaffolding.

#37 remains open for manual/procedural methodology and evidence qualification,
sampling inference, remaining assurance terminology/adopter annotations and
unresolved result/representation questions. Route blocking questions there before
implementation relies on them. ADR 0015 records the migration table and escalation
conditions; probabilistic completeness, dynamic scope, generic delegation, automatic
supersession, cross-time equivalence, generic artifacts or changed technical evidence
selection/roll-up require architecture. No wire/version/algorithm freeze, runtime
change, monitoring or ADR 0011 operational-view redesign is implied.

## Historical assessment and operational interpretation

[ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md) has its factual v4 representation implemented under #32; the operational view remains **accepted design, not yet implemented**. Historical outcomes remain immutable at `evaluated_at` under their exact plan, evidence snapshot, evaluator, planning/evaluation composition and waiver revision/application. Exact current `plan_id` equality means only **Plan-aligned**; a mismatch, including provenance-only differences, means **Different plan**.

At query instant `q`, evidence timeliness is derived from the historical successful selections and the assessed plan's recorded requirements (`q - collected_at <= max_age`, equality included). No mutable evidence substitution, query-time re-selection or historical roll-up recomputation is allowed. Historical `waived` remains waived after expiry; recorded waiver validity is qualified separately. Outcome, alignment, timeliness, waiver validity and coverage/applicability aggregate independently under ADR 0011's state matrix. Neither plan alignment nor timely evidence establishes present-state certainty, absence of drift, or continuous effectiveness.

#32 retains validated, identity-bound selection references (evidence ID plus complete-document digest), selected `collected_at`, and unambiguous assessed-plan requirement associations resolving `max_age`, with references into the complete snapshot and successful selections distinguished from nonselected candidates. Existing evidence identity and ADR 0010 assessment semantics are unchanged. #32 owns this representation obligation, not query-time judgments. A later separately authorized operational view depends on #32; no runtime implementation or new artifact family is authorized by #66.

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

Repository retirement and archival are complete. ADR 0007 foundation/cutover issues #31–#36 are completed history. Active assurance architecture and post-#73 coordinated migration planning remain with #37; #73 owns only ADR 0012 implementation. Dormant product-DNA review remains with #38.

## Compatibility/freeze model

The project remains pre-freeze with no external compatibility consumers. A contract becomes compatibility-bound only through an explicit reviewed freeze. Version-like names and historical artifacts do not themselves create permanent current-reader obligations.

Semantic JSON identity uses contract-specific normalization followed by RFC 8785/JCS where specified. Raw source-tree/artifact identities retain their exact-byte/path construction. Provisional algorithm identifiers remain alpha until explicitly frozen.

## Out of scope

Firewall/network-policy repositories and product work remain outside this project unless explicitly reopened. Consolidation does not authorize cross-product coupling.
