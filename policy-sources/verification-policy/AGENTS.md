# Verification-policy instructions

This root owns source-only synthetic baselines, overlays, requirements, realizations, mappings, deliberate conflicts, and related verification resources. It is the independently named partial policy source `verification-policy`, rooted at `policies/`.

## Boundaries

- Reusable controls, helpers, and schemas belong to `policy-sources/control-library/`; do not copy them here.
- Do not add real company policy, private realizations, secrets, inventory, evidence, generated artifacts, or downstream starter policy.
- Source content identity is calculated from this semantic root. Repository layout, Git revision, path, and source order are nonsemantic.
- Preserve source-order rejection, identical-only coalescing, fail-closed divergent conflicts, and expected invalid inputs.
- This source has no independent version, archive producer, tag validator, or hosted publisher lane.
- The canonical composed feature suite belongs to `verification/scenarios/`.

## Validation

After committing the candidate revision and ensuring the checkout is clean, run from the repository root:

```sh
bash policy-sources/verification-policy/scripts/validate-verification-policy.sh
```

Do not weaken or mechanically refresh an expected conflict or outcome merely to make validation pass; inspect and acknowledge the semantic change.
