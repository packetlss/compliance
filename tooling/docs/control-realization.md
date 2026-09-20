# Control Requirements and Environment Realizations

Status: **Implemented experimental contract — ADR 0024 Tranches A/B (#199/#201)**

This optional layer connects a reviewed Objective to one complete policy-authored
demonstration for an applicable subject. Direct technical policy remains valid
without an Objective wrapper. [ADR 0024](../../docs/adr/0024-objective-assurance-and-parameter-policy.md)
owns the accepted semantics; [ADR 0023](../../docs/adr/0023-foundational-semantic-responsibility-boundaries.md)
freezes Evidence and Assessment responsibilities and meanings.

Parameter ownership is the separate implemented
[ParameterPolicy contract](policy-parameters.md). ControlRealization owns only the
symbolic links consumed by its authored Checks. RequirementBaseline remains
Objective grouping only; direct technical policy can consume the same typed values
without an Objective wrapper.

## 1. Problem

The current prototype maps executable control instances to frameworks through
`external_refs`. That provides traceability but cannot prove that the mapped
checks completely implement a higher-level requirement. It also cannot state
how several technical results combine into the parent result.

For example, “access is role based” is not proven merely because SSSD is
installed. A particular Linux environment may need to prove that:

1. SSSD is installed;
2. SSSD uses the approved central IAM domain;
3. SSH authorization requires an approved central group; and
4. unmanaged local accounts cannot obtain interactive access.

The model needs an explicit, reviewable assertion that these checks together
realize the parent objective.

## 2. Layers

```text
External framework requirement
          ↓ mapping
Company ControlRequirement
          ↓ pinned realization
Environment-private ControlRealization
          ↓ expansion
Technical control instances
          ↓ evaluation
Technical results
          ↓ complete required Check roll-up
Requirement assessment
          ↓ RequirementBaseline roll-up
Top baseline assessment
```

These layers answer different questions:

| Object | Question |
|---|---|
| `ControlRequirement` | What technology-neutral outcome is required? |
| `RequirementBaseline` | Which control objectives must be reported together? |
| `ControlRealization` | How does this environment implement and prove the objective? |
| Technical control instance | What exact state is checked on one subject? |
| Requirement assessment | Did the selected realization currently satisfy its objective? |
| Baseline assessment | Did every applicable required objective receive a defensible result? |

### Company interpretation, operating practice, and external assurance

The realization chain supports both company-originated objectives and broad
external obligations. External wording is not supplied directly to OPA. Policy
owners state the reviewed company interpretation as a technology-neutral
`ControlRequirement`, then select a complete environment realization. An
internal objective can use exactly the same path without inventing an external
parent or carrying any `external_refs`.

The chain should be explainable in the language of normal operation:

```text
Internal concern -> reviewed company objective
External requirement and scope -> reviewed company interpretation -> company objective
Company objective -> intended ownership, approval, and change practice
Company objective -> environment realization and resolved technical controls
Realization -> technical evidence and results
Results -> conservative objective and baseline assessment
```

The operating-practice step explains how the organization intends to fulfill
the objective—for example, reviewed identity-provider groups combined with
approved access changes and centrally managed host authorization. It is not
itself technical proof. A realization can support only the portions of that
practice represented by attributable checks and suitable evidence. Manual or
procedural portions remain explicit gaps unless and until they receive their
own evidence contract and assessment logic.

The mapping is many-to-many. Several external requirements may reference one
reusable company objective, and one broad external requirement may require
several company objectives or realizations. The `external_refs` retained on
requirements and technical controls record those relationships but do not
claim completeness, select a realization, or change roll-up semantics.

Each realized technical control retains its effective parameters, stable
implementation and instance identities, definition fingerprint, lineage, and
provenance in the assessment plan. A separate external adapter may consume
those records for a delivery workflow; typed actual-state evidence and OPA
results show whether the required state is currently present. Neither external
generated output nor an apply receipt replaces observed evidence.

Likewise, the rolled-up result is an evidence-backed assessment of the mapped
company objective for one environment, subject, plan, and evaluation time. It
does not by itself establish that every requirement in an external framework
was in scope or satisfied. [ADR 0021](../../docs/adr/0021-project-governed-framework-obligation-declarations.md)
accepts a separate project-owned `FrameworkObligationDeclaration` responsibility for
the closed, versioned scope and obligation ledger. Its bounded satisfaction
projection requires the exact declaration in addition to exact retained assessment
support; it does not turn an Objective result into external conformity.

Verification scenarios should demonstrate this chain with credible synthetic
operational stories and document the exact limit of each claim. The accepted
scenario rules are in
[`verification-scenarios.md`](verification-scenarios.md). ADR 0021 records the
minimum declaration responsibility semantically. #161 implements its experimental
wire form, project path, schema, identity algorithm, runtime, and CLI; ADR 0022's
four-category target and subsequent migration remain separate and are not frozen.

A pure governance obligation needs no synthetic `ControlRequirement`, realization,
or assertion evidence merely to re-prove the reviewed declaration. Its reviewed
governance determination may be affirmative, conclusively negative, or not
established; all three remain declaration-side rather than assessment outcomes. Drift
is not sufficient for assessment: actual occurrence, completion, outcome, population,
or technical material may become ordinary evidence only when company Compliance
policy owns the complete criterion and evaluates Control-unaware descriptive facts.
Otherwise it remains a Governance or other-domain determination. A mixed obligation
requires both authorities only when its assessed portion independently passes that
admission test; the governance determination is not evidence and does not alter
complete required Check membership.

The existing `Baseline` and `BaselineOverlay` contracts continue to describe
technical desired state and explicit changes to it. A realization is not a
replacement for an overlay: an overlay records what policy was adopted or
deviated from, while a realization records how an adopted objective is
implemented and proven.

The distinction is also visible in output: a technical-only plan has control
results but no requirement or requirement-baseline assessments. That is a
complete and valid assessment for its intended scope, not a missing objective.

## 3. Technology-neutral requirement

System [ADR 0024](../../docs/adr/0024-objective-assurance-and-parameter-policy.md)
assigns technology-neutral parameter declarations and explicit derivation to
ParameterPolicy. A realization owns links from exact ParameterPolicy slots into its
required technical, Evidence-input and freshness destinations. Plans materialize
those values with provenance; copied literals do not supply the semantic linkage.
[The parameter contract](policy-parameters.md) defines the concrete fields and
identity projection. Realizations still declare their complete checks. ADR 0024
Tranche A separately represents missing realizations as implementation gaps and
removes the redundant satisfaction expression; complete Check membership and
provenance-only `based_on` remain.
Broader assurance and external-claim authority require separate promoted work.

A `ControlRequirement` is suitable for a signed company-policy release. It has a
stable ID and revision, a technology-neutral statement, and optional external
framework mappings. It contains no environment hostnames, IAM domains, group
names, evidence, or technical parameters.

The synthetic example requirement is
[`company-role-based-access.json`](../../policy-sources/verification-policy/policies/requirements/company/company-role-based-access.json).
Its statement requires interactive access to use centrally governed role or
group membership rather than unmanaged subject-local authorization.

`RequirementBaseline` pins each requirement by revision and content digest.
This prevents a private environment realization or a historical baseline tick
from silently floating to changed central intent.

## 4. Complete ordinary and private realizations

A `ControlRealization` pins the exact requirement it claims to realize and
declares:

- applicable subject types;
- adoption status, assurance method, owner, and approved implementation
  reference;
- a non-empty collection of uniquely identified technical Checks when implemented.

Every declared Check is required. There is no satisfaction expression or optional Check.

The ordinary company Linux example is
[`company-linux-role-based-access.json`](../../policy-sources/verification-policy/policies/realizations/company/company-linux-role-based-access.json).
It is a complete, directly assessable implementation for ordinary company Linux
systems. Its source ownership and acquisition boundary determine who may access
it; the realization carries no core information-classification field.

The restricted alternative is
[`restricted-linux-role-based-access.json`](../../verification/fixtures/iam-private-boundary/policy/realizations/restricted/restricted-linux-role-based-access.json).
It contains fictitious values but represents content that could remain visible
only inside a need-to-know environment.

Both documents embed complete technical instances. This keeps the completeness
claim atomic and reviewable: every declared Check is required and uniquely identified. Reuse occurs
through the shared control implementations and through selecting the complete
company realization where it applies; there is no separate template or binding
resource.

The restricted realization records a pinned `based_on` link to the company
realization. This is provenance only. Nothing is inherited, copied, merged, or
overridden at runtime: the restricted realization remains complete and its
own checks and parameters are the only ones evaluated when it is selected. A
stale or incorrect `based_on` digest is rejected during provenance validation.

## 5. Adoption is not runtime compliance

Realization adoption and current assessment are separate dimensions:

| Adoption | Meaning |
|---|---|
| `implemented` | An approved technical realization exists. |
| `not_implemented` | The applicable objective has no completed realization. |
| `not_applicable` | An approved, reviewed determination says the objective is outside scope. |

An implemented realization may pass, fail, become unknown, encounter an error,
or contain a waived failure at runtime. `implemented` must never produce a pass
without successful technical evidence. An authored `not_implemented` declaration creates an implementation gap with no
Assessment outcome. Its selected realization, owner and declaration remain visible.
Zero matching realizations creates a separate `no_realization` implementation state;
there is no authored adoption to retain or manufacture. Both prevent successful
demonstration without producing FAIL, UNKNOWN, refusal, unassigned scope or N/A.

Parent `not_applicable` comes only from the approved realization-level
determination. A required child technical check returning `not_applicable` is
an incomplete realization result and rolls up to `unknown`, not pass. If a
check truly does not apply, it should not be present in the realization selected
for that subject type.

## 6. Deterministic roll-up

Every Check of an implemented realization is required. The evidence-derived roll-up is:

1. any required `fail` makes the requirement `fail`;
2. otherwise any `error` makes it `error`;
3. otherwise missing, `unknown`, or child `not_applicable` makes it `unknown`;
4. otherwise any `waived` result makes it `waived`; and
5. only every required check passing produces `pass`.

An evidence-established failing Check is conclusive for the Objective roll-up even if another check is
unknown. The output retains every child status and summary count so the parent
tick never hides its basis.

A `RequirementBaseline` uses the same conservative principle. Any required
objective failing prevents the top baseline tick. Missing or inconclusive
required objectives produce `unknown`. Explicitly not-applicable objectives
remain visible and are excluded from the applicable pass condition; when every
required objective is not applicable, the baseline is `not_applicable` rather
than pass.

The unified CLI evaluates the selected realization and performs the deterministic
roll-up as part of an assessment. The failing IAM fixture produces three
technical passes, one technical failure, a failed IAM objective, and a failed
top requirement baseline. Its private source must be independently materialized,
so the repository-owned gate runs that operator flow in a temporary assembly:

```sh
scripts/dev gate iam
```

### Frozen representation and gap reporting

Each planned Objective has `implementation_state`: `no_realization`,
`not_implemented`, `not_applicable`, or `implemented`. Only a selected realization
supplies `adoption`. `technical_instance_ids` is the resolved membership relation;
validation independently reconstructs it from the exact retained realization Checks.
Constant membership `required` and `satisfaction` are rejected in current artifacts.

Compact Objective and RequirementBaseline result rows have `implementation_gap`
independently of their evidence-derived `status`. A gap Objective has `status: null`;
a baseline rolls up only existing outcomes and has `status: null` when all its
Objectives are gaps. Mixed gaps and actual FAIL/ERROR/UNKNOWN/WAIVED/PASS preserve
both dimensions. Explicit N/A remains attributable; all-N/A is N/A, never PASS.
A contribution-only ParameterPolicy has no Objective, Check, or baseline result row.

Overall result `outcome` aggregates actual outcomes; it is null for gap-only
assessment. Exact operation accounting retains that result slot. `all_passed`
requires passing outcomes and no implementation gap, so a mixed PASS/gap operation
is complete but unsuccessful. A gap has no Check failure and is never waiver-eligible.
Current Coverage and exact historical explanation expose implementation state
separately. Framework interpretation receives no passing support from a gap.

This is a coordinated pre-freeze migration. Plan/member/operation/result projections
and exact content pins change, while identity architecture and domains remain.
No compatibility reader or conversion is provided; old artifacts retain their
original meaning under historical tooling.

## 7. Selection and coverage rules

The planner selects realizations after resolving subject identity,
groups, assignments, and requirement baselines:

1. determine whether the parent requirement applies to the subject scope;
2. find realizations whose subject type and trusted `match_labels` constraints
   match;
3. require exactly one complete effective realization with no ordering
   precedence;
4. retain no matching realization as `no_realization`, without fabricated adoption or Assessment outcome;
5. treat multiple applicable realizations as a plan error; and
6. expand the selected realization's technical instances into the subject plan.

A subject with no applicable assignment has Coverage `unassigned` and creates no
expected result.
Once a requirement is assigned, zero applicable realizations retains
`no_realization` implementation state and a gap; exactly one retains its authored
state and, when implemented, expands and evaluates every Check; multiple applicable
realizations make policy resolution ambiguous and planning fails. Evidence never
selects policy or a realization.

The production planner exercises these rules. The ordinary
and restricted Linux example intentionally uses different values of the single
`iam-profile` label so its two realization selectors are disjoint. That example
does not require classifications or groups generally to form mutually exclusive
partitions: stable governed persona, access-profile, deployment-model, environment,
lifecycle and factual-membership inputs may overlap. When that overlap makes more
than one realization applicable to the same assigned requirement, the existing
ambiguity failure applies without order or specificity precedence. Applicability
selects the realization before its complete Check set is evaluated, so the
roll-up cannot hide a failed or missing implementation branch.

## 8. Need-to-know compilation boundary

Final policy compilation and rendering happen within the deployed environment:

```text
Verified shared-policy artifact by digest
              +
Private environment overlay and realization repository
              +
Private project inventory and assignments
              +
Local typed evidence
              ↓
Local planner and OPA evaluator -> exact plans/results
```

Shared policy distribution is one-way. The central repository does not clone,
compile, or inspect the private realization. The local environment records the
actual planning composition, operation/member/bound-plan identities, technical
results, and full plan-owned realization provenance.

Neither `ControlRealization.metadata` nor the frozen plan's realization projection
carries an information-classification enum. Confidentiality is enforced by source
ownership, acquisition/materialization, repository access, and deployment controls;
the assessment engine does not make access decisions from a semantic label.

The implemented experimental ADR 0021 `framework status` / `framework explain`
projection receives the exact retained declaration, an exact operation anchor as the
scope witness, and the exact independently valid bound plans/results needed by its
assessed or direct portions. A downstream signed
export would remain an attestation or presentation from that environment, not a new
core result, central re-evaluation, external certification, or substitute for those
exact inputs. Raw evidence, parameters, implementation names, group names, and
remediation may remain local under a separately designed disclosure boundary.

## 9. Implemented contracts and limitations

Strict Draft 2020-12 schemas now exist for:

- `ControlRequirement`;
- `RequirementBaseline`; and
- `ControlRealization`.

The policy gate validates parent and optional `based_on` pins, unique check
identities, complete required Check membership, implementation applicability, and
effective parameters. Subject planning enforces trusted-label exactly-one
selection. Evaluation supports the declared result states and conservative
requirement and baseline roll-up.
The planner freezes the selected realization, requirement ancestry, adoption,
technical checks, and provenance into the content-addressed subject plan. The
evaluator persists technical, requirement, and requirement-baseline results,
and the status/explain views expose all three levels.

The complete result envelope is intrinsically validated against the strict
`assessment-results/v4` tooling contract. Before persistence or full reporting,
mandatory validation against the exact assessed plan recalculates compact
requirement and top-baseline outcomes and checks conservative roll-up precedence,
so an inconsistent parent tick cannot be accepted merely because its JSON shape is
valid.

Requirement `external_refs` are frozen into the exact plan and interpreted with the
compact immutable requirement assessment. `assessment mappings --level objective`
therefore exposes the immutable outcome of the complete realized objective from an
exact validated pair rather than inferring it from one mapped technical check.

The registered `iam-realization` project assembles the named `control-library`,
`verification-policy`, and `environment-private` sources locally. The private
source contains only the restricted realization; schemas and reusable controls
come from `control-library`, while requirement intent, requirement baseline,
and the ordinary company realization come from verification policy. The
resulting plan records all three source digests in its actual planning
composition and binds its resolved member commitment through the frozen
operation. The project provides the illustrative
inventory DAG, assignment, fixture collector input, and intentional failing
result; reusable Rego and evidence schemas remain in `control-library`.
The [IAM gate](../../verification/fixtures/iam-private-boundary/README.md)
physically materializes `environment-private` separately before execution. The contract deliberately
does not yet:

- support nested, threshold, or alternative satisfaction expressions;
- sign shared releases or exported assurance claims;
- define inheritance or overlays on realizations themselves;
- provide a generic process/GRC/activity-history evidence abstraction.

Complete embedded checks and non-inheriting `based_on` provenance are the
accepted authoring model. ADR 0024 Tranche B now places declarations, binding,
tailoring, and contributions on explicitly applicable `ParameterPolicy` resources;
realization-owned symbolic links consume their resolved values for Objective-backed
Checks. Realization templates and automatic realization inheritance remain deferred.

The stable Linux hardening rollout scenario in
`verification/scenarios/projects/linux-hardening-rollout` uses only
the complete shared company realization. Its container host supplies all four
access observations and rolls up to a passing objective. Its standard host
deliberately supplies no access document, so all four checks and the objective
remain `unknown`; the unrelated audit-package failure may be waived without
affecting that roll-up. The restricted alternative and its private details
remain confined to the separately materialized synthetic IAM boundary project;
real private environment sources remain physically separate.
