# OPA Compliance Toolset

An evolving architecture for a compliance platform built around
[Open Policy Agent](https://www.openpolicyagent.org/).

The current design discussion lives in
[`docs/architecture.md`](docs/architecture.md). The policy repository,
evidence, control, and baseline design is developed further in
[`docs/policy-model.md`](docs/policy-model.md). The model for deriving company
policy from external benchmarks is in
[`docs/baseline-inheritance.md`](docs/baseline-inheritance.md). Inventory
grouping and group-to-baseline assignment are documented in
[`docs/inventory-and-assignments.md`](docs/inventory-and-assignments.md). The
canonical shape and complete configuration contract for an independently
operable project are in [`docs/project-layout.md`](docs/project-layout.md).
The implemented link between high-level objectives, environment-private technical
implementations, and defensible top-level baseline results is exercised in
[`docs/control-realization.md`](docs/control-realization.md).
Development topology and repository ownership are governed by destination
[ADR 0005](../docs/adr/0005-content-addressed-development-boundaries.md), the
current system [architecture](../docs/ARCHITECTURE.md), and
[repository map](../docs/REPOSITORIES.md).
Repository layout is not semantic policy, release, or runtime identity.
The resolved assessment plan is also the machine-readable handoff to external
IaC, PaC, MDM, ticketing, or configuration-management programs. Core tooling
does not compile configuration or provide a backend adapter/plugin runtime.
The exact subject/control exception lifecycle and its separation from desired
policy are documented in [`docs/waivers.md`](docs/waivers.md).
The accepted separation between scenario-first verification, exploratory
development projects, and boundary examples—and the required
company-policy and optional framework-to-implementation assurance narrative—is documented in
[`docs/verification-scenarios.md`](docs/verification-scenarios.md).

## Two complementary uses

The same platform intentionally supports two levels of policy without forcing
one into the other:

| Use | Authoring path | Result |
|---|---|---|
| Technical desired-state enforcement | `Baseline` / `BaselineOverlay` → control instances | Independently attributable package, hardening, or configuration results |
| Control assurance | `RequirementBaseline` → `ControlRequirement` → `ControlRealization` → control instances | Technical results plus a conservative objective and top-baseline roll-up |

A project may use either path or both. Requiring Homebrew packages, an SSH
setting, or a SaaS option is useful policy by itself and does not need an
artificial regulatory objective. Use the requirement path when the organization
needs to show that a complete higher-level company or external-framework
objective has been implemented and is currently satisfied. The realization
then states which technical checks jointly support that claim in the selected
environment.

Consequently, `Objectives: 0` is a valid and expected plan summary for a
project that assigns only technical baselines. It means no high-level
requirements were assigned; it does not mean the technical checks are missing
or ineffective. See
[`docs/policy-model.md`](docs/policy-model.md#two-policy-paths-one-assessment-plan)
for the selection rules and reporting semantics.

Runnable end-to-end examples are available for:

- synthetic AWS and SaaS API-governed subjects in
  [`mock-fleet/`](../projects/mock-fleet/README.md); and
- a synthetic restricted Linux IAM realization in
  [IAM boundary fixture](../verification/fixtures/iam-private-boundary/README.md);
- synthetic standard and container-runtime server personas, including an
  invalid overlapping classification, in
  [`server-personas/`](../projects/server-personas/README.md); and
- the stable synthetic Linux hardening rollout in
  [canonical scenarios](../verification/scenarios/projects/linux-hardening-rollout/README.md).

## Operator CLI

The prototype exposes one operator-facing command. From a repository checkout,
initialize the pinned development environment once and invoke its installed
entry point through the repository adapter. Repository paths come from the
automatically discovered root registry [`compliance.yaml`](../compliance.yaml):

```sh
scripts/dev setup
scripts/dev cli config show
scripts/dev cli inventory list assets
scripts/dev cli inventory graph
scripts/dev cli coverage list assets
scripts/dev cli coverage explain cloud-account/aws-111122223333
scripts/dev cli policy validate
scripts/dev cli policy diff before-plan.json after-plan.json
scripts/dev cli policy diff-set before-plans/ after-plans/
scripts/dev cli assessment status
scripts/dev cli assessment frameworks
```

Repository development and testing use `scripts/dev cli ...`; an independently
installed product is invoked as `compliance ...`. The adapter does not define a
second CLI: it executes the managed environment's installed `compliance`
entrypoint from the repository root and makes the pinned OPA available.

That registry exposes multiple isolated projects. `mock-fleet` is the current
default; list or select projects from the checkout root without passing config
paths. This checkout topology is transition metadata, not a permanent product
contract:

```sh
scripts/dev cli config list
scripts/dev cli --project mock-fleet inventory validate
scripts/dev cli --project iam-realization inventory validate
scripts/dev cli --project server-personas assessment status
scripts/dev cli --project server-personas waiver list
```

The command hierarchy follows `Inventory → Coverage → Assessment` while
keeping rendered plans available as the adapter handoff:

```text
compliance config      show or validate resolved project configuration
compliance inventory   validate, list, graph, or explain inventory scope
compliance coverage    list or explain current assessment expectation
compliance policy      validate policy inputs or diff stored plan artifacts
compliance waiver      validate or inspect temporary approved exceptions
compliance plan        render or inspect immutable assessment plans
compliance assessment  run assessments or inspect fleet, group, and subject status
```

Common examples:

```sh
scripts/dev cli inventory explain cloud-account/aws-111122223333
scripts/dev cli coverage list assignments --format json
scripts/dev cli coverage explain cloud-account/aws-111122223333
scripts/dev cli plan render cloud-account/aws-111122223333
scripts/dev cli policy diff before-plan.json after-plan.json --format json
scripts/dev cli policy diff-set before-plans/ after-plans/ --format json
uv run python compliance-tooling/examples/prepare_policy_diff_set.py
uv run python compliance-tooling/examples/verify_examples.py
uv run python compliance-tooling/examples/verify_examples.py --show waiver
scripts/dev cli --project mock-fleet plan show
scripts/dev cli --project mock-fleet \
  plan show cloud-account/aws-111122223333
scripts/dev cli assessment run cloud-account/aws-111122223333
scripts/dev cli assessment status --group aws-accounts --outcome fail --plan-alignment plan_aligned
scripts/dev cli assessment groups
scripts/dev cli assessment frameworks
scripts/dev cli assessment explain cloud-account/aws-111122223333
```

Command-line path options override configuration. Use `--project NAME` to
select a registered project, `--config PATH` to select an explicit
project registry or project file, or `--no-config` to require explicit paths. See
[`docs/cli.md`](docs/cli.md) for the complete discovery, precedence, and
path-resolution contract.

Inventory views present supplied normalized facts. Coverage views derive current
policy applicability and assessment expectation without persistence; assessment
views retain result/history responsibility. `asset` is CLI vocabulary only and
does not rename the underlying `Subject` resource or IDs. Operator views support
`--format json` for automation.
Collectors remain separate executables and emit typed evidence; the unified
CLI does not embed platform probes.

External adapters may map the assessment plan's stable `implementation`,
`definition_fingerprint`, resolved `parameters`, instance and subject identity,
lineage, deviations, and policy-source provenance into backend-specific output.
Assessment does not require an adapter. External output must reference its
source plan when it records provenance, and is neither proof of execution nor
compliance evidence.

`assessment frameworks` lists objective and technical `external_refs`
mappings with their current status and alignment to parent policy. It keeps a
tailored company-policy pass visibly separate from an unaltered upstream
framework mapping.

Select the mock project explicitly to inspect its three-asset fleet:

```sh
scripts/dev cli --project mock-fleet inventory graph
scripts/dev cli --project mock-fleet assessment status
```

Select the IAM project to see technical checks roll up through an implemented
control objective to its assigned requirement baseline:

```sh
scripts/dev cli --project iam-realization assessment status
scripts/dev cli --project iam-realization \
  assessment explain host/restricted-linux-01
```

`compliance` is the sole supported operator entry point. The Python modules
behind it are internal implementation details, not supported scripts or a
public Python API.

## Contributor validation

Run `./scripts/validate-tooling.sh` from a clean, committed tooling checkout.
The source gate requires only this repository, the pinned toolchain, and frozen
Python dependencies. CLI discovery, planning, evaluation, provenance, and
negative contracts use tooling-owned synthetic fixtures. See
[validation ownership and commands](docs/validation.md) for focused development
and the separate installed-package/release gates. The complete composed feature
suite is owned by `compliance-verification-scenarios`.
