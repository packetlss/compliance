# ADR 0023: Freeze foundational semantic responsibility boundaries

- **Status:** Accepted
- **Date:** 2026-09-20
- **Exploration and promotion contract:** [#175](https://github.com/packetlss/compliance/issues/175)
- **Scope:** Semantic responsibility and meaning only; representations remain experimental

## Context

The implemented core has repeatedly exercised the same responsibility model through
focused tests, composed scenarios and operator walkthroughs:

```text
Governed Inventory + Governed Policy
          -> deterministic resolved technical intent
          -> descriptive Evidence
          -> Assessment

Inventory -> Coverage -> Assessment
```

The individual contracts that currently carry this model remain development
contracts. Their schemas, identifiers, digests, CLI JSON and other wire details may
still need to change as the product and developer interfaces are exercised. Treating
that representational freedom as semantic uncertainty, however, would permit a future
implementation to move authority between domains or weaken established claim and
failure boundaries without an explicit architecture decision.

Issue #175 therefore reviewed only the responsibility and meaning layer. This ADR
records the first selective semantic freeze. It does not freeze the current
implementation shape.

## Decision

### Frozen foundational invariants

A semantically compatible implementation must preserve all ten invariants below.

1. **Governed Inventory supplies subject facts.** Normalized Governed Inventory is
   the authoritative source of the supplied subject identity and governed subject
   facts consumed by resolution. Operation selection may select subjects from those
   supplied facts, and Governed Policy may interpret those facts for applicability,
   but neither may independently invent, replace or correct them. Governed Inventory
   is not by itself the owner of operation selection, assessment scope or policy
   applicability.

2. **Governed Policy supplies intent and criteria.** Governed Policy owns desired
   technical intent, the policy consequences of applicability, complete assessment
   criteria and direct technical policy. Resolution interprets Governed Inventory
   through that policy; evidence and assessment do not choose or amend it.

3. **Coverage is a current explanation.** Coverage is the deterministic, current and
   ephemeral explanation of the assessment scope expected from the supplied Governed
   Inventory and Governed Policy through the resolver. It is not an assessment input,
   durable artifact, identity, snapshot, historical result or alternate resolver.

4. **Evidence is descriptive observation.** Evidence represents attributable
   observations about reality. It does not choose Governed Policy or a realization,
   correct Governed Inventory, or encode another domain's normative conclusion as an
   assessment result.

5. **Criterion ownership is the first assessment admission gate.** An
   `AssessmentResult` is admissible only when Governed Policy owns the complete
   normative criterion and Assessment evaluates it from Control-unaware descriptive
   observations. Governance retains reviewed external and other non-core
   determinations. This freezes the substantive boundary of
   [ADR 0022](0022-criterion-ownership-and-external-judgment-retirement.md), using
   `Governed Policy` as the durable domain owner rather than freezing earlier wording.

6. **Assessment owns deterministic evaluation.** Assessment deterministically
   evaluates resolved Governed Policy against qualifying Evidence and owns the
   attributable result. It does not re-resolve policy, select an operation or
   realization, repair inventory facts, or treat authored adoption/implementation
   state as observed implementation evidence.

7. **Outcome and refusal meanings are stable.** The meanings below are frozen.
   Current spellings, containers and aggregation representations are not.

   | Meaning | Semantic commitment |
   | --- | --- |
   | **PASS** | Qualifying admissible evidence establishes that the resolved criterion is satisfied. |
   | **FAIL** | Qualifying admissible evidence establishes that the resolved criterion is not satisfied. |
   | **UNKNOWN** | Criterion truth cannot be established from admissible evidence, but that lack of determination can be safely attributed and explained. |
   | **ERROR** | Criterion execution or decision interpretation failed, while trusted orchestration can still construct a trustworthy attributable result. |
   | **WAIVED** | An underlying FAIL is covered by an applicable explicit waiver at the assessment instant. It remains distinguishable from PASS and does not establish criterion satisfaction. |
   | **Refusal** | The shared prerequisites needed to construct and publish a trustworthy attributable result cannot be established; no assessment result is published. |

   Existing concrete refusal causes remain examples and executable owners of this
   boundary, not an exhaustive compatibility-frozen taxonomy. This ADR does not freeze
   a general outcome aggregation ordering, Requirement/Realization roll-up semantics,
   applicability/N/A semantics, or any status wire vocabulary beyond the meanings
   above.

8. **Direct technical policy needs no synthetic objective.** Complete direct
   technical policy is valid and assessable without synthesizing an Objective or a
   Requirement/Realization wrapper.

9. **Closed-world claims stay bounded to supplied inputs.** Deterministic resolution,
   accounting and results make claims only about their exact supplied inputs and
   governed scope. They do not establish external inventory or population
   completeness, external legal or framework applicability, conformity,
   certification, recognition, governance sufficiency, continuous effectiveness or
   upstream truth.

10. **Historical results keep exact historical meaning.** A published result remains
    an immutable conclusion attributable to the exact assessed operation and resolved
    plan meaning. Later inventory, policy, evidence, declaration or clock state does
    not mutate it into a latest/current-state record or cause current re-resolution to
    reinterpret it. Any current qualification is a separate derived interpretation.

### Semantic compatibility and evolution

These invariants define semantic compatibility independently of representation. A
future implementation may change schemas, resource shapes, identifiers, identity
algorithms, artifact layouts, command grammar or presentation surfaces while
remaining semantically compatible if it preserves every responsibility and meaning
above.

Moving an owner, weakening a boundary, changing one of the frozen meanings or making
a previously bounded claim unbounded is a semantic incompatibility. It requires an
explicit reviewed successor architecture decision and a deliberate compatibility and
migration decision; it cannot be introduced as an in-place refactor or incidental
wire migration.

Conversely, the semantic freeze does not require current readers to accept
superseded experimental representations. Until a representation is separately
frozen, a coordinated reviewed migration may replace it in place, and historical
artifacts retain their original meaning under their historical tooling.

### Executable owners

The current representations are not normative for this ADR, but the following tests
independently exercise the frozen responsibilities. Successor implementations may
replace these tests only with equivalent executable ownership.

| Invariant | Current executable owners |
| --- | --- |
| Governed Inventory supplies subject facts | `tooling/tests/test_render_plan.py` (`test_resolution_consumed_inventory_change_produces_new_identity`, lifecycle and unassigned cases); `tooling/tests/test_operation.py` (selection-domain, direct/inherited membership and nonselected-candidate cases) |
| Governed Policy supplies intent and criteria | `tooling/tests/test_render_plan.py` (source-order independence, exact coalescence/conflict, overlapping-assignment and effective-policy cases); `tooling/tests/test_policy_parameters.py` |
| Coverage is a current explanation | `tooling/tests/test_operator_views.py` (`test_coverage_resolution_calls_existing_planner_in_asset_order`, additive-value/applicability and invalid-resolution cases) |
| Evidence is descriptive observation | `policy-sources/control-library/tests/test_policy_resources.py` producer-contract tests; `verification/scenarios/scripts/assert-semantic-anchors.py` IAM descriptive relationship cases |
| Criterion ownership is the first gate | `tooling/tests/test_framework.py` retired-basis admission cases; `verification/scenarios/scripts/assert-semantic-anchors.py` framework-governance and IAM relationship cases |
| Assessment owns deterministic evaluation | `tooling/tests/test_assessment_v4.py` selection, error and refusal cases; `tooling/tests/test_operation.py` exact operation accounting cases |
| Outcome and refusal meanings | `tooling/tests/test_assessment_v4.py` unknown/error/waiver/refusal cases; `tooling/tests/test_operator_views.py::test_assessment_refusal_is_bounded_and_publishes_no_result` |
| Direct technical policy needs no synthetic objective | `tooling/tests/test_operator_views.py::test_technical_only_explanation_has_checks_and_no_objective`; the technical-only canonical scenario in `verification/scenarios/scripts/assert-semantic-anchors.py` |
| Closed-world claims stay bounded | `tooling/tests/test_operation.py` missing-member, unassigned, empty/non-assessable selection and exact-accounting cases; canonical semantic anchors |
| Historical results keep exact meaning | `tooling/tests/test_operation.py` (`test_historical_accounting_does_not_reopen_policy_or_evidence`, different-plan, deleted-plan and waiver-qualification cases) |

## Preserved extension space and sequencing

This freeze deliberately preserves a product/developer-interface exploration space
for:

- schema discovery/catalog and validation surfaces;
- generated SDKs, types, builders and examples;
- collector conformance tooling;
- evidence-schema reorganization;
- derived machine-consumable read models; and
- a possible canonical semantic read-model layer shared by the CLI, a thin read-only
  web UI, visualization and integrations.

Such work must preserve one semantic interpretation. Raw `assessment-results/v4`
must not become a visualization API merely because it exists. Plan-owned policy
meaning must not be duplicated into authoritative results for dashboard convenience,
and a read model must not become a second semantic interpretation layer.

The intended roadmap sequence is:

```text
foundational semantic freeze
  -> product/developer-interface exploration
  -> bounded collector/read-model/browser falsification
  -> reassessment
  -> later selective identity/wire freeze work
```

This sequence supersedes any assumption that the next automatic step is a
source/evidence/resource identity freeze. It records ordering only: this ADR does not
design, promote or authorize any later phase.

## Explicit exclusions

This ADR does not freeze:

- any current schema, resource or artifact representation, field layout, identifier,
  schema URI, digest or identity algorithm;
- CLI grammar, machine-readable CLI JSON, presentation text or query/read-model wire;
- `assessment-plan/v4` or `assessment-results/v4` layout or provisional identity;
- Requirement/Realization representation, selection, parameters, additive-set form
  or roll-up/aggregation semantics;
- `FrameworkObligationDeclaration` representation, identity/digest or framework
  status/explanation wire;
- evidence organization, schema layout, catalog/discovery API, collector interface or
  current evidence-type identities;
- a general assessment outcome aggregation order or applicability/N/A redesign;
- storage, retention, monitoring, scheduling, remediation or browser/UI architecture;
  or
- Stage 11 or any other exact identity/wire commitment.

ADRs 0016, 0017, 0018 and 0021 and the current assessment v4,
Requirement/Realization and framework-declaration contracts remain experimental at
their representational layers. This decision does not relabel them wholesale.

## Consequences

Implementations and interfaces may now rely on the ten responsibility and meaning
invariants as durable architecture. Product and developer-interface exploration may
reshape how those semantics are discovered, validated and consumed without treating
the current wires as compatibility commitments.

Any finding that requires a different semantic owner, a weaker claim/failure
boundary, Requirement/Realization aggregation changes or a current wire freeze must
return to architecture before implementation.
