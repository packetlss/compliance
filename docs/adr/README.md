# Architecture decision sources during consolidation

System architecture remains normatively owned by `packetlss-labs/compliance-workspace` until the later documentation-authority cutover under migration coordinator `packetlss-labs/compliance-workspace#69`.

To avoid duplicating normative architecture during the transition, this repository links the accepted ADRs at the exact immutable workspace commit that followed ADR 0008 acceptance:

- workspace migration source: `193f0330cae7535409e526fc4de60d6343efadc9`
- [ADR 0005 — Content-addressed development boundaries](https://github.com/packetlss-labs/compliance-workspace/blob/193f0330cae7535409e526fc4de60d6343efadc9/docs/adr/0005-content-addressed-development-boundaries.md)
- [ADR 0006 — Regulatory assurance remains core; configuration adaptation is external](https://github.com/packetlss-labs/compliance-workspace/blob/193f0330cae7535409e526fc4de60d6343efadc9/docs/adr/0006-regulatory-assurance-and-external-adapter-boundary.md)
- [ADR 0007 — Separate actual composition provenance from expected enforcement](https://github.com/packetlss-labs/compliance-workspace/blob/193f0330cae7535409e526fc4de60d6343efadc9/docs/adr/0007-unified-actual-and-expected-composition-provenance.md)
- [ADR 0008 — Consolidate non-sensitive development in a private personal repository](https://github.com/packetlss-labs/compliance-workspace/blob/193f0330cae7535409e526fc4de60d6343efadc9/docs/adr/0008-consolidated-private-development-repository.md)

These links are migration/design provenance. The workspace Git commit is not semantic runtime identity. When documentation authority is explicitly transferred to this repository, the owning migration issue must move or restate the normative artifacts deliberately and update this index rather than leaving two active authorities.
