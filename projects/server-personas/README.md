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

Run this bounded waiver and refusal walkthrough from the checkout root. Both
assessment instants recollect the same existing fixture so evidence remains timely;
all runtime output stays in a temporary directory. The first `scripts/dev cli` call
prepares the managed `.dev/venv` used by the collector.

```sh
persona_run="$(mktemp -d "${TMPDIR:-/tmp}/compliance-server-personas.XXXXXX")"
persona_config=projects/server-personas/compliance.yaml
persona_active_at=2026-09-01T00:00:00Z
persona_expired_at=2026-12-02T00:00:00Z

scripts/dev cli --config "$persona_config" inventory validate
scripts/dev cli --config "$persona_config" policy validate
scripts/dev cli --config "$persona_config" waiver validate
scripts/dev cli --config "$persona_config" waiver list --at "$persona_active_at"

.dev/venv/bin/python tooling/collectors/mock-api/collect.py \
  projects/server-personas/fixtures \
  "$persona_run/active-evidence" --collected-at "$persona_active_at"
scripts/dev cli --config "$persona_config" assessment run \
  host/standard-app-01 --evidence "$persona_run/active-evidence" \
  --plan-output "$persona_run/active-plans" \
  --output "$persona_run/active-results" \
  --waivers projects/server-personas/waivers --at "$persona_active_at"
scripts/dev cli --no-config assessment explain host/standard-app-01 \
  --plan "$persona_run/active-plans/host__standard-app-01.json" \
  --results "$persona_run/active-results" \
  --at "$persona_active_at" --as-of "$persona_active_at"

.dev/venv/bin/python tooling/collectors/mock-api/collect.py \
  projects/server-personas/fixtures \
  "$persona_run/expired-evidence" --collected-at "$persona_expired_at"
scripts/dev cli --config "$persona_config" assessment run \
  host/standard-app-01 --evidence "$persona_run/expired-evidence" \
  --plan-output "$persona_run/expired-plans" \
  --output "$persona_run/expired-results" \
  --waivers projects/server-personas/waivers --at "$persona_expired_at"
scripts/dev cli --no-config assessment explain host/standard-app-01 \
  --plan "$persona_run/expired-plans/host__standard-app-01.json" \
  --results "$persona_run/expired-results" \
  --at "$persona_expired_at" --as-of "$persona_expired_at"
```

The first explanation reports `WAIVED`, names the missing `auditd` failure, and
states that Governance accepted that failure under
`standard-app-01-auditd-rollout`; the underlying technical outcome was never
rewritten to `PASS`. The second explanation reports `FAIL` after the waiver's
2026-12-01 expiry. The plan still requires `auditd` in both cases.

The assessment plans expose the complete baseline lineage, external benchmark
references, resolved parameters, and any deviations. The container plan retains
`auditd`, `containerd`, ASLR, and forwarding as resolved technical controls.
The complete immutable derivation records are consumed by `compliance policy diff
BEFORE AFTER` without consulting the current policy checkout.

The third subject deliberately has both persona labels. Inspect current resolution
before attempting assessment:

```sh
scripts/dev cli --config "$persona_config" \
  coverage explain host/persona-conflict-01
scripts/dev cli --config "$persona_config" plan render \
  host/persona-conflict-01 --output "$persona_run/conflict-plans"
scripts/dev cli --no-config plan show \
  "$persona_run/conflict-plans/host__persona-conflict-01.json"

set +e
scripts/dev cli --config "$persona_config" assessment run \
  host/persona-conflict-01 --evidence "$persona_run/active-evidence" \
  --plan-output "$persona_run/conflict-plans" \
  --output "$persona_run/conflict-results" \
  --waivers projects/server-personas/waivers --at "$persona_active_at"
persona_refusal_status=$?
set -e
test "$persona_refusal_status" -eq 1
test ! -e "$persona_run/conflict-results/host__persona-conflict-01.json"
```

The subject selects both sibling assignments, which require incompatible values
for the same stable forwarding control. `coverage explain` shows those paths and
the invalid resolution. Assessment then uses the bounded refusal surface: it
identifies the asset, `control-instance-conflict`, affected Check and policy,
states that no AssessmentResult was published, and directs the operator back to
`coverage explain`. Exit status 1 and the absent result file are expected.

This is an inventory classification error, not a waiver. A durable persona-wide
difference belongs in a reviewed overlay. The standard subject demonstrates the
separate temporary exception mechanism: the failure remains visible, the approval
expires, and assessed technical policy is not rewritten.

The development-project validator remains the executable owner of persona,
waiver, invalid-resolution, and publication-boundary semantics. This walkthrough
only makes those existing surfaces runnable by an operator.

The project assembles reusable controls and evidence/parameter schemas from `control-library` with
this synthetic benchmark and company policy from `verification-policy`.
Neither partial source is treated as a complete catalog by itself.

The `project-config/v1alpha3` configuration uses executing tooling’s inventory and
assignment schemas. Assessment plans/results use v4 actual composition, evaluator,
and evidence provenance; generated state remains local to this project.
