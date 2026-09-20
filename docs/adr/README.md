# Architecture decisions

[System architecture](../ARCHITECTURE.md) explains what Compliance is now.
[Contract maturity](../CONTRACT_MATURITY.md) defines freeze and compatibility status;
[Repositories](../REPOSITORIES.md) and [Development Workflow](../DEVELOPMENT_WORKFLOW.md)
define ownership and engineering practice. ADRs preserve significant decisions,
rationale and explicit supersession history. Their implementation chronology does
not supply active scope; use current GitHub implementation contracts for that.

## Accepted decisions

- [ADR 0005 — Content-addressed development boundaries](0005-content-addressed-development-boundaries.md)
- [ADR 0006 — Regulatory assurance remains core; configuration adaptation is external](0006-regulatory-assurance-and-external-adapter-boundary.md)
- [ADR 0007 — Separate actual composition provenance from expected enforcement](0007-unified-actual-and-expected-composition-provenance.md)
- [ADR 0008 — Consolidate non-sensitive development in a private personal repository](0008-consolidated-private-development-repository.md)
- [ADR 0009 — Converge active compliance vocabulary](0009-active-compliance-vocabulary.md)
- [ADR 0010 — Required evidence, attributable errors, and assessment refusal](0010-required-evidence-status-and-assessment-refusal.md)
- [ADR 0011 — Separate historical assessment outcomes from operational evidence timeliness](0011-historical-assessment-and-operational-evidence-timeliness.md)
- [ADR 0012 — Explicit policy-parameter resolution and policy-owned evidence freshness](0012-explicit-policy-parameter-resolution.md) — parameter ownership/representation partially superseded by ADR 0024; runtime cutover pending.
- [ADR 0016 — Closed-world company policy assessment](0016-closed-world-policy-assessment.md) — supersedes ADRs 0013–0015; bounded closed-world assessment. Implementation-absence representation superseded by ADR 0024 Tranche A, implemented under #199.
- [ADR 0017 — Author policy and technical-check meaning on canonical source objects](0017-source-authored-policy-and-check-meaning.md)
- [ADR 0018 — Retain minimal durable assessment explanation facts](0018-durable-assessment-explanation-facts.md)
- [ADR 0019 — Typed identifier namespaces and schema URI ownership](0019-typed-identifier-namespaces-and-schema-uri-ownership.md)
- [ADR 0020 — Governed policy composition without sealing](0020-governed-policy-composition-without-sealing.md) — amends ADR 0012 composition/sealing and ADR 0019 pre-freeze schema evolution.
- [ADR 0021 — Project-governed framework obligation declarations and bounded satisfaction](0021-project-governed-framework-obligation-declarations.md) — framework governance and satisfaction; its external-judgment category is superseded by ADR 0022.
- [ADR 0022 — Criterion ownership is the first assessment admission gate](0022-criterion-ownership-and-external-judgment-retirement.md) — criterion ownership; current runtime excludes external-judgment and conclusion-producing assertion families.
- [ADR 0023 — Freeze foundational semantic responsibility boundaries](0023-foundational-semantic-responsibility-boundaries.md) — freezes foundational semantic responsibilities only; representations remain experimental.
- [ADR 0024 — Separate Objective assurance from governed parameter policy](0024-objective-assurance-and-parameter-policy.md) — accepted design under [#192](https://github.com/packetlss/compliance/issues/192); Tranche A implemented under #199, Tranche B pending. Partially supersedes ADRs 0012 and 0016 while preserving every ADR 0023 frozen invariant; separates implementation gaps from Assessment outcomes and explicitly assigned ParameterPolicy from Objective grouping.

## Superseded decisions

- [ADR 0013 — Scoped assurance, population completeness, and obligation instances](0013-scoped-assurance-and-obligation-instances.md) — superseded by ADR 0016.
- [ADR 0014 — Attributable applicability determinations and authority acceptance](0014-attributable-applicability-and-authority-acceptance.md) — superseded by ADR 0016.
- [ADR 0015 — Bounded external claims and explicit assurance recognition](0015-bounded-external-claims-and-assurance-recognition.md) — superseded by ADR 0016.

## Historical provenance

ADRs 0005–0008 restate decisions from the immutable final architecture snapshot
`packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`.
That snapshot and archived issues/PRs are rationale and migration provenance, not
active architecture dependencies, runtime identity or repository boundaries.
Historical artifacts retain their original meaning under their historical tooling.
