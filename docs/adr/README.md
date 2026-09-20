# Architecture decisions

`packetlss/compliance` owns current normative system architecture after the documentation-authority transfer coordinated by #29 / #39.

Accepted decisions:

- [ADR 0005 — Content-addressed development boundaries](0005-content-addressed-development-boundaries.md)
- [ADR 0006 — Regulatory assurance remains core; configuration adaptation is external](0006-regulatory-assurance-and-external-adapter-boundary.md)
- [ADR 0007 — Separate actual composition provenance from expected enforcement](0007-unified-actual-and-expected-composition-provenance.md) — accepted; experimental result/plan ownership refinement implemented under [#90](https://github.com/packetlss/compliance/issues/90).
- [ADR 0008 — Consolidate non-sensitive development in a private personal repository](0008-consolidated-private-development-repository.md)

ADRs 0005–0008 are normative restatements of the accepted decisions from the immutable final architecture snapshot:

`packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`

The historical workspace copies, issues, and PRs remain decision/migration provenance. The workspace commit is not semantic runtime identity and is no longer an active architecture dependency after this transfer.

Accepted destination decisions:

- [ADR 0009 — Converge active compliance vocabulary](0009-active-compliance-vocabulary.md)
- [ADR 0010 — Required evidence, attributable errors, and assessment refusal](0010-required-evidence-status-and-assessment-refusal.md) — accepted and implemented; runtime implementation in #32, promotions #61 (invalid evidence) and #62 (evidence selection ambiguity), and required-only simplification in #84.

- [ADR 0011 — Separate historical assessment outcomes from operational evidence timeliness](0011-historical-assessment-and-operational-evidence-timeliness.md) — accepted and implemented for current v4 historical operation reporting; promotion #66, factual v4 representation in #32, operational view in #80, retention clarification #89, and exact plan/result refinement [#90](https://github.com/packetlss/compliance/issues/90).
- [ADR 0012 — Explicit policy-parameter resolution and policy-owned evidence freshness](0012-explicit-policy-parameter-resolution.md) — experimental, implemented under #73; promotion under #37, coordinated runtime/schema/consumer migration in [#73](https://github.com/packetlss/compliance/issues/73).

- [ADR 0013 — Scoped assurance, population completeness, and obligation instances](0013-scoped-assurance-and-obligation-instances.md) — superseded by [ADR 0016](0016-closed-world-policy-assessment.md); historical design.
- [ADR 0014 — Attributable applicability determinations and authority acceptance](0014-attributable-applicability-and-authority-acceptance.md) — superseded by [ADR 0016](0016-closed-world-policy-assessment.md); historical design.
- [ADR 0015 — Bounded external claims and explicit assurance recognition](0015-bounded-external-claims-and-assurance-recognition.md) — superseded by [ADR 0016](0016-closed-world-policy-assessment.md); historical design.

- [ADR 0016 — Closed-world company policy assessment](0016-closed-world-policy-assessment.md) — experimental, implemented under #78; supersedes ADRs 0013–0015 and clarifies ADR 0006. Its promotion history is #37; ADR 0024 subsequently supersedes implementation-absence representation.

- [ADR 0017 — Author policy and technical-check meaning on canonical source objects](0017-source-authored-policy-and-check-meaning.md) — accepted and implemented under #100; experimental, not frozen. Its architecture contract is #97.
- [ADR 0018 — Retain minimal durable assessment explanation facts](0018-durable-assessment-explanation-facts.md) — implemented under #102; experimental, not frozen. Its architecture contract is #98.

- [ADR 0019 — Typed identifier namespaces and schema URI ownership](0019-typed-identifier-namespaces-and-schema-uri-ownership.md) — implemented under #136; experimental, not frozen. Its architecture contract is #134 and exploration is #132.

- [ADR 0020 — Governed policy composition without sealing](0020-governed-policy-composition-without-sealing.md) — implemented under [#144](https://github.com/packetlss/compliance/issues/144). It amends ADR 0012's sealing/additive-set closure clauses and refines ADR 0019's pre-freeze schema-evolution rule.

- [ADR 0021 — Project-governed framework obligation declarations and bounded satisfaction](0021-project-governed-framework-obligation-declarations.md) — implemented by [#161](https://github.com/packetlss/compliance/issues/161), experimental, and not frozen. It introduces `FrameworkObligationDeclaration` as project-governance state outside policy sources and ordinary plans, plus an ephemeral three-state satisfaction projection over an exact declaration and exact retained assessment history.

- [ADR 0022 — Criterion ownership is the first assessment admission gate](0022-criterion-ownership-and-external-judgment-retirement.md) — accepted under [#167](https://github.com/packetlss/compliance/issues/167) and implemented by [#169](https://github.com/packetlss/compliance/issues/169). It requires a complete Governed Policy criterion and Control-unaware descriptive observations before an `AssessmentResult` is admissible; it retires the ADR 0021 `external-judgment` target architecture while preserving historical artifacts under their original tooling.

- [ADR 0023 — Freeze foundational semantic responsibility boundaries](0023-foundational-semantic-responsibility-boundaries.md) — accepted through [#175](https://github.com/packetlss/compliance/issues/175). It freezes ten responsibility and meaning invariants across Governed Inventory, Governed Policy, Coverage, descriptive Evidence, Assessment, outcome/refusal meaning, bounded claims and immutable history while leaving current wires, schemas, identifiers and detailed experimental representations unfrozen.

- [ADR 0024 — Separate Objective assurance from governed parameter policy](0024-objective-assurance-and-parameter-policy.md) — accepted design under [#192](https://github.com/packetlss/compliance/issues/192), not yet implemented. Partially supersedes ADRs 0012 and 0016 while preserving every ADR 0023 frozen invariant; separates implementation gaps from Assessment outcomes and explicitly assigned ParameterPolicy from Objective grouping.

Current system-level documents:

- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../REPOSITORIES.md`](../REPOSITORIES.md)
- [`../DEVELOPMENT_WORKFLOW.md`](../DEVELOPMENT_WORKFLOW.md)
- [`../CONTRACT_MATURITY.md`](../CONTRACT_MATURITY.md)

ADR 0007 foundation/cutover issues #31–#36, architecture issue
[#37](https://github.com/packetlss/compliance/issues/37), and ADR 0012
implementation #73 are completed history. ADR 0016 supersedes the three-ADR
migration; #78 implements its bounded embedded operation accounting and ordinary
typed assertion successor. Direct result consumption, new semantics or common
abstractions require a new focused architecture review.

Do not treat historical workspace topology or issue numbers as current component/repository boundaries. Historical references remain provenance links only.
