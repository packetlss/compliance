# Shared control-library instructions

This root owns reusable controls and helpers, control parameter schemas, policy/evidence schemas, and technology-neutral requirement contracts. Its semantic source is `control-library`, rooted at `policies/`.

## Boundaries

- Do not add real environment inventory, evidence, secrets, restricted parameters, generated artifacts, or adopter-specific desired policy.
- Synthetic baselines, requirements, realizations, mappings, and deliberate conflicts belong to `policy-sources/verification-policy/`.
- Controls consume typed evidence and return attributable results. Missing or stale evidence is `unknown`, never `pass`.
- Policy sources compose without precedence. Preserve content identity, immutable digest/fingerprint review, identical-only coalescing, fail-closed divergence, and typed overlay semantics.
- Assessment plans are the external-adapter handoff. Do not add adapter code, backend templates, apply behavior, or source precedence.
- Historical hosted releases are archived provenance. Do not publish a new control-library release without separately reviewed work.

## Assurance routing

[ADR 0016](../../docs/adr/0016-closed-world-policy-assessment.md) supersedes ADRs
0013–0015. Reusable evidence/requirement contracts support explicitly supplied
company policy; governance owns external applicability and sufficiency. Mappings
are attributable policy/reporting content. Selected evidence contracts and exact
beneficiary dependencies constrain assurance; no generic certificate, recognition
or external completeness machinery is required. #78 implements the bounded accounting and typed assertion cutover. #37 remains
open for residual architecture and escalation; no broader assurance subsystem is authorized.

## Validation

After committing the candidate revision and ensuring the checkout is clean, run from the repository root:

```sh
bash policy-sources/control-library/scripts/validate-shared-policy.sh
```

Use `policy-sources/control-library/docs/validation.md` for coverage and focused commands. A change must remain within its contract and must not move resources into verification policy, projects, scenarios, or private fixtures.
