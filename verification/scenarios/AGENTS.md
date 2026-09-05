# Verification-scenario instructions

This root owns stable, deterministic, end-to-end verification projects and the complete public CLI/domain feature suite.

## Boundaries

- Each project remains isolated, uses the public `compliance` CLI and normal schemas, runs offline from synthetic fixtures, and asserts machine-readable behavior.
- Do not add exploratory contracts before they are accepted and documented.
- Keep generated evidence, plans, results, and adapter output ignored.
- Fixtures must be fictitious and operationally credible; scenario READMEs state inputs, scope, expected outcomes, assurance gaps, and claim limitations.
- Assessment plans are the external-adapter handoff; scenarios do not implement or execute adapters.
- Preserve independently named policy sources, nonsemantic source order, fail-closed conflicts, and the separately materialized synthetic `environment-private` source.
- Expected invalid, waived, and `unknown` states are part of the verification contract.

## Validation

After committing the candidate revision and ensuring the checkout is clean, run from the repository root:

```sh
bash scripts/validate-verification-scenarios.sh
```

Use `verification/scenarios/integration/README.md` for the assembly contract and detailed assertions. Do not reintroduce sibling repositories, repository-coordinate manifests, or historical workspace acquisition.
