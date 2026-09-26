# ADR 0025: Build a trusted-snapshot successor

- **Status:** Accepted successor direction; documentation/specification only, not implemented
- **Date:** 2026-09-26
- **Contract:** [#206](https://github.com/packetlss/compliance/issues/206), including its [execution and interpretation note](https://github.com/packetlss/compliance/issues/206#issuecomment-5844713229)
- **Sequencing:** [Latest successor decision on #85](https://github.com/packetlss/compliance/issues/85#issuecomment-5844706143)
- **Baseline:** Implemented legacy at `8c4eae2459fffad57b771c7eec9984bbba37fc96` (PR #202)
- **Preserves:** All ten foundational responsibility/meaning invariants of [ADR 0023](0023-foundational-semantic-responsibility-boundaries.md)

## Context and decision

The product owner accepted a clean-slate policy-resolution and assessment
application. The current implementation supplies useful authored intent and
semantic edge cases, but its independently verifiable provenance, derivation replay
and experimental representations are not the successor's product contract.
Translating the Python modules, schemas or tests would carry those mechanisms into
the replacement without a current requirement.

Build fresh from the behavioral contract in the
[successor architecture](../SUCCESSOR_ARCHITECTURE.md). That document owns the target
responsibility model, persona and Objective safeguards, acceptance stories,
unresolved operating/value questions and bounded experiment specification. This ADR
owns the replacement decision, trust tradeoff, supersession and promotion gates.
The [system architecture](../ARCHITECTURE.md) routes the still-implemented legacy
contracts; they continue to govern legacy execution until explicit cutover.

Clean-slate replacement is the method; incremental, independently reviewed delivery
is the execution strategy. A single giant rewrite PR is neither required nor
authorized. Go with embedded OPA/Rego is a hypothesis to investigate, with a clean
Python design as comparator; neither the host language nor criterion engine is
selected for production.

## Deliberate trust reduction and retired guarantees

The successor trusts the planner, a controlled operation-local input set and
faithful external retention. It preserves the meaning of the recorded operation,
resolved intent and conclusions, without independently proving their derivation
from historical catalogs. Ordinary record IDs are references, not content identity,
immutability, authorship authentication or tamper evidence. Version, Git and source
metadata explain attribution; they do not attest what executed.

The following are **retired from the successor**, not removed from the current
runtime by this decision:

- JCS semantic provenance/identity chains; content-derived operation, member, plan
  and result IDs; mandatory actual-composition identity; direct expected-content
  enforcement and composition locks.
- Runtime tooling-source, wheel-receipt, installed-file and bytecode attestation,
  and evaluator-executable identity as assessment-publication prerequisites.
- Independent historical replay of policy derivation, ParameterPolicy ancestry or
  contribution assembly, and inventory selector/candidate-selection witnesses.
- `FrameworkObligationDeclaration` and framework-satisfaction interpretation,
  including governance-plus-assessment obligation aggregation. Framework mappings
  remain descriptive traceability; governance-only conclusions must not return as
  synthetic Objectives or assertion evidence.
- Additive parameter contributions, automatic set union from independent owners,
  multiple-parent policy inheritance, and generic override/merge/precedence machinery.
- Query-time qualification of old results against current plans, evidence age or
  waiver windows. Assessment-time freshness and waiver applicability remain;
  new operational conclusions require a fresh assessment.
- Automatic compatibility with experimental schemas, artifact layouts, digest
  algorithms, CLI grammar, test fixtures or release packaging.

This is a reduction of guarantees, not a serializer substitution. Structural and
relational checks still reject mismatched or conflicting supplied records, but
cannot establish original authorship or detect every coordinated alteration of
otherwise consistent records. A stable input set must be established before
loading; merely ceasing to read files after loading is insufficient. The mechanism
is an [open decision](../SUCCESSOR_ARCHITECTURE.md#unresolved-decision-questions),
not an implicit new provenance lock.

Ordinary software-delivery integrity, dependency pinning, exact-head review and
suitable testing remain necessary. Commodity libraries and ordinary internal
checksums are permitted; they must not silently restore a retired application
feature or become a second semantic owner. No residual legacy machinery means no
inherited runtime dependency, compatibility burden or retired feature without a
current requirement. It does not demand reinvention or equivalence of two runtimes.

## Compact supersession map

This map applies to the successor direction only. Earlier ADRs keep their historical
rationale and authority for the implemented legacy behavior. Linked target sections
own successor details; this table does not freeze replacement representations.

| Decision | Retained responsibility | Successor replacement | Legacy-only mechanism |
| --- | --- | --- | --- |
| [0005](0005-content-addressed-development-boundaries.md) / [0007](0007-unified-actual-and-expected-composition-provenance.md) | Independent named sources, no order precedence, external-adapter handoff, historical meaning | Trusted resolved snapshots and ordinary references | JCS/content-addressed chains, composition enforcement, tooling/evaluator attestation, v4 wires |
| [0010](0010-required-evidence-status-and-assessment-refusal.md) / [0011](0011-historical-assessment-and-operational-evidence-timeliness.md) | Required-evidence qualification at assessment time; attributable outcomes/refusal; immutable history | Retained explanation of the original assessment; fresh assessment for new conclusions | Current-plan alignment, query-time evidence/waiver qualification, digest-bound selection representation |
| [0012](0012-explicit-policy-parameter-resolution.md) / [0020](0020-governed-policy-composition-without-sealing.md) / [0024](0024-objective-assurance-and-parameter-policy.md), parameters | Governed explicit values, typed direct consumption, policy-owned freshness, no sealing or precedence | [Complete values and single-parent tailoring](../SUCCESSOR_ARCHITECTURE.md#persona-tailoring-and-parameters) | Contributions/union, multiple parents, content pins/fingerprints and independent ancestry reconstruction |
| [0016](0016-closed-world-policy-assessment.md) / [0024](0024-objective-assurance-and-parameter-policy.md), assurance | Closed-world scope, exactly-one complete realization, every Check required, implementation gaps, conservative demonstration | [Complete Objective assurance](../SUCCESSOR_ARCHITECTURE.md#complete-objective-assurance) and recorded required slots | Selector/candidate witnesses, content-derived operation/member identity and frozen representation |
| [0017](0017-source-authored-policy-and-check-meaning.md) / [0018](0018-durable-assessment-explanation-facts.md) | Authored meaning, effective context, exclusions/deviations, evidence-use and safe failure explanations | [Plan/result fact ownership](../SUCCESSOR_ARCHITECTURE.md#responsibility-and-record-ownership); minimal retained evidence remains open | Identity-bearing explanation projections and complete snapshot-descriptor/diagnostic layout |
| [0019](0019-typed-identifier-namespaces-and-schema-uri-ownership.md) | Unambiguous typed references, schema qualification, fail-closed conflicts; names grant no authority | Explicit authoring/value and ordinary record admission contracts to be promoted | Current lexical/schema-URI/version layout and digest-pinned exact interfaces as automatic successor requirements |
| [0021](0021-project-governed-framework-obligation-declarations.md) / [0022](0022-criterion-ownership-and-external-judgment-retirement.md) | Criterion ownership is the first assessment admission gate; external/non-core determinations stay with Governance | Descriptive mappings only; no replacement framework-accounting owner | Framework declaration, obligation ledger, satisfaction categories and governance/assessment aggregation |
| [0023](0023-foundational-semantic-responsibility-boundaries.md) | All ten frozen responsibility/meaning invariants | Fresh implementation and evidence of those invariants | Its executable-owner paths and earlier roadmap sequence are not successor implementation requirements |

ADR 0023 is not blanket-superseded. In particular, retiring current qualification
does not weaken immutable historical meaning: its invariant 10 permits a separate
qualification if provided, but does not require that feature. Retiring framework
accounting does not transfer Governance's criterion authority into Assessment.

## Repository and compatibility decision

Keep `packetlss/compliance` as the authority repository: a new repository would add
an ownership split without improving this non-sensitive development boundary.
[Repository strategy](../REPOSITORIES.md#successor-repository-strategy) owns the blank
tree, isolation, legacy preservation and eventual single-implementation cutover.
An internal staging directory is not a private-data boundary.

There is no automatic old/new compatibility contract. Historical artifacts retain
their meaning with historical tooling. No permanent legacy subsystem,
strict-provenance mode, old/new switch, dual artifact reader or automatic conversion
layer is authorized. [Contract maturity](../CONTRACT_MATURITY.md) distinguishes this
accepted direction from implemented experimental legacy behavior and undecided
successor representations.

## Staged promotion gates

[Roadmap #85](https://github.com/packetlss/compliance/issues/85#issuecomment-5844706143)
owns active sequencing and backlog disposition. Its prior consolidation/freeze
sequence is superseded; #203/#204/#205 are paused, and #154/#182 are deferred
legacy-only work. Neither pause nor deferral means completion, transfer of scope
or permission to discard unmerged work.

1. **Documentation/specification:** #206 promotes this ADR, target stories,
   experiment specification and authority/maturity routing. Complete repository and
   documentation validation, exact-head CI and fresh-context review. Human
   architecture review and merge precede the next stage.
2. **Separately promoted bounded experiment:** a durable contract authorizes only
   the [specified investigation](../SUCCESSOR_ARCHITECTURE.md#bounded-platform-experiment-specification).
   Compare designs first, then prototype the leading candidate. Report exact
   revision, commands, observations, failures, risks and a promotion recommendation.
3. **Platform and operating-contract decisions:** explicitly promote production
   choices, including answers to the four open decision questions, before production
   code depends on them. Prototype choices and successful demonstrations do not
   constitute acceptance or a library/version freeze.
4. **Fresh incremental implementation:** authorize bounded slices against the
   behavioral portfolio, with one semantic owner and independent review per slice.
   Legacy schemas, modules, tests and output counts are not a translation backlog.
5. **Operator acceptance and explicit legacy cutover:** establish replacement
   behavioral/platform evidence and a separately reviewed migration of runtime,
   packaging, instructions and required CI responsibilities. Preserve historical
   access before retiring the old implementation. Human retains final authority.

#206 authorizes no executable experiment, production framework skeleton, code/schema
port, workflow or packaging change, new repository, release/tag, history rewrite or
legacy deletion. Existing four CI contexts and exact-head/current-base review rules
remain in force under [Development Workflow](../DEVELOPMENT_WORKFLOW.md). Any future
context replacement requires a bounded migration with replacement evidence.

Do not repeat comprehensive exploration as an automatic prerequisite or reopen the
accepted product direction because representation remains unresolved. Escalate a
changed semantic owner, weakened retained outcome/accounting/private-data boundary,
new shared abstraction or service/store, material scope expansion, contradiction of
the charter, or routing that cannot be made coherent without runtime/workflow
changes. Resolve that ambiguity in durable architecture before dependent work.
