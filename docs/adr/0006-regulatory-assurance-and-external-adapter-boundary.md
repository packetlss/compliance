# ADR 0006: Regulatory assurance remains core; configuration adaptation is external

- **Status:** Accepted
- **Original date:** 2026-09-03
- **Destination authority transfer:** 2026-09-04
- **Historical source:** `packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`, `docs/adr/0006-regulatory-assurance-and-external-adapter-boundary.md`

This is the destination-owned normative restatement of accepted workspace ADR 0006. Its original ownership/topology restatement is clarified by the successor decisions below.

[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) clarifies
the common required-evidence `unknown` / `error` / assessment-refusal boundary.
Detailed assurance design was promoted through #37 and narrowed by ADR 0016.

[ADR 0016](0016-closed-world-policy-assessment.md) clarifies this boundary: optional company objective
assurance remains core; engine-established external legal/certification conformity
is not a generic core responsibility. Framework mappings are attributable company
policy/reporting content. Existing explicit N/A behavior remains unchanged and
is not reopened by this ADR; any successor change requires focused promotion.

[ADR 0022](0022-criterion-ownership-and-external-judgment-retirement.md)
supersedes this ADR's unqualified manual/procedural-assurance wording. Such material
can support an assessment only when Compliance owns the complete criterion and
evaluates Control-unaware descriptive observations; it cannot translate another
domain's conclusion into an objective result.

## Context

The compliance core supports evidence-backed technical assessment and an optional requirement/realization assurance layer. A separate prototype previously added configuration intent compilation and backend renderers. The resolved assessment plan already contains the stable, provenance-bearing information an external configuration/policy adapter needs.

## Decision

### Technical assessment and objective assurance are complementary

Ordinary technical assessment remains first-class:

```text
subject / group assignment
  -> Baseline / BaselineOverlay
      -> resolved technical Control instances
          -> typed evidence
          -> pass / fail / unknown
```

A project does not need a requirement/realization wrapper to use technical baselines.

Optional company objective assurance remains core:

```text
subject / group assignment
  -> RequirementBaseline
      -> internal desired requirement
          -> applicable environment realization
              -> required technical controls
              -> required manual/procedural assurance evidence, if any
          -> objective result
      -> attributable regulatory/framework mapping and bounded company reporting
```

Requirements express internal desired assurance objectives. Realizations describe how an applicable scope demonstrates those objectives. Framework/regulatory mappings are attributable company policy/reporting content rather than the source of technical desired state.

### Assurance results are evidence-derived

A realization is design-time mapping, not proof of implementation.

Preserve these constraints:

- authored adoption/implementation labels cannot create pass;
- technical results remain independently attributable;
- manual/hybrid assurance requires typed, attributable, freshness-bounded,
  Control-unaware descriptive evidence under ADR 0022's criterion-ownership rule;
- missing, stale, invalid, or inconclusive required evidence is `unknown`, never pass;
- not-applicable requires deterministic applicability or an attributable reviewed determination;
- ownership, implementation references, and organizational labels are annotations unless an authority contract explicitly makes them assessment inputs;
- information classification is a source/package/access-control concern or adopter annotation by default, not a universal closed semantic enum;
- realization selection is deterministic and fail-closed; source order is not precedence;
- authored mapping coverage labels such as complete, partial or supporting are policy/reporting metadata, not engine-established external coverage authority; and
- company objective results are scoped to exact company policy/objective revisions, subject/scope, selected realization, assessment time, evidence snapshot, evaluator, and policy composition; reported mappings retain their exact revisions and attribution without establishing external conformity.

The core does not establish organizational certification, legal compliance or external-framework conformity. It may report exact company-policy results and mappings as bounded company reporting with attributable provenance; modeled mappings and evaluated evidence do not upgrade those results into external conformity claims.

Destination issue #37 is completed promotion history for the successor
terminology/evidence/mapping/result semantics implemented through ADR 0016 and
#78. New semantics require a focused architecture issue.

### In-core configuration generation is removed

The core does not own:

- configuration-intent compilation or composition;
- backend capability registration;
- Ansible/cloud-init/Terraform/MDM/provider renderers;
- configuration plan/render-result/explanation artifact families;
- provider credentials/state, approval, execution, or apply behavior; or
- an executable adapter/plugin runtime.

Those retired surfaces have no ADR 0007 successor.

### The assessment plan is the external-adapter handoff

The resolved assessment plan remains the canonical handoff to an external IaC, PaC, MDM, ticketing, or configuration-management adapter. For each resolved control it preserves, at minimum:

- subject identity/type and plan identity;
- actual planning composition with policy-source names/content digests;
- stable control instance and implementation/control IDs;
- resolved parameters;
- definition fingerprint;
- disposition, derivations, deviations, lineage, and source provenance; and
- requirement/realization lineage when applicable.

An adapter may consume the plan or a documented lossless projection and may emit its own adapter/version/output-digest provenance referencing the source plan.

Adapter output is not evidence that configuration was approved, applied, successful, persistent, or compliant. Assessment remains valid without an adapter installed. Policy sources do not provide executable adapter code/templates for core execution.

## Current implementation state

Configuration-generation code/artifacts are removed. The consolidated canonical
scenario covers both technical assessment and objective assurance without an
in-core adapter. ADR 0007 defines the accepted provenance successor; destination
#31–#36 are completed implementation/consumer-migration history. #37 is completed
promotion history for the detailed assurance semantics narrowed by ADR 0016 and
implemented under #78.

## Consequences

The core is deliberately narrow: policy resolution, provenance, evidence, assessment, requirement/realization roll-up, and external-adapter handoff. Backend-specific mapping, credentials, state, approval, execution, and apply authority stay outside the compliance trust boundary.

## Non-decisions

This ADR does not freeze current assurance names/schemas, define regulator-specific content/legal conclusions, define an adapter SDK/registry, add apply authority, change digest/JCS/evidence/waiver/source-order/conflict semantics, or authorize firewall work.
