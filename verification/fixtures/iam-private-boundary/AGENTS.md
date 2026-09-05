# IAM private-boundary fixture instructions

This synthetic fixture models a restricted environment boundary. It owns project inventory, assignments, observations, and the retained private partial policy tree under `policy/`; it contains no real private data.

## Boundaries

- Validation must copy `policy/` into a distinct temporary `environment-private` source and remove the fixture-side copy from the execution assembly.
- Never compose directly from the checked-in fixture path or use symlink/same-inode shortcuts.
- Compose exactly `control-library`, `verification-policy`, and `environment-private`; no source has order precedence.
- Never copy the retained realization into either central policy source.
- Generated evidence, plans, results, credentials, provider state, and operational data remain temporary and untracked.
- Assessment plans remain the external-adapter handoff. Do not add adapter execution, backend rendering, or successor schema work here unless separately routed.

## Validation

After committing the candidate revision and ensuring the checkout is clean, run from the repository root:

```sh
bash scripts/validate-iam-private-boundary.sh
```
