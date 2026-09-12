# ADR 0017: Author policy and technical-check meaning on canonical source objects

- **Status:** Implemented under #100; experimental, not frozen
- **Date:** 2026-09-07
- **Architecture contract:** [#97](https://github.com/packetlss/compliance/issues/97)
- **Implementation:** [#100](https://github.com/packetlss/compliance/issues/100)

## Context

The existing architecture already retains the causal path needed to explain why
technical policy applies:

```text
supplied inventory facts
    -> group membership
    -> assignment
    -> resolved policy
    -> effective technical check
    -> required evidence
```

It also retains stable instance and implementation IDs, effective parameters,
evidence dependencies and freshness, baseline and realization lineage, overlay
derivations, deviations, exclusions, source provenance and content identities.
That path must remain the explanation model. A second policy hierarchy would
duplicate resolved policy rather than fill the actual gap.

Inspection at baseline `ce8abf01edd37a760ac709f9cb2f44cc01690ecf`
found the narrower gap below.

| Current object or artifact | Current authored or frozen meaning | Gap |
| --- | --- | --- |
| `Control` | Stable ID/version, executable entrypoint, applicable subject types, parameter schema, required evidence contracts, default severity and remediation | No authored human check name or intrinsic purpose |
| `Baseline` / `BaselineOverlay` | Stable ID/revision, exact controls or pinned derivation and operations; optional `origin` exists only on `Baseline` | No canonical human name for the selected technical policy |
| `ControlRequirement` | Required `title` and `statement`; optional rationale and external references | Already sufficient to name and explain an Objective |
| `RequirementBaseline` | Stable ID/revision, exact requirement pins, optional origin, parameter derivation | No canonical human name for the selected objective policy |
| `ControlRealization` | Pinned Objective, applicability, adoption, complete checks, satisfaction and parameter links | The relationship is already structured; no missing general-purpose prose field was demonstrated |
| Rendered plan | Complete resolved policy facts; active controls also embed the Control manifest under `policy_inputs` | No first-class frozen policy/check vocabulary, and excluded controls do not retain the Control definition from which a reporter could recover it |

For example, the current technical-only package plan can expose
`verification.technical-packages@1`,
`verification.technical-packages.required`, and `linux.packages.required`, plus
the package parameters and `linux.packages/v1` dependency. It cannot produce
“Linux package baseline” or “Required system packages are installed” from
authored domain meaning. Transforming those IDs, interpreting Rego, or treating
the remediation sentence as purpose would invent meaning.

This decision is subordinate to ADRs 0005–0012 and 0016. In particular, it
preserves independently named content-addressed policy sources, exact-only
coalescing, fail-closed divergence, standalone technical assessment, optional
Objective assurance, explicit parameter/freshness resolution, closed-world
scope, immutable plan/result attribution and the external-adapter boundary.
It changes no assessment status or evidence semantics.

## Decision

Choose **authored meaning on canonical source objects**. The minimum new source
vocabulary is:

1. a required `spec.title` on every assignable policy root: `Baseline`,
   `BaselineOverlay`, and `RequirementBaseline`;
2. a required `spec.title` on every `Control`; and
3. a required `spec.purpose` on every `Control`.

No other descriptive field is added. Existing `ControlRequirement.spec.title`
and `spec.statement` remain the Objective name and meaning. Existing remediation,
parameters, derivations, deviations and exclusion rationale retain their distinct
jobs.

These fields are normative authored policy meaning and are identity-bearing,
but they are non-executable: changing them changes which authored policy bytes
and explanation were assessed, while never changing a selector, resolved value,
evidence dependency, criterion invocation or result by interpreting the prose.

### A. Operator vocabulary

| Operator concept | Canonical authored source | Meaning |
| --- | --- | --- |
| Applicable policy | `Baseline.spec.title`, `BaselineOverlay.spec.title`, or `RequirementBaseline.spec.title` | Concise human name of the exact assigned policy root. If several policy roots apply, report each; do not choose one by order. |
| Check | `Control.spec.title` | Concise human name of the reusable technical evaluation. It must remain true for every valid instance of that Control. |
| Check purpose | `Control.spec.purpose` | Concise authored statement of what condition the technical evaluation verifies. It is stable across parameter bindings and is not an executable rule. |
| Objective | Existing `ControlRequirement.spec.title` | Concise name of a desired technology-neutral outcome. |
| Objective meaning | Existing `ControlRequirement.spec.statement` | Normative desired outcome. Existing optional `rationale` may explain why it matters. |
| Effective check context | Existing resolved instance parameters, evidence inputs and freshness | The concrete configured instance. These facts specialize the stable check meaning without rewriting it. |
| Why policy applies | Existing group-membership and assignment path | Scope explanation. A title never selects policy. |
| Why a check was tailored | Existing overlay derivation plus deviation rationale | Exact before/after structured state and reviewed reason. |
| Why a check was excluded | Existing excluded disposition plus deviation rationale | Policy disposition, not an assessment result. |
| What to do after failure | Existing effective `remediation` | Optional corrective guidance, distinct from check purpose. |

Normal presentation joins a control's existing provenance baseline reference to
the corresponding resolved policy title. The same exact policy reference reached
through several assignments may be shown once with every path retained. Distinct
policy references remain distinct even when their titles are equal; advanced output
disambiguates them by stable reference and provenance.

`title` is a concise label, not a sentence generated from an ID. `purpose` is
one or more concise authored sentences describing the invariant checked. Both
must contain non-whitespace text. Their exact JSON string values are preserved;
titles need not be globally unique and must never be used as lookup keys.

The Control purpose must be accurate without relying on one particular parameter
value. For `linux.sysctl.required`, for example, the stable meaning is that Linux
kernel settings match policy. `net.ipv4.ip_forward = 1` is effective instance
context. If one reusable Control cannot truthfully have one intrinsic name and
purpose across all valid instances, the authoring problem is a Control boundary,
not a reason to add instance prose overrides.

No general policy description is required. A policy title plus its existing
selected controls/Objectives, scope path and structured tailoring is enough for
the accepted operator scenarios. A future demonstrated need for policy purpose
must return to architecture rather than accrete conventional documentation fields.

The minimum check vocabulary distinguishes **what is checked** (`purpose`) from
**how to fix a failure** (`remediation`). It does not add a mandatory technical
“why it matters” field: an Objective may already provide that context through its
statement and optional rationale, while a technical-only check remains adequately
explained by its intrinsic purpose and exact configured criterion. A demonstrated
need for check-specific risk rationale is future architecture work.

### B. Ownership, inheritance, override and validation

| Field | Owner | Inheritance and override | Validation |
| --- | --- | --- | --- |
| Technical policy `title` | Each `Baseline` or `BaselineOverlay` | Not inherited and not an override of a parent title. Every overlay names the new assignable effective policy it defines. No overlay operation changes another policy object's title. | Required non-whitespace string; retained on each resolved assigned baseline. |
| Objective policy `title` | Each `RequirementBaseline` | Not inherited. A parameter-derived child names itself; it does not replace the parent title. | Required non-whitespace string; retained on each resolved assigned requirement baseline. |
| Check `title` | Canonical `Control` definition | Inherited by every instance using that implementation. `tailor`, `exclude`, `add`, and `annotate` cannot override it. `substitute` uses the selected substitute Control's title. | Required non-whitespace string; frozen for active and excluded resolved checks and checked against the selected implementation definition during planning/plan validation where the definition is embedded. |
| Check `purpose` | Canonical `Control` definition | Same rules as check title. Effective parameters and derivations provide context; they do not rewrite purpose. | Required non-whitespace string; frozen for active and excluded resolved checks under the same consistency rule. |
| Objective `title` / `statement` | Existing `ControlRequirement` | Unchanged. A realization references the exact Objective; it does not override its words. | Existing required-string validation and exact requirement digest pins remain. |
| Remediation | Existing Control default or effective instance/`annotate` value | Existing precedence remains: effective instance, then Control default, then planner fallback. It is the only existing check text that an overlay may specialize. | Existing schema and resolved-plan validation remain. It is never a fallback for title or purpose. |
| Tailoring/exclusion reason | Existing deviation record | Owned by the operation that changes disposition or criteria. It explains that operation, not intrinsic check meaning. | Existing complete deviation validation remains. |
| Realization relationship | Existing pinned requirement, applicability, checks, satisfaction and parameter links | No new title, description or override. A realization's structured relationship is authoritative. | Existing exact pin, exactly-one selection, complete `allOf`, applicability and typed-link validation remain. |

`metadata.origin.name` does not satisfy the new policy title requirement. Origin
describes the source/lineage of authored policy and is optional on only some roots;
it does not consistently name the exact selected policy. Assignment and group IDs
also remain stable scope identities rather than presentation names.

A resolved plan must carry the selected policy title on each
`resolved_baselines[]` and `resolved_requirement_baselines[]` record, and the
Control title and purpose on each active and excluded control record. These are
lossless projections of canonical source meaning, not independently authored
presentation text. Existing frozen `policy_inputs` remain the source-fact basis
where present; planner and artifact validation must reject contradictory projected
meaning rather than choose one copy. Excluded controls must gain enough frozen
selected-Control definition facts to validate that same relationship without
reloading a current policy checkout. Compact results do not copy this policy-owned
meaning: full interpretation continues to require the exact validated plan/result
pair.

Normal output leads with authored titles and purpose. Stable IDs, revisions,
digests, paths, fingerprints and composition belong in advanced provenance
drill-down and diagnostics. They remain visible and authoritative for identity,
but no implementation ID is transformed into primary human prose.

### C. Identity semantics

The new fields are **semantic and identity-bearing authored policy content**.
“Does not affect evaluation” does not mean “excluded from identity.” A historical
operator must be able to recover the exact authored explanation that accompanied
the assessed policy, and two sources must not silently coalesce when they disagree
about what the same check means.

| Field | Identity-bearing? | Consequences |
| --- | --- | --- |
| Policy-root `spec.title` | Yes | Changes the policy-source tree identity and the complete Baseline/Overlay/RequirementBaseline resource digest. Parent digest pins and locks that consume changed content must be updated. The resolved plan title/digest changes policy diff and member-plan identity. |
| `Control.spec.title` | Yes | Changes the policy-source tree identity, exact-definition coalescing digest, Control implementation content fingerprint and frozen plan meaning. Exact implementation pins in realization parameter links must be updated. |
| `Control.spec.purpose` | Yes | Same as Control title. Purpose disagreements are definition conflicts even when Rego and parameter schemas match. |
| Existing Objective title/statement/rationale | Yes, unchanged | They remain part of the requirement document digest and exact requirement pins; title and statement are already frozen into the plan, with the full document retained in parameter facts. |
| Existing remediation | Yes, unchanged | It remains versioned policy metadata. Effective remediation already affects the resolved plan and plan identity without affecting pass/fail logic. |

The current effective technical instance `definition_fingerprint` remains the
fingerprint of the instance state described by the baseline-inheritance contract.
It does not absorb Control title/purpose and its provisional algorithm is not
redesigned here. The separate Control implementation fingerprint already hashes
the complete manifest, parameter schema and implementation-local modules; it
therefore changes when Control title or purpose changes. The plan also freezes
title/purpose directly. This preserves the distinction between an effective
instance definition and the implementation definition it uses.

Therefore a title/purpose-only edit does not change an effective instance's
`definition_fingerprint` or an overlay operation's
`expected_parent_fingerprint`. A policy-root title edit does change that root's
complete document digest, so a child `extends` pin to that document must be updated.
Control title/purpose edits change exact Control implementation fingerprints and
their consumers, but do not silently rebase technical instance derivations.

Under the current identity construction, any changed policy-source bytes also
change that source's content digest and actual composition digest. Frozen operation
identity includes planning composition plus every member-plan digest. Consequently,
after migration or a later wording change:

- newly rendered applicable member-plan digests change when their frozen meaning
  or policy-root digest changes;
- the operation ID and every bound plan ID in an operation may change through the
  changed composition or member commitment, including unaffected siblings in the
  same operation;
- a newly produced result ID changes because result identity includes exact
  `plan_id`; and
- existing historical plans/results retain their original IDs and meaning and are
  never rewritten.

This is the existing content-addressed consequence, not a new digest algorithm.
No title/purpose-specific normalization, digest exclusion, or presentation-only
identity is introduced. Current algorithms remain provisional and are not frozen
by this ADR.

### D. Deterministic resolution and overlay behavior

Policy sources remain an unordered set.

- Exact-identical definitions in the same ADR 0019 typed lookup namespace,
  including identical title and purpose, may coalesce while retaining all source
  locators.
- Same-identity definitions with different title or purpose are divergent resource
  definitions and fail closed. Equal executable fields do not make their human
  semantic conflict mergeable.
- Equal titles on different stable IDs do not merge the objects. Titles are never
  keys, selectors, precedence or identity substitutes.
- Existing effective-instance conflicts remain conflicts even if both candidates
  have the same friendly title. Friendly names may enrich a diagnostic but cannot
  select a winner.
- Source/file/assignment order, latest wording, and overlay position grant no text
  precedence.

Overlays do not override check title or purpose. `tailor` changes structured
effective values and retains the Control meaning; `exclude` retains the same
meaning while changing disposition; `add` obtains meaning from its Control; and
`substitute` obtains meaning from the substituted Control. Existing `annotate`
continues to own severity, remediation and external references only. Adding
presentation-specific title/purpose overlay operations would create two authors
for intrinsic meaning and is rejected.

No evaluator, group resolver, assignment resolver, overlay resolver, parameter
resolver, planner or evidence selector may parse, pattern-match or otherwise
interpret title, purpose, Objective wording, remediation or deviation prose to
derive technical behavior. In particular, wording such as “Ensure X is disabled”
cannot create `expected = false`; only the existing structured policy can.

### Candidate assessment

| Option | Assessment | Decision |
| --- | --- | --- |
| A — authored meaning on canonical source objects | One owner for intrinsic meaning; exact historical plan attribution; existing conflict and content-addressed semantics apply; small coordinated schema/source/plan migration | **Accepted** |
| B — separate nonsemantic presentation projection | Avoids some domain hashes only by creating a second mutable owner that can say something different from assessed policy. It weakens historical reproducibility and needs its own lookup/version/conflict semantics. | Rejected |
| C — reuse current data unchanged | Works for Objective title/statement, scope paths, parameters, deviations and evidence. It fails technical-only policy/check naming, excluded-check naming, and generic check purpose without transforming IDs, reading Rego or misusing remediation. | Rejected |
| Per-instance or realization-authored check prose | Can make one parameterization sound polished, but duplicates the canonical Control meaning across baselines and realizations and creates override/conflict rules for every tailored instance. Existing structured context already distinguishes instances. | Rejected absent a concrete future case |

## E. Deterministic examples

The following are normative presentation examples. Layout is not frozen, but the
ownership and claims shown are required. Titles and purposes are illustrative
authored values to be committed during migration; digests are deliberately
abbreviated because migration changes them.

### Technical-only policy

Normal operator explanation:

```text
Asset: host/technical-A
Applicable policy: Linux package baseline
Applies via: managed-linux -> managed-linux-packages

Check: Required system packages are installed
Purpose: Verify that the packages mandated by this policy are present.
Effective parameters: ecosystem=linux-native, required=[auditd]
Required evidence: linux.packages/v1
Freshness: 24 hours
```

There is no Objective line.

Advanced provenance drill-down:

```text
Policy: verification.technical-packages@1
Policy digest: sha256:<baseline-content>
Policy source: verification-policy:baselines/technical/technical-packages.json
Check instance: verification.technical-packages.required
Control implementation: linux.packages.required@1
Implementation fingerprint: sha256:<manifest-schema-modules>
Instance definition fingerprint: sha256:<effective-instance>
Evidence dependency: observation -> linux.packages/v1, max_age=86400s
Planning composition: control-library=sha256:<tree>, verification-policy=sha256:<tree>
Plan: sha256:<operation-bound-plan>
```

The normal `24 hours` is a deterministic display of the resolved fixed duration
`86400s`, not prose inferred from an implementation ID.

### Company IAM Objective and checks

Normal operator explanation:

```text
Asset: host/container-app-01
Applicable policy: Company identity and access objectives

Objective: Access is granted through centrally governed roles
Meaning: Interactive access to governed systems must be authorized through centrally governed role or group membership and must not depend on unmanaged subject-local authorization.
Realized by:
  Check: Linux access settings match policy
  Purpose: Verify that a Linux identity or access setting has the effective value mandated by policy.
  Effective context: section=packages, setting=sssd_installed, expected=true

  Check: Linux access settings match policy
  Purpose: Verify that a Linux identity or access setting has the effective value mandated by policy.
  Effective context: section=sssd, setting=domain, expected=company.example

  Check: Linux access settings match policy
  Purpose: Verify that a Linux identity or access setting has the effective value mandated by policy.
  Effective context: section=ssh, setting=allowed_groups, expected=[company-linux-operators]

  Check: Linux access settings match policy
  Purpose: Verify that a Linux identity or access setting has the effective value mandated by policy.
  Effective context: section=accounts, setting=unmanaged_interactive_accounts, expected=[]
```

The Objective is not repeated as the check description. The reusable Control owns
intrinsic check meaning; each realized instance supplies exact context.

Advanced provenance drill-down:

```text
Policy: company.identity-access-objectives@1
Objective: company.iam.role-based-access@1
Objective digest: sha256:<requirement-content>
Realization: company.linux.central-role-access@1
Realization digest and source attribution: sha256:<realization-content> / <policy-source>
Freshness slot: company.iam.role-based-access/privileged_evidence_max_age = 86400s
Consumption: slot -> each named realization check dependency observation/max_age
Check instance: company.linux.rbac.sssd-installed
Control implementation: linux.access.setting-equals@1
Planning sources and plan: <exact named source digests and bound plan ID>
```

### Linux persona tailoring

Normal operator explanation:

```text
Asset: host/container-app-01
Applicable policy: Company container-runtime host policy

Check: Linux kernel settings match policy
Purpose: Verify that configured Linux kernel parameters have the values mandated by policy.
Effective parameters: settings={net.ipv4.ip_forward=1}
Tailoring: settings changed from {net.ipv4.ip_forward=0} to {net.ipv4.ip_forward=1}
Why: Approved container runtime hosts require IPv4 forwarding for workload networking.
Required evidence: linux.sysctl/v1
Freshness: 24 hours
```

“Tailoring” is rendered from the exact structured before/after parameter facts;
the rationale is authored. The base title/purpose is not rewritten for the persona.

Advanced provenance drill-down:

```text
Policy lineage:
  benchmark.example.linux-server-hardening@2026.1 sha256:<parent>
  company.linux-server-hardening@1 sha256:<company>
  company.container-runtime-host@1 sha256:<persona>
Check instance: benchmark.example.linux-server.ip-forwarding-disabled
Control implementation: linux.sysctl.required@1
Alignment/disposition: tailored / evaluate
Parent fingerprint: sha256:915a4af338d0397029462fbca2069aeb4166615dc65301460502447ff43d8591
Before: settings={net.ipv4.ip_forward=0}
After: settings={net.ipv4.ip_forward=1}
Deviation: DEV-LINUX-CONTAINER-001 / required-platform-feature
Approval/review: company-policy/container-runtime-host-networking / 2027-08-31
```

### Excluded check

Normal operator explanation:

```text
Asset: workstation/tooling-macos-fixture
Applicable policy: Company macOS policy

Check: Required Homebrew formulae are installed
Purpose: Verify that the Homebrew formulae mandated by policy are present.
Disposition: Excluded
Reason: The illustrative benchmark audit formula is not part of the approved company workstation tooling.
Assessment result: none (excluded policy disposition)
```

Advanced provenance drill-down:

```text
Policy: company.macos-policy@1
Check instance: benchmark.example.macos.audit-formula-required
Control implementation: macos.homebrew.formulae-required@1
Alignment/disposition: deviated / excluded
Derivation: exclude by company.macos-policy@1
Parent fingerprint: sha256:97eb6ef06ca9ad85422311b55328f46518a97dfcf1f640b1ebb5a46d200fc62a
Deviation: DEV-MAC-002 / alternative-company-control
Approval/review: company-policy/endpoint-monitoring / 2027-01-31
```

No PASS, UNKNOWN, ERROR or N/A is manufactured for an excluded check.

### Conflicting policy

If `source-a` and `source-b` both provide the same Control identity but one says
“Verify that required packages are present” and the other says “Verify only that
the package manager is reachable,” the catalog is invalid even when executable
fields are identical:

```text
Policy resolution: INVALID
Conflict: Control linux.packages.required
Candidate A: Required system packages are installed
  source-a:controls/linux/packages-required/control.json
Candidate B: Package manager is reachable
  source-b:controls/linux/packages-required/control.json
Disposition/result: none; no source-order winner
```

Similarly, two applicable baselines that define one instance ID with incompatible
effective parameters remain an effective-instance conflict. Friendly titles may
make the candidates easier to recognize; they never make divergence mergeable.

## F. Migration and compatibility

The project is pre-freeze and has no external compatibility consumers. The new
fields become required in one coordinated cutover; there is no optional-field grace
period, fallback from IDs/remediation, compatibility alias, or dual old/new reader.
Keeping them optional would preserve the exact unexplained case this decision is
intended to remove.

The implementation migration must:

1. add required non-whitespace `spec.title` and `spec.purpose` to the Control
   authoring schema;
2. add required non-whitespace `spec.title` to the Baseline, BaselineOverlay and
   RequirementBaseline authoring schemas;
3. author those fields on all maintained objects, including the current 13 Controls,
   15 technical Baseline/BaselineOverlay objects and 3 RequirementBaseline objects;
4. freeze the selected policy/check meaning into active and excluded v4 plan records,
   retain the selected Control definition facts needed for offline validation,
   update the strict plan schema and enforce source/projection consistency;
5. make normal explanation and stored-plan policy diff expose the authored meaning
   while retaining current advanced identifiers/provenance;
6. recompute affected Control implementation fingerprints, realization destination
   pins, Baseline/RequirementBaseline `extends` document pins, policy-source
   identities, composition locks or release fixtures, and maintained expectations;
   existing overlay `expected_parent_fingerprint` values remain unchanged unless
   effective instance state also changes;
7. regenerate disposable development plans/results rather than checking them in; and
8. preserve historical source, plans and results unchanged for use with their
   historical tooling.

The current authoring API versions and `assessment-plan/v4` schema gain these
required fields in place under the existing pre-freeze policy. There is no version
bump or compatibility reader. No digest algorithm is changed or promoted to `/v1`.
The changed included content nevertheless produces changed digests and fingerprints
as described above.

Adding the words alone does not change Rego decisions for identical structured
policy and evidence. New plan IDs cause existing current-plan comparisons to report
different plans, as they must: the exact assessed authored meaning changed. Stored
policy diff must report title/purpose changes as effective policy metadata changes,
not hide them as identity-context-only churn.

## G. Implementation promotion

Promote **one atomic implementation issue**. Splitting schemas/source migration from
plan/explanation consumption would either make maintained sources invalid or permit
new authored meaning to be discarded before historical attribution.

### Objective

Implement the required source-authored policy/check vocabulary accepted here and
carry it losslessly through validation, resolution, v4 plans, policy diff and the
existing assessment explanation, without changing technical evaluation.

### Bounded write scope

- the four policy authoring schemas named above;
- maintained Control, Baseline, BaselineOverlay and RequirementBaseline source
  objects plus mechanically affected digest/fingerprint pins;
- planner/catalog resolution and v4 assessment-plan schema/semantic validation;
- existing assessment explanation and policy diff consumers;
- focused tooling/policy/scenario tests and directly applicable contract docs; and
- maintained lock/release test inputs whose exact identities change.

Do not change Rego decisions, assessment-result payload fields, evidence schemas,
inventory/group/assignment semantics, ControlRequirement or ControlRealization
descriptive schemas, statuses, waiver logic, adapter boundaries, release topology,
or private operational data.

### Schema and identity impact

The authoring and v4 plan schemas gain required fields in place under the pre-freeze
contract. Affected source/resource/implementation/composition/member/operation/plan
and new-result identities change according to section C. Effective instance
fingerprint construction and all digest algorithm identifiers remain unchanged.

### Invariants

- A technical-only policy is fully explainable without an Objective.
- Objective and Check remain separate concepts and separately authored.
- One Control owns intrinsic check title/purpose; instances own effective context.
- Text never drives selection, resolution, parameters, evidence, evaluation or
  roll-up.
- Source/file order remains nonsemantic; divergent same-identity text fails closed.
- Overlays cannot override check title/purpose; existing remediation annotation and
  deviation semantics remain.
- Exclusion remains policy disposition with no assessment result.
- The exact plan, not the compact result or a mutable catalog, owns historical
  policy/check meaning.

### Acceptance criteria

1. Schema validation rejects every affected source kind when its required title or
   purpose is absent, empty or whitespace-only.
2. All maintained source trees validate with authored, reviewable text.
3. The technical-only scenario emits the normal explanation shown above with zero
   Objectives and no prose inferred from IDs.
4. The IAM scenario emits policy -> Objective -> realized checks, uses the existing
   Objective statement, and uses Control meaning rather than repeating the Objective
   title for each check.
5. The Linux persona scenario shows stable Control meaning, effective parameters,
   exact structured before/after tailoring and existing authored rationale.
6. The macOS exclusion shows Control meaning, excluded disposition and existing
   deviation reason with no result state.
7. Distinct same-identity title/purpose definitions fail closed independent of
   source and file order; exact-identical copies still coalesce.
8. A prose-only change does not change evaluation given the same resolved structured
   inputs, but does change the required content-addressed identities and policy diff.
9. Active and excluded plan meaning survives removal/change of the current policy
   checkout and is validated from the stored plan under the exact historical
   plan/result contract.
10. Advanced output retains exact policy/check IDs, revisions, digests, source
    locators, fingerprints, lineage, derivations, deviations and plan identity.

### Validation

- focused schema/catalog/planner/artifact/explanation/policy-diff unit tests;
- order-permutation and divergent-text conflict tests;
- `git diff --check` and repository documentation/link validation;
- control-library and verification-policy validation after a clean checkpoint;
- canonical technical-only, IAM, Linux-tailoring and macOS-exclusion scenarios;
- applicable full tooling validation; and
- all four exact-head CI contexts: `component-validation`,
  `verification-scenarios`, `installed-release-provenance`, and
  `macos-portability`.

### Expected invalid behavior

- A missing or whitespace-only required title/purpose is a source-schema failure.
- Divergent same-identity authored meaning is a policy-resource conflict, not a
  warning or display choice.
- A stale document or implementation fingerprint pin exposed by migration is a
  resolution failure until explicitly regenerated and reviewed.
- A new-format plan with missing, contradictory or non-frozen check meaning fails
  strict artifact or semantic validation.
- A pre-cutover source document or v4 plan is not silently upgraded or supplied
  fallback prose by current post-cutover tooling; historical tooling remains its
  reader.

### Dependencies and sequencing

Create a new successor issue after this ADR is accepted; #97 remains the
architecture decision and does not become runtime authority. Implement the source,
pin, plan, validation and reporter changes atomically from current `main`. The
implementation has no dependency on #98. #98 may consume the resulting exact-plan
check meaning after this cutover, but must not be pulled into the implementation.

### Escalation conditions

Return to architecture if implementation requires per-instance or realization prose,
title/purpose overlay overrides, localization/presentation catalogs, parsing text for
behavior, excluding authored meaning from content identity, a new resource/artifact
family, a new digest algorithm, a compatibility reader, a plan/result ownership
change, or changes to Objective, evidence, status, waiver, exclusion or adapter
semantics.

## Consequences and non-goals

This decision makes authored operator meaning reviewable beside the policy it
describes and reproducible from the exact plan. Authors must maintain concise stable
Control meaning and policy titles, and wording-only edits deliberately cause policy
identity and downstream plan/result churn. In exchange, reporters neither invent
prose nor depend on mutable presentation catalogs.

This ADR does not implement CLI behavior, a GUI, a generic policy superclass or DSL,
a presentation hierarchy, synthesized Objectives, a generic description field,
localization, framework-certification semantics, evidence redesign, new assessment
statuses, broader catalog content, or firewall/network-policy work. It does not
address #98's absent/stale evidence causes, attempt/refusal history or durable
assessment diagnostics. A future #98 renderer may reference the canonical check
title and purpose decided here from the exact plan.

## Decision test

Yes. After the bounded implementation, a deterministic reporter can explain a
technical-only check, an Objective-backed check, a tailored check, a conflicting
policy and an excluded check using only canonical authored meaning plus existing
structured effective-policy facts. It need not manufacture an Objective, parse
Rego, derive prose from IDs, depend on filenames/digests as primary vocabulary, or
create a parallel policy hierarchy.
