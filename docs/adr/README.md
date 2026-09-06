# Architecture decisions

`packetlss/compliance` owns current normative system architecture after the documentation-authority transfer coordinated by #29 / #39.

Accepted decisions:

- [ADR 0005 — Content-addressed development boundaries](0005-content-addressed-development-boundaries.md)
- [ADR 0006 — Regulatory assurance remains core; configuration adaptation is external](0006-regulatory-assurance-and-external-adapter-boundary.md)
- [ADR 0007 — Separate actual composition provenance from expected enforcement](0007-unified-actual-and-expected-composition-provenance.md)
- [ADR 0008 — Consolidate non-sensitive development in a private personal repository](0008-consolidated-private-development-repository.md)

ADRs 0005–0008 are normative restatements of the accepted decisions from the immutable final architecture snapshot:

`packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`

The historical workspace copies, issues, and PRs remain decision/migration provenance. The workspace commit is not semantic runtime identity and is no longer an active architecture dependency after this transfer.

Accepted destination decisions:

- [ADR 0009 — Converge active compliance vocabulary](0009-active-compliance-vocabulary.md)
- [ADR 0010 — Required evidence, attributable errors, and assessment refusal](0010-required-evidence-status-and-assessment-refusal.md) — accepted and implemented; runtime implementation in #32, promotions #61 (invalid evidence) and #62 (evidence selection ambiguity), and required-only simplification in #84.

- [ADR 0011 — Separate historical assessment outcomes from operational evidence timeliness](0011-historical-assessment-and-operational-evidence-timeliness.md) — accepted and implemented for v4 historical operation reporting; promotion #66, factual v4 representation in #32, and operational view in #80.
- [ADR 0012 — Explicit policy-parameter resolution and policy-owned evidence freshness](0012-explicit-policy-parameter-resolution.md) — experimental, implemented under #73; promotion under #37, coordinated runtime/schema/consumer migration in [#73](https://github.com/packetlss/compliance/issues/73).

- [ADR 0013 — Scoped assurance, population completeness, and obligation instances](0013-scoped-assurance-and-obligation-instances.md) — superseded by [ADR 0016](0016-closed-world-policy-assessment.md); historical design.
- [ADR 0014 — Attributable applicability determinations and authority acceptance](0014-attributable-applicability-and-authority-acceptance.md) — superseded by [ADR 0016](0016-closed-world-policy-assessment.md); historical design.
- [ADR 0015 — Bounded external claims and explicit assurance recognition](0015-bounded-external-claims-and-assurance-recognition.md) — superseded by [ADR 0016](0016-closed-world-policy-assessment.md); historical design.

- [ADR 0016 — Closed-world company policy assessment](0016-closed-world-policy-assessment.md) — experimental, implemented under #78; supersedes ADRs 0013–0015 and clarifies ADR 0006; #37. ADR 0012 remains unchanged.

Current system-level documents:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../REPOSITORIES.md`](../REPOSITORIES.md)
- [`../DEVELOPMENT_WORKFLOW.md`](../DEVELOPMENT_WORKFLOW.md)
- [`../CONTRACT_MATURITY.md`](../CONTRACT_MATURITY.md)

ADR 0007 foundation/cutover issues #31–#36 and ADR 0012 implementation #73 are
completed history. [#37](https://github.com/packetlss/compliance/issues/37) remains
open for residual architecture and escalation. ADR 0016 supersedes the three-ADR
migration; #78 implements its bounded embedded operation accounting and ordinary
typed assertion successor. Direct result consumption, new semantics or common
abstractions require separate architecture review.

Do not treat historical workspace topology or issue numbers as current component/repository boundaries. Historical references remain provenance links only.
