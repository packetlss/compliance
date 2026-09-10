# Synthetic Server Personas

This project demonstrates how inventory personas and inherited policy work
together. It uses fictitious Linux hosts and mock evidence.

The policy chain is:

```text
Illustrative Linux server benchmark
  -> company Linux server hardening
     -> company container-runtime host
```

All Linux servers also receive the independent company operations baseline.
The standard application server selects the company hardening baseline. The
container-runtime server selects its derived baseline, which changes IPv4
forwarding from `0` to `1`, records the approved deviation, and adds
`containerd`. Assigning only the leaf policy avoids applying both a parent and
its tailored child to the same subject.

Run from the checkout root:

```sh
scripts/dev cli --config projects/server-personas/compliance.yaml inventory validate
scripts/dev cli --config projects/server-personas/compliance.yaml policy validate
scripts/dev cli --config projects/server-personas/compliance.yaml waiver validate
scripts/dev cli --config projects/server-personas/compliance.yaml waiver list
uv run --project tooling python tooling/collectors/mock-api/collect.py \
  projects/server-personas/fixtures \
  projects/server-personas/generated/evidence

scripts/dev cli --config projects/server-personas/compliance.yaml assessment run \
  host/standard-app-01
scripts/dev cli --config projects/server-personas/compliance.yaml assessment run \
  host/container-app-01
scripts/dev cli --config projects/server-personas/compliance.yaml assessment explain \
  host/container-app-01 --plan generated/plans/host__container-app-01.json \
  --assessed-plans generated/plans --at 2026-09-01T00:00:00Z \
  --as-of 2026-09-01T00:00:00Z
```

The container subject should pass. The standard subject intentionally lacks
`auditd`; its exact technical failure is covered by the active
`standard-app-01-auditd-rollout` waiver and therefore reports `WAIVED`, not
`PASS`. Its assessment plan still records the underlying desired technical
policy and requires `auditd`; the waiver changes only the evaluation result.

The assessment plans expose the complete baseline lineage, external benchmark
references, resolved parameters, and any deviations. The container plan retains
`auditd`, `containerd`, ASLR, and forwarding as resolved technical controls.

`assessment explain` shows the exact effective forwarding Check, parameters,
required evidence, immutable outcome, and current qualification. The complete
immutable derivation records remain in the assessed plan and are consumed by
`compliance policy diff BEFORE AFTER`, so a historical plan comparison can show
the exact forwarding criteria and approved deviation without consulting the
current policy checkout.

The third subject deliberately has both persona labels:

```sh
scripts/dev cli --config projects/server-personas/compliance.yaml plan render \
  host/persona-conflict-01
scripts/dev cli --config projects/server-personas/compliance.yaml plan show \
  host/persona-conflict-01
```

It selects both sibling assignments, which require incompatible values for the
same stable forwarding control. Resolution must be invalid and must not choose
a policy based on assignment or file order. This is an inventory classification
error, not a waiver. A durable persona-wide difference belongs in a reviewed
overlay. The standard subject demonstrates the separate temporary exception
mechanism: the failure remains visible, the approval expires, and assessed
technical policy is not rewritten.

The project assembles reusable controls and evidence/parameter schemas from `control-library` with
this synthetic benchmark and company policy from `verification-policy`.
Neither partial source is treated as a complete catalog by itself.

The `project-config/v1alpha3` configuration uses executing tooling’s inventory and
assignment schemas. Assessment plans/results use v4 actual composition, evaluator,
and evidence provenance; generated state remains local to this project.
