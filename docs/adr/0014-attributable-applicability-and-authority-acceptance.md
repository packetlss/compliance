# ADR 0014: Attributable applicability determinations and authority acceptance

- **Status:** Superseded by [ADR 0016](0016-closed-world-policy-assessment.md)
- **Superseded:** 2026-09-06
- **Date:** 2026-09-05
- **Parent and promotion contract:** [#37](https://github.com/packetlss/compliance/issues/37)
- **Coordinated decisions:** [ADR 0013](0013-scoped-assurance-and-obligation-instances.md), [ADR 0015](0015-bounded-external-claims-and-assurance-recognition.md)

This decision is historical. [ADR 0016](0016-closed-world-policy-assessment.md) replaces its core
responsibilities, conformance obligations and migration routing. Only semantics
explicitly retained by that successor remain active; this text does not authorize
implementation of external completeness, applicability authority or recognition.

## Context

Applicability decides which obligations govern an exact scope. Satisfaction asks
whether the applicable obligations are demonstrated. A source's asserted label,
a content digest or an approval reference cannot answer both questions.
[ADR 0012](0012-explicit-policy-parameter-resolution.md) deliberately leaves
external authority outside parameter binding. This decision accepts a narrow
consumption contract for applicability authority, without turning the core into
a governance or reviewer-authorization system.

## Decision

```text
attributable fact/determination
    + accepted applicability basis
    -> applicability decision
    -> exact applicable obligation instances
```

Applicability and satisfaction are strictly distinct. Determining that an entity
is governed by an obligation creates no evidence that it meets that obligation.
Determining external applicability does not automatically assign or adopt
company policy. Missing company interpretation remains a visible gap in
[ADR 0015](0015-bounded-external-claims-and-assurance-recognition.md) accounting.
[ADR 0013](0013-scoped-assurance-and-obligation-instances.md) governs exact scope,
quantification and instance formation, never a requirements-by-members product.

### Minimum semantic obligations

For every consumed determination preserve:

| Fact | Required attribution |
| --- | --- |
| Assertion identity | Exact assertion, revision and content identity; identify the exact assertion within a multi-assertion document, not just the document |
| Origin | Issuer/source identity and provenance |
| Meaning | Exact scope and quantification, with the source-owned asserted vocabulary/schema |
| Time and conditions | Relevant effective/validity interval and conditions, evaluated for the bounded claim's `t` |
| Acceptance | Pinned acceptance basis explaining why this issuer/assertion is accepted for this destination, purpose, scope and conditions |
| Consumption | Exact consuming applicability decision and resulting obligation references/instances |
| Explanation | Rationale, conflicts, rejected candidates and unresolved conditions where applicable |

Retain exact attribution to the normalized assertion and, where relevant, exact
source-artifact byte/content identity. This does not require a generic attachment
artifact family. Document identity alone is insufficient when different
assertions in the same document concern different scopes or conditions.

Source-owned terms keep their asserted vocabulary/schema; do not impose a
universal classification enum. The core consumes the exact accepted basis and
its attributable decision, not an inferred translation from a familiar label.
No generic rules engine, expression language or organizational IAM is introduced.

### Authority acceptance is a narrow input boundary

The core consumes an exact governance/policy decision saying which authority or
assertion is accepted for which purpose, destination, scope and conditions. That
pinned acceptance basis is itself an explicit semantic input, not a conclusion
inferred from where a file was found. Its exact identity and relationship to the
consumed assertion must remain explainable and immutable.

Content digests, repository/source names, `issuer` labels, `approval_ref` and
signatures by themselves do not establish semantic authority. A signature may
identify signed content without establishing that its signer has authority for
this purpose. Recording an approval reference does not verify reviewer powers.
The core does not acquire a generic reviewer-authorization verifier or authority
delegation graph. Governance establishes the acceptance decision outside that
narrow consumption boundary; the core preserves and checks its exact applicable
meaning, scope and conditions.

The same source may be accepted for one purpose or beneficiary and not another.
No source, issuer, file, order, location, specificity or organizational title
creates implicit precedence. Content-addressed provenance proves consumed
content, not truth or external authority.

### Accumulation, contradiction and N/A

Compatible determinations may accumulate obligations. Contradictory overlapping
determinations remain unresolved unless an exact accepted replacement or
supersession relationship is itself established. A later date, more specific
scope, preferred issuer, signature or matching name is not automatic supersession.
Retain the conflicting/rejected candidates and the accepted relation when one
exists; do not silently choose a winner.

Missing, expired, narrower or unavailable applicability authority does not
establish N/A. An attributable accepted determination may establish that no
obligation is applicable for an exact target under its conditions; absence of
such a basis cannot. N/A concerns exact applicability, not satisfaction, waiver
or a mechanism to hide a missing interpretation/realization. A legitimate
zero-applicable result cannot create a positive conformity/certification claim
from an empty denominator under ADR 0015.

### Failure and evidence boundaries

Safely attributable inability to establish an applicability decision means the
bounded claim is not established. Independently valid technical/objective
assessment remains publishable where its own plan is valid. This is not evidence
`unknown`, nor automatically an assessment-wide refusal.

After a valid dependency is resolved, evidence insufficiency uses
[ADR 0010](0010-required-evidence-status-and-assessment-refusal.md). Shared plan,
routing, composition/provenance, snapshot, evaluator or result-envelope integrity
failures that prevent trustworthy publication require ADR 0010 refusal. Required
unresolved policy retains ADR 0012's non-assessable boundary. See
[ADR 0013's failure matrix](0013-scoped-assurance-and-obligation-instances.md#preserve-existing-assessment-boundaries).
An authority problem cannot bypass either policy resolution or shared integrity.

## Conceptual conformance vectors

| Case | Expected conclusion |
| --- | --- |
| Exact accepted assertion says entity E belongs to source-defined category X during an interval containing `t`; accepted basis associates X with obligation O | Applicable instance O/E with complete decision attribution; satisfaction still requires the appropriate company interpretation/design/evidence |
| Same document also asserts category Y for subsidiary S | Consuming E's assertion cannot silently consume S's; identify each assertion exactly |
| Two accepted compatible determinations impose O1 and O2 on E | Both applicable instances retained; no issuer precedence |
| Accepted assertions contradict over E and `t` with no accepted replacement relation | Applicability unresolved and bounded claim unestablished, even if mapped technical checks pass |
| Exact accepted supersession identifies old and replacement assertions and applies to E at `t` | Apply that relationship and retain old/rejected attribution; do not infer a general latest-wins rule |
| Authority expired before `t`, cannot be acquired, or covers only E's subsidiary | Cannot establish E's N/A; narrower scope never expands |
| Signed assertion or content-addressed source supplies a recognizable `issuer` but no applicable acceptance decision | Semantic authority not established; signature/digest alone is insufficient |
| Valid accepted applicability excludes O for exact E/target/`t` with rationale and conditions | O may be accounted as not applicable; this is neither evidence of satisfaction nor a waiver |
| All target obligations are legitimately determined not applicable | Report exactly that determination; no vacuous positive certification/conformity |
| Required integration evidence is absent after valid scoped dependency resolution | Evidence insufficiency under ADR 0010; distinguish this from missing applicability authority |

## Migration and ownership

| Surface | Current foundation | Successor obligation |
| --- | --- | --- |
| Policy/requirement external references | Mapping and company intent; governance metadata without implicit authorization | Exact attributable applicability and acceptance inputs, preserving company policy independence |
| Tooling applicability/planning | Current experimental assignment and assurance behavior | Bind exact assertion, source-owned meaning, acceptance, `t`, consuming decision and resulting instances without a generic engine |
| Plan/results/provenance/explanation | Content-addressed composition and attributable results | Preserve consumed and rejected/conflicting facts, relevant source bytes, acceptance pins and unresolved conditions with integrity validation |
| Claim accounting | Existing mappings cannot prove authority or N/A | Expose unresolved applicability separately from evidence outcomes and interpretation/realization gaps |

No resource discriminator, wire spelling, artifact version, algorithm or generic
`Determination` abstraction is selected. Population bases, applicability
assertions and recognition rules have different semantic obligations despite
possible shared envelope fields. Runtime/schema/fixture changes wait for the
[coordinated post-#73 migration plan](0015-bounded-external-claims-and-assurance-recognition.md#coordinated-migration-and-remaining-architecture).

## Alternatives, consequences and validation

A universal classification vocabulary would replace source-owned meaning with
unreviewed translations. Implicit issuer priority or automatic supersession would
hide contradictions. A general authorization verifier would expand the trust
boundary beyond this decision. Explicit pinned acceptance costs authoring and
attribution work, but permits precise unresolved outcomes without false N/A.

Preserve exactly-one realization selection, existing conservative roll-up and
fail-only waivers, company-owned objectives, design-time realizations, immutable
history and ADR 0012 parameter identity/resolution/direct typed consumption.
This decision settles neither manual/procedural methodology nor sampling; those
remain architecture work under #37, not implementation-local choices.

Promotion uses the documentation checks, conceptual vectors, exact-head
independent review and four stable CI contexts specified in ADR 0013. Human
retains final squash merge authority. Generic delegation, automatic supersession,
dynamic expressions or inability to preserve immutable attribution requires a
return to architecture under ADR 0015's escalation route.
