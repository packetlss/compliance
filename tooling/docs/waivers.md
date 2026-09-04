# Temporary Waivers

Status: **Implemented initial contract (v0.1)**
Last updated: **2026-08-28**

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

For every evaluation:

1. validate and normalize the complete project waiver catalog;
2. calculate a deterministic `waiver_revision` over that catalog;
3. select at most one active exact subject/control match without supplying it
   to Rego;
4. evaluate the unchanged control and evidence with OPA;
5. change only an underlying `fail` result to `waived`; and
6. persist the complete normalized waiver snapshot, its digest, and
   `underlying_status: fail` in the immutable result.

An active waiver does not change `pass`, `unknown`, `not_applicable`, or
`error`. The original failure reason, expected state, observed state, severity,
remediation, evidence references, and policy provenance remain intact. A
waived result is therefore an accepted failure, never proof of compliance.
Keeping the waiver out of Rego input makes the underlying decision independent
Rego controls must not originate `waived`; a claimed waived result without the
evaluator's active waiver snapshot and revision fails artifact validation.

Requirement and requirement-baseline roll-ups remain conservative. A waived
required technical check produces a waived parent only when no child is fail,
error, missing, or unknown under the existing precedence rules.

New result envelopes and their technical children record the same
`waiver_revision`. Older non-waived `assessment-results/v1` artifacts without
that extension remain readable. Any result claiming `waived` must contain a
valid, active, target-matching waiver snapshot and revision.

## 4. Desired policy remains independent

Waivers are resolved during evaluation and do not change the assessment plan.
An external delivery or change-approval workflow may choose to defer action
while a waiver is active, but it must make that decision explicitly; the
compliance tool does not weaken desired state.

Changing, adding, or expiring a waiver changes the waiver revision and future
results. It does not change the assessment plan ID.

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
