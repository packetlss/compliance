# Compliance development projects

This root contains ordinary exploratory development projects. Projects are
co-located only because they share the same development ownership and
information-sharing boundary; each project remains a separate logical
configuration with its own inventory, assignments, fixtures, waivers, and
generated runtime paths.

| Project | Historical source snapshot | Role |
| --- | --- | --- |
| [`mock-fleet`](mock-fleet/) | `packetlss-labs/compliance-project-mock-fleet@e24440f679e4527b5beb570c9c7d56ad0ddd43e9` | Synthetic AWS/SaaS assessment, evidence isolation, framework mapping, and filter development |
| [`server-personas`](server-personas/) | `packetlss-labs/compliance-project-server-personas@966c472e551533d3f6b919a11f2ffe223ec9fcee` | Synthetic Linux persona inheritance, approved deviation, temporary waiver, and classification-conflict development |

The archived predecessor repositories retain the history of those earlier
project migrations. The ordinary project source moved here from
`packetlss-labs/compliance-development-projects` at
`fa0eb99dc472a041e57c38103913c81753b963ab`.

## Boundaries

- `projects/<id>/` roots never merge state or catalogs for convenience.
- Reusable controls and schemas remain in `policy-sources/control-library`.
- Synthetic verification policy remains in `policy-sources/verification-policy`.
- Canonical scenarios and the IAM/private-boundary fixture are not part of this root.
- Generated evidence, plans, results, external-adapter outputs, credentials, and execution state are not source-controlled.
- Source order is never policy precedence.

## Validation

Install the versions in [`toolchain/versions.env`](../toolchain/versions.env),
commit the proposed destination changes, and run from the repository root:

```sh
bash scripts/validate-development-projects.sh
```

The focused gate exports committed `tooling/`, both independently named policy
producers, and `projects/` into a temporary non-Git directory. It validates the
assembly byte-for-byte, runs fixed-time collection and assessment assertions
for each project, preserves expected failures and project isolation, and
removes generated output. It does not fetch or pin historical repositories.

The complete registered feature suite remains owned by the canonical
verification-scenarios migration stage and is not invoked by this focused gate.
