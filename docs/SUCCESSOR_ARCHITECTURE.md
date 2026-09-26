# Trusted-snapshot successor architecture

Status: **Accepted target, not implemented.** [ADR 0025](adr/0025-trusted-snapshot-successor.md)
owns the replacement rationale, trust reduction, retired guarantees and promotion
gates. [System architecture](ARCHITECTURE.md) routes implemented legacy contracts;
[contract maturity](CONTRACT_MATURITY.md) owns compatibility status. This document
owns target behavior and acceptance stories. [ADR 0026](adr/0026-minimal-successor-production-architecture.md)
owns the promoted Go/embedded-OPA direction, operating/value contracts, Linux
platform and production test/sequence decisions. Production is not yet implemented.

> Resolve governed inventory and reviewed policy into explicit subject-scoped
> intent; assess descriptive observations against that intent; explain the recorded
> conclusions using lightweight retained snapshots.

## Application boundary

One local/offline application has a thin CLI, ordinary file inputs/outputs and an
internal application/domain layer independent of presentation. No mandatory server,
database, account system, scheduler, plugin framework, remote policy service or
persistent history/discovery service is part of the target. Later presentation must
reuse the same semantic owners.

The resolved assessment plan is the external infrastructure-adapter handoff.
Credentials, configuration compilation/apply, provider state, inventory acquisition
and operational evidence collection remain external. Normal assessment needs no
adapter, network connection, Git checkout or legacy runtime. Real private policy,
realizations, inventory, evidence and results remain outside this repository; see
the [repository/private boundary](REPOSITORIES.md).

## Responsibility and record ownership

[ADR 0023](adr/0023-foundational-semantic-responsibility-boundaries.md) remains the
owner of the ten frozen responsibilities and PASS/FAIL/UNKNOWN/ERROR/WAIVED/refusal
meanings. The following assigns target facts to those owners without fixing a wire
layout or adding an alternate resolver:

| Owner | Facts and responsibility |
| --- | --- |
| Governed Inventory | Supplied subject identities and governed classifications; current inventory/group DAG resolution. Overlapping group membership does not duplicate fleet subjects or grant specificity precedence. |
| Governed Policy and resolver | Applicability consequences, desired intent, complete criteria, explicit parameters and selected complete realizations. Independently named/materialized policy sources remain separate; source/file/assignment order grants no precedence. Exact-identical same-identity definitions may coalesce; divergent definitions fail closed. |
| Operation selection and resolved plan | Selected subjects, required result slots and subject-scoped resolved intent. Retain authored policy/Objective/Check meaning, membership, effective values, exclusions, deviations, reasons, source/revision attribution and approval references needed for explanation and adapter use. |
| Coverage | Current ephemeral explanation from the same resolver: Inventory -> Coverage -> Assessment. It is neither a stored authority nor an Assessment input. Missing required coverage cannot disappear into unqualified success. |
| Descriptive Evidence | Subject-attributed observations independent of desired outcome. Collector identity is attribution, not a particular observation or authority to select a persona. |
| Assessment and result | Evaluate already-resolved intent using required observations qualified for subject, schema and assessment-time freshness. Own attributable conclusions, evidence-use/selection facts, safe failure explanations and underlying failure plus applied-waiver facts. Do not re-resolve policy or copy plan-owned meaning into a second authority. |
| Retained explanation and derived views | Join supplied matching operation/plan/result records without current catalogs or re-resolution. Policy Diff compares explicit resolved snapshots. Framework mappings supply descriptive traceability only. External retention owns keeping the required records faithfully. |
| Governance | Reviewed policy choices, Objective-demonstration sufficiency, approvals, waivers and external/non-core determinations. These are not evidence of implementation or proof of external conformity. |

Assessment consumes one coherent operation-owned input snapshot under
[ADR 0026 admission](adr/0026-minimal-successor-production-architecture.md#coherent-input-admission).
Coherence before resolution is an environmental/admission precondition. Missing, stale, schema-invalid,
ambiguous or inconclusive required observations cannot establish PASS. Evidence
filename, source order, collector identity or a convenient fallback must not choose
between conflicting observations. Valid complete duplicates introduce no ordering
precedence; typed equality/admission follows ADR 0026.
Attributable criterion-execution or decision failures are ERROR; inability to
establish shared prerequisites for a trustworthy result is refusal, with no new
result published. Result absence alone is not proof that a refused attempt occurred.

Record the selected subjects and required result slots before interpreting aggregate
success. Missing required members remain in the denominator, and another operation,
plan or subject's result cannot fill their slots. Accounting completeness is
necessary but not sufficient for success. Mismatched or conflicting supplied record
references fail admission under [ADR 0026 records](adr/0026-minimal-successor-production-architecture.md#retained-explanation-and-ordinary-records).
Ordinary IDs do not make records immutable; publication mechanics remain local choices.

Retained results keep the meaning of their original operation, resolved plan and
assessment instant after policy, inventory, evidence or the clock changes. Retained
explanation must not compute current plan alignment, current evidence timeliness or
current waiver qualification. A fresh operational conclusion requires a fresh
assessment; future assessment does not depend on prior results. Missing retained
material cannot be repaired with current mutable inputs or a fabricated history.
ADR 0026 defines the retained evidence minimum and unavailable-record behavior.

## Persona tailoring and parameters

Persona selection uses existing concepts:

```text
governed classification -> inventory group -> assignment
    -> selected leaf policy -> resolved Checks
```

Technical policy and simplified ParameterPolicy may each derive from **one parent**,
with explicit revision references and bounded typed changes. Branching variants are
allowed. Independent nonconflicting policies can apply together; assigning an
ancestor and a conflicting tailored child is a conflict, not an override. There is
no more-specific-group winner, generic profile combiner, Persona/Exception engine
or new policy DSL. The inventory-group DAG has an independent purpose and remains.

- **Tailoring** changes reviewed desired state. Retain what changed and why;
  passing the adopted variant does not establish unmodified benchmark conformance.
- **Exclusion** names a Check outside the adopted technical variant. Retain the
  exclusion and approval basis without PASS or inferred external N/A.
- **Waiver** accepts a scoped underlying FAIL during its applicable assessment-time
  window. Desired state stays unchanged; WAIVED remains distinct from PASS. A waiver
  cannot cure UNKNOWN, ERROR, missing implementation or a contradictory policy.

ParameterPolicy owns typed declarations and explicit complete values independently
of Objectives. Applicable assignments select it; loading a declaration or referencing
a consumer does not create ambient applicability. Check authors own direct typed
consumer links on technical and realization paths, including policy-owned freshness.
Resolve required values and final interfaces before assessment, with no defaults,
generic expressions, contribution collection, independent-owner merging or automatic
set union. An allowed-software variant supplies its whole intended set. A
parameter-only assignment does not manufacture an Objective or passing assessment.

Retain authoring safeguards for parent revision, target existence, expected inherited
state and final-interface/type validity. Stale authoring fails rather than silently
rebasing. [ADR 0026](adr/0026-minimal-successor-production-architecture.md#narrow-typed-authoring-contract)
defines the narrow JSON/value boundary; field layouts remain implementation contracts.
Explicit expected values do not offer exact-content-pin guarantees; reviewed
immutable revision practices belong to governance.

## Complete Objective assurance

Direct technical assessment remains valid without a synthetic Objective. Optional
Objective assurance retains `ControlRequirement` as the authored proposition and
`RequirementBaseline` as grouping of required Objectives, separate from parameters.
For each assigned Objective and applicable subject, select exactly one complete
`ControlRealization` through governed applicability; evidence never selects it.

| Resolved case | Required meaning |
| --- | --- |
| Zero applicable realizations | Visible implementation gap; no fabricated realization, adoption or technical outcome. |
| One realization declares non-implementation | Visible authored implementation gap, not observed FAIL, UNKNOWN, refusal, unassigned coverage or N/A. |
| One explicitly declares N/A | Retain the attributable determination and basis separately; it is not PASS. No new applicability/N/A semantics are introduced. |
| One implemented realization | A complete, nonempty demonstration; assess every declared Check, without short-circuiting away children. Authored implementation alone proves nothing. |
| Multiple applicable realizations | Ambiguous resolution; no assessable plan, even if candidate Checks agree. No fallback or specificity choice. |

Preserve conservative required-child demonstration: FAIL, otherwise ERROR,
otherwise missing/UNKNOWN/child N/A, otherwise WAIVED, otherwise all PASS. Missing
or unexpected children also fail exact membership admission; a conservative display
is not permission to accept a truncated result. Child N/A does not establish parent
N/A. Explicit Objective N/A is excluded from the applicable pass condition; all-N/A
is never PASS. Implementation gaps remain separately visible and prevent successful
required-policy demonstration regardless of passing Checks elsewhere, without hiding
their actual outcomes or invalidating otherwise attributable assessment work.

Realizations are complete authored demonstrations, not inheritable patch sets. A
persona can select a different complete realization, but cannot contradict an
unchanged Objective or remove a required demonstration Check and still claim that
Objective passed. Sufficiency and consistency with the prose Objective are an
**authored-policy/review responsibility**. The engine checks selected membership
and declared criteria; it does not prove logical sufficiency/equivalence, authenticate
external claims or introduce a theorem prover. Governance-only conclusions cannot
be recast as synthetic Objectives or assertion evidence.

## Behavioral acceptance stories

These fresh examples are illustrative input/expected-behavior specifications, not
frozen resource syntax or whole-output oracles. The existing
[persona walkthrough](../projects/server-personas/README.md) and
[synthetic IAM boundary](../verification/fixtures/iam-private-boundary/README.md)
provide semantic evidence only. Legacy test counts, wires and outputs are not
success criteria.

| Story and small input | Expected behavior | Retained invariant | Retired proof not required |
| --- | --- | --- | --- |
| **1. Standard and container.** Governed hosts S and C select standard and approved container leaves. Standard requires forwarding `0`, ASLR `2`, and audit service present. Container tailors forwarding to `1`, retains ASLR/audit and adds a runtime-presence Check. Fresh observations match each leaf. | Both adopted variants pass their Checks. C explains the `0 -> 1` deviation, source/revision, reason and approval reference. C does not claim unmodified benchmark conformance. An independent nonconflicting operations policy may also apply. | Policy owns persona intent; direct technical assessment needs no Objective. | Content-pinned ancestry and independent historical derivation replay. |
| **2. Conflict and classification trust.** Host X has both standard/container classifications; host Y is standard but evidence reports a runtime installed. A required target Z lacks policy coverage. | X's contradictory forwarding selections fail visibly without a winner. Y keeps standard intent. Z's missing required coverage remains visible and cannot contribute to unqualified success. | Governed classification, deterministic conflicts and honest scope accounting. | Selector/candidate-inventory witnesses or source-content composition proof. |
| **3. Exclusion and waiver.** A reviewed leaf explicitly excludes Check E. Another required Check still requires audit service; fresh evidence shows it absent. A scoped waiver applies at T1, expires before T2, and fresh T2 evidence still shows absence. | E remains visible as excluded with its reason/approval, never PASS or inferred external N/A. The service Check is WAIVED at T1 with underlying FAIL and unchanged desired state; the new T2 assessment FAILs. Retained T1 remains WAIVED. | Exclusion, desired-state tailoring and fail-only waiver are distinct; history is immutable. | Query-time waiver qualification or waiver/content digest chains. |
| **4. Complete company Objective.** One assigned access Objective groups into an access RequirementBaseline. The selected complete realization requires central-login, allowed-group and audit Checks. Evidence passes two and fails allowed-group. Variants remove all matches, declare non-implementation, match two realizations, or omit a required child. | All three Checks are assessed and the Objective does not pass. Zero match/non-implementation remains a gap; ambiguity prevents an assessable plan; omission cannot be admitted as complete. A persona's incompatible demonstration must be rejected in authored review, not presented as satisfying the unchanged Objective. Explicit N/A stays separate. | Exactly-one complete demonstration, every child required, conservative outcomes and authored sufficiency. | Digest-bound realization/plan replay or automatic proof of equivalence to Objective prose. |
| **5. Parameters and stale authoring.** Explicit freshness value `1h` links to two Checks. Standard allowed software is `{audit-agent}`; a child states the complete `{audit-agent, container-runtime}` value. Negative variants have a missing value, wrong type, absent target or stale expected parent state. | Both consumers receive the resolved freshness. The software child supplies the whole set; no contributions are collected. Every negative variant fails before assessment, including a stale final consumer interface. | Explicit typed values, direct fan-out and reviewed single-parent changes. | Additive union, content fingerprints or reconstructed ParameterPolicy ancestry. |
| **6. Evidence and execution.** A Check needs a fresh subject-qualified observation. Supply absent, stale, schema-invalid or conflicting admissible candidates; separately reorder complete duplicates, supply a conclusive negative observation, trigger an attributable criterion error, or lose a shared execution prerequisite. | Missing/stale/invalid/ambiguous evidence is UNKNOWN, never PASS. Duplicates create no order winner. Valid negative evidence yields FAIL; an attributable execution/decision failure yields ERROR. Shared-prerequisite refusal publishes no new result. | Required-evidence qualification, deterministic selection, outcome/refusal boundary. | Complete evidence digest-set identity or evaluator/tooling byte attestation. |
| **7. Recorded A/B/C.** An operation selects A/B/C with required result slots. Only A/B results are supplied, plus a result for C from another operation or plan. | Denominator stays A/B/C; C remains missing, and the foreign result cannot fill it. A wrong-subject or conflicting record fails admission. Existing outcomes are not rewritten, and incomplete accounting cannot establish whole-operation success. | Exact recorded membership and slot association; bounded supplied scope. | Historical selector/candidate replay or content-derived operation/member IDs. |
| **8. Retained explanation.** Retain the needed operation, plan, result and chosen evidence facts for a tailored, waived assessment. Remove or change current catalogs, inventory and evidence, and advance the clock. Also supply mismatched or conflicting record references. | Original intent, outcomes, evidence use, deviation and waiver remain explainable without re-resolution or current qualification. Mismatched/conflicting references fail admission. IDs cannot prove original authorship or tamper resistance; missing retained material cannot be replaced by current facts. | Original operation/plan meaning, single fact ownership and honest integrity limits. | Derivation replay, current catalog alignment or cryptographic provenance verification. |
| **9. Packaged and separate sources.** Materialize two independent policy sources plus a separately supplied synthetic private realization. Execute representative assessment and retained explanation outside the source checkout on the supported production platform, initially Linux. | Normal execution needs no network or legacy runtime; source order grants no precedence. The private source stays separate and real private data stays outside this repository. | Offline operability, independent sources and actual access/deployment boundaries. | Legacy wheel receipt, installed-file attestation or equality with legacy packaging/output. |

<a id="unresolved-decision-questions"></a>

## Promoted operating decisions

[ADR 0026](adr/0026-minimal-successor-production-architecture.md) resolves the four
experiment questions: coherent operation-owned admission, minimum retained consumed
observation facts, ordinary relationally admitted records with trusted retention,
and narrow strict JSON authoring/value semantics. Go is the production host;
embedded OPA evaluates trusted authored criteria only. No hostile-policy sandbox,
replay service, mandatory evidence database or universal publication/lock protocol
is promoted. Its production sequence requires separate bounded implementation
contracts after human architecture merge.

## Bounded platform-experiment specification

**Historical experiment specification; #209 completed through human-merged #216.**
The original comparison was Go/embedded OPA versus a clean Python/process design.
The merged [REPORT](../successor/experiments/209-platform/REPORT.md) and
[NOTES](../successor/experiments/209-platform/NOTES.md) preserve assumptions,
observations and limitations. ADR 0026 promotes only the minimal production
contracts, not prototype code, representations or its test suite. No executable
Python comparator is required by that evidence.

The table below records the experiment's acceptance requirements, including its
native macOS investigation; it does not add macOS to the Linux production contract.

| Hypothesis or risk | Required acceptance evidence |
| --- | --- |
| Thin CLI and domain layer can retain one semantic owner | Trace one standard/container resolution, one complete Objective and retained explanation through the same application/domain owners; show no presentation-side policy interpretation. |
| Embedded criterion evaluation is suitable | Run real authored criteria; exercise valid decisions, inconclusive decisions, malformed decisions, evaluator errors and shared-prerequisite refusal. Explain cancellation, resource behavior, isolation and testability. In-process evaluation does not imply process-level failure isolation. |
| Offline deterministic execution is enforceable | Account explicitly for network-capable and nondeterministic evaluator behavior, module/schema access and controlled inputs. OPA must not own applicability, evidence selection, waivers, remote bundles or management infrastructure. No incidental policy language or application-coded criterion catalog. |
| Lightweight records and no-JCS typed values suffice | Demonstrate original-meaning explanation after mutable inputs disappear, required-slot accounting, conflicting references, partial publication and stale authoring. Report candidate equality/admission/retention rules as experiment assumptions, including privacy and unavailable-record limits. |
| Deployment is practical on both platforms | Package and run representative assessment plus retained explanation outside the source checkout on Linux and native macOS; report commands, dependency footprint and deployment burden. Normal execution uses no network or legacy runtime. |

Report the exact experiment revision, platform/environment and commands, observed
behavior against each story, failures, unresolved risks, and a platform promotion
recommendation with its evidence and limits. Record why a second executable
comparator is or is not needed. Prototype code is disposable and is not production
by default. No benchmark claim may be inferred without measurements.

Exclusions include production scaffolding, full catalog/schema/test ports, services
or persistent stores, legacy compatibility, actual adapter/apply integration,
framework satisfaction, release/tag publication and legacy deletion. #208 permits
only the real test/packaging wiring owned by the separately promoted #209 contract;
unrelated workflow redesign remains excluded.
Any proposed expansion, changed semantic owner, weakened retained boundary or new
shared abstraction returns to architecture under ADR 0025; it is not resolved as a
local experiment convenience.
