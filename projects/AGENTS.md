# Development-project instructions

This root owns ordinary exploratory compliance projects whose ownership and information-sharing boundary permits co-location. Every `projects/<id>/` directory is logically independent.

## Boundaries

- Do not combine inventories, assignments, waivers, fixtures, generated paths, or project catalogs across projects.
- Reusable controls/helpers/schemas belong to `policy-sources/control-library/`; synthetic verification-only policy belongs to `policy-sources/verification-policy/`.
- Generated evidence, plans, results, adapter outputs, caches, credentials, tokens, private keys, provider state, approval, and apply concerns stay out of Git.
- Fixtures are synthetic observations, not desired policy.
- Tooling-owned schemas, canonical scenarios, and the IAM/private-boundary fixture have separate owners; follow their instruction routes.

## Validation

After committing the candidate revision and ensuring the checkout is clean, run from the repository root:

```sh
bash scripts/validate-development-projects.sh
```

The gate exports only explicit committed co-located roots into a temporary non-Git assembly. Preserve project isolation and do not restore sibling acquisition or historical workspace dependencies.
