# Release contracts

Forward releases use the tooling-owned generic contracts:

- `compliance.example/policy-source-release-manifest/v1`
- `compliance.example/policy-source-archive/v1`
- `compliance.example/policy-source-tree-digest/v1alpha1`

This component intentionally does not copy the generic schema or validator.
Release preparation and verification run with the co-located `tooling/`
implementation while preserving the `compliance-tooling` distribution contract.

The immutable historical `compliance-policy v0.2.0` producer-specific schemas and
bundle implementation remain available from its historical tag. Current source
does not copy or validate that retired format; historical reproduction uses the
historical source and tooling revisions and their checksum rules.
