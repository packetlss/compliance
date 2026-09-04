# Verification scenario repository instructions

This destination root owns stable, deterministic, end-to-end verification projects.
Each project must remain isolated, use the public compliance CLI and normal
schemas, run offline from synthetic fixtures, and assert machine-readable
behavior. Do not add exploratory contracts here before they are accepted and
documented.

Keep generated evidence, assessment plans, results, and any external-adapter
output ignored.
Fixtures must be fictitious and operationally credible. Scenario READMEs must
state authoritative inventory inputs, policy scope, operating practice,
expected outcomes, assurance gaps, and claim limitations. Assessment plans are
the external-adapter handoff; scenario validation must not implement or execute
an adapter.

This root is the sole owner of the canonical composed scenario and complete
CLI/domain feature suite. Assembly exports only the explicit committed destination
roots documented in `integration/README.md` from the current destination revision.
The historical sibling-repository manifest and acquisition path are retired.
Preserve logical source boundaries and project-relative paths. Stable scenarios
consume normal verification contracts; they do not become an alternate
implementation path or import real restricted IAM project content. The synthetic
IAM policy must be independently materialized as `environment-private` and removed
from the fixture-side execution tree before composition.

## Validation

Follow [the integration guide](integration/README.md) to assemble the exact
source inputs in a temporary non-Git root, then run:

```sh
./scripts/validate-scenarios.sh --integration-root "$integration_root"
```

The supported Python, uv, and OPA versions remain pinned in
`scripts/ci-versions.env`. The canonical gate verifies the temporary non-Git
assembly against the committed destination revision before and after validation and:

- validates project configuration, inventory/DAG, policy, and waivers;
- uses the fixed `2026-09-01T00:00:00Z` instant for deterministic collection,
  waiver lifecycle, and assessment;
- runs the standard and container assessments and asserts their stored JSON;
- verifies the standard audit-package result remains `waived`, missing access
  checks/objective remain `unknown`, and the resolved plan retains the `auditd`
  control;
- verifies the container's eight technical checks and access objective pass,
  and its resolved plan includes the approved forwarding deviation plus the
  `containerd` control;
- asserts a representative assessment plan retains the subject, policy-source
  digests, stable control IDs, resolved parameters, fingerprints, derivations,
  deviations, lineage, and requirement/realization provenance needed by an
  external adapter;
- requires retired configuration commands, artifact schemas, intent inputs,
  renderers, and the generation-only development project to remain absent;
- requires the contradictory persona to remain an invalid, non-assessable plan
  with no precedence winner;
- asserts the scenario README retains its declared assurance gaps and claim
  limitations;
- runs the tooling executable feature suite so all 20 retained CLI leaves and
  18 retained domain features have one primary owner; and
- requires the scenario source and assembled scenario checkouts to remain clean,
  keeps generated artifacts in temporary output directories, and removes them
  after validation.

Git revisions and materialization paths are review/acquisition metadata only.
They must not enter source identity, precedence, release-lock identity, or
generated-artifact semantic identity. Do not introduce a replacement common
composition abstraction.

GitHub Actions uses the stable `verification-scenarios` check with the ordinary
destination checkout and no persisted credentials. Do not add App credentials,
PAT fallbacks, sibling clones, or explicit historical repository checkouts.

Expected invalid states are part of the verification contract. Do not weaken a
conflict, waiver, unknown result, or assurance gap merely to make CI green.
