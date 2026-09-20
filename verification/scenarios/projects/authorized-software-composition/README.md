# Authorized software composition

This isolated synthetic Stage 8/9 scenario proves `installed package IDs ⊆ resolved
allowed_software` through `linux.packages.only-allowed@1`, then validates the
current-inventory/history boundary. It composes the independently named
`control-library` and source-only `verification-policy` roots through the public CLI.

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
- one retained explicit two-host operation in which both members pass, while the
  database member's exact plan retains the PostgreSQL contribution and the
  application member does not;
- a copied current-input view that removes only the database host's factual
  `feature.database` classification. Its Inventory explanation loses the database
  path; current Coverage loses the database contribution and returns to the base
  set, while application Coverage remains unchanged;
- comparison rendering of the same two-host request: the application
  `member_plan_digest` remains unchanged, the database digest changes, the
  operation ID changes, and both operation-bound plan IDs change;
- retained historical accounting remains the original complete two-member PASS
  operation. Its comparison qualification is `different_plan` for both members,
  without synthesizing a current outcome; the retained database explanation still
  exposes the old PostgreSQL effective parameter and database applicability path;
- stored-plan policy diff classifies the application comparison as effective policy
  unchanged with identity-context-only differences, and the database comparison as
  an effective policy change due to the removed database assignment/contribution.

## Operator walkthrough

Run from the repository root. This keeps the original evidence, plans and results
in a temporary retained-history view, then copies only Inventory into a separate
temporary current-input view and removes the database classification there. The
first `scripts/dev cli` call prepares the managed `.dev/venv` used by the collector.

```sh
authorized_run="$(mktemp -d "${TMPDIR:-/tmp}/compliance-authorized.XXXXXX")"
authorized_registry=verification/scenarios/compliance.yaml
authorized_project=verification/scenarios/projects/authorized-software-composition
authorized_at=2026-09-01T00:00:00Z

scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition \
  coverage explain host/authorized-base
scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition \
  coverage explain host/authorized-database

.dev/venv/bin/python tooling/collectors/mock-api/collect.py \
  "$authorized_project/fixtures" \
  "$authorized_run/evidence" --collected-at "$authorized_at"
scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition assessment run \
  host/authorized-base host/authorized-database \
  --evidence "$authorized_run/evidence" \
  --plan-output "$authorized_run/historical-plans" \
  --output "$authorized_run/historical-results" --at "$authorized_at"

mkdir -p "$authorized_run/current-inventory"
cp "$authorized_project"/inventory/*.json "$authorized_run/current-inventory/"
python3 - "$authorized_run/current-inventory/database.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
document = json.loads(path.read_text())
del document["metadata"]["labels"]["feature.database"]
path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
PY

scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition inventory explain \
  host/authorized-database --inventory "$authorized_run/current-inventory"
scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition coverage explain \
  host/authorized-base --inventory "$authorized_run/current-inventory"
scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition coverage explain \
  host/authorized-database --inventory "$authorized_run/current-inventory"
scripts/dev cli --config "$authorized_registry" \
  --project authorized-software-composition plan render \
  host/authorized-base host/authorized-database \
  --inventory "$authorized_run/current-inventory" \
  --output "$authorized_run/current-plans"

authorized_anchor="$authorized_run/historical-plans/host__authorized-base.json"
authorized_comparison="$authorized_run/current-plans/host__authorized-base.json"
scripts/dev cli --no-config assessment status \
  --plan "$authorized_anchor" \
  --assessed-plans "$authorized_run/historical-plans" \
  --results "$authorized_run/historical-results" \
  --comparison-plan "$authorized_comparison" \
  --at "$authorized_at" --as-of "$authorized_at"
scripts/dev cli --no-config assessment explain host/authorized-database \
  --plan "$authorized_anchor" \
  --assessed-plans "$authorized_run/historical-plans" \
  --results "$authorized_run/historical-results" \
  --comparison-plan "$authorized_comparison" \
  --at "$authorized_at" --as-of "$authorized_at"

scripts/dev cli --no-config policy diff \
  "$authorized_run/historical-plans/host__authorized-base.json" \
  "$authorized_run/current-plans/host__authorized-base.json"
scripts/dev cli --no-config policy diff \
  "$authorized_run/historical-plans/host__authorized-database.json" \
  "$authorized_run/current-plans/host__authorized-database.json" || \
  test "$?" -eq 1
```

The original operation reports both members `PASS`. In the current input view,
the application Coverage is unchanged, while database Coverage loses the
`database-software` assignment/contribution and its effective allowed set changes
from `auditd,curl,postgresql` to `auditd,curl`. No retained artifact is overwritten.

The comparison operation therefore has a different operation ID and both
operation-bound plan IDs differ. Exact historical status still reports the original
complete two-member PASS operation and qualifies both members as `DIFFERENT PLAN`;
database explanation still shows PostgreSQL in the retained effective parameters.
The first policy diff reports `NO EFFECTIVE POLICY CHANGES` with only plan/operation
identity context changes. The database diff reports `EFFECTIVE POLICY CHANGED`,
returns status 1 by design, and attributes removal of the database assignment and
contribution. The renderer's current verbosity is outside this walkthrough's scope.

`assert-scenario.py` and the canonical scenario gate remain the primary executable
owners of composition and history semantics. The commands above expose their
existing behavior without duplicating assertions.

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
This scenario adds no remediation, adapter execution, persisted Coverage, latest or
cross-operation result lookup, or current PASS/FAIL inference. `different_plan` is
only exact plan alignment; stored-plan policy diff is the separate authority for the
effective-policy distinction. It does not broaden the independent
`technical-only-packages` anchor or Stage 9 scenario scope.

Identifiers introduced under #131 remain experimental. Implemented ADR 0019 owns the
namespace and schema-URI conventions; the #136 migration establishes no compatibility
alias or contract freeze.

Tranche B uses an explicitly assigned base ParameterPolicy and independently
applicable database contribution. A direct technical Baseline owns the consumer
link, so no synthetic Objective, RequirementBaseline or ControlRealization is
needed. The contribution-only policy creates no assessment row. Removing it leaves
the valid base and turns observed PostgreSQL into an Evidence-derived technical
FAIL; removing the required base prevents an assessable plan. Historical
explanation and Policy Diff reconstruct complete contribution attribution from the
exact retained ParameterPolicy documents and applicability.
