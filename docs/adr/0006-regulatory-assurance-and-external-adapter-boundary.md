# ADR 0006: Regulatory assurance remains core; configuration adaptation is external

- **Status:** Accepted
- **Original date:** 2026-09-03
- **Destination authority transfer:** 2026-09-04
- **Historical source:** `packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`, `docs/adr/0006-regulatory-assurance-and-external-adapter-boundary.md`

This is the destination-owned normative restatement of accepted workspace ADR 0006. It preserves the accepted product/trust boundary and updates only ownership/topology references.

[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md) clarifies the common required-evidence `unknown` / `error` / assessment-refusal boundary; detailed assurance design remains with #37.

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

Optional objective assurance remains core:

```text
subject / group assignment
  -> RequirementBaseline
      -> internal desired requirement
          -> applicable environment realization
              -> required technical controls
              -> required manual/procedural assurance evidence, if any
          -> objective result
      -> explicit regulatory/framework mapping and coverage claim
```

Requirements express internal desired assurance objectives. Realizations describe how an applicable scope demonstrates those objectives. External frameworks are explicit mappings/claims rather than the source of technical desired state.

### Assurance results are evidence-derived

A realization is design-time mapping, not proof of implementation.

Preserve these constraints:

- authored adoption/implementation labels cannot create pass;
- technical results remain independently attributable;
- manual/hybrid assurance requires typed, attributable, freshness-bounded evidence;
- missing, stale, invalid, or inconclusive required evidence is `unknown`, never pass;
- not-applicable requires deterministic applicability or an attributable reviewed determination;
- ownership, implementation references, and organizational labels are annotations unless an authority contract explicitly makes them assessment inputs;
- information classification is a source/package/access-control concern or adopter annotation by default, not a universal closed semantic enum;
- realization selection is deterministic and fail-closed; source order is not precedence;
- mappings distinguish complete coverage from partial/supporting alignment; and
- regulatory/objective results are scoped to exact objective/mapping revisions, subject/scope, selected realization, assessment time, evidence snapshot, evaluator, and policy composition.

The system does not claim organizational certification or legal compliance beyond the modeled mapping and evaluated evidence.

Detailed successor terminology/evidence/mapping/result semantics remain open in destination issue #37.

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
- actual policy-source names/content digests and final policy revision;
- stable control instance and implementation/control IDs;
- resolved parameters;
- definition fingerprint;
- disposition, derivations, deviations, lineage, and source provenance; and
- requirement/realization lineage when applicable.

An adapter may consume the plan or a documented lossless projection and may emit its own adapter/version/output-digest provenance referencing the source plan.

Adapter output is not evidence that configuration was approved, applied, successful, persistent, or compliant. Assessment remains valid without an adapter installed. Policy sources do not provide executable adapter code/templates for core execution.

## Current implementation state

Configuration-generation code/artifacts are removed. The consolidated canonical scenario covers both technical assessment and objective assurance without an in-core adapter. ADR 0007 defines the accepted provenance successor; destination #31–#36 own its implementation/consumer migration. Destination #37 owns detailed assurance semantics.

## Consequences

The core is deliberately narrow: policy resolution, provenance, evidence, assessment, requirement/realization roll-up, and external-adapter handoff. Backend-specific mapping, credentials, state, approval, execution, and apply authority stay outside the compliance trust boundary.

## Non-decisions

This ADR does not freeze current assurance names/schemas, define regulator-specific content/legal conclusions, define an adapter SDK/registry, add apply authority, change digest/JCS/evidence/waiver/source-order/conflict semantics, or authorize firewall work.
