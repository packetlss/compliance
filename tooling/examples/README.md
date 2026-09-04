# Runnable feature examples

The tooling feature catalog covers every retained public `compliance` leaf
command and the important component behaviors that span commands. After removal
of in-core configuration generation it contains 20 CLI leaves and 18 domain
features.

The complete composed suite is owned by
[`compliance-verification-scenarios`](https://github.com/packetlss-labs/compliance-verification-scenarios).
That currently separate repository coordinate is transitional integration
metadata; its scenario-gate ownership and isolated project contracts survive
source consolidation under workspace
[ADR 0005](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/adr/0005-content-addressed-development-boundaries.md).
Its persistent manifest remains on the pre-cutover composition until scenario
issue #11 selects the final tooling, policy-source, and project revisions
together. Tooling #67 does not advance that manifest.

[`feature-coverage.json`](feature-coverage.json) records the retained catalog
and assigns each feature to one primary verification, development, or boundary
scenario. Tooling tests derive the real CLI leaf set from the parser and reject
missing or duplicate catalog entries.

## Retained command coverage

| Command | Contract exercised |
|---|---|
| `config show`, `config validate`, `config list` | Project/workspace selection and resolved paths |
| `inventory validate`, `inventory list`, `inventory graph`, `inventory explain` | Typed inventory, references, DAG membership, and assignment provenance |
| `policy validate` | Named sources, controls, parameter schemas, baselines, overlays, requirements, realizations, and Rego entrypoints |
| `policy diff`, `policy diff-set` | Stored-plan semantic comparison with distinct context changes |
| `waiver validate`, `waiver list`, `waiver explain` | Bounded approvals, lifecycle, and exact target scope |
| `plan render`, `plan show` | Immutable provenance-bearing assessment plans |
| `assessment run`, `assessment status`, `assessment groups`, `assessment frameworks`, `assessment explain` | Evidence-backed technical and objective assessment |

Configuration planning, showing, explaining, and rendering commands are not
part of the current CLI.

## Retained domain coverage

The catalog retains:

- deterministic typed evidence collection and schema enforcement;
- multi-parent inventory resolution;
- named policy-source and private-realization composition;
- ordinary technical baselines and every overlay operation;
- invalid-resolution refusal;
- requirement/realization roll-up and missing-evidence `unknown`;
- waiver application and filtering;
- framework alignment and assessment filtering;
- policy implementation coverage; and
- versioned machine-readable output.

The assessment plan is the external-adapter handoff. A separate program may
consume stable `implementation`, `instance_id`, resolved `parameters`,
`definition_fingerprint`, active/excluded disposition, derivations,
deviations, baseline and requirement/realization lineage, subject/plan identity,
and named policy-source content digests.

Core tooling does not load executable adapters from policy sources and
assessment requires no adapter. External IaC, PaC, MDM, ticketing, or
configuration-management output is neither proof of execution nor compliance
evidence. Output provenance must reference its source assessment plan.

## Focused policy diff samples

`prepare_policy_diff_set.py` renders three isolated before/after plan pairs
without collecting evidence or evaluating controls:

- `unchanged` — two identical valid subject sets; expected exit `0`;
- `changed` — one modified, one removed, and one added subject; expected exit
  `1`; and
- `incomplete` — an intentional assignment conflict; expected exit `2`.

```sh
uv run python compliance-tooling/examples/prepare_policy_diff_set.py
```

Pass `--output /tmp/compliance-policy-diff-demo` to retain the snapshots.
