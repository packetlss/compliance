# Tooling architecture

Status: **Current; interfaces and representations remain experimental**

[System architecture](../../docs/ARCHITECTURE.md) owns system responsibilities;
[contract maturity](../../docs/CONTRACT_MATURITY.md) owns compatibility status.
This document routes the detailed tooling contracts. ADR 0023 freezes semantic
responsibilities, not these modules, schemas, identities or interface wires.

## Current execution model

The installed `compliance` CLI resolves explicit normalized inventory, assignments
and independently named policy sources into provenance-bearing assessment plans.
Assessment evaluates the resolved criteria against qualifying descriptive Evidence
using OPA away from governed subjects. Collectors observe state without desired
policy or Control knowledge. The core does not host evaluation/reporting services,
Evidence stores, finding lifecycles, scheduling, notifications or authentication.

```text
Governed Inventory + Governed Policy -> resolved assessment plan
                                              + descriptive Evidence + waivers
                                              -> Assessment -> exact plan/result history

explicit current inputs -> Inventory / Coverage projections
explicit retained history -> Assessment / mappings projections
exact governance declaration + required history -> Framework satisfaction
explicit before/after plans -> Policy Diff
```

Technical Baseline/Overlay assessment is complete without a synthetic Objective.
Optional Requirement/Realization assurance shares planning and evaluation while
retaining its own selection, adoption and roll-up contracts. Governance owns
reviewed external/non-core determinations; mappings supply traceability only.

## Authority, retention and time

Authored policy owns intent, criteria and check meaning. Normalized Governed
Inventory owns the supplied subject facts consumed by resolution. Evidence records
descriptive observations; provenance binds supplied content without authenticating
upstream truth. Governance owns waiver resources and framework declarations.

Generated plans, results, Evidence, caches and response captures stay untracked and
do not become authored policy. A retained validated bound plan/result pair is,
however, the exact historical assertion: the plan owns resolved intent, operation
membership and planning provenance; the result owns immutable conclusions,
evaluation provenance, selected Evidence, unsuccessful dispositions and applied
waivers. Retention is an external operating choice, not a core store obligation.

Historical outcome, exact accounting, plan alignment, selected-evidence timeliness
and recorded waiver qualification remain separate dimensions. Query-time
qualification neither changes the outcome nor reselects Evidence or re-resolves
historical policy. Current Coverage, governance determinations and framework
satisfaction are distinct from historical Assessment outcomes. None establishes
continuous effectiveness, external conformity or real-world completeness.

## Producer interface

The experimental [producer interface](producer-interface.md) discovers contracts
from explicitly materialized policy sources, exports exact canonical schemas and
validates one ordinary typed Evidence document. Tooling alone does not include
policy-owned Evidence schemas. The analogous Subject check uses the installed
tooling-owned inventory schema and validates only one normalized resource.

Document validation covers supported representation, exact type/schema and envelope/
payload validity. It does not establish observation truth, freshness, selection,
policy applicability or criterion satisfaction. Caller-supplied identity and
schema-permitted extensions remain intact; extensions do not become criterion
inputs. There is no network registry, implicit source precedence or generated SDK.
The isolated standard-library collector exercise demonstrates ordinary construction
without private imports, project configuration, OPA or policy knowledge.

## Derived-read interface

The experimental [CLI/query boundary](cli.md#experimental-external-read-consumption)
provides purpose-specific responses. Historical Assessment entry points share only
a derived, non-persisted validated context: one exact operation-bearing anchor,
explicit retained assessed plans/results, explicit relevant instants and an optional
comparison anchor. Existing owners perform intrinsic validation, exact identity
resolution, competing-result detection and mandatory available plan/result relations
before full interpretation, accounting and qualification.

Inventory/Coverage consume current inputs through their existing resolver.
Framework retains declaration validation and satisfaction semantics; Policy Diff
validates explicit before/after plans independently. No context contains every domain.
Missing expected results leave unfilled slots, not inferred refusals. An orphaned
result exposes only bounded result-owned facts. Invalid or contradictory supplied
artifacts reject full interpretation.

Explanations join plan-owned titles, dependency inputs and mappings to result facts
through exact plan and dependency identities. Optional retained Evidence enriches
collector presentation only after exact ID+digest matching; missing bytes do not
erase retained historical facts. Caller-trusted external refusal context remains
separate from core result history. Inventory views omit arbitrary annotations and
attributes. The isolated browser consumes derived responses and only navigates,
filters, sorts and formats them; it does not interpret raw artifacts. This boundary
adds no universal report model, public Python API, service or latest-state store.

## Detailed current contracts

| Concern | Local contract |
| --- | --- |
| Commands, projections and external read consumption | [CLI](cli.md) |
| Policy, Controls, evidence and assessment | [Policy model](policy-model.md) |
| Inventory, assignments and current Coverage | [Inventory and assignments](inventory-and-assignments.md) |
| Exact operation scope and accounting | [Operation accounting](operation-accounting.md) |
| Plan/result ownership, validation and history | [Artifact provenance](artifact-provenance.md) |
| Explicit parameters and freshness | [Policy parameters](policy-parameters.md) |
| Baseline derivation | [Baseline inheritance](baseline-inheritance.md) |
| Optional Objective assurance | [Control realization](control-realization.md) |
| Project configuration and isolation | [Project layout](project-layout.md) |
| Waivers | [Waivers](waivers.md) |
| Actual composition and expected enforcement | [Composition](composition.md) |
| Source/distribution release ownership | [Release distribution](release-distribution.md) |
| Focused validation and canonical scenarios | [Validation](validation.md), [scenario contract](verification-scenarios.md) |

## External and private boundaries

The assessment plan is the external-adapter handoff. External programs own backend
mapping, credentials, state, approval and apply behavior. Policy sources supply data
and criteria, not executable adapters. Adapter output does not prove deployment or
criterion satisfaction; Assessment remains usable without an adapter.

Private inputs remain in separately authorized environments. Tooling runs with
materialized content and no Git or hosted-provider dependency. Content-addressed
provenance and independently named sources preserve exact attribution, identical-only
coalescing and fail-closed divergence without source-order precedence. Repository
layout and acquisition metadata do not establish semantic identity or trust.

## 11. Decision log

The entries below preserve implementation and design history, including superseded
proposals. They are not current implementation scope or an independent normative
layer. Use the current contracts above and accepted system ADRs for present behavior;
GitHub owns active delivery scope and sequencing.

### 2026-09-20 — Validated derived-read projections and browser falsification (#187)

Assessment and Framework historical CLI entry points share one derived,
non-persisted validation context containing only an exact operation-bearing anchor,
explicit retained assessed plans/results, explicit assessment/query instants and an
optional comparison anchor. It consolidates intrinsic validation, exact identity
admission, competing-result detection and all available mandatory plan/result
relations before delegating accounting and qualification to `operation.py`.
Inventory/Coverage, Framework declaration interpretation and policy diff remain
independent owners.

Purpose-specific JSON projections retain plan-owned dependency inputs and authored
titles without copying them into results. Optional retained Evidence enriches only
collector presentation after exact ID+digest matching; missing bytes leave history
usable. Separately caller-trusted refusal context qualifies a missing expected slot
without becoming a result or core attempt artifact. Inventory presentation now
intentionally omits arbitrary annotations/attributes. The isolated static browser
accepts only those derived response schemas through local files and performs only
navigation, filtering, sorting and formatting. This creates no universal report,
service, query language, store, public Python API or wire freeze.

### 2026-09-20 — Experimental producer surface (#186)

The [producer interface](producer-interface.md) exposes existing explicit-source
Evidence catalog admission, complete canonical schema export and document-only
validation, plus one normalized Subject resource check using the installed
inventory schema. Typed documents remain the interoperability contract; tooling
and policy schema ownership stay separate. The external standard-library collector
exercise supplies falsification evidence without generated bindings, policy-aware
construction, a schema registry, changed assessment admission or a compatibility
freeze. Exact authored schemas are retained apart from internal catalog locators.


### 2026-09-13 — Project-governed framework obligation declaration (#159; superseded in part by ADR 0022)

System [ADR 0021](../../docs/adr/0021-project-governed-framework-obligation-declarations.md)
accepts `FrameworkObligationDeclaration` as separately versioned project-governance
state outside ordinary policy sources and plans. It owns exact declared framework
scope and a closed applicable/excluded/not-applicable obligation ledger. The original
five-category/drift test is historical rationale for #161, not current admission
authority: ADR 0022 now permits only `governance-declared`,
`evidence-assessed-objective`, `direct-technical-policy`, or
`mixed-governance-assessed` target categories. It requires complete criterion
ownership and Control-unaware descriptive observations before assessment; drift alone
does not admit another domain's conclusion. The four ADR 0022 basis categories are
the current runtime contract.

The accepted framework-satisfaction interpretation is ephemeral over an exact
declaration, an exact retained operation anchor as scope witness, exact bound
plans/results required by assessed/direct portions, and explicit query time where
needed. Its states are `satisfied`, `not_satisfied`, and `not_established`;
any conclusive required governance or assessed failure is `not_satisfied`, unresolved
support without a conclusive failure is `not_established`, and only every required
basis affirmatively satisfied is `satisfied`. Governance-negative remains declaration-
side and creates no assessment result. Waivers/deviations and external recognition
remain qualifications. The declaration is
not embedded in plans and does not alter current Coverage, policy/composition/member/
operation/plan/result identity, or historical outcomes. Issue #161 implements the
pre-freeze resource, independent digest, optional `frameworkDeclarations` path,
exact-history `framework` operator, and Alder Forge proving-consumer migration. It
adds no generic framework engine, process evidence abstraction, conformity claim, or
freeze.

### 2026-09-13 — Canonical technical BaselineOverlay parent pins (#147)

`BaselineOverlay.spec.extends` alone is an unordered exact set of complete
technical parent pins. The semantic projection orders those pins by RFC
8785/JCS bytes before the existing digest construction; it leaves authored
operations, raw source identity, RequirementBaseline, additive-set, and all
technology-neutral semantics unchanged. Resolver preflight rejects duplicate
and contradictory pins before lookup, compatible parents union only exact
attribution records, and divergent parents fail without precedence while
retaining canonical candidate diagnostics. No identity algorithm, compatibility
reader, generic normalization layer, or new identity family is introduced.

### 2026-09-12 — Implement canonical identifier and schema URI migration (#136)

ADR 0019's grammar and role/owner-derived schema `$id` layouts are implemented
across maintained policy, tooling contracts, references, pins, fixtures, and release
vectors. A technical Baseline/BaselineOverlay and RequirementBaseline sharing one
kindless assignment `id@revision` now fail admission before planning independently
of source order. No alias, normalization, source qualification, precedence, network
schema discovery, Control multi-version redesign, or ADR 0012 semantic change is
introduced.

### 2026-09-12 — Typed identifier namespaces and schema URI ownership (#134)

System ADR 0019 accepts typed lookup namespaces with canonical dot-separated
kebab-case semantic policy IDs, owner-local snake_case slots/properties, independent
evidence `/vN` dispatch types, and predictable absolute HTTPS schema-contract `$id`
values. Source/repository/release coordinates, platform wire discriminators,
digests/fingerprints, Rego entrypoints and filesystem paths retain separate owners.
Kindless assignment references require fail-closed admission when a technical and
RequirementBaseline definition share one `id@revision`. This documentation promotion
implements none of the resource/schema/runtime migration or collision validation;
PR #133 receives only its separately bounded amend-before-merge mappings.

### 2026-09-12 — Explicit additive-set parameter architecture (#127)

ADR 0012 now accepts one bounded, documentation-only exception to atomic parameter
composition. A string-array requirement slot must opt in explicitly; current
resolution requires exactly one compatible declaration and base, accumulates every
independently applicable contribution without precedence, and freezes a canonical
union with complete member-origin and applicability-path attribution. Contributions
target stable requirement-slot identity, do not import their target or mutate the
base, and remain distinct from bind/tailor operations and deviations. Fixed bases
may receive compatible contributions. Coverage owns only current ephemeral projection;
historical explanation uses the exact frozen plan/result. Schema/runtime behavior is
deferred to a dedicated successor issue, with no new artifact, resource, cache,
digest/identity family, trust rule, compatibility path or contract freeze.

### 2026-09-12 — Explicit additive-set parameter implementation (#129)

The coordinated pre-freeze cutover adds the accepted `composition.kind:
additive-set` string-array declaration, stable-target RequirementBaseline
contributions, canonical union and complete origin/path attribution to the existing
parameter resolver and planner. Existing exact realization links materialize the
completed value. The current v4 plan extends `parameter_facts` and
`parameter_derivation`; persisted validation recomputes those frozen facts without
live policy. Coverage projects the current value and bounded derivation from that
same plan. Atomic defaults, artifact/resource/version/identity families, realization
selection, compatibility and trust boundaries are unchanged.

### 2026-09-12 — Governed inventory and realization terminology (#124)

Upstream systems or reviewed configuration retain subject-fact authoring authority,
while the exact normalized inventory supplied to an operation is authoritative to
closed-world resolution. Stable governed classifications may select policy and
realizations without requiring mutually exclusive groups; assignments accumulate
and divergence fails closed. Policy owns the mapping from classifications to
implementation semantics. Existing zero/one/multiple realization behavior,
complete `satisfaction.allOf`, evidence/result boundaries and content-addressed
identity are unchanged.

### 2026-09-11 — Declared evidence facts at control admission (#113)

The five maintained AWS, SaaS, and Linux field-selecting controls now enumerate
only the facts declared and typed by their corresponding evidence payload
schemas. Unsupported extension selectors and selector/type mismatches fail
policy validation before planning or evaluation. Evidence schemas remain open;
extensions remain preserved and identity-bearing. This bounded Stage 6 cleanup
adds no runtime schema introspection, selector framework, evidence type, changed
outcome semantics, compatibility alias, or cross-domain consolidation.

### 2026-09-11 — Inventory and evidence producer contracts (#111)

The pre-freeze producer surface retains normalized `Subject` resources for
applicability and independently typed evidence observations for assessment.
`Subject` stable fields and labels drive scope; `spec.attributes` remains the
rich adapter-specific extension point and is not selector input. Evidence retains
the seven-field envelope, with each self-contained source schema owning one typed
observation/selection-unit payload. Catalog admission now checks common-envelope
conformance without a runtime base schema or evidence-family hierarchy.

Evidence types name collector capabilities, not controls. New criteria reuse an
existing type when subject, authority, permissions, cadence, atomicity, and
selection semantics match; a same-unit undeclared fact is added as an optional
typed payload field, while a materially distinct observation requires a new type.
No current type is merged, renamed, aliased, deleted, or frozen by this decision.

### 2026-09-11 — Exact-operation Assessment operator views (#105)

Assessment presentation consumes exact frozen-operation accounting, exact retained
plan/result pairs, and separately derived current qualification. `assessment run`
reports exact slot accounting; `status`, `status --by group`, `mappings`, and
`explain` remain anchored to one exact operation. Current policy expectation belongs
only to Coverage. Missing result slots remain accounting omissions without a
synthetic historical outcome, and result-only explanation without the exact assessed
plan remains bounded to result-owned facts. No history service, latest-result lookup,
persistent Coverage state, new artifact family, or shared view framework is added.

### 2026-09-09 — Current inventory and coverage operator views (#104)

The operator sequence is `Inventory → Coverage → Assessment`. Inventory
presents supplied normalized asset/group/assignment facts and membership
attribution. Coverage is a purpose-specific, ephemeral table/JSON projection
that calls the existing planner and accounting-disposition owner; it has no
resource, artifact, persistence, identity, cache, evidence selection, or second
applicability algorithm. Its five current expectation classes remain
`result_required`, `inactive`, `unassigned`, `no_assessable_policy`, and
`invalid_resolution`. CLI `asset` vocabulary does not rename `Subject` wire or
domain contracts. Ordinary explanations retain bounded authored meaning and
failure context, while fingerprints, derivation state, lineage, digests, source
locators, and raw planner provenance remain owned by the exact plan and advanced
artifact surfaces. Assessment/history redesign remains outside this change.

### 2026-09-06 — Exact bound-plan/result historical pair (#90)

Implemented under #90: replace the duplicated self-contained result
with an explicit exact bound-plan/result pair. The plan owns resolved intent,
operation context, planning composition/enforcement, parameters, dependencies and
mappings; the result owns immutable conclusions, actual evaluation composition and
evaluation enforcement, evaluator, evidence snapshot/selections, compact outcomes,
and exact applied-waiver facts. Whole-catalog waiver revision and unrelated waivers
do not enter result identity. Intrinsic result validation is distinct from mandatory
plan/result relational validation. Historical plan resolution uses exact `plan_id`
from bounded input, without a new history/run/discovery system or compatibility path.
The runtime/schema cutover remains experimental and is not frozen.

### 2026-09-06 — Frozen operation and bound-plan identity simplification (#87)

The pre-freeze operation representation now uses one exact normalized request,
a mode-sensitive selection witness, relevant assignments, a compact ADR 0007
composition commitment, compact expected membership, and sorted member-plan
commitments. Catalog-wide inventory/assignment revisions and the predecessor
plan digest wrappers are removed. Each bound plan ID derives only from operation
ID and subject ID. Accounting disposition is derived rather than frozen as
legacy presentation counters. No compatibility alias, inventory snapshot artifact, result
redesign, evidence/composition identity change or freeze is introduced.

### 2026-09-06 — Frozen operation accounting and typed assertions (#78)

The [operation contract](operation-accounting.md) specifies the embedded frozen
projection, exact-set historical reporting and concrete typed assertion examples.
Every selected Subject has an accounting row; only assessable members require
results. Operation context changes enclosing plan/result identity. One assessment
instant applies to all evaluated members. This implements ADR 0016 without another
artifact family, certificate subsystem, common-assurance engine or result graph.
ADR 0010/0012 and existing explicit N/A, missing realization and waivers are unchanged.

Earlier promotion entries below record their historical stage; #78 is the bounded
implementation. New architecture or escalation requires a new focused promotion.


### 2026-09-05 — Explicit parameter and freshness implementation (#73)

[Policy parameters](policy-parameters.md) specifies pinned declarations, explicit
binding and parameter-only derivation, direct dependency consumption, policy-owned
freshness and frozen artifact validation. Existing v4 plans/results carry the
additional identity-bearing facts; historical artifacts require historical tooling.
ADR 0010/0011 behavior is unchanged. The then-current ADR 0013–0015 design was subsequently superseded by ADR 0016 below.


### 2026-09-06 — Closed-world assessment replaces ADRs 0013–0015 (#37)

System [ADR 0016](../../docs/adr/0016-closed-world-policy-assessment.md) supersedes
the 2026-09-05 scoped-assurance/applicability/recognition design and migration route.
It is implemented experimentally under #78 and simplified under #87. Tooling retains Subject/group DAG/
assignment resolution, exact governed policy instances, every applicable path,
deterministic conflicts, typed evidence qualification and immutable results.
Future run accounting must detect omissions from the exact expected assessment set
of the supplied operation, without a new inventory hierarchy or chosen wire family.

The core assesses supplied company policy, not external inventory exhaustiveness,
external obligation-universe completeness, legal applicability authority, recognition
or independent external conformity. Governance owns those judgments. Mappings are
attributable policy/reporting content; results must remain bounded to supplied and
resolved company targets. Provenance deterministically attributes exact inputs and
supports reproducibility, integrity/tamper detection and evidence qualification; it
does not authenticate upstream truth or establish legal correctness or governance
sufficiency.

Required assurance dependencies identify evidence contracts. Certificate fields are
contract-specific, never universal. Common assurance needs an explicit named beneficiary
dependency and attributable source assurance plus required correlation/integration
evidence; typed evidence may suffice. Direct assessment-result consumption is not
required and needs separate review if later found necessary.

Preserve ADR 0010 unknown/error/refusal, ADR 0012 parameters/direct consumption and
freshness, exactly-one design-time realization selection, missing-realization failure,
conservative roll-up and fail-only waivers. Unassigned is not automatic N/A; existing
explicit N/A remains distinct. Invalid required resolution cannot become a partial
valid plan or synthetic evidence unknown.

At that stage, #73 was complete and #37 next permitted narrow read-only exploration
of expected run accounting, typed external/procedural assurance dependencies and
qualification, beneficiary attribution, and whether common reuse was needed. This
paragraph records historical routing; it is not current implementation authority.

### 2026-09-05 — Explicit policy parameters and policy-owned freshness (#37)

System [ADR 0012](../../docs/adr/0012-explicit-policy-parameter-resolution.md)
accepts explicit binding and descendant tailoring, stable requirement slots,
direct typed realization-dependency consumption and policy-owned effective
`max_age`. Required unresolved or conflicting parameters prevent an assessable
plan; evaluation consumes already resolved values. Exact resolved implementation
inputs remain distinct from semantic requirement slots. Immutable plan facts
retain values, pins, operations, links, destinations and freshness provenance.
The bounded migration is [#73](https://github.com/packetlss/compliance/issues/73).
Current literal-input schemas and Control-owned ages remain executable until
that cutover; no runtime behavior changes in this documentation promotion.
ADR 0010/0011 evidence semantics and missing-realization behavior are preserved.

### 2026-09-05 — Predecessor retirement (#33)

After #31/#32 and destination cutovers #34–#36, current tooling accepts only
project-config v1alpha3, composition-lock v1alpha1 and assessment plan/results v4.
Delete predecessor schemas/readers/digests/dispatch and compatibility fixtures;
reproduce historical artifacts with historical tooling. V4 domain validation and
construction are native, retaining the existing semantic identity projections,
actual composition, ADR 0010/0011 evidence behavior and adapter handoff.


Substantial choices should become Architecture Decision Records under
`docs/adr/`. Until then, proposed choices remain in this document and are
explicitly labelled as assumptions.

The 2026-08-28 configuration compiler and renderer rows below are retained as
historical prototype decisions. They are superseded by the 2026-09-04 product
boundary: core ends at the assessment plan, configuration artifact families
and commands are unsupported, and adaptation is external.

| Date | Decision | Status |
|---|---|---|
| 2026-08-23 | Keep policy and evaluation off governed objects | Accepted |
| 2026-08-23 | Separate collection, evaluation, and reporting | Accepted |
| 2026-08-23 | Accept arbitrary JSON through explicit versioned evidence types | Accepted |
| 2026-08-23 | Model hierarchy as a DAG with group-level baseline assignments | Accepted |
| 2026-08-23 | Render an immutable effective assessment plan for each subject | Accepted |
| 2026-08-23 | Keep evidence schemas minimal and open to additional fields | Accepted |
| 2026-08-23 | Produce independently attributable results per control | Accepted |
| 2026-08-23 | Do not implicitly merge parameters across control instances | Accepted |
| 2026-08-23 | Choose per-control versus whole-plan OPA calls after prototyping | Proposed |
| 2026-08-23 | Start with a Linux baseline and validate with a SaaS control | Superseded by the implemented macOS, AWS, SaaS, and Linux IAM prototypes; the original local-Mac boundary project is now retired |
| 2026-08-23 | Model evaluation decisions separately from findings | Proposed |
| 2026-08-23 | Declare evidence dependencies in control manifests | Accepted |
| 2026-08-23 | Build OPA bundle, catalog, and schemas as one policy release | Proposed |
| 2026-08-23 | Keep group definitions and assignments in Git; resolve membership from inventory | Proposed |
| 2026-08-23 | Derive company policy through explicit overlays on immutable baselines | Accepted |
| 2026-08-23 | Keep company compliance separate from parent benchmark alignment | Accepted and exposed in bounded assessment mapping views |
| 2026-08-23 | Target assignments at stable groups; use singleton groups for one asset | Proposed |
| 2026-08-23 | Version inventory, assignments, and policy independently in each plan | Proposed |
| 2026-08-23 | Treat policy-selecting inventory labels as authoritative resolution input when supplied through the governed projection | Accepted and implemented |
| 2026-08-23 | Treat subject inventory as a read-only projection; upstream systems or reviewed configuration retain fact-authoring/sourcing authority | Accepted; clarified by #124 |
| 2026-08-23 | Use Kubernetes resource conventions for canonical inventory authoring | Accepted |
| 2026-08-23 | Use one-resource-per-file for Git collaboration and multi-document YAML for importer streams | Accepted |
| 2026-08-23 | Model resolution, assessment coverage, and evaluation outcome as separate dimensions | Accepted |
| 2026-08-23 | Require assigned, active policy with at least one control before evaluation | Accepted |
| 2026-08-23 | Aggregate status by resolved DAG membership without treating group totals as mutually exclusive | Accepted |
| 2026-08-23 | Expose inventory, planning, evaluation, and reporting through one operator CLI while keeping collectors separate | Accepted |
| 2026-08-23 | Use a versioned, repository-local project config with CLI-over-config precedence and config-relative paths | Accepted |
| 2026-08-23 | Validate every baseline and overlay against a strict kind-specific schema before policy resolution | Accepted |
| 2026-08-23 | Require every authored YAML file to declare an editor-resolvable schema association | Accepted |
| 2026-08-23 | Model API-governed cloud and SaaS subjects through provider-specific typed evidence and off-subject evaluation | Accepted |
| 2026-08-23 | Treat checked framework automation profiles as explicit mappings, not claims of complete benchmark conformance | Accepted |
| 2026-08-23 | Allow shared evidence directories while strictly selecting evidence by subject identity before evaluation | Accepted |
| 2026-08-23 | Validate strict control manifests and effective instance parameters for every resolved baseline before planning or evaluation | Accepted |
| 2026-08-23 | Treat the repository as a workspace registry of isolated named projects with an explicit default and shared CLI project selection | Accepted |
| 2026-08-23 | Standardize maintained projects on a complete path contract and per-subject generated artifact directories | Accepted |
| 2026-08-23 | Add a first-class high-level requirement and environment-private technical realization layer | Accepted initial `allOf` contract; integrated with validation, planning, evaluation, and reporting |
| 2026-08-23 | Validate evidence-schema references and exact Rego entrypoints in the policy gate | Accepted |
| 2026-08-23 | Expose external references as separate objective and technical mappings with explicit parent alignment | Accepted |
| 2026-08-23 | Support standalone technical baselines and optional high-level objective assurance in the same assessment model | Accepted |
| 2026-08-23 | Split tooling, shared policy, and project/trust boundaries into independent Git repositories with an unversioned local checkout parent | Historical transition decision; the independent-repository requirement is superseded by workspace ADR 0005, while logical policy-source, project, and real trust boundaries remain |
| 2026-08-23 | Assemble stable named policy sources locally with independent digests, no source precedence, identical-only coalescing, hard conflicts, and explicit overlay/realization semantics | Accepted and implemented |
| 2026-08-28 | Project effective technical-control parameters into typed backend-neutral configuration plans, with separate backend adapters and no execution in the initial scope | Accepted initial contract; Linux and AWS/Terraform prototypes implemented |
| 2026-08-28 | Model required packages as one neutral intent type with an explicit extensible ecosystem; keep Windows features and roles in separate intent families | Accepted design constraint for the configuration prototype |
| 2026-08-28 | Represent required packages as identifier objects, initially requiring only `id`, and defer version/source fields until their cross-ecosystem semantics are defined | Accepted design constraint for the configuration prototype |
| 2026-08-28 | Persist configuration composition conflicts in content-addressed invalid plans, retain every candidate and contributor, and require adapters to refuse invalid plans | Accepted and implemented with the sysctl prototype |
| 2026-08-28 | Compose Linux sysctl intent by key: equal values coalesce and different values are hard conflicts independent of input order | Accepted and implemented |
| 2026-08-28 | Expose stored configuration provenance, effective parameters, composition, and conflicts through `configuration explain` | Accepted and implemented |
| 2026-08-28 | Model Amazon S3 account-level Block Public Access as a narrow four-setting intent with dedicated evidence and field-level hard conflicts | Accepted and implemented |
| 2026-08-28 | Take AWS Terraform target identity from trusted inventory while keeping provider credentials, state ownership, import, approval, and execution outside policy and generation | Accepted and implemented prototype boundary |
| 2026-08-28 | Emit a schema-validated JSON form of the stored configuration explanation | Accepted and implemented |
| 2026-08-28 | Validate rendered assessment plans and immutable result envelopes against tooling-owned strict schemas plus cross-field digest, count, revision, and conservative roll-up invariants at persistence and read boundaries | Accepted and implemented |
| 2026-08-28 | Select operational personas through trusted inventory groups, express durable persona-wide differences through reviewed derived baselines, and fail closed when sibling persona assignments conflict | Accepted and implemented prototype; waiver workflow remains deferred |
| 2026-08-28 | Show complete active and excluded overlay-deviation approval metadata directly in the human-readable subject assessment explanation | Accepted and implemented |
| 2026-08-28 | Require provenance explanations to connect selection scope with effective criteria, ordered inheritance operations, and deviations; do not treat source identifiers alone as an explanation | Accepted and implemented for assessment and configuration explanations |
| 2026-08-28 | Freeze normative overlay derivations as parent fingerprint, inherited lineage, and exact before/after criteria in the rendered assessment plan instead of reconstructing historical differences from current policy | Accepted and implemented; consumed by the initial stored-plan `policy diff` |
| 2026-08-28 | Model temporary exceptions as project-owned, exact subject/control, approved and bounded waiver resources resolved at evaluation time; only an underlying failure may become waived, while plans and configuration intent remain unchanged | Accepted and implemented initial contract |
| 2026-08-29 | Version the integration workspace separately, pin component repositories as submodules, use branches only as review lanes and immutable tags for tested compositions, keep separate workspaces for need-to-know boundaries, and make runtime independent of Git metadata | Historical initial workspace contract; its upstream development/topology role is superseded by workspace ADR 0005, while exact leaf-integration metadata, real need-to-know separation, and runtime independence from Git remain |
| 2026-08-29 | Compare validated stored plans for the same subject as the initial policy-diff scope, preserve exact effective-policy and provenance changes without re-resolution, treat identity-context-only churn as context, and reserve CI exits 0/1/2 for unchanged/changed/incomplete comparisons | Accepted and implemented initial contract; authored baseline diff remains future work |
| 2026-08-29 | Compare two strict project plan snapshots by stable subject identity, reuse the immutable per-subject policy diff, report valid additions/removals and effective modifications, and fail the aggregate comparison closed for invalid-resolution subjects, mixed artifacts, empty sets, or duplicate identities | Accepted and implemented as `policy diff-set`; authored baseline diff remains future work |
| 2026-08-29 | Enforce the pinned evidence-type JSON Schemas after exact subject routing and before freshness selection; preserve valid extension fields, report matching schema failures as independently attributable control errors without invoking OPA, and refuse unreadable or non-object evidence that cannot be routed safely | Historical implemented rule; schema-invalid evidence → `error` classification superseded by system [ADR 0010](../../docs/adr/0010-required-evidence-status-and-assessment-refusal.md). Runtime correction to `unknown` is implemented by #32; historical rationale retained |
| 2026-08-29 | Separate stable scenario-first verification from exploratory development and boundary examples; use credible deterministic synthetic situations, explicit feature coverage, normal production contracts, and project isolation even when several projects share one repository | Accepted verification strategy; first scenario migration implemented, broader repository migration remains proposed |
| 2026-08-29 | Explain external assurance as a chain from versioned framework scope through company intent, documented operating practice, complete technical realization, evidence, conservative results, deviations, waivers, and gaps; never infer whole-framework fulfillment from mapped technical checks | Accepted documentation and claim boundary; ADR 0021 later accepts a separate project-governed declaration and ephemeral bounded projection, still without mapping inference or a joined current/latest view |
| 2026-08-29 | Treat internal policy and external obligations as complementary inputs that converge on reviewed company requirements and technical baselines; external mappings are many-to-many and broad framework language requires an explicit company interpretation, complete realization, intended-configuration trace, and evidence-backed result | Accepted authoring and explanation boundary; ADR 0021 now accepts the separately owned `FrameworkObligationDeclaration` design, with implementation still future work |
| 2026-08-29 | Create an independently versioned verification-scenarios repository, keep development projects non-normative, implement the first Linux hardening rollout project, assign every registered example feature to one primary scenario, and use fixed mock collection/evaluation instants | Implemented transitional repository; canonical integration ownership, deterministic scenarios, and feature mapping remain accepted across consolidation, while repository placement follows workspace ADR 0005 |
| 2026-08-29 | Keep tooling, policy, and stable verification scenarios on the core release path while treating end-user examples as downstream consumers of supported releases that can be copied or forked and must never feed back into core verification | Logical release/dependency boundary accepted; source-repository placement follows workspace ADR 0005, and external starter UX remains future work |
| 2026-08-29 | Separate released reusable policy, verification-only policy, and released example-company policy into independent lifecycle and repository roles; use the shared library as their only common policy dependency, prohibit verification/example cross-dependencies and copied reusable controls, and have the starter workspace pin supported shared and example-policy releases | Policy-source identity, lifecycle, and dependency separation accepted; separate Git repositories are not required by workspace ADR 0005, and example-company policy remains proposed |
| 2026-09-03 | Retire the pre-unified direct Python/module operator wrappers while preserving their internally imported implementations | Accepted; `compliance` is the sole supported operator entry point and internal module paths are not a public Python API |
| 2026-09-04 | Support only CPython 3.13 during pre-freeze development, with Python 3.13.15 as the exact canonical validation patch | Accepted; distribution metadata is `>=3.13,<3.14`, and another minor requires an explicit metadata and CI decision |
| 2026-09-04 | Retire the old repository's hosted tooling publisher during consolidation while retaining provider-neutral release construction and validation | Accepted; historical releases remain immutable, and a consolidated publisher is deferred until a concrete downstream need exists |
| 2026-09-04 | Remove the in-core configuration compiler, backend renderers, commands, and artifact families while preserving the provenance-bearing assessment plan as the external-adapter handoff | Accepted and implemented; external output is neither execution proof nor compliance evidence |
| 2026-09-04 | Remove the superseded workspace-centered repository strategy from current tooling documentation | Accepted; workspace ADR 0005 and current workspace architecture own topology, while tooling documentation retains executable/domain contracts |
| 2026-09-05 | Evaluate policy-source generated-directory exclusions only within the explicitly supplied semantic root | Corrected a path-dependent implementation defect without changing the provisional digest algorithm; artifacts carrying the erroneous empty identity require regeneration |
| 2026-09-05 | Intentionally rename the maintained reusable semantic source to `control-library`, independently of path and distribution, without changing policy bytes or adding an alias | Accepted and implemented under #57 Tranches 0–1; destination [ADR 0009](../../docs/adr/0009-active-compliance-vocabulary.md) owns vocabulary and deferred work |
| 2026-09-05 | Rename the project-selection schema, loader vocabulary, and diagnostics from `workspace-config` to `project-registry`, preserving selection and isolation without a compatibility alias | Implemented under #57 Tranche 2 and destination ADR 0009; supersedes only the registry terminology in the 2026-08-23 decision, with registry data/location remaining nonsemantic to composition |
| 2026-09-05 | Promote the common required-evidence status/refusal boundary, clarifying ADRs 0006/0007 and reconciling #32 | Historical promotion state: system [ADR 0010](../../docs/adr/0010-required-evidence-status-and-assessment-refusal.md) is normative and implemented by #32; #37 then retained broader assurance design; #62 owned tied-candidate selection |
| 2026-09-05 | Implement ADR 0007 actual composition, optional direct/complete enforcement, v1alpha3 configuration and verified local wheel receipts; refuse v1alpha3 assessment generation pending #32 | Accepted under #31; [composition contract](composition.md) defines normalized projections and transitional diagnostics; predecessor readers retained for #33 |
| 2026-09-05 | Extend ADR 0010 with #62 evidence selection ambiguity: canonical-identical latest duplicates coalesce for selection only; distinct equally latest eligible documents select none and make dependent controls `unknown` without OPA | Implemented by #32. Supersedes predecessor traversal-order selection and the earlier unresolved #62 follow-up; complete snapshot provenance remains preserved |
| 2026-09-05 | Separate immutable historical assessment outcomes, exact plan alignment, derived evidence timeliness and recorded waiver validity; require minimal factual temporal provenance in v4 (option B, #66) | System [ADR 0011](../../docs/adr/0011-historical-assessment-and-operational-evidence-timeliness.md) is normative and implemented for v4 historical operation reporting. #32 owns its factual representation and #80 implements the derived operational view. ADR 0010 retains assessment-time semantics. |
| 2026-09-05 | Implement provenance-bearing assessment v4, ADR 0010 required-evidence invalidity/ambiguity, and ADR 0011 factual successful-selection provenance | #32; [v4 contract](artifact-provenance.md). #80 subsequently implemented operational evidence timeliness; predecessor consumers/readers were retired by #34–#36/#33. |
| 2026-09-06 | Remove the unverified collector-supplied `integrity.digest` and the optional-evidence discriminator/runtime branch; make every evidence dependency required by definition | #84; complete-document/set identity algorithms and ADR 0010 selection, outcome, refusal, freshness, provenance, ambiguity, canonical-copy and fail-only waiver semantics remain unchanged |
| 2026-09-08 | Require source-authored policy titles and Control-owned check title/purpose, freeze them in exact plans, and expose them through policy diff and assessment explanation without changing technical evaluation | Implemented under #100; ADR 0017 remains experimental and no compatibility format or identity algorithm was added |
| 2026-09-08 | Retain canonical unsuccessful dependency dispositions and closed safe criterion error facts in assessment results, with atomic producer/schema/identity/admission/relational/publication/consumer cutover | Implemented under #102; ADR 0018 remains experimental, old development v4 results require historical tooling, and no identity algorithm identifier changed |
| 2026-09-11 | Represent `linux.sysctl.required` desired policy as one keyed value per sysctl name and classify divergent duplicate selected observations as attributable inconclusiveness | Accepted for the domain-local #115 cleanup; `linux.sysctl/v1`, general evidence selection, outcome taxonomy, and identity algorithms remain unchanged |
| 2026-09-11 | Compare current pre-migration `macos.system.minimum_version` with macOS-owned numeric dotted-version semantics and classify malformed selected product versions as attributable inconclusiveness | Accepted for the domain-local #117 cleanup; ADR 0019's canonical target is `macos.system.minimum-version`; policy minimum remains explicit three-component syntax, observed versions may have two or three components, and no shared SemVer/version framework is introduced |
| 2026-09-11 | Remove realization information classification from reusable policy and frozen plans | Implemented under #120 as a pre-freeze deletion; confidentiality remains enforced by source ownership, acquisition/materialization, repository access, and deployment controls, with no replacement runtime taxonomy or access decision |
## ADR 0024 Tranche A implementation (#199)

The current [realization contract](control-realization.md) removes redundant
`satisfaction.allOf` and constant membership flags. Zero-match resolution has no
fabricated adoption; authored non-implementation retains its declaration. Both
are implementation gaps with no Assessment outcome. Plans retain exact complete
Check membership; result rows retain the gap dimension separately from nullable
outcomes. Gaps prevent successful demonstration without hiding real evidence-derived
results. Contribution-only policy creates no assessment rows. Historical
artifacts require historical tooling; identity architecture is unchanged.

## ADR 0024 Tranche B implementation (#201)

`ParameterPolicy` is the sole active governed parameter owner. Explicit
`parameterPolicyRefs` select it independently of baseline policy. Exact symbolic
consumer links remain owned by the Check-authoring ControlRealization, Baseline or
BaselineOverlay. The plan retains exact ParameterPolicy source documents,
applicability and consumers once; admission reconstructs effective state,
composition and attribution before checking materialized execution inputs. The
RequirementBaseline-owned representation has no current compatibility reader.
