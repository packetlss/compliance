# Control Requirements and Environment Realizations

Status: **Implemented initial contract (v0.1)**  
Last updated: **2026-09-04**

This document defines how a high-level regulatory or company control objective
can receive a defensible top-level result from environment-private technical
checks. The initial `allOf` contract is integrated with policy validation,
rendered assessment plans, evaluation results, and operator views.

This layer is optional. Standalone technical baselines remain the preferred
model for package lists, hardening profiles, and configuration drift when no
complete higher-level objective needs to be asserted. A subject may receive
those controls alongside realized objectives in the same assessment plan. The
realization model exists to support a genuine objective-level assurance claim,
not to wrap every useful technical check in governance ceremony.

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
          ↓ declared satisfaction rule
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
was in scope or satisfied. Complete framework claims require versioned scope,
accounting for applicable and omitted requirements, and visible
not-applicable determinations in addition to objective results.

Verification scenarios should demonstrate this chain with credible synthetic
operational stories and document the exact limit of each claim. The accepted
scenario rules are in
[`verification-scenarios.md`](verification-scenarios.md). A separate
machine-readable operating-practice or framework-coverage resource remains
deferred until these scenarios reveal a stable contract that the current
requirement, realization, plan, and explanation artifacts cannot express.

The existing `Baseline` and `BaselineOverlay` contracts continue to describe
technical desired state and explicit changes to it. A realization is not a
replacement for an overlay: an overlay records what policy was adopted or
deviated from, while a realization records how an adopted objective is
implemented and proven.

The distinction is also visible in output: a technical-only plan has control
results but no requirement or requirement-baseline assessments. That is a
complete and valid assessment for its intended scope, not a missing objective.

## 3. Technology-neutral requirement

A `ControlRequirement` is suitable for a signed company-policy release. It has a
stable ID and revision, a technology-neutral statement, and optional external
framework mappings. It contains no environment hostnames, IAM domains, group
names, evidence, or technical parameters.

The synthetic example requirement is
[`company-role-based-access.json`](https://github.com/packetlss-labs/compliance-verification-policy/blob/main/policies/requirements/company/company-role-based-access.json).
Its statement requires interactive access to use centrally governed role or
group membership rather than unmanaged subject-local authorization.

`RequirementBaseline` pins each requirement by revision and content digest.
This prevents a private environment realization or a historical baseline tick
from silently floating to changed central intent.

## 4. Complete ordinary and private realizations

A `ControlRealization` pins the exact requirement it claims to realize and
declares:

- its information classification;
- applicable subject types;
- adoption status, assurance method, owner, and approved implementation
  reference;
- independently attributable technical control instances; and
- a constrained satisfaction expression over those instances.

The ordinary company Linux example is
[`company-linux-role-based-access.json`](https://github.com/packetlss-labs/compliance-verification-policy/blob/main/policies/realizations/company/company-linux-role-based-access.json).
It is a complete, directly assessable implementation for ordinary company Linux
systems. Its `internal` classification illustrates that shared company policy
is not necessarily public policy.

The restricted alternative is
[`restricted-linux-role-based-access.json`](https://github.com/packetlss-labs/compliance-project-iam-realization/blob/main/policy/realizations/restricted/restricted-linux-role-based-access.json).
It contains fictitious values but represents content that could remain visible
only inside a need-to-know environment.

Both documents embed complete technical instances. This keeps the completeness
claim atomic and reviewable: every declared check must occur exactly once in
`satisfaction.allOf`, and every referenced check must be defined. Reuse occurs
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
without successful technical evidence. A `not_implemented` required objective
produces a failing requirement assessment while retaining the separate
adoption state.

Parent `not_applicable` comes only from the approved realization-level
determination. A required child technical check returning `not_applicable` is
an incomplete realization result and rolls up to `unknown`, not pass. If a
check truly does not apply, it should not be present in the realization selected
for that subject type.

## 6. Deterministic roll-up

The first prototype permits only `satisfaction.allOf`. Its precedence is:

1. any required `fail` makes the requirement `fail`;
2. otherwise any `error` makes it `error`;
3. otherwise missing, `unknown`, or child `not_applicable` makes it `unknown`;
4. otherwise any `waived` result makes it `waived`; and
5. only every required check passing produces `pass`.

A failing result is conclusive for an `allOf` rule even if another check is
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
top requirement baseline:

```sh
uv run compliance --project iam-realization \
  assessment run host/restricted-linux-01
uv run compliance --project iam-realization \
  assessment explain host/restricted-linux-01
```

## 7. Selection and coverage rules

The planner selects realizations after resolving subject identity,
groups, assignments, and requirement baselines:

1. determine whether the parent requirement applies to the subject scope;
2. find realizations whose subject type and trusted `match_labels` constraints
   match;
3. require exactly one complete effective realization with no ordering
   precedence;
4. treat no matching realization as `not_implemented`, never as not applicable;
5. treat multiple unresolved realizations as a plan error; and
6. expand the selected realization's technical instances into the subject plan.

The production planner and selection helper exercise these rules. The ordinary
and restricted Linux realizations require mutually exclusive trusted
`iam-profile` labels. No matching label reports the requirement as not
implemented for that subject; overlapping selectors are an error. Applicability
selects the realization before its `allOf` rule is evaluated, so the roll-up
expression cannot hide a failed or missing implementation branch.

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
Local compiler, planner, OPA evaluator, and result store
```

Shared policy distribution is one-way. The central repository does not clone,
compile, or inspect the private realization. The local environment records the
shared release digest, private policy revision, rendered plan digest, technical
results, and full realization provenance.

If central governance needs framework-level status, the environment may export
a signed minimal assurance claim containing requirement identity, result,
assessment time, policy digests, and an opaque subject reference. Such a claim
is an attestation from the local evaluator, not a central re-evaluation. Raw
evidence, parameters, implementation names, group names, and remediation may
remain local.

## 9. Implemented contracts and limitations

Strict Draft 2020-12 schemas now exist for:

- `ControlRequirement`;
- `RequirementBaseline`; and
- `ControlRealization`.

The policy gate validates parent and optional `based_on` pins, unique check
identities, complete `allOf` coverage, implementation applicability, and
effective parameters. Subject planning enforces trusted-label exactly-one
selection. Evaluation supports the declared result states and conservative
requirement and baseline roll-up.
The planner freezes the selected realization, requirement ancestry, adoption,
technical checks, and provenance into the content-addressed subject plan. The
evaluator persists technical, requirement, and requirement-baseline results,
and the status/explain views expose all three levels.

The complete result envelope is validated against the strict
`assessment-results/v4` tooling contract before persistence and when loaded for
reporting. Validation recalculates technical, requirement, and top-baseline
summaries and independently checks the conservative roll-up precedence, so an
inconsistent parent tick cannot be accepted merely because its JSON shape is
valid.

Requirement `external_refs` are frozen into the plan and copied into the
immutable requirement assessment. `assessment frameworks --level objective`
therefore exposes the current result of the complete realized objective rather
than inferring it from one mapped technical check.

The registered `iam-realization` project assembles the named `control-library`,
`verification-policy`, and `environment-private` sources locally. The private
source contains only the restricted realization; schemas and reusable controls
come from `control-library`, while requirement intent, requirement baseline,
and the ordinary company realization come from verification policy. The
resulting plan records all three source digests and the final deterministic
policy revision. The project provides the illustrative
inventory DAG, assignment, fixture collector input, and intentional failing
result; reusable Rego and evidence schemas remain in `control-library`.
The [IAM gate](../../verification/fixtures/iam-private-boundary/README.md)
physically materializes `environment-private` separately before execution. The contract deliberately
does not yet:

- support nested, threshold, or alternative satisfaction expressions;
- sign shared releases or exported assurance claims; or
- define inheritance or overlays on realizations themselves.

Complete embedded checks and non-inheriting `based_on` provenance are the
accepted initial authoring model; template/binding and automatic realization
inheritance remain deliberately deferred.

The stable Linux hardening rollout scenario in
`verification/scenarios/projects/linux-hardening-rollout` uses only
the complete shared company realization. Its container host supplies all four
access observations and rolls up to a passing objective. Its standard host
deliberately supplies no access document, so all four checks and the objective
remain `unknown`; the unrelated audit-package failure may be waived without
affecting that roll-up. The restricted alternative and its private details
remain confined to the separately materialized synthetic IAM boundary project;
real private environment sources remain physically separate.
