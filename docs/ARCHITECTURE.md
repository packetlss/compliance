# System architecture

This document defines the current system-level architecture for `packetlss/compliance`. The accepted architecture decisions are ADRs 0005–0012 and 0016–0018 (ADRs 0013–0015 are superseded) in `docs/adr/`.

Historical `packetlss-labs/compliance-workspace` architecture remains migration/design provenance. After this documentation-authority transfer, this repository owns current normative system architecture.

## Semantic composition

The product composition model is:

```text
tooling + N named policy sources + project inputs
```

A policy source is an independently named/materialized semantic input. Repository names, Git revisions, checkout paths, source roles, acquisition URLs, and source/file order are not policy identity or precedence.

Canonical runtime/generated-artifact provenance is content-addressed. Preserve the applicable tooling source/distribution identity, policy-source content digests, actual composition identity, evaluator executable identity, evidence snapshot identity, and artifact-specific semantic identities. Git metadata remains useful review/navigation provenance but is not required after runtime inputs are materialized.

ADR 0007 accepts the successor line `project-config/v1alpha3`, `composition-lock/v1alpha1`, `assessment-provenance/v1alpha1`, and assessment plan/results v4. Its destination implementation packets are #31–#36. Consumer cutover is complete; #33 retires the predecessor config, release-lock, and assessment readers. Historical artifacts require historical tooling.

Before result identity freeze, [#90](https://github.com/packetlss/compliance/issues/90)
replaces the duplicated self-contained result representation with an
exact retained `{bound plan, result}` historical pair. The bound plan owns resolved
intent, operation membership, planning composition/enforcement, parameters,
dependencies, mappings, and plan semantics. The result owns the immutable conclusion
and evaluation-stage provenance. This experimental implementation adds no core
storage/history/run/discovery subsystem or compatibility reader.

Actual composition provenance and expected enforcement are separate: every successor run records what actually executed; direct expected-source identities or a complete composition lock may additionally refuse mismatches. Expected identity never substitutes for missing actual identity.

[ADR 0009](adr/0009-active-compliance-vocabulary.md) intentionally renames the maintained reusable semantic source from `shared-library` to `control-library`. The component path `policy-sources/control-library/`, semantic root `policy-sources/control-library/policies/`, and distribution `compliance-control-library` remain distinct namespaces; tooling receives source names explicitly. The name grants no precedence, trust, mandatory dependency, or reserved role. Policy-tree content identity is unchanged, while name-bearing composition/provenance identities change without a compatibility alias.

ADR 0007 `composition-lock` is the sole forward complete expected-composition abstraction. The #57 `workspace-config` → `project-registry` cutover is implemented: the registry selects one project configuration by explicit name or default without composing policy or merging project state. Registry data/location and repository/workspace topology are nonsemantic; the retired discriminator is unsupported without an alias. The changed tooling source bytes affect only existing tooling provenance; technical control/assurance resource names remain unchanged pending #37.

## Primary intended user jobs

The system preserves decided security intent through policy resolution, technical realization, infrastructure handoff, independent evidence, assessment, and explanation. Infrastructure tooling, repository topology, and evidence-collection mechanisms do not become authoritative for policy meaning.

These jobs describe the intended product scope of the accepted core, not a claim that every operator workflow is complete in the current CLI.

- **Policy owner:** trace a decided policy objective or technical policy to the concrete technical criteria intended to realize it. This includes direct technical policy through `Baseline` / `BaselineOverlay` and optional higher-level objectives through requirement → realization → technical controls, with resolved parameters, lineage, deviations, exclusions, and source provenance. An authored realization describes design intent; it does not prove deployment or effectiveness.
- **Security operator:** determine whether decided technical controls are actually satisfied and understand policy and assessment coverage. Keep a decided criterion's `pass` / `fail` / `unknown` / `error` assessment state distinct from unassigned scope, explicit exclusions or deviations, an absent realization for an assigned objective, missing or stale evidence, and broader security conditions with no identified active criterion. Passing assigned controls does not prove complete security-policy coverage. Discovery of observed-but-unaddressed security conditions is a separate future capability, not an implemented assessment claim.
- **Infrastructure operator:** consume exact resolved, subject-scoped technical intent with provenance and integrate it into independently owned infrastructure tooling. External systems may translate the assessment plan into Ansible, Terraform, MDM, cloud-init, ticketing, configuration-management, or other delivery mechanisms, within the [external-adapter boundary](#external-adapter-boundary). Backend capability selection, configuration compilation, credentials, approvals, execution/apply, and provider state remain outside the core. Generated configuration does not establish that intended state was deployed or remains effective.
- **Auditor / reviewer:** obtain attributable evidence and explanations of whether decided controls were satisfied, failed, unknown, waived, or otherwise qualified, with the provenance needed to understand the conclusion. Provenance identifies the inputs and execution used; it does not itself authenticate observation truth or approval authority. A point-in-time assessment is not automatically proof of continuous effectiveness. Framework mappings are attributable reporting content, not engine-established certification or legal-compliance conclusions.
- **Evidence operator:** understand evidence demand and health: required evidence types, the subjects and controls requiring them, freshness requirements, missing/stale/invalid/otherwise unusable evidence, and the assessment outcomes blocked by those problems. This is an intended product job even though the current CLI does not provide a complete evidence-operator workflow. It does not introduce a new evidence resource or collection-failure taxonomy.

These jobs do not themselves settle evidence or temporal interpretation. [ADR 0010](adr/0010-required-evidence-status-and-assessment-refusal.md) owns assessment-time evidence validity/status/refusal, and [ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md) owns immutable history, exact plan alignment and derived operational evidence timeliness. ADR 0016 below owns the closed-world responsibility boundary; manual/procedural methodology and sampling inference remain with #37; policy-gap discovery, evidence-operator CLI design, collector failure taxonomy and durable evidence retention remain separate work. Point-in-time assessments cannot establish continuous effectiveness.

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

Optional company objective assurance:

```text
subject / group assignment
  -> RequirementBaseline
      -> internal desired requirement
          -> applicable realization
              -> technical controls
              -> required manual/procedural assurance evidence, if any
          -> objective result
      -> attributable framework/regulatory mapping and bounded company reporting
```

Requirements are desired assurance objectives. Realizations are design-time mappings, not proof of implementation. Authored adoption/implementation labels cannot create pass. Missing, stale, invalid, or inconclusive required evidence is `unknown`. Realization selection is deterministic and fail-closed; source order is never precedence. Technical results remain independently attributable. Framework mappings are attributable policy/reporting content and do not establish external conformity or certification/legal compliance.

Destination [#37](https://github.com/packetlss/compliance/issues/37) remains the open parent assurance architecture effort. ADR 0012 and bounded successor #73 own parameter/freshness resolution; ADR 0016 below supersedes ADRs 0013–0015 with closed-world assessment. Residual methodology and narrow repository-grounded exploration remain with #37; promotion does not complete that issue.

[ADR 0010](adr/0010-required-evidence-status-and-assessment-refusal.md) owns the common required-evidence `unknown`, attributable execution `error`, and assessment-wide refusal boundary. It clarifies ADRs 0006/0007; #32 implements its schema-invalid-evidence and evidence selection ambiguity corrections as the only semantic preservation exceptions after #31. These corrections are implemented in the sole supported v4 path. #31 is complete; broader assurance design remains with #37.

The implemented evidence core supports required dependencies only: every
declared dependency is required by definition and has no optionality
discriminator. Typed envelopes have no normative collector-supplied
`integrity.digest`; unchanged complete-document and evidence-set digests bind
the exact snapshot used by assessment. Opaque extensions remain ordinary
complete-document content and do not acquire integrity semantics.

## Source-authored policy and check meaning

[ADR 0017](adr/0017-source-authored-policy-and-check-meaning.md) accepts the
minimum human vocabulary needed to explain resolved policy without another policy
hierarchy. Each assignable `Baseline`, `BaselineOverlay`, and
`RequirementBaseline` owns a required title. Each reusable `Control` owns a
required intrinsic check title and purpose. Existing `ControlRequirement` title
and statement continue to own Objective meaning; effective parameters, overlay
derivations, deviations, exclusions, and remediation keep their separate roles.

The authored words are identity-bearing policy meaning but never executable input.
They must be frozen into active and excluded plan records so normal explanation can
lead with human meaning while advanced views retain stable IDs, fingerprints,
digests, lineage, and named-source provenance. Overlays and realizations cannot
override intrinsic Control title or purpose, and divergent same-identity text fails
closed under the existing exact-definition rule. Technical-only policy does not
synthesize an Objective.

ADR 0017 requires the plan artifact, when retained, to contain enough authored
meaning for offline interpretation. It does not make the core a plan or result
retention service: external users and orchestration decide whether to retain these
artifacts. The coordinated schema/source/plan/reporter migration is not implemented
or authorized by ADR 0017; its bounded promotion contract is recorded in that ADR.

## Explicit policy parameters and freshness

[ADR 0012](adr/0012-explicit-policy-parameter-resolution.md) is implemented under [#73](https://github.com/packetlss/compliance/issues/73). The [experimental parameter contract](../tooling/docs/policy-parameters.md) defines the coordinated schema/runtime/consumer representation. Its common model is declaration → explicit binding → optional explicit descendant tailoring → concrete effective value → explicit dependency consumption → resolved assessment plan. Required unresolved parameters and independently applicable divergent bindings prevent an assessable plan. Source/file order, ancestry, assignment scope or specificity, strictness and min/max never choose values; constraints and JSON Schema defaults cannot manufacture them.

Requirement slots have stable technology-neutral identity with exact declaration/revision/type-schema pins. Realizations retain explicit typed links into required dependency inputs; plans materialize every linked value with immutable provenance, and evaluation does not resolve parameters again. Technical destinations belong to an exact resolved implementation/interface, including after substitution. Selected derivation permits explicit tailoring; independently assigning divergent ancestor and descendant policies is a conflict.

Effective evidence `max_age` belongs to policy/baseline/requirement intent. Controls retain evidence dependency contracts and optional capability restrictions; realizations link semantic freshness slots where applicable. Maintained baselines bind effective ages explicitly; objective realizations consume pinned semantic freshness slots. Controls no longer provide effective-age defaults. ADR 0010 still owns assessment-time evidence semantics and ADR 0011 immutable historical selection attribution; the future-timestamp question is unchanged.

Policy resolution determines company intent; assessment tests evidence against that
intent. Passing company policy does not establish external conformity. ADR 0016
places external comparison outside the generic core unless a future explicit company
policy dependency models a concrete condition. Fixed/open external binding restrictions
do not authenticate issuer authority. Missing realization/coverage gaps remain distinct
from unresolved parameters and missing evidence. Ordinary named private policy sources
need no new resource family or precedence. ADR 0012 extends the existing provenance-bearing
plan, not the adapter or authorization artifact surface.

## Closed-world policy assessment

[ADR 0016](adr/0016-closed-world-policy-assessment.md) supersedes ADRs 0013–0015
and is **experimental, implemented under #78**. The core evaluates explicitly
supplied company policy against attributable reality. Governance owns inventory
exhaustiveness, external applicability and the legal/regulatory sufficiency of
chosen policy and demonstration. Optional company objective assurance remains core
under ADR 0006; engine-established external conformity/certification does not.

```text
supplied inventory -> deterministic groups -> applicable assignments
    -> exact resolved policy/requirement instances
    -> expected assessment set -> attributable results
```

Preserve Subject identity, InventoryGroup DAG semantics, PolicyAssignment resolution,
all membership/assignment paths, deterministic conflicts and exact governed subjects.
Host/entity/system requirements retain their quantification; do not form a Cartesian
product. The core accounts for the exact expected assessment set of the
supplied operation and detect omitted results. A/B passing supports exact A/B target
success; unsupplied real-world C is outside that guarantee. Supplied A/B/C with C's
result absent cannot produce aggregate success. No ClaimScope, PopulationSnapshot,
external completeness artifact or parallel inventory hierarchy is introduced. #78
selects only the embedded frozen operation projection.

Policy determines requirements and accepted demonstration; governance owns why
those choices are appropriate; evidence asserts facts about reality; the core tests
admissible evidence against resolved policy. Authored adoption, implementation,
issuer/approval/signature references, mappings or digests cannot manufacture pass.
Content-addressed provenance identifies inputs without endorsing their truth,
authority or legal sufficiency.

A required dependency identifies its evidence contract; only attributable evidence
satisfying it may determine the dependency. Certificate/assurance fields are required
only by the selected evidence type/schema/dependency contract, not a universal
certificate model. A's evidence cannot satisfy B without the exact legitimate
consumer/beneficiary relationship. Common assurance needs an explicit named
beneficiary dependency, attributable source assurance and required correlation/
integration evidence. Typed evidence may suffice; direct assessment-result
consumption is not required and would need separate architecture review for graph,
cycle and temporal semantics.

Framework/reference mappings are attributable policy-authoring/reporting content.
A supplied company target P revision R containing O1/O2/O3 cannot silently omit O2;
its list is not an authoritative external obligation universe. Report only exact
resolved company policy/scope, for example: “All required instances in company
target P revision R passed for resolved subjects A and B.” Do not upgrade this to
all-assets compliance, framework satisfaction or certification/legal conformity.
External conformity comparison is outside the generic core unless a future explicit
company-policy dependency models a concrete condition. ADR 0012 remains unchanged.

### Preserved failure and N/A boundaries

Unresolved groups, cycles, ambiguous identities, conflicting assignments/policy,
unresolved required parameters, invalid dependency targets and integrity/tampering
fail closed. Required unresolved policy is non-assessable, not evidence `unknown`.
After valid dependency resolution, missing/stale/invalid/inconclusive evidence is
ADR 0010 `unknown`, attributable execution failures are `error`, and shared integrity
preventing trustworthy publication requires refusal. Preserve design-time realizations,
exactly-one selection, separate missing-realization coverage/failure behavior,
conservative roll-up, fail-only waivers and immutable result attribution.

No assignment is unassigned/outside supplied assessment scope, not automatic N/A.
Existing explicit N/A remains distinct pending separate architecture review. Never
infer external N/A from absent assignments, evidence or realizations.

### Deliberate narrowing and implementation routing

The core relinquishes external real-world inventory exhaustiveness, authoritative
external obligation-universe completeness, external legal/applicability authority
conflicts or supersession, generic destination recognition authority and independent
external conformity conditions. Exact supplied-policy/scope provenance, bounded
reporting and ordinary explicit assurance dependencies mitigate this narrowing.
There is no separate runtime applicability/authority-acceptance/recognition engine
or mandatory external completeness gate.

[#78](https://github.com/packetlss/compliance/issues/78) implements embedded frozen
operation accounting and concrete external assertions through existing typed evidence;
[#87](https://github.com/packetlss/compliance/issues/87) simplifies its pre-freeze
selection, member commitment, operation identity and bound-plan representation.
The [operation contract](../tooling/docs/operation-accounting.md) specifies exact
selection, membership, plan identity, result matching and historical reporting.
#37 remains open for residual architecture and mandatory escalation. No direct result
graph, external conformity engine or certificate subsystem is introduced.

## Historical assessment and operational interpretation

[ADR 0011](adr/0011-historical-assessment-and-operational-evidence-timeliness.md)
has its original factual v4 representation implemented under #32 and its derived
historical operational view under #80. #90 makes the exact
assessed bound plan plus its result the historical assertion: the plan owns planning
composition/enforcement and resolved policy meaning; the result retains immutable
outcomes, actual evaluation composition/enforcement, evaluator identity, complete
evidence snapshot identity, exact successful selections, and exact applied-waiver
facts. Exact operation-bound `plan_id` equality means only **Plan-aligned**; a
mismatch, including provenance-only differences, means **Different plan**.

Historical interpretation is conditional on retention by the surrounding operating
environment. The core does not require or own long-term retention of assessment
plans or results, and a new assessment does not read or depend on prior outcomes.
Retaining the required historical artifacts enables later historical views; deleting
them removes that historical capability but does not affect future assessments.
An orphaned result can expose raw recorded facts but cannot support full policy,
timeliness, requirement, or alignment interpretation without the exact relationally
validated plan. Multi-subject interpretation retains one operation-bearing plan as
the denominator anchor plus each exact result plan that must be interpreted; no
missing-result plan artifact is invented merely to prove omission.

At query instant `q`, evidence timeliness is derived from historical successful
`(instance_id, dependency_id, evidence_id, document_digest, collected_at)` records
and the exact assessed plan's dependency `max_age` (`q - collected_at <= max_age`,
equality included). No mutable evidence substitution, query-time re-selection or
historical roll-up recomputation is allowed. Historical `waived` remains waived
after expiry; validity is qualified from the retained exact applied-waiver snapshot.
Whole-catalog waiver revision/content is not result identity or a historical
assertion fact, and unrelated waivers do not perturb a result. Outcome, alignment,
timeliness, waiver validity and coverage/applicability aggregate independently under
ADR 0011's state matrix. Neither plan alignment nor timely evidence establishes
present-state certainty, absence of drift, or continuous effectiveness.

#90 replaces the positional/copied dependency record with stable dependency
identity while preserving validated evidence ID plus complete-document digest,
selected `collected_at`, references into the independent complete snapshot, and the
distinction between successful selections and nonselected candidates. Existing
evidence identity and ADR 0010 assessment semantics are unchanged. Before publication
and full interpretation, intrinsic result validation plus mandatory exact plan/result
relational validation must succeed; otherwise publication fails closed. #80's
query-time judgments remain derived without a new artifact family.

## Durable assessment explanation facts

[ADR 0018](adr/0018-durable-assessment-explanation-facts.md) is an **accepted
design, not yet implemented**, under [#98](https://github.com/packetlss/compliance/issues/98).
It retains a canonical result-level table only for unsuccessful required-dependency
selection: `absent`, `stale`, `invalid` or `ambiguous`. Existing successful selection
continues to be owned solely by `provenance.selectedEvidence`. The two structures
must partition every active plan dependency under mandatory exact plan/result
validation. These disposition names are assessment-time facts, not result statuses.

Stale and ambiguous facts retain only necessary already-snapshotted document
ID/digest attribution and collection instants. Invalid facts retain stable code,
document attribution and safe schema constraint path/keyword, without evidence
values, evidence-instance paths, raw schema-library messages or schema source
locations. Attributable technical `error` additionally retains one closed
criterion-execution or criterion-decision stage/code; raw evaluator output,
exception text and stack traces never enter the result. All new structured facts
are committed by the result-domain semantic projection.

A criterion-returned `unknown` needs no second diagnostic object: complete
successful dependency selection plus the technical decision establishes that the
criterion, rather than selection, was inconclusive. Waiver, operation accounting,
plan applicability and current historical qualification keep their existing owners.
Refusal still publishes no result; any durable attempt/refusal claim belongs to
separately trusted external orchestration or audit history. The core defines no
attempt artifact or history service.

### Explanation ownership and retention

The two decisions compose through existing domain artifacts rather than a combined
explanation wrapper or digest:

```text
authored policy meaning
  -> effective plan semantics
  -> exact bound plan
  -> assessment against that exact plan
  -> immutable result facts
      + assessment-time unsuccessful dependency dispositions
      + safe structured evaluation error facts
      + successful evidence use in provenance.selectedEvidence
  -> historical qualification over the exact retained plan/result pair

refused-attempt history
  -> external orchestration, never core result history
```

When retained, the exact plan owns applicable policy and Objective meaning, check
title/purpose, effective parameters, evidence requirements, exclusions, derivations,
and tailoring context. The exact result owns immutable outcomes, successful selected
evidence, unsuccessful dependency dispositions, safe structured `error` explanation,
and applied-waiver facts. Mandatory relational validation binds the pair. Result
diagnostics use stable `instance_id` and `dependency_id` references where needed;
they do not copy plan-owned policy, Objective, check title, or purpose strings.

Each artifact's existing semantic projection remains responsible for its own
identity-bearing facts. ADR 0017 changes policy and plan identities; ADR 0018 changes
result identity. No second combined explanation identity is introduced. Retention
remains an external operating choice: deleting an assessed plan reduces later
historical interpretation but neither rewrites its result nor affects future
assessments. Query-time views never reselect evidence or reconstruct refused attempts.

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
