# Frozen operation accounting

Implementation contract: [#78](https://github.com/packetlss/compliance/issues/78),
under [ADR 0016](../../docs/adr/0016-closed-world-policy-assessment.md).
The representation is experimental and remains inside assessment plan/results v4.

`operation` embeds explicit selection, normalized supplied Subjects, group DAG,
assignments, planning composition and one expected accounting row per selected
Subject. Explicit subject selection retains the selected Subjects and projects
explicit group references onto them. Group/all selection retains the supplied
inventory needed to reproduce that selection. Catalog loading rejects dangling
explicit references before selecting a subset. Group definitions retain every
direct source and applicable inherited edge; no full path enumeration is needed.
Subject/group/assignment and membership lists use deterministic identity order.

Each row contains the subject's coverage, resolved membership and assignments,
inventory/assignment revisions, compact policy membership and plan-content digest.
The compact policy facts retain selected baseline references/digests, required
requirement pins, named check membership, adoption/satisfaction, mapping references,
control document digests and assignment attribution. They omit complete sibling
plans, evaluator interfaces, parameter derivations and evidence bodies. Each
actual child retains its existing full resolved policy and ADR 0012 validation.

Validation independently recomputes selection, group closure, applicable assignments,
baseline membership, required instance membership and coverage from frozen facts.
It checks those facts against each actual plan/result and preserves existing
parameter, provenance and roll-up validation. Recomputing the outer artifact digest
does not repair inconsistent expected membership. Content identity identifies the
frozen supplied facts; it does not authenticate their real-world truth.

## Identity

The provisional plan-digest algorithm hashes the existing semantic plan projection
with `id` and `operation` removed as `plan_body_digest`. Each frozen row retains
that compact commitment, alongside its subject, revision, membership, assignment,
coverage and policy facts. `plan_content_digest` hashes all those row fields;
validation recomputes it for every member, including siblings whose full plan
bodies are absent. Correlated edits to sibling coverage and policy membership
cannot retain the original member commitment merely by recomputing the enclosing
artifact digest. The actual child also derives these same facts and its body
commitment from its full plan.

The enclosing plan ID hashes the JCS object
`{"plan_content_digest": digest, "operation": projection}`. Exact expected plan IDs
are reconstructible without embedding foreign plan bodies or recursive references.
Composition descriptive metadata and expected enforcement remain nonsemantic.
Operation planning composition includes only actual composition and its digest.

A in `[A]` has a different enclosing identity from A in `[A,B]`. There is no
cross-operation result equivalence. Policy diff exposes `operation_digest` among
context changes; unchanged effective subject policy remains distinguishable.
Results carry the same operation, exact plan reference and one recorded assessment
instant shared by multi-subject execution. The result digest retains these fields.

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
subject, expected plan, operation and recorded instant. Complete canonical document
copies coalesce as copies. Distinct competing results for one exact slot refuse
reporting; there is no latest-file precedence. Another operation/plan/instant cannot
fill a missing slot. Historical reporting works without inventory, policy or evidence
paths; `--no-config` also avoids reopening project configuration.

`accounting_complete` means every assessable expected member has an exact result.
Unassigned, inactive and assigned-with-no-active-policy rows require no result.
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

The canonical [closed-world scenario](../../verification/scenarios/projects/closed-world/README.md)
keeps reusable contracts in control-library, synthetic objectives in verification-policy
and the host realization in separately materialized environment-private policy.
