# Canonical source integration

This destination root owns the composed deterministic scenarios and complete
registered CLI/domain feature suite. Canonical validation consumes only these
committed roots from one reviewed `packetlss/compliance` revision:

- `tooling/`;
- `policy-sources/control-library/`;
- `policy-sources/verification-policy/`;
- `projects/`;
- `verification/fixtures/iam-private-boundary/`; and
- `verification/scenarios/`.

The historical `integration/components.json` repository-coordinate manifest is
retired. There are no sibling revisions, repository coordinates, mutable branch
lookups, or external acquisition credentials in this lane. The outer destination
revision selects the committed development inputs for review and export only; it
is not semantic runtime identity.

This remains a **source-development integration lane**. Installed-release
acquisition and no-Git runtime provenance remain the separate
`installed-release-provenance` gate. Tooling, `control-library`, and
`verification-policy` retain distinct roots and identities. Ordinary projects
remain isolated.

The synthetic IAM fixture is exported with the other committed inputs, but its
checked-in `policy/` tree is physically copied into a separate
`external-sources/environment-private/` root and removed from the fixture-side
execution tree before validation. The scenario therefore cannot consume the
private policy by traversing its co-located checkout path.

## Local validation

Install the versions in `toolchain/versions.env`, commit the proposed destination
changes, and run from the repository root:

```sh
bash scripts/validate-verification-scenarios.sh
```

The gate first runs the assembly guard tests. It then exports exactly the six
roots above from the current committed destination revision into a temporary
non-Git directory, independently materializes `environment-private`, installs
the frozen tooling environment into the temporary run area, and runs:

```sh
verification/scenarios/scripts/validate-scenarios.sh \
  --integration-root "$integration_root"
```

The scenario-owned `integration/compliance.yaml` registry selects the Linux
rollout, two ordinary development projects, and the synthetic IAM project using
destination-local paths. The validator uses the public CLI, the existing
`COMPLIANCE_EXAMPLE_PROJECT_REGISTRY` interface, and the fixed
`2026-09-01T00:00:00Z` instant.

Validation preserves waiver lifecycle and underlying failure, unknown access
coverage, policy provenance, requirement/realization outcomes, and expected
persona, policy, and realization conflicts. A representative assessment plan is
checked for the subject, named policy-source digests, stable control IDs,
resolved parameters, fingerprints, derivations, deviations, lineage, and
source plus requirement/realization provenance required at the external-adapter
handoff. No adapter is installed or executed.

The canonical project uses `project-config/v1alpha3` and v4 assessment
artifacts. Validation recomputes actual source/editable tooling and named-source
identity from the temporary non-Git assembly, requires exact planning/evaluation
source equality, and checks evaluator, complete evidence snapshot, factual
successful-selection, and applied-waiver provenance. A temporary locked variant
proves that identical actual composition produces the unlocked semantic plan ID
while recording distinct expected enforcement. Direct and complete-lock
mismatches must refuse before plan/domain execution.

The company-IAM and technical-only anchors split the former mixed closed-world
proof into coherent company-objective and direct technical stories. They use the
public CLI and separately materialized private IAM realization; their proof is
`scripts/assert-semantic-anchors.py`. The Requirement/Realization story remains
experimental and does not freeze the v4 representation.

The complete feature runner executes once and requires exactly one owner for
each of the 21 retained CLI leaves and 19 retained domain features. Generated
outputs stay in a temporary run directory and are removed. Before and after
execution, the assembly is byte-compared with the transformed committed export;
the destination checkout must remain clean.

## CI ownership

Destination GitHub Actions runs the same root gate in the stable
`verification-scenarios` context for every pull request and `main` push. The job
uses only the ordinary destination checkout with credential persistence disabled.
It does not create a GitHub App token, use a PAT fallback, clone historical
components, or explicitly check out sibling repositories.

`component-validation` retains focused repository, tooling, policy, project, and
IAM gates. It does not duplicate the complete feature runner.
`installed-release-provenance` retains the installed tooling/release lane.

## Changing the composition

Composition changes occur through a bounded destination issue and PR that edits
the applicable committed roots atomically. Review semantic source identities and
expected outcomes directly; do not turn the destination revision or materialized
paths into policy identity, precedence, or an active lock. If a change requires a
new common composition abstraction, return it as an architectural finding.
