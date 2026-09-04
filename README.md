# Compliance

This private repository is the selected destination for consolidated non-sensitive compliance development under accepted `packetlss-labs/compliance-workspace` ADR 0008.

Authority transfers by source domain during the staged cutover coordinated by
`packetlss-labs/compliance-workspace#69`. Destination `tooling/` and the
independently named policy roots under `policy-sources/control-library/` and
`policy-sources/verification-policy/` are authoritative. Each remaining
`packetlss-labs/*` repository stays authoritative for its source domain until its
explicit migration stage is merged and cut over.

The target development composition remains:

```text
tooling + N named policy sources + project inputs
```

Repository layout is not semantic identity. Tooling and policy-source content identities remain content-addressed, policy roots remain independently named and materialized, source/file order is nonsemantic, divergent same-identity definitions fail closed, and real private environment inputs remain outside this repository.

## Current phase

The repository currently contains authoritative tooling, reusable
control-library source, source-only verification policy, and the ordinary
`mock-fleet` and `server-personas` projects. Migration issue #20 stages the
synthetic IAM private-boundary proof under
`verification/fixtures/iam-private-boundary/`. That fixture source domain does
not transfer authority until its migration PR is merged and the cutover is
explicitly recorded. Real private environment inputs remain outside this
repository.

Normal development after the initial bootstrap commit follows:

```text
issue -> branch -> PR -> CI -> review -> human squash merge
```

See `AGENTS.md` for repository instructions, `docs/adr/README.md` for the immutable accepted architecture sources governing migration, and `docs/history/pre-consolidation.md` for migration provenance.
