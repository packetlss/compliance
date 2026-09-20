# ADR 0024: Separate Objective assurance from governed parameter policy

- **Status:** Accepted; Tranche A implemented under #199, Tranche B pending; experimental representation
- **Date:** 2026-09-20
- **Contract:** [#192](https://github.com/packetlss/compliance/issues/192)
- **Supersedes in part:** [ADR 0012](0012-explicit-policy-parameter-resolution.md), parameter ownership and redundant frozen representation; [ADR 0016](0016-closed-world-policy-assessment.md), fabricated missing-realization adoption and failing-Requirement representation
- **Preserves:** Every frozen invariant of [ADR 0023](0023-foundational-semantic-responsibility-boundaries.md), and [ADR 0020](0020-governed-policy-composition-without-sealing.md)'s removal of sealing

## Context and authority

Optional Objective assurance describes a reviewed proposition and its complete
policy-authored demonstration. Governed values also serve direct technical policy:
authorized software does not need an Objective merely to own an allowed-package
set. Current RequirementBaseline parameter derivation and contribution ownership
couple these independent responsibilities. Current `satisfaction.allOf` and
membership `required: true` repeat facts that have no alternative semantic value.
Repeated frozen parameter states duplicate deterministically reconstructable facts.

This documentation decision succeeds the affected representation, not the frozen
responsibilities. The [realization](../../tooling/docs/control-realization.md) and
[parameter](../../tooling/docs/policy-parameters.md) contracts describe the current
experimental implementation until coordinated follow-on cutover. This tranche
changes no schemas, runtime, maintained policy, artifacts or identity algorithms.
Examples below specify semantics, not final field spellings.

## Decision

### Objective ownership and complete demonstrations

`ControlRequirement` (Objective) owns the reviewed proposition, authored meaning
and mappings. `RequirementBaseline` remains the assignable grouping of exact
Objective revision/content membership; every member is required by definition.
It contains at least one genuine Objective and owns no parameter declarations,
bind/tailor operations, contributions or parameter-only `extends`. There is no
replacement Objective-group resource. Remove constant membership `required: true`.

`ControlRealization` owns one complete demonstration for its pinned Objective and
applicable subject, the attributable adoption declaration, and its Checks. Retain
current subject-type/label selection: zero applicable realizations is a gap,
exactly one is selected, and multiple applicable realizations fail closed even if
their checks or declared adoption happen to agree. No fallback, ordering,
specificity or Evidence-driven selection is permitted. `based_on` remains exact
provenance only; it grants no inheritance or automatic check reuse.

An implemented realization contains a non-empty collection of uniquely identified
Checks. Every declared Check is required and evaluated; a negative or unknown child
cannot short-circuit the remaining Checks. Remove `satisfaction.allOf`, without
introducing another satisfaction expression. The exact plan has one authoritative
check-membership relation connecting Objective, realization and materialized
instances. That relation validates duplicates, exact child-result membership,
parameter destinations, historical explanation and roll-up. Instance IDs remain
unique across direct technical and Objective paths in a subject plan.

### Implementation state is separate from Assessment outcome

Use **implementation state** for the resolution/adoption dimension and
**Objective demonstration** for whether required policy was successfully
demonstrated. Neither is an additional Evidence or Assessment outcome taxonomy.
An **implementation gap** is unsuccessful required policy, with its exact reason
retained; it is not a technical negative observation.

| Resolved case | Implementation basis | Assessment and required-policy consequence |
| --- | --- | --- |
| No applicable realization | Exact assigned Objective and zero-match resolution; no authored adoption exists | Implementation gap; Objective is not demonstrated. Do not synthesize a realization, `not_implemented` adoption, technical result or Assessment outcome. |
| One realization explicitly declares non-implementation | Exact selected realization and its authored `not_implemented` declaration, owner and governance attribution | Implementation gap; Objective is not demonstrated. Retain the declaration without manufacturing Checks, Evidence or Assessment outcomes. |
| One realization explicitly declares N/A | Exact attributable governed `not_applicable` determination | Preserve explicit N/A and its basis; exclude it from the applicable pass condition. It is not PASS or an implementation gap. |
| One implemented realization | Exact complete Check membership and authored implementation declaration | Evaluate every Check; only actual Check outcomes supply the conservative evidence-derived Objective roll-up. Adoption alone never establishes success. |
| Multiple applicable realizations | All ambiguous candidates and resolution diagnostics | Invalid policy resolution; no assessable plan or selection fallback. |

An implementation gap does not itself invalidate otherwise resolved policy or
force assessment refusal. Keep the assigned Objective in frozen expected membership
and reporting, including when it has no Checks. The plan owns the gap basis; the
existing operation/result reporting must retain its unsuccessful demonstration
without inventing technical results or dropping that member from accounting.
A gap-only member remains accounted required policy, never unassigned scope,
vacuous success or a reason to erase an expected operation member. Trustworthy
results for actual Checks elsewhere remain independently attributable. Unresolved
required parameters or other invalid policy still prevent an assessable plan;
a gap cannot bypass that validation.

For an implemented realization preserve the bounded child ordering: any `fail`,
otherwise any `error`, otherwise missing/`unknown`/child `not_applicable`, otherwise
any `waived`, otherwise all `pass`. Missing or unexpected child results also remain
subject to exact plan/result membership validation; `unknown` presentation is not
permission to admit a truncated result. Child N/A does not establish the parent
N/A determination. Each child's basis remains visible.

RequirementBaseline reporting retains every Objective implementation state and,
where present, evidence-derived outcome. Any implementation gap prevents successful
baseline and whole-operation demonstration regardless of other passing Checks.
It does not override or hide actual FAIL, ERROR, UNKNOWN or WAIVED outcomes; the
gap dimension and the bounded outcome roll-up are reported separately. With no gaps,
retain existing conservative roll-up over applicable Objectives. Explicit N/A is
excluded from the applicable pass condition; all-N/A remains N/A, never PASS.
Complete operation accounting and successful demonstration remain independent.
Fail-only waivers apply to actual evidence-derived failures; a gap cannot become
waiver-eligible through an aggregate spelling of `fail`.

```text
implementation gap
  != evidence UNKNOWN
  != evidence FAIL
  != refusal
  != unassigned Coverage
  != explicit N/A
```

UNKNOWN requires a resolved criterion whose truth cannot safely be established
from admissible Evidence. FAIL requires admissible negative Evidence. ERROR and
refusal retain their attributable-execution and trustworthy-publication boundaries.
Coverage explains current assignment, implementation and parameter applicability
through the existing resolver; it supplies no historical outcome. Framework
obligation ownership/categories and satisfaction semantics are unchanged: a gap
provides no passing assessed support, and must not be disguised as assessed FAIL
or as a governance-authored determination. This ADR introduces no Framework redesign.

### Bounded ParameterPolicy ownership and applicability

`ParameterPolicy` owns governed typed values, independently of Objectives. Its
bounded contents are owner-local slot declarations, explicit base bindings and
selected descendant tailoring, exact parent/derivation facts, and independently
applicable string-set contributions. It owns no Checks, Objectives, Assessment
rows, Evidence or expression evaluation. A contribution-only policy is valid.

The minimal assignment relationship is an explicit typed ParameterPolicy reference
collection on project `PolicyAssignment`, using the existing target group, subject
membership and assignment applicability semantics. Technical Baseline/
BaselineOverlay and RequirementBaseline references keep their existing baseline
reference surface and collision rules. ParameterPolicy references occupy a separate
typed surface/catalog, with exact `id@revision` selection and validated content
identity; they are never interpreted through `baselineRefs`. An assignment may
select either collection or both, but must select at least one policy. Field
spellings remain experimental; this applicability relationship does not.

Only explicitly applicable assignments select ParameterPolicy roots for the subject.
A selected descendant brings its exact pinned ancestry as derivation input, not
as another independently assigned candidate. Loading a resource in a named source,
a consumer reference or a contribution target never makes it applicable. There is
no ambient lookup of values, automatic owner import, global default or registry.
Catalog admission retains identical-only same-identity coalescence and rejects
divergence. Separate typed kinds grant no precedence; repeated paths retain full
attribution. Invalid/dangling assignments fail under existing admission semantics.
A parameter-only assignment affects value resolution and Coverage, but cannot
create an Objective, Check, assessment row or successful assessment by itself.

Stable slot identity is `(ParameterPolicy owner ID, owner-local slot name)`.
Exact declaration references additionally pin owner revision/content, declaration
and schema identity/digest. Descendant operations refer to that declaration owner;
derivation does not rename the inherited slot. Parameters are no longer owned by
ControlRequirement. Objectives can describe their proposition without importing
values or requiring synthetic membership to activate them.

Resolve every required slot in selected effective parameter policy before an
assessable plan. Unconsumed governed values are permitted and create no assessment
obligation of their own. A selected consumer must resolve its exact referenced slot
within applicable policy, even when the same literal could have been written locally.
No current required consumption edge may be lost merely by replacing it with a
copied literal during migration.

### Preserve binding, tailoring and additive composition

Preserve ADR 0012's value and resolution semantics with ParameterPolicy as owner:

- Values are typed JSON; scalars, objects and ordinary arrays are atomic complete
  values. Defaults and constraints never manufacture a binding. There is no merge,
  specificity, strictest-wins, source/file/assignment/traversal-order precedence.
- A required effective slot has one compatible applicable declaration and base
  after identical-only coalescence. Independent divergent bindings conflict,
  including separately assigned ancestor and descendant states. Equal literals
  cannot erase different declaration/linkage facts.
- `bind` fills an open unbound slot within its explicit structural scope; `tailor`
  changes inherited bound state through exact parent/content pins, target pins,
  authored expected parent fingerprint, explicit from/to values and complete
  deviation/governance metadata. Binding scope now names ParameterPolicy identities.
  Duplicate same-slot operations in one policy fail; operation order is not priority.
  Stale pins, fingerprints, from-values or interfaces fail rather than silently rebase.
- Preserve ADR 0020: fixed identifies the base, not a seal. Valid governed descendant
  tailoring and compatible independently applicable contributions remain possible.
  Structural constraints and governance metadata do not authenticate issuer authority.
- Duration normalization remains exact positive integral `s`, `m`, `h`, `d` to
  seconds; one day is 86400 seconds. Preserve authored values. No arithmetic,
  rounding, conversions, expressions, interpolation or calendar durations are added.

Only an explicitly opted-in string-set slot composes:

```text
canonical effective set = tailored base union every applicable contribution
```

Members use exact JSON-string equality and lexicographic UTF-8-byte ordering after
deduplication. Validate every member and the entire final set; do not discard an
invalid member to obtain validity. With no contributions, the base still resolves.
Atomic arrays and technical Baselines do not acquire additive semantics.

A contribution targets only stable `(ParameterPolicy owner ID, slot name)`;
it does not pin declaration revision, schema digest, base policy, parent
fingerprint or from-value. Current resolution binds it to the unique compatible
applicable declaration/base. It neither imports that owner nor binds, tailors or
mutates the base. Contribution identity is `(contributing ParameterPolicy ID,
local contribution ID, target owner ID, target slot)`, with exact owner revision,
content and source attribution retained separately. Repeated paths to one
contribution coalesce semantically while retaining every path; separate equal-member
contributions retain every origin. Tailoring changes only the base and cannot
suppress contributions. Removal, denial, subtraction, priority, structured/mixed/
numeric members, generic reducers and contributor authority machinery are excluded.

Missing/ambiguous targets or bases, atomic targets, incompatible declarations,
invalid members/final values, stale derivation and invalid consumers fail closed
before an assessable plan. No partially resolved success or evidence UNKNOWN
substitute is permitted.

### Check authors own typed consumption

The policy object authoring/materializing a Check owns its exact symbolic link:
`ControlRealization` for Objective-backed Checks, `Baseline` / `BaselineOverlay`
for direct technical Checks. ParameterPolicy owns values only. A link identifies
an exact declaration/slot and a concrete instance, exact implementation ID/version/
fingerprint, and typed technical-parameter path or named Evidence dependency/input
(including `max_age`). Object paths do not address array positions. One slot may
fan out to several explicit destinations; each destination receives one completely
resolved value. Conflicting links or literal/link prescriptions cannot gain
precedence by ordering; equal copied literals do not constitute a link.

A derived technical policy retains inherited links unless an explicit governed
operation changes the affected Check/link. Final destination validation follows
all explicit overlay changes, including substitution. Preserving an instance ID
cannot authorize a stale implementation interface. This adds no additive technical
Baseline merging: independently applicable technical conflicts remain conflicts,
even when their parameters originate in one ParameterPolicy. Reusable Controls
still own criterion/interface and dependency contracts, not applicability or values.

Freshness remains policy-owned intent. Check authors may supply explicit literal
freshness or an exact ParameterPolicy consumption link. Control capability
restrictions validate the supplied value without supplying or tightening it.
Evaluation uses only materialized values; it does not re-resolve ParameterPolicy.
ADR 0010 Evidence selection and ADR 0011 historical dependency attribution remain
unchanged, including exact `(instance_id, dependency_id)` selection facts.

### Retain historical source facts once; reconstruct summaries

The exact plan remains the resolved-intent and external-adapter handoff owner.
Retain each independently meaningful frozen input once, with references where it
is reused. The semantic owners are:

| Fact | Frozen owner |
| --- | --- |
| Objective meaning/mappings and baseline membership | Exact selected Objective and RequirementBaseline documents/pins |
| Adoption, zero-match basis and complete Check membership | Selected realization document where one exists; exact resolution facts where none exists; one resolved membership relation |
| Declaration/schema, base, ancestry and authored bind/tailor expectations | Exact selected ParameterPolicy documents, parent pins, operation facts and schema content |
| Contributions and local identities | Exact contributing ParameterPolicy documents and members |
| Applicability | Exact assignment/group/policy paths and consumed subject facts, retaining every origin |
| Consumer and final interface | Exact Check-authoring links plus implementation/interface facts |
| Execution inputs | Materialized technical parameters and named dependency bindings |
| Provenance | Existing operation/planning facts, exact revisions/digests and named-source attribution |

Do not separately persist independently editable copies of effective slot state,
derivation state, contribution-owner documents, replayed before/after summaries,
consumption values or member-origin summaries when the above facts reconstruct
them. Current candidates include `parameter_facts.states` and
`parameter_derivation.states`. Authored `from`, `to`, base values and
`expected_parent_fingerprint` remain inputs, even when comparison values can be
recomputed. Materialized Check inputs remain necessary execution facts and must
be checked against reconstruction; they are not a second source of policy authority.

Persisted validation independently checks document/pin/schema identity, exact
ancestry and operations, applicability/complete contribution membership, typed
consumer destinations, reconstructed union/attribution and materialized values.
Recompute derived summaries from retained facts for validation, explanation and
Policy Diff. Do not trust only the outer digest or consult current policy,
inventory or Evidence to repair history. Exact source normalization remains
contract-specific followed by existing canonical serialization; named source
content identity retains acquired bytes independently. Wire/document-table layout
is not frozen, but every retained fact must have one semantic owner and every
removed summary must be independently reconstructable.

Contribution-only ParameterPolicy creates no Objective/Requirement/baseline
assessment row, synthetic N/A or Objective membership. Its effects remain fully
attributable through assignments, Coverage, parameter resolution, history,
Policy Diff and plan provenance/identity. Coverage uses the existing current
resolver; historical explanation uses the exact retained plan/result pair.

### Supersession, frozen invariants and identity consequences

ADR 0012's Requirement-owned slot identity, RequirementBaseline parameter
operations/derivation/contributions, realization-only consumption and duplicated
frozen summaries are superseded by the owners above. Its parameter resolution,
atomic default, typed consumption, additive union, duration, freshness, provenance,
private-source and fail-closed invariants survive, as amended by ADR 0020.
ADR 0016's fabricated `not_implemented` adoption for zero realizations and failing
Requirement for implementation absence are superseded. Exact zero/one/multiple
selection, N/A, independent technical outcomes and conservative implemented roll-up
survive with complete membership replacing the redundant `allOf` expression.

All ten ADR 0023 invariants remain intact:

1. Governed Inventory supplies the same authoritative subject facts; no policy IDs
   or parameter members are inferred as inventory truth.
2. Governed Policy retains complete criteria, values and applicability consequences.
3. Coverage stays a current ephemeral explanation through the existing resolver.
4. Evidence stays descriptive and cannot select policy or realization.
5. Complete criterion ownership and Control-unaware observations remain the first
   admission gate; authored implementation absence is not negative Evidence.
6. Assessment evaluates resolved intent deterministically without re-resolution.
7. PASS/FAIL/UNKNOWN/ERROR/WAIVED/refusal keep their frozen meanings; implementation
   state and unsuccessful demonstration do not create Assessment outcome aliases.
8. Direct technical policy requires no synthetic Objective.
9. Accounting and claims remain closed-world and bounded to exact supplied inputs.
10. Exact historical meaning remains immutable; current inputs cannot rewrite it.

Preserve the [operation identity architecture](../../tooling/docs/operation-accounting.md):
member-plan digest commits resolved member intent; operation ID commits the exact
request, selection, relevant assignments, composition and member commitments;
bound plan ID binds operation and subject; result identity includes its exact plan
reference and evaluation-owned facts. The later coordinated pre-freeze migration
intentionally changes current member-plan digests, operation IDs, bound plan IDs
and result identities because their committed projections change. This is not a
new identity architecture, domain, algorithm freeze or `/v1` promotion.
No compatibility aliases, dual readers, historical conversion or cross-operation
result equivalence are added. Historical artifacts retain original meaning under
historical tooling. This documentation-only commit does not perform that migration.

## Conformance and follow-on implementation

| Maintained case | Required successor behavior |
| --- | --- |
| [IAM/private boundary](../../verification/fixtures/iam-private-boundary/README.md) | Move freshness ownership to explicitly assigned ParameterPolicy; exact 24h → 1h tailoring fans out through the same four realization-owned links. Keep separate private-source materialization, unchanged selection, and evidence-based outcomes. Independent divergent ancestor assignment still conflicts. |
| [Hybrid administrative access](../../verification/scenarios/projects/hybrid-administrative-access/README.md) | Keep the Linux and SaaS complete demonstrations of the same Objective and separate direct Linux package policy. Fresh negative guest-access Evidence remains FAIL; a missing realization is instead an implementation gap. |
| [Authorized software](../../verification/scenarios/projects/authorized-software-composition/README.md) | Assign base ParameterPolicy and factual database-group contribution explicitly. A direct technical Check consumes the canonical `auditd,curl,postgresql` set, without an Objective wrapper or contribution-only assessment row. Removing the contribution leaves a valid base and makes observed PostgreSQL a real FAIL; missing base instead prevents an assessable plan. Preserve history and Policy Diff attribution. |

These cases need no registry, new selection semantics, Evidence semantics or identity
architecture. Later executable ownership must cover zero-match versus authored
non-implementation, gap-only accounting and mixed gap/actual outcomes; all Checks
and N/A/ambiguity; direct technical typed consumption/substitution; missing required
values and stale pins; duration/freshness fan-out; fixed-base additive contributions,
all paths and permutations/conflicts; retained-fact tampering after deduplication;
Coverage, technical-only explanation, Policy Diff, exact historical operation
accounting, and ADR 0023 semantic anchors.

Promote two coordinated implementation contracts after this architecture merges:

- **A — Requirement/Realization simplification:** remove redundant membership,
  fabricated adoption and absence-as-FAIL; retain Objective grouping, complete Checks,
  selection/N/A/roll-up and remove contribution-only assessment rows. Coordinate
  schemas, source, plan/results, validation, Coverage, explanations and tests.
- **B — Parameter ownership and frozen representation:** introduce explicit typed
  assignment and ParameterPolicy; migrate declarations/operations/contributions,
  both consumption owners and direct authorized software; reconstruct frozen
  summaries and coordinate all sources, validators, views, identities and scenarios.

A may precede or be coordinated with B only through repository-valid accepted
checkpoints. Do not remove active parameter-bearing RequirementBaseline contracts
before their consumers cut over. Each implementation contract records atomic
migration scope and equivalent executable ownership; no local semantic invention
is authorized by unspecified wire spelling.

## Non-goals and escalation

No generic realization algebra, optional Checks, global parameter/value registry,
expressions or transformations, additive technical Baseline merging, new Evidence
semantics, Framework redesign, result dependencies, identity architecture,
compatibility scaffolding, storage or mutable-history subsystem is introduced.

If the bounded model cannot support IAM freshness, additive authorized software
and direct technical consumption without those additions, new selection/result
semantics, source precedence or broader assignment scope, stop and return to
architecture. Do not expand this decision during implementation.

## Validation of this documentation tranche

Check documentation links, ADR supersession and architecture/maturity coherence;
compare the three maintained scenarios conceptually; run repository validation and
`git diff --check`. Record exact-head stable CI and fresh-context read-only review
in the PR. Runtime/schema tests of the successor belong to the later migrations;
passing current tests does not claim the successor is implemented.
