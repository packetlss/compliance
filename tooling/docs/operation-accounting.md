# Frozen operation accounting

Implementation contracts: [#78](https://github.com/packetlss/compliance/issues/78)
and the pre-freeze identity simplification
[#87](https://github.com/packetlss/compliance/issues/87), under
[ADR 0016](../../docs/adr/0016-closed-world-policy-assessment.md).
The current representation is experimental and remains inside assessment
plan/results v4. The accepted [#90](https://github.com/packetlss/compliance/issues/90)
successor retains the frozen operation only in the plan and makes a result's exact
`plan_id` the sole link to that operation context; implementation is pending.

`operation` embeds one exact normalized request, a mode-sensitive frozen selection
witness, the relevant assignment union, a compact actual-composition commitment,
and one compact row per selected Subject. Catalog loading still rejects dangling
references before selection. Domain-owned sets and lists use deterministic order;
RFC 8785/JCS is only the final serialization step.

The request contains `all`, sorted unique `subjects`, and sorted unique `groups`.
`all=true` is exclusive. Otherwise at least one explicit subject or group is
required. The request itself is identity-bearing: explicit A and group G are
different operations even when G currently selects only A.

The selection witness has three modes:

- `explicit` retains no candidate inventory. Its denominator is exactly the
  request's subjects, so supplying nonselected C cannot affect an A/B operation.
- `all` retains only the sorted unique supplied subject-ID domain.
- `groups` retains each requested group plus its complete reverse-reachable
  descendant closure, direct parent edges, selectors, and supplied direct-member
  edges. If any retained group has a selector, `candidates` contains every supplied
  subject ID and only the label presence/value facts for keys consulted by the
  closure. Matching and nonmatching candidates are included. Without selectors,
  no candidate label domain is stored.

This projection preserves empty-but-valid group identity, unmatched descendant
selectors and closed-world omission proof without annotations, display metadata,
source paths, document boundaries, precomputed inherited paths or unrelated groups.
Mixed selection is the union of explicit subjects and frozen group resolution.

Each selected-member row contains `subject_id`, resolution-consumed type/lifecycle
and label facts, assignment-relevant resolved membership attribution,
`member_plan_digest`, and compact expected control/requirement/mapping membership.
It does not repeat assignments, baseline bodies or digests, control bodies/digests,
requirement document digests, realization/adoption/satisfaction bodies, full
provenance, inventory acquisition facts or derived coverage counters.

Assignments appear once per operation as `{id, target_group, baselines}` and only
when their target resolves for a selected member. Applicability is rederived from
member group facts. Validation recomputes the witness denominator, operation ID,
member commitment for the concrete plan/result, compact expected membership,
assignment applicability and the existing parameter/provenance/roll-up invariants.
Content identity identifies the frozen supplied facts; it does not authenticate
their real-world truth or claim inventory exhaustiveness.

## Identity

`member_plan_digest` hashes the complete resolved intent for one member without
operation or composition context. It includes resolution-consumed subject facts,
assignment-relevant membership, applicable assignments, resolved baselines,
requirements, controls, exclusions and resolution state. The current result carries
the same resolved-policy projection so validation independently recomputes the
commitment. #90 removes that copy: the exact plan owns the member projection and
mandatory plan/result relational validation establishes the relationship. No
predecessor digest is retained as an alias.

`operation_id` hashes the operation domain tag, exact request, selection witness,
relevant assignments, planning-composition algorithm/digest, compact expected
membership/mappings and sorted member commitments. The composition reference is
checked against the artifact's independently validated ADR 0007 actual composition.

The exact bound plan ID hashes only the operation-bound-plan domain tag,
`operation_id` and `subject_id`. Exact expected plan IDs are reconstructible without
foreign member bodies or recursive references. Composition descriptive metadata and
expected enforcement remain nonsemantic.

A in `[A]` has a different enclosing identity from A in `[A,B]`. There is no
cross-operation result equivalence. Policy diff exposes `operation_id`,
`member_plan_digest` and the composition digest as independently meaningful context;
unchanged effective subject policy remains distinguishable.
Current results carry the same operation, exact plan reference and one recorded
assessment instant shared by multi-subject execution. Under #90, results retain only
the exact plan reference and assessment instant; different operation context still
changes the bound plan and therefore the result assertion.

## Planning, execution and history

```sh
compliance --config project.json plan render host/A host/B --output generated/plans
compliance --config project.json assessment run host/A host/B --at 2026-09-01T00:00:00Z
compliance --config project.json assessment run --group hosts --at 2026-09-01T00:00:00Z
compliance --config project.json assessment run --all --at 2026-09-01T00:00:00Z
compliance --no-config assessment status --plan generated/plans/host__A.json \
  --results generated/results --at 2026-09-01T00:00:00Z --format json
```

`assessment run --format json` emits machine-readable operation accounting; the
default text output summarizes counts and member states.

Explicit subject IDs and repeated groups select a union; `--all` selects supplied
inventory. Empty selection fails. Invalid selected policy prevents operation
execution. Existing single-subject `plan render` may still emit an invalid
diagnostic plan; it cannot support operation success or assessment execution.
Multi-subject outputs require distinct per-subject paths. Plans are published
before member evaluation, preserving the expected denominator if evaluation stops.
Already trustworthy children remain independently valid if a later member refuses.

Historical `status`, `groups`, `explain` and `frameworks` accept `--plan` and `--at`.
They use the anchor's frozen denominator and accept only results matching exact
subject, expected plan and recorded instant. Complete canonical document copies
coalesce as copies. Distinct competing results for one exact slot refuse reporting;
there is no latest-file precedence. Another operation/plan/subject/instant cannot
fill a missing slot. Under #90, every result requiring full interpretation resolves
its assessed plan solely by exact `plan_id` from an explicit plan file or bounded plan
set and passes relational validation; filename, traversal order, subject-only/latest,
current-plan substitution, and approximate equality are forbidden. Historical
reporting works without inventory, policy or evidence paths; `--no-config` also avoids
reopening project configuration.

`accounting_complete` means every result-required member has an exact result.
Member disposition is derived from frozen lifecycle, membership, assignments and
expected policy: inactive, unassigned, no assessable policy, or result required.
The first three require no result.
`all_passed` additionally requires a passing state for every selected member. Thus
A pass plus B unassigned is complete accounting without unqualified A/B success.
An operation consisting entirely of non-assessable members has no passing basis.
No absent assignment is inferred N/A. Existing explicit N/A, missing realization,
fail-only waivers and independent technical assessment retain their behavior.

Historical mapping filters are visibly filtered. Mapping references and whole-operation
accounting remain separate, and mappings never produce external conformity. Current
inventory views without `--plan` retain their legacy operator comparison role.

Historical operation views additionally require explicit `--as-of q` and may accept
a validated `--comparison-plan`. They derive, without changing artifacts or accounting,
exact operation-bound plan alignment, selected required-evidence timeliness, and the
recorded applied-waiver window. Dependency timeliness uses only frozen successful-use
facts and the exact rule `q - collected_at <= max_age`; equality and future collection
timestamps are timely. Missing successful use is unavailable and never triggers
reselection. Stale and unavailable dependencies may coexist for one control, while a
control with no required evidence receives no timeliness claim. Comparison membership
never changes the historical denominator. Historical outcomes and roll-ups remain
unchanged, and `all_passed` is labeled only as a frozen historical fact.

A multi-subject historical view retains one operation-bearing plan as denominator
anchor, each exact bound plan needed to interpret a retained result, and the results.
The anchor alone proves missing expected slots; no plan artifact is invented for a
member whose result is absent. Deleting a historical result plan makes full
interpretation of that result unavailable without affecting future assessment.

## Concrete typed assertion contracts

`organization.assertion.required` consumes ordinary required
`organization.assertion/v1` evidence for an entity. The named dependency's typed
`inputs.scheme` is company intent. The payload supplies beneficiary, assertor,
source locator, scheme, outcome and validity interval. The criterion compares the
beneficiary with the exact consuming Subject, scheme with required intent, and the
recorded assessment instant with the inclusive validity interval. A qualifying
positive assertion passes; a qualifying negative fails. A different beneficiary,
scheme, expired/not-yet-valid or inconclusive assertion is unknown. These fields
belong only to this concrete observation contract, not universal certificate fields.

`iam.integration.required` consumes two ordinary named dependencies for a host:
`iam.service.observation/v1` and `iam.integration.observation/v1`. The source
observation retains the original service-scoped assertion unchanged, including its
subject, assertor, condition, outcome and source locator. Its consumer wrapper does
not relabel the underlying assertion. A separate attributable relationship observation
must name the consumer, service and exact source assertion locator. Authored service
integration intent alone cannot pass. The same source assertion can support A/B
only through each explicit named dependency and its own relationship observation.

All-matching-candidate validation, policy-owned freshness, unique latest selection,
complete-document ambiguity and snapshot identity remain ADR 0010/0012 behavior.
Dependency inputs never select an issuer or create evidence precedence. Missing or
unusable required observations are unknown; attributable execution failure is error;
untrustworthy shared prerequisites refuse publication. No assessment-result graph,
certificate subsystem, beneficiary resource or common-assurance engine is added.

The canonical [company IAM scenario](../../verification/scenarios/projects/company-iam-policy-assessment/README.md)
keeps reusable contracts in control-library, company policy in verification-policy,
and the host realization in separately materialized environment-private policy.
