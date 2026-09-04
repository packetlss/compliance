# Compliance

This private repository is the selected destination for consolidated non-sensitive compliance development under accepted `packetlss-labs/compliance-workspace` ADR 0008.

It is **not yet authoritative** for migrated component source. During the staged cutover coordinated by `packetlss-labs/compliance-workspace#69`, each existing `packetlss-labs/*` repository remains authoritative for its source domain until an explicit migration stage transfers that domain here.

The target development composition remains:

```text
tooling + N named policy sources + project inputs
```

Repository layout is not semantic identity. Tooling and policy-source content identities remain content-addressed, policy roots remain independently named and materialized, source/file order is nonsemantic, divergent same-identity definitions fail closed, and real private environment inputs remain outside this repository.

## Current phase

Only repository bootstrap documentation and migration provenance belong here until the bounded migration issues move executable source.

Normal development after the initial bootstrap commit follows:

```text
issue -> branch -> PR -> CI -> review -> human squash merge
```

See `AGENTS.md` for repository instructions, `docs/adr/README.md` for the immutable accepted architecture sources governing migration, and `docs/history/pre-consolidation.md` for migration provenance.
