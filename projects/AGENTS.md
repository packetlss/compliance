# Development-project instructions

This root owns ordinary exploratory compliance projects whose ownership and
information-sharing boundary permits co-location. Every `projects/<id>/`
directory is a logically independent project. Do not combine inventories,
assignments, waivers, fixtures, generated paths, or project catalogs across
projects for convenience.

Reusable controls, helpers, and schemas belong in
`policy-sources/control-library`. Synthetic verification-only policy belongs in
`policy-sources/verification-policy`. Neither source has precedence. Do not
copy retired MacBook collection/privacy content, canonical verification
scenarios, or restricted IAM realization content here.

Generated evidence, plans, results, external-adapter outputs, caches,
credentials, tokens, and private keys stay out of Git. Fixtures are synthetic
observations, not desired policy. Provider credentials, execution state,
approval, and apply concerns remain outside project policy inputs.

Canonical validation runs from the destination repository root:

```sh
bash scripts/validate-development-projects.sh
```

Commit proposed changes before running the gate. It exports the exact current
destination revision into a temporary non-Git assembly containing only the
registry and these explicit co-located roots:

```text
tooling/
policy-sources/control-library/
policy-sources/verification-policy/
projects/
```

The gate verifies the materialized bytes against the committed destination
revision before and after fixed-time public CLI assertions. It preserves
project isolation, expected failures, owning-repository cleanliness, and
temporary-output cleanup. Repository names, Git revisions, and checkout paths
remain acquisition/review metadata rather than runtime identity.

Destination CI runs this focused gate inside `component-validation` after the
repository, tooling, control-library, and verification-policy gates. No App
credentials, PATs, sibling clone, repository-coordinate manifest, or explicit
historical checkout is part of normal validation. The complete feature suite
remains owned by canonical verification scenarios and is not duplicated here.

Do not implement `project-config/v1alpha3`, composition lock, assessment v4,
the IAM/private-boundary fixture, or workspace successor semantics as part of
ordinary project migration. Those remain separately routed work.
