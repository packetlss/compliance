# Hybrid administrative access

This fixed-time synthetic scenario assesses exactly one Linux administrative
bastion and one SaaS administration tenant in a single operation. Both enter
the factual `administrative-access=managed` scope and receive the same narrow
Objective: interactive administrative access is gated by centrally managed
identity controls, while unmanaged local or guest access paths are disabled.

The Linux realization proves that meaning through the company IAM domain, the
approved SSH operator group, and no unmanaged interactive local accounts. The
SaaS realization proves it through enforced SSO and disabled guest access. The
Linux member separately receives the direct `company.linux-server-operations@1`
technical package policy; it does not gain a synthetic Objective for that policy.

Fresh valid evidence makes every Linux check pass. The SaaS fixture makes SSO
pass but reports guest access as enabled, producing an attributable `fail`, not
an `unknown`. The one two-member operation therefore has complete accounting and
`all_passed=false`. Coverage is current policy expectation only; historical
explanation uses the exact plan/result pair and does not claim framework
conformity, inventory completeness, continuous effectiveness, or remediation.

## Operator walkthrough

Run from the repository root. The maintained scenario registry selects the
project, while evidence, plans and results go only to a temporary directory.

```sh
hybrid_run="$(mktemp -d "${TMPDIR:-/tmp}/compliance-hybrid-access.XXXXXX")"
hybrid_registry=verification/scenarios/compliance.yaml
hybrid_at=2026-09-01T00:00:00Z

scripts/dev cli --config "$hybrid_registry" \
  --project hybrid-administrative-access inventory validate
scripts/dev cli --config "$hybrid_registry" \
  --project hybrid-administrative-access \
  coverage explain host/admin-bastion-01
scripts/dev cli --config "$hybrid_registry" \
  --project hybrid-administrative-access \
  coverage explain saas/administration-tenant

uv run --project tooling --frozen python \
  tooling/collectors/mock-api/collect.py \
  verification/scenarios/projects/hybrid-administrative-access/fixtures \
  "$hybrid_run/evidence" --collected-at "$hybrid_at"

scripts/dev cli --config "$hybrid_registry" \
  --project hybrid-administrative-access assessment run \
  host/admin-bastion-01 saas/administration-tenant \
  --evidence "$hybrid_run/evidence" \
  --plan-output "$hybrid_run/plans" \
  --output "$hybrid_run/results" --at "$hybrid_at"

hybrid_anchor="$hybrid_run/plans/host__admin-bastion-01.json"
scripts/dev cli --no-config assessment status \
  --plan "$hybrid_anchor" --assessed-plans "$hybrid_run/plans" \
  --results "$hybrid_run/results" --at "$hybrid_at" --as-of "$hybrid_at"
scripts/dev cli --no-config assessment explain host/admin-bastion-01 \
  --plan "$hybrid_anchor" --assessed-plans "$hybrid_run/plans" \
  --results "$hybrid_run/results" --at "$hybrid_at" --as-of "$hybrid_at"
scripts/dev cli --no-config assessment explain saas/administration-tenant \
  --plan "$hybrid_anchor" --assessed-plans "$hybrid_run/plans" \
  --results "$hybrid_run/results" --at "$hybrid_at" --as-of "$hybrid_at"
```

Both Coverage explanations select
`company.administrative-access.identity-gated@1`, but show the Linux and SaaS
realizations respectively. Linux Coverage and exact explanation also keep
`company.linux-server-operations@1` as a separate direct technical policy with
no synthetic Objective. The single status view reports complete `2/2` accounting,
Linux `PASS`, SaaS `FAIL`, and `all_passed=false`; the two exact explanations retain
the distinct realization and technical outcomes.

`assert-scenario.py` and the canonical scenario gate remain the primary executable
owners. The walkthrough does not add a second semantic assertion path.
