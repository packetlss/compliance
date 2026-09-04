# Standard control-library component instructions

This component root owns the released standard control library: reusable controls
and helpers, control parameter schemas, policy and evidence schemas, and
technology-neutral requirement contracts. Its semantic source is explicitly named
`shared-library` and rooted at `policies/` (destination path
`policy-sources/control-library/policies/`). It is a recommended reusable policy
source, not a mandatory platform component or adopter desired policy.

Do not add real environment inventory, evidence, secrets, restricted
parameters, generated plans, assessment results, synthetic company adoption
policy, or verification-only baselines and realizations. Controls consume typed
JSON evidence and return independently attributable results. Missing or stale
evidence is `unknown`, never `pass`.

Policy sources compose by stable identity and content, never by source order.
Preserve per-source digests, identical-only coalescing, hard errors for divergent
same-identity resources, immutable parent/digest/fingerprint review, and typed
overlay semantics. Do not introduce implicit precedence or last-writer-wins
behavior.

## Validation

Run the component gate from a clean, committed destination checkout:

```sh
./policy-sources/control-library/scripts/validate-shared-policy.sh
```

[docs/validation.md](docs/validation.md) defines retained coverage and the canonical
local/CI procedure. The gate consumes the co-located destination `tooling/` root at
the same outer Git revision. It exports only committed tooling and control-library
objects to a temporary non-Git directory and removes its temporary environment and
outputs on exit. Local input edits are not consumed. No sibling repository,
project, workspace registry, or cross-repository acquisition is part of this gate.

The supported Python, uv, and OPA versions are pinned in
`scripts/ci-versions.env`. Preserve library resource/schema/reference validation,
the direct current-state source boundary, source-tree identity, generic release/archive
contracts, Rego formatting, and Rego unit tests. Keep repository cleanliness
checks. The canonical complete feature suite and composed project assertions
belong to `compliance-verification-scenarios`; do not add an aggregate runner here.

Destination GitHub Actions runs this real gate inside the stable
`component-validation` context after repository and tooling validation. The single
ordinary read-only checkout selects the exact destination head and disables
credential persistence. Do not add App credentials, PAT fallbacks, `git clone`, an
explicit sibling-repository checkout, or the historical tooling repository as a
normal CI input.

Hosted release publication remains retired. Existing tags, GitHub Releases, and
hosted assets in `packetlss-labs/compliance-control-library` are immutable historical
records; do not cut or publish a new control-library release here. Preserve
`release/VERSION` and the provider-neutral local descriptor/archive prepare and
verify path as the current release-contract proof. A new publisher requires
separate reviewed work when a real downstream release is needed.

Restricted realizations belong to their authorized environment repository. Do
not add a runnable duplicate here: the named multi-source contract assembles
shared schemas and controls with verification policy and private partial trees
inside the environment.

Controls are assessment-only capabilities. Preserve their stable control IDs,
parameter schemas, Rego entrypoints, evidence requirements, and independently
attributable results. Ordinary technical baselines and requirement/realization
assurance remain complementary consumers of those controls.

The provenance-bearing resolved assessment plan is the external-adapter handoff.
An external program may map stable control IDs, definition fingerprints, resolved
parameters, and provenance to IaC, PaC, MDM, ticketing, or configuration-management
output. Do not add adapter code, backend templates, compatibility scaffolding,
source precedence, or a replacement configuration-plan abstraction to policy.

Reusable library content remains here; synthetic baselines, requirements,
realizations, mappings, and deliberate conflicts live in
`compliance-verification-policy`. Current-state tests derive the source inventory
directly from `policies/` and reject adoption-specific resources and external
mappings. A future example-company policy is separate downstream release work and
must not copy verification content.

A control-library change must remain within its bounded destination issue and must
not move resources into verification policy, projects, scenarios, or private
fixtures. Integration revisions advance only through separately justified consumer
work.
