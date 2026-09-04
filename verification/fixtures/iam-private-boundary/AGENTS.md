# IAM private-boundary fixture instructions

This synthetic fixture models a restricted environment boundary. It owns the
project inventory, assignments, synthetic observations, and the retained
private partial policy tree under `policy/`. It does not represent a real
private environment or authorize private data to enter this repository.

Validation must never compose directly from this checked-in `policy/` path.
The destination gate copies that tree into a separate temporary
`environment-private` source root, removes the fixture-side copy from the
temporary execution assembly, and then composes exactly these named sources:

- `shared-library`;
- `verification-policy`; and
- `environment-private`.

Never copy the restricted realization into either central policy source. Keep
source order nonsemantic and selection fail-closed. Generated evidence, plans,
results, credentials, provider state, and operational data remain temporary
and untracked.

Run the focused gate from a clean, committed destination checkout:

```sh
bash scripts/validate-iam-private-boundary.sh
```

The assessment plan remains the external-adapter handoff. Do not add adapter
execution, configuration rendering, or successor schema work here.
