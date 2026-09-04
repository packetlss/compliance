# Architecture decisions

`packetlss/compliance` owns current normative system architecture after the documentation-authority transfer coordinated by #29 / #39.

Accepted decisions:

- [ADR 0005 — Content-addressed development boundaries](0005-content-addressed-development-boundaries.md)
- [ADR 0006 — Regulatory assurance remains core; configuration adaptation is external](0006-regulatory-assurance-and-external-adapter-boundary.md)
- [ADR 0007 — Separate actual composition provenance from expected enforcement](0007-unified-actual-and-expected-composition-provenance.md)
- [ADR 0008 — Consolidate non-sensitive development in a private personal repository](0008-consolidated-private-development-repository.md)

These destination files are normative restatements of the accepted decisions from the immutable final architecture snapshot:

`packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`

The historical workspace copies, issues, and PRs remain decision/migration provenance. The workspace commit is not semantic runtime identity and is no longer an active architecture dependency after this transfer.

Current system-level documents:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../REPOSITORIES.md`](../REPOSITORIES.md)
- [`../DEVELOPMENT_WORKFLOW.md`](../DEVELOPMENT_WORKFLOW.md)
- [`../CONTRACT_MATURITY.md`](../CONTRACT_MATURITY.md)

Open accepted-design implementation/design successors are destination issues #31–#38. In particular, #31–#36 own ADR 0007 implementation/consumer migration and #37 owns detailed requirement/realization assurance semantics.

Do not treat historical workspace topology or issue numbers as current component/repository boundaries. Historical references remain provenance links only.