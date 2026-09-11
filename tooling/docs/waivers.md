# Temporary Waivers

Status: **Implemented initial contract (v0.1), including exact applied-waiver
attribution under [#90](https://github.com/packetlss/compliance/issues/90)**
Last updated: **2026-09-06**

This document defines the first project-owned waiver contract. A waiver is an
approved, time-bounded acceptance of one observed failure. It does not change
effective policy, baseline inheritance, assessment-plan identity, resolved
control parameters, or evidence.

## 1. Boundary

The three related mechanisms answer different questions:

| Mechanism | Meaning | Changes desired policy? |
|---|---|---|
| Inventory persona | Which stable policy scope applies? | No; it selects assignments |
| Overlay deviation | What has the company deliberately adopted instead of the parent policy? | Yes |
| Waiver | Which current subject/control failure is temporarily accepted? | No |

A broad or durable exception belongs in a reviewed derived baseline. Waivers
must not become a second selector language, an informal group assignment, or a
way to suppress control planning or assessment.

For assessment results, a whole-catalog `waiver_revision` is neither
result identity nor a historical assertion fact. The normative retained fact is
either no applied waiver, or an exact normalized applied-waiver snapshot with its
identity/digest, exact subject/control target, evaluation-time applicability, and
underlying `fail`. An unrelated waiver elsewhere in the project cannot perturb a
result, and no applied waiver requires no retained proof of a complete catalog.
This correction adds no mutable substitution, revocation, or query-time
reinterpretation semantics.

## 2. Authored resource

Waivers are Kubernetes-shaped, project-owned resources under `waivers/`. The
initial contract targets exactly one stable subject ID and one effective
technical control instance ID:

```yaml
# yaml-language-server: $schema=../../compliance-tooling/schemas/waivers/resource.schema.json
apiVersion: compliance.example/v1alpha1
kind: Waiver
metadata:
  name: standard-app-01-auditd-rollout
spec:
  subjectRef:
    id: host/standard-app-01
  controlRef:
    instanceId: company.linux-server.audit-package
  validFrom: "2026-08-01T00:00:00Z"
  expiresAt: "2026-12-01T00:00:00Z"
  rationale: The replacement image is awaiting its approved audit package rollout.
  owner: platform-operations
  approval:
    reference: risk-acceptance/RA-2026-042
    approvedBy: security-risk-owner
    approvedAt: "2026-07-31T14:00:00Z"
```

The strict tooling-owned schema rejects unknown fields. Semantic validation
also requires timezone-aware timestamps, `validFrom < expiresAt`, approval no
later than the start of the waiver, unique waiver IDs, and non-overlapping
validity windows for the same subject/control target.

The validity interval is start-inclusive and end-exclusive:

```text
validFrom <= evaluated_at < expiresAt
```

An expired waiver remains valid historical authoring data but is not active.
It can be retained for audit and appears as `expired` in operator views.

## 3. Evaluation semantics

Waivers enter after the subject assessment plan has been rendered:

```text
inventory + assignments + policy -> immutable assessment plan
waiver catalog ---------------------> evaluation input
typed evidence ---------------------> OPA technical decision
active exact-match waiver + fail ---> waived result
```

The current executable implementation does the following for every evaluation:

1. validate and normalize the complete project waiver catalog;
2. select at most one active exact subject/control match without supplying it
   to Rego;
3. evaluate the unchanged control and evidence with OPA;
4. change only an underlying `fail` result to `waived`; and
5. persist the complete normalized waiver snapshot, its digest, and
   `underlying_status: fail` in the immutable result.

An active waiver does not change `pass`, `unknown`, `not_applicable`, or
`error`. The original failure reason and expected/observed state remain intact.
Plan-owned severity, remediation, evidence dependencies, mappings, and policy
provenance are interpreted from the exact assessed plan. A
waived result is therefore an accepted failure, never proof of compliance.
Keeping the waiver out of Rego input makes the underlying decision independent.
Rego controls must not originate `waived`; a claimed waived result without the
evaluator's active waiver snapshot fails artifact validation.

Requirement and requirement-baseline roll-ups remain conservative. A waived
required technical check produces a waived parent only when no child is fail,
error, missing, or unknown under the existing precedence rules.

Any result claiming `waived` must contain a valid, evaluation-time active,
target-matching applied-waiver snapshot and its exact digest.

## 4. Desired policy remains independent

Waivers are resolved during evaluation and do not change the assessment plan.
An external delivery or change-approval workflow may choose to defer action
while a waiver is active, but it must make that decision explicitly; the
compliance tool does not weaken desired state.

Only a change to the exact waiver applied to an underlying failure changes result
identity; unrelated catalog changes do not. Neither form changes the assessment plan
ID.

## 5. Operator interface

```sh
compliance waiver validate
compliance waiver list [--subject SUBJECT] [--state active|scheduled|expired]
compliance waiver explain WAIVER
```

`list` and `explain` accept `--at RFC3339` for deterministic review and tests;
otherwise they use the current UTC time. They support table and JSON output.
`assessment run` loads the configured waiver catalog. `assessment status`
reports `WAIVED` distinctly, and `assessment explain` displays the underlying
failure plus validity, rationale, ownership, approval, and immutable digest.

### Historical validity qualification

System [ADR 0011](../../docs/adr/0011-historical-assessment-and-operational-evidence-timeliness.md) is implemented for frozen v4 historical operation views by #80.
A stored historical `waived` result remains waived after its recorded exception
expires. Future assessment views qualify that immutable applied snapshot separately:
**Recorded waiver within validity window** when `validFrom <= q < expiresAt`, or
**Recorded waiver expired** at/after the exclusive end. They do not substitute the
current catalog, add revocation authority, or change historical outcomes to fail or
unknown. Validation of the applied waiver in a historical result concerns its
`evaluated_at`, not the later report timestamp.

Assessment requires an explicit `--as-of` instant and qualifies the recorded applied
waiver without changing its immutable outcome; the authored-resource
`waiver list/explain --at` lifecycle above is a separate interface. Expiration alone does not mutate the stored
applied-waiver snapshot; it changes applicability to future evaluations.
Recorded waiver qualification is independent of historical outcomes, plan alignment,
evidence timeliness and coverage, and does not recompute historical assurance
roll-ups. Fail-only application remains unchanged and a waiver never proves compliance.
#32's ADR 0011 addition remains factual evidence provenance only; #80 derives the
assessment presentation without changing the waiver catalog or result artifact.

## 6. Ownership and limitations

The environment/project repository owns waiver resources because it owns the
subject scope and local approval boundary. Waiver-approval authority must be
separate from policy-authoring authority through repository protection and the
organization's governance workflow. The prototype records approval data but
does not verify it against an external risk system or signature authority.

The initial contract deliberately does not provide:

- group-, selector-, implementation-, requirement-, or framework-wide waivers;
- open-ended waivers or automatic renewal;
- revocation events separate from a reviewed resource change;
- cross-project waivers;
- external approval verification or cryptographic signatures; or
- finding suppression and workflow lifecycle, which belongs to the future
  findings/reporting service.

Those extensions should be driven by concrete operational cases without
weakening the exact, attributable, expiring default.
