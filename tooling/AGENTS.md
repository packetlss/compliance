# Tooling repository instructions

This repository owns the unified `compliance` CLI, planner, evaluator, generic
collectors, project configuration and inventory schemas, tests, and detailed
executable architecture contracts.

Preserve the architectural invariants in `docs/architecture.md`. Collectors
emit evidence and never contain desired policy. OPA evaluation remains off the
governed subject. Projects and policy sources are independently versioned
dependencies and must not be copied into this repository as production data.

The released reusable policy library and verification-only policy source are
separate. `compliance-control-library` owns reusable controls, helpers, and contracts;
`compliance-verification-policy` owns retained synthetic requirements,
baselines, mappings, realizations, and deliberate conflicts. A future released
example-company policy remains proposed. Verification and future example policy
must not depend on each other or copy reusable controls.

Policy inputs are stable named sources, not an ordered override stack. Preserve
per-source digests, order invariance, identical-only resource coalescing,
divergent identity/schema errors, partial-tree support, and multi-module OPA
evaluation. Customization belongs in typed baseline overlays or complete
realizations, never generic source precedence.

The provenance-bearing assessment plan is the external interoperability
boundary. Preserve stable control implementation and instance IDs, resolved
parameters, definition fingerprints, disposition, derivations, deviations,
baseline and requirement/realization lineage, subject and plan identity, and
named policy-source content digests. External programs may consume that plan
for IaC, PaC, MDM, ticketing, or configuration-management output, but core
tooling does not load adapters, render backend artifacts, or treat external
output as execution or compliance evidence.

## Validation

Run the canonical source gate from this repository root:

```sh
./scripts/validate-tooling.sh
```

Commit your changes before running the gate: it requires a clean tooling
checkout before and after validation and verifies the selected tooling revision.
Python, uv, and OPA are pinned in `scripts/ci-versions.env`. Frozen dependency
setup and all tooling unit/contract tests use only this repository and temporary
synthetic fixtures. No external checkout or cross-repository credential is
required. Focused development can use:

```sh
uv run --frozen python -m unittest discover -s tests -v
```

GitHub Actions retains the stable `tooling-validation` check and checks out the
exact tooling PR head with the ordinary read-only repository token, without
persisting credentials. The canonical composed scenario gate in
`compliance-verification-scenarios` owns the complete feature suite and real
policy/project composition. See [validation ownership](docs/validation.md)
for coverage and contributor commands.

Installed-package, locked-artifact, release-preparation, and generic policy-source
release conformance remain distinct gates. Policy-source release conformance is
fully local and provider-neutral: it builds and installs the current wheel, then
validates a minimal synthetic generic descriptor/archive without producer Git,
hosted downloads, or cross-repository credentials. Historical pre-freeze policy
manifest reproduction uses the corresponding historical tooling and release state.

Use narrow authored edits, keep generated artifacts out of Git, and update the
relevant architecture document and decision log when a domain contract changes.
A tooling PR must not change workspace gitlinks or sibling repositories.
