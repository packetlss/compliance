# Standalone component validation

Destination `component-validation` validates this producer's reusable policy and
release contracts from the consolidated checkout. Workspace ADR 0005 governs the
separation of component, composed integration, and installed-release validation.

## Inputs and local command

Install the Python, uv, and OPA versions in `scripts/ci-versions.env`. The explicit
tooling contract is the co-located destination `tooling/` root at the same outer
Git revision. From the destination root:

```sh
./policy-sources/control-library/scripts/validate-shared-policy.sh
```

The validator verifies the exact proposed destination revision through optional
`COMPLIANCE_CONTROL_LIBRARY_SHA`, then exports only the committed `tooling/` and
`policy-sources/control-library/` objects from that one revision into a temporary
non-Git directory. It creates an isolated frozen Python environment there and
deletes temporary material on exit. It does not read local edits, use a parent
registry, acquire a sibling repository, or change the checkout. Commit local
changes before running the gate: the destination repository must be clean before
and after validation.

The co-located tooling root provides the policy catalog, canonical source digest,
generic descriptor model, and archive safety validator without restoring the
removed configuration runtime. The outer Git revision is atomic review and
acquisition metadata; it does not participate in policy content identity.

## Coverage ownership

The gate retains:

- All retained library resource, parameter, policy, and evidence schemas,
  reference compatibility, and compiled Rego entrypoint validation.
- Direct current-state source-boundary checks, exhaustive reusable-file coverage,
  unique identities, resolved references, and adoption-specific resource and
  external-mapping absence.
- Negative cases for missing/invalid parameter schemas, missing evidence schemas,
  invalid control manifests, rejected configuration facets, and nonexistent Rego
  entrypoints.
- Current generic producer tests: path-and-raw-byte source identity, deterministic
  archive identity, exact candidate content and representation digests,
  materialized content verification, no-Git construction, optional noncanonical
  metadata, release-lock projection, and unsafe or tampered source/archive refusal.
- Rego formatting and all control-owned Rego unit tests; destination repository
  cleanliness and temporary-output cleanup.

The direct reusable-source assertions live in `tests/test_policy_resources.py`.
Verification resource bytes and mappings belong to verification-policy validation;
project source composition and full feature coverage belong to the canonical
`compliance-verification-scenarios` integration lane. This component runs no
project matrix, tooling-owned full unit suite, or complete feature runner. Retired
producer-specific historical readers, fixtures, schemas, and bundle builders are
not part of current validation.

## CI and candidate integration

The destination's stable `component-validation` job checks out the exact proposed
head once, runs repository validation and retained tooling validation, and then
runs the resource/schema/source-boundary tests, generic local release/archive
validation, and Rego checks from the co-located component roots. The ordinary
read-only repository token is not persisted. No GitHub App credential, PAT,
`git clone`, or explicit sibling-repository checkout is used or passed to the
validator.

The former duplicate generic-release workflow and its publisher-only annotated-tag
gate are retired. Hosted release publication is not part of current component CI;
provider-neutral local prepare/verify remains covered by the stable gate.

The accepted integration baseline is scenario main
`a3981ab4d108552307631b0220672e2b85d77747` (PR #10, green head
`0386ce54e27ae348339f78fb19a0df94a8c89e0e`), selecting control-library
`e49121763ed471f87dbf2a9e27cebd1065cc322c` and running all 24 registered commands and
24 domains. A validation-only change cites that evidence and proves with a diff
scan that policy and other scenario-consumed inputs are unchanged. Changes to
consumed contracts instead need a disposable candidate composition under the
issue's candidate-integration rule. Do not automatically advance the scenario
manifest or introduce a dependency back on it.
