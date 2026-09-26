# ADR 0026: Minimal successor production architecture

- **Status:** Accepted production direction, not implemented; human architecture review and merge under #217 precede production work
- **Date:** 2026-09-26
- **Contract:** [#217](https://github.com/packetlss/compliance/issues/217), including its human simplification and branch-rule transition comments
- **Prerequisite:** #218 / human-merged #219 admits this documentation on `successor`
- **Evidence:** merged #209 [REPORT](../../successor/experiments/209-platform/REPORT.md) and [NOTES](../../successor/experiments/209-platform/NOTES.md), delivered by #216
- **Foundation:** [ADR 0025](0025-trusted-snapshot-successor.md) and [target behavior](../SUCCESSOR_ARCHITECTURE.md); all ten ADR 0023 invariants remain

## Decision and supersession

Go is the production host direction. Embedded OPA/Rego is acceptable only for
trusted authored criterion evaluation. This resolves ADR 0025's platform hypothesis
and four operating questions; it does not replace that ADR's trust reduction,
retired guarantees, legacy authority or compatibility decision. No language/library
version, production schema, CLI grammar or record layout is frozen here.

The #209 experiment established feasibility, including native macOS execution.
Its dependency footprint is accepted cost evidence, not a reason to add services
or management infrastructure. A second executable Python comparator is not required.
Production implementation is fresh: the prototype is disposable evidence, never
seed code or an imported runtime. Retain it until separately authorized deletion
after equivalent production acceptance coverage exists. Only separately reviewed
behavioral vectors, concrete regressions and useful isolation techniques may carry
forward; do not port its test suite.

## Evaluator boundary

The application owns applicability, policy resolution, evidence selection/schema
qualification/freshness, waivers, outcome interpretation, records and publication.
OPA receives admitted criterion modules, resolved values and qualified observation
facts; it owns criterion evaluation only. The boundary must constrain capabilities
so normal evaluation cannot acquire network, current clock, randomness or mutable
external state implicitly. Malformed decisions and attributable execution failures
are ERROR, inconclusive decisions are UNKNOWN, and failed shared prerequisites
refuse publication. Cancellation must preserve that attribution/refusal boundary.
Safe diagnostics must not expose arbitrary evaluator internals or private payloads.

There is **no hostile-policy sandbox guarantee**. Embedded evaluation shares the
host process and heap; cooperative cancellation is not hard memory/fault containment.
If hostile policy or hard per-criterion memory/fault isolation becomes a product
requirement, return to architecture for a focused process-boundary evaluation.
Do not prebuild a process framework, remote OPA, bundle management or plugins.

## Coherent input admission

Assessment consumes one coherent operation-owned snapshot spanning its required
inventory, policy, modules, schemas, parameters, evidence and waiver inputs. Input
coherence is an explicit environmental/admission precondition established before
resolution. The application owns admitted copies and does not reread mutable inputs
during assessment. Malformed input and observable mutation during acquisition
refuse admission; copying or rereading cannot prove coherence against all writers.
Externally frozen inputs or an atomic supplied envelope are possible environment
choices, not new product protocols. Neither `.admission.lock` nor any universal
advisory-lock or provenance-lock protocol is promoted.

## Retained explanation and ordinary records

Retain the minimum exact observation facts actually consumed, stable observation
identity, subject/collector/time attribution and sufficient qualification/selection
diagnostics to explain the original result, including why required evidence was
unusable. Collector identity alone cannot identify an observation. Do not retain
rejected payload bytes by default. Plan-owned intent, tailoring/exclusion reasons
and approvals remain in the plan; results own outcomes, evidence use and applied
waiver facts, including underlying FAIL. Minimize retained private data without
removing facts needed to explain the conclusion.

Records use ordinary opaque/random references with explicit operation, plan,
subject, required-slot and child membership. Structural and relational admission
fails closed on malformed, conflicting or foreign relationships, truncated required
children, conflicting waiver/observation identities across the supplied record,
and realization/Objective reference mismatch. Exact typed duplicates may coalesce;
divergent same-identity content must not win by order. Missing result slots remain
in the operation denominator and cannot establish complete success or inferred
refusal. A published reference must never silently rebind to conflicting content.
Only complete admitted records may be exposed as published; interrupted publication
must not make partial content admissible. No atomic fleet transaction is required.

IDs are not content identity, authentication or tamper evidence. Faithful retention
is trusted; relational checks cannot detect every coordinated consistent rewrite.
Publication mechanics are local choices behind these guarantees: the prototype's
hard-link/fsync procedure and exact-byte retry layout are not promoted.

Historical explanation reads supplied retained records only. It neither replays
derivation nor performs current-state lookup or query-time qualification. Missing
required retained facts make the dependent explanation unavailable; report the
missing material without repairing it from current inputs or inventing history.
Malformed/conflicting supplied records fail admission. There is no mandatory
evidence database, history service or replay engine. Fresh current conclusions
require fresh assessment.

## Narrow typed authoring contract

Initial production authoring uses **strict JSON only**. No YAML, aliases/tags,
implicit coercion or generic serialization/canonicalization framework is required.
These domain rules apply at admission and equality boundaries, independently of
host-language defaults; production schemas will name the actual fields separately.

| Boundary | Initial semantics |
| --- | --- |
| Objects | Reject duplicate member names after JSON escape decoding at every depth, including equal duplicates. Reject unknown members against the declared input shape. Member order is nonsemantic; whitespace/escape spelling does not create a different value. |
| Absence and null | Reject `null`. Required members must be present. An explicitly optional absent member is absence, never a default value, empty string or zero. |
| Numbers | Integer tokens only, in the inclusive range `-(2^53-1)` through `2^53-1`. Reject fractional and exponent spellings, overflow, non-JSON numbers and leading-zero forms. `-0` and `0` denote the same integer. Booleans are distinct from integers; no float rounding or string-to-number coercion. |
| Booleans | Only JSON `true` and `false`, with exact boolean equality. |
| Strings | Valid UTF-8 JSON strings decoding to Unicode scalar sequences; reject malformed UTF-8 and unpaired surrogate escapes. Equality is exact decoded sequence equality, without normalization, case folding or trimming. JSON escape spellings for the same sequence compare equal. Field-specific identity constraints may narrow strings explicitly. |
| Arrays | The parameter/value domain supports ordered string lists only: every element is a string, order and multiplicity matter, and an empty list is valid unless its field contract forbids it. No scalar/list coercion or automatic union. Structural collections must separately declare element types and membership constraints; source/file order never supplies precedence. |
| Timestamps | Explicit timestamp fields use UTC whole seconds, exactly `YYYY-MM-DDTHH:MM:SSZ`, years `0001`–`9999`, valid calendar date/time, seconds `00`–`59`. Reject offsets, fractions, leap seconds and invalid dates. Compare valid timestamps by instant; do not infer timestamps from ordinary strings or obtain an implicit current clock. |

The required value domain is only integer, boolean, string and ordered string-list,
plus explicit timestamps where needed. Equality is type-aware and recursive over
declared record shapes, not byte equality or content identity. No decimals, generic
nested parameter values or Unicode permutation test program is implied.

ParameterPolicy owns declarations and explicit complete values. Consumers must
agree with declared final interfaces, including technical and realization paths;
validate declarations and supplied values even when unconsumed. Preserve explicit
applicability, single-parent revision/expected inherited-state guards, target
existence and stale-authoring refusal. Complete replacements do not accumulate
contributions. There are no defaults, expressions, union engine, multiple-parent
inheritance or generic precedence framework. Revision labels/expected typed values
are authoring safeguards, not content pins. Do not promote the prototype decoder.

## Platform and acceptance

Linux is the initial supported packaged/offline production platform. Story 9 and
cutover require real packaged assessment and retained explanation outside checkout
on that supported platform, with no legacy runtime or normal-runtime network
dependency. Native macOS experiment evidence remains valid historical evidence;
macOS may work as developer convenience but is not a required package, release
promise or production CI gate without a future explicit product requirement.

## Production test selection

A durable production test must protect at least one frozen semantic responsibility
or outcome invariant, accepted behavioral/public contract, trust/admission/publication
boundary, or concrete regression violating one of those. Preserve guarantees rather
than prototype structure. Keep a small focused/unit/contract/E2E portfolio with
these behavioral vectors:

- persona selection and conflict; tailoring versus exclusion versus waiver;
- complete Objective realization, every required child and implementation gaps;
- ParameterPolicy ownership, type/interface agreement and stale authoring;
- missing, stale, schema-invalid and ambiguous evidence;
- real criterion PASS/FAIL/UNKNOWN/ERROR and shared-prerequisite refusal;
- operation denominator, foreign-slot refusal and conflicting record relationships;
- retained historical explanation and source-order/no-precedence behavior;
- #216 regressions: lost tailoring attribution, waiver identity conflict,
  record-wide observation identity conflict and realization/Objective mismatch;
- evaluator capability, error and cancellation boundaries, without a sandbox claim.

Do not require tests solely for prototype advisory locking, decoder internals,
Unicode permutations beyond the promoted string contract, hard-link/fsync mechanics,
experimental CLI/record layout, timing/benchmarks, redundant semantic permutations
or duplicate Linux/macOS E2E coverage. Rewrite admission/value/publication tests
against the promoted boundaries. The [workflow owner](../DEVELOPMENT_WORKFLOW.md#durable-production-successor-ci)
owns the three durable contexts and bounded first-slice CI migration.

## Production sequence and limits

After human merge, separately promote these bounded implementation contracts:

1. Fresh Go skeleton and one vertical assessment: strict admitted input boundary,
   embedded OPA criterion interface, one subject/Check, ordinary plan/result,
   retained explanation, Linux packaged/offline execution and durable successor CI
   migration. Resolve trusted-base path admission before adding production files.
2. Persona tailoring and ParameterPolicy.
3. Complete Objective assurance.
4. Multi-subject operation completeness, evidence/waivers and publication admission.
5. User-facing Coverage, Policy Diff, thin CLI and infrastructure-adapter surface.
6. Operator acceptance and separately authorized exact-tree legacy cutover.

Each slice must stay smaller than the experiment and delete temporary scaffolding
when its purpose ends. Do not accumulate a parallel prototype and production suite.
Production gains no generic canonicalization/serialization framework, JCS or
content-addressed semantic identity, composition/provenance lock, universal advisory
lock, history database/service, replay engine, compatibility reader/dual runtime,
OPA bundle/remote management/plugin infrastructure, Objective theorem/equivalence
engine, generic CI impact framework or shared abstraction merely because the
experiment duplicated code.

#217 changes architecture/documentation/instructions only. It authorizes no Go
source, schema files, workflow/ruleset changes, prototype refactor, legacy deletion,
release or tag. Existing trusted-base scope and checks remain active for this PR.
A changed semantic owner, weakened trust/outcome boundary, new service/common
abstraction or material scope expansion requires durable architecture resolution
before dependent implementation. Representation details within these boundaries
belong to each small implementation contract, not a new comprehensive exploration.
