# Authorized software composition

This isolated synthetic Stage 8 scenario proves `installed package IDs ⊆ resolved
allowed_software` through `linux.packages.only-allowed@1`. It composes the independently
named `control-library` and source-only `verification-policy` roots through the public CLI.

Two fictitious managed Linux hosts receive `company.authorized-software-base@1`,
which authorizes `auditd` and `curl`. The database host's factual `feature.database`
classification also selects the contribution-only `company.database-software@1`,
adding `postgresql`. Inventory contains no desired package names or policy IDs.
The Linux realization directly links the string-array slot to `/allowed`, with an
explicit 24-hour observation freshness requirement. No transformation is involved.

`assert-scenario.py` copies inputs into temporary roots and uses the existing mock
collector at `2026-09-01T00:00:00Z`. Machine-readable assertions prove:

- base-only pass with installed `auditd` and absent-but-authorized `curl`;
- database pass with the canonical union directly materialized into the control;
- valid planning followed by failure for `postgresql` when only its contribution
  assignment is removed, preserving the same base and evidence;
- deterministic failure identifying an added unexpected `telnet` package;
- current Coverage contribution, effective-value and applicability attribution;
- ordinary plan/result validation and identical historical explanation of the
  retained pair after current policy, inventory and evidence are removed.

Run focused assertions from the repository root against the working tree:

```sh
uv run --project tooling --frozen python \
  verification/scenarios/projects/authorized-software-composition/assert-scenario.py \
  --integration-root .
```

The canonical scenario harness runs this proof from committed exported inputs.
Generated artifacts are temporary and removed after execution.

The claim is limited to exact installed package IDs in eligible supplied evidence.
Allowed-but-absent packages are permitted; versions, repositories, sources and
signatures are not authorization criteria. Supplied inventory and observation
completeness remain governance responsibilities. Passing this synthetic policy
establishes neither complete security coverage nor continuous effectiveness.
Missing/ineligible evidence remains `unknown` under the existing evidence contract.
This scenario adds no remediation or adapter execution and does not broaden the
independent `technical-only-packages` anchor or Stage 9 scenario scope.

Identifiers introduced under #131 remain experimental. Accepted ADR 0019 owns the
namespace and schema-URI conventions; this scenario applies only its bounded PR #133
mappings and establishes no compatibility alias or contract freeze.
