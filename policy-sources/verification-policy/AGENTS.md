# Verification policy component instructions

This component root owns source-only internal test content: synthetic baselines,
overlays, requirements, realizations, external mappings, deliberate conflicts,
and related policy resources used by development projects and integration
scenarios.

It is a partial named policy source. Reusable controls, Rego helpers, evidence
schemas, and policy resource schemas belong in the co-located
`policy-sources/control-library/` producer and must not be copied here.
Configuration-intent schemas are not an active control-library contract. Projects
assemble named sources without precedence; source order must not resolve semantic
conflicts.

The source is independently named `verification-policy`, rooted at
`policy-sources/verification-policy/policies/`, and identified semantically by
the actual canonical content digest of that root. The destination Git revision
selects one atomic reviewed development composition; repository layout, checkout
paths, and that outer revision do not replace policy-source content identity.

Do not place real company policy, secrets, inventory, evidence, generated plans,
results, or downstream starter policy here. The restricted IAM realization
remains environment-private in its project boundary and must not be copied into
this source.

Sixteen synthetic assessment and assurance resources remain after generation-only
fixtures were retired. Preserve the current ownership boundary; do not move
resources between producers merely to satisfy validation. Source locators and
plan IDs are provenance surfaces, while control fingerprints, effective criteria,
parameters, dispositions, lineage, deviations, mappings, severity, and remediation
are semantic review surfaces.

Verification policy has no current independent version, release cadence,
release/archive producer, tag validator, or hosted publisher. Do not restore
those surfaces or create a replacement publication workflow. Historical tags,
GitHub Releases, manifests, archives, and checksums remain immutable in
`packetlss-labs/compliance-verification-policy`, but they are not current runtime
or validation dependencies.

## Validation

Run the component gate from a clean, committed destination checkout:

```sh
./policy-sources/verification-policy/scripts/validate-verification-policy.sh
```

The toolchain is pinned in `scripts/ci-versions.env`. The gate consumes the
co-located destination `tooling/`, `policy-sources/control-library/`, and this
component root at the same outer Git revision. It exports only committed objects
to a temporary non-Git directory, creates an isolated frozen environment, and
removes all temporary outputs on exit. Local edits are not consumed. No sibling
repository, project, workspace registry, cross-repository credential, or
repository-coordinate acquisition is part of this gate.

This source owns resource/schema/reference validity, its partial-source boundary,
deterministic independent content identity, source-order nonsemantics,
identical-only resource coalescing, fail-closed divergent resource and technical
control conflicts, expected invalid inputs, repository cleanliness, and temporary
output cleanup. The explicit tooling input supplies named-source loading,
schema/reference validation, canonical digest calculation, and the frozen Python
environment. The explicit control-library input supplies referenced reusable
controls, schemas, and Rego entrypoints. Neither input makes verification policy
a release unit or creates an aggregate source tree.

The canonical composed scenario lane remains owned by
`compliance-verification-scenarios` until its separate migration. Component tests
retain focused policy and technical-conflict invariants without restoring a
project matrix, aggregate feature runner, parent-repository requirement, or
implicit source discovery.

Destination GitHub Actions runs this real gate inside the stable
`component-validation` context after repository, tooling, and control-library
validation. The single ordinary read-only checkout selects the exact destination
head and disables credential persistence. Do not add App credentials, PAT
fallbacks, `git clone`, an explicit sibling-repository checkout, or historical
component repositories as normal CI inputs.

Expected invalid resources and conflicts are verification inputs. Do not weaken,
remove, reorder, or add precedence to them merely to make CI green. If a semantic
pin or expected outcome changes, inspect and acknowledge the underlying semantic
change rather than mechanically refreshing it.
