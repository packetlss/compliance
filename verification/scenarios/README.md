# Compliance verification scenarios

This destination root owns the canonical composed scenario and complete
CLI/domain feature suite. Stable, deterministic end-to-end scenarios live here.
The root may contain several independently configured projects
when they share maintainers and visibility; their inventories, assignments,
waivers, fixtures, and generated artifacts remain isolated.

The repository-level `compliance.yaml` selects one local scenario at a time.
The scenario-owned integration registry points directly to the same project
config and the retained development and synthetic IAM fixtures.

See [the integration guide](integration/README.md) for the explicit co-located
source inputs, temporary non-Git assembly, local validation, and CI ownership.

Current scenarios:

- [`company-iam-policy-assessment`](projects/company-iam-policy-assessment/README.md) —
  exact two-host company IAM assessment through the experimental assurance path;
- [`technical-only-packages`](projects/technical-only-packages/README.md) —
  direct package assessment without Requirement/Realization wrappers; and
- [`linux-hardening-rollout`](projects/linux-hardening-rollout/README.md) —
  company Linux operations and hardening, complete access realization,
  deterministic evidence, a temporary waiver, a provenance-bearing assessment
  plan for external-adapter handoff, and safe refusal of contradictory persona
  classification.
