# Contract maturity and compatibility

Status: **Accepted successor direction alongside implemented experimental legacy**

Historical detailed audits remain in `packetlss-labs/compliance-workspace`; this file owns the active compatibility/freeze rules in this repository.

## Successor and legacy status

| Surface | Maturity and authority |
| --- | --- |
| Foundational responsibilities and outcome meanings | Frozen by [ADR 0023](adr/0023-foundational-semantic-responsibility-boundaries.md), retained by the successor. |
| Trusted-snapshot successor direction | Accepted design, not implemented. [Target architecture](SUCCESSOR_ARCHITECTURE.md) owns behavior and stories; [ADR 0025](adr/0025-trusted-snapshot-successor.md) owns trust reduction, retired guarantees and supersession. |
| Production platform and operating/value/retention contracts | [ADR 0026](adr/0026-minimal-successor-production-architecture.md) promotes Go, embedded OPA for trusted criteria, strict JSON/typed values, coherent admitted snapshots, minimal retained facts and ordinary records. Linux is the initial supported packaged platform. Accepted design, not production implementation or a wire/version freeze. |
| Development lane | #208 activation is recorded; foundation proves infrastructure only. [Workflow](DEVELOPMENT_WORKFLOW.md) separates current experiment/shared duties from the future production migration. |
| Platform experiment | #209 / #216 is merged disposable evidence, including Linux and native macOS. It is not production seed code or a test-port backlog; ADR 0026 owns reviewed carry-forward limits. |
| Existing Python tooling, schemas, identifiers, artifacts and interfaces | Implemented experimental legacy. Their detailed contracts below remain valid for that implementation, without automatic successor compatibility. |
| Guarantees retired from the successor | Still implemented where the legacy contracts require them; “retired from target” does not mean “removed from current runtime.” ADR 0025 enumerates them. |

The latest [#85 sequencing decision](https://github.com/packetlss/compliance/issues/85#issuecomment-5847393168)
supersedes the post-ADR-0024 consolidation/freeze sequence. No further identity/wire
freeze, completion of paused cleanup issues or comprehensive exploration is an
automatic prerequisite. Future compatibility commitments still require explicit
review; neither documentation acceptance nor a successful experiment creates one.

## Compatibility is explicit

The project is development-only and currently has no external compatibility consumers.

A version-like identifier, checked-in schema, generated artifact, Git tag, or historical Release does **not** by itself create a permanent public compatibility promise. Compatibility begins only through an explicit reviewed freeze recorded in durable architecture/release documentation.

Maturity terms:

- **Experimental** — expected to change; no compatibility promise.
- **Likely stable** — direction is sound but not frozen.
- **Compatibility candidate** — suitable for an explicit freeze review, but not yet frozen.
- **Design pass required** — semantic/naming/authority ambiguity remains.
- **Accepted design, not yet implemented** — architecture accepted; current runtime has not fully cut over.
- **Historical/removed** — retained only in historical source/releases, not current product surface.

Historical readability and recommended current use are separate concerns.

## Frozen semantic architecture

[ADR 0023](adr/0023-foundational-semantic-responsibility-boundaries.md) is the
first explicit compatibility freeze. It freezes only the responsibility and meaning
layer across Governed Inventory, Governed Policy, Coverage, descriptive Evidence and
Assessment:

- normalized Governed Inventory authoritatively supplies the subject identity and
  governed subject facts consumed by resolution, while operation selection and
  Governed Policy retain their separate selection and interpretation roles;
- Governed Policy owns desired technical intent, applicability consequences,
  complete criteria and direct technical policy;
- Coverage remains a deterministic current/ephemeral explanation, never an
  assessment input, artifact, identity, snapshot or historical result;
- Evidence remains descriptive observed reality and cannot select policy or encode
  another domain's conclusion;
- Governed Policy ownership of a complete criterion plus Control-unaware descriptive
  observations is the first admission gate for an `AssessmentResult`;
- Assessment owns deterministic evaluation of resolved policy against qualifying
  evidence;
- PASS, FAIL, UNKNOWN, ERROR, WAIVED and assessment refusal retain the meanings in
  ADR 0023, without freezing a general aggregation order;
- direct technical policy remains valid without a synthetic Objective;
- closed-world claims remain bounded to exact supplied inputs; and
- historical results retain their exact operation/plan meaning rather than becoming
  mutable latest-state records.

A semantically compatible successor must preserve those commitments even if it uses
different representations. Reassigning an owner, weakening a boundary or changing a
frozen meaning requires explicit successor architecture and a deliberate
compatibility/migration decision.

The legacy contracts below remain classified at their own representational maturity. In
particular, current schemas, identifiers, schema URIs, identity algorithms, CLI and
machine-readable views, assessment v4 wires, Requirement/Realization and framework-
declaration representations, evidence organization, and their aggregation/wire
details remain experimental unless separately frozen. A coordinated pre-wire
migration may replace those representations without a compatibility reader while
preserving ADR 0023 semantics and historical meaning under historical tooling.

## Implemented legacy experimental interfaces

The producer and derived-read interfaces are implemented and remain experimental.
The producer surface provides explicit-source discovery, canonical schema export,
ordinary typed document construction and standalone document validation. The
installed/no-Git collector exercise supports this minimal surface without generated
bindings or a producer framework. See the [producer contract](../tooling/docs/producer-interface.md).

Read consumers use purpose-specific validated projections with one narrowly shared,
non-persisted historical Assessment foundation. Inventory/Coverage, declaration-owned
Framework interpretation and Policy Diff retain independent owners. The external
browser renders derived responses without interpreting raw artifacts. Raw results
are not a visualization API; plan-owned meaning is not copied into authoritative
results. See the [read interface](../tooling/docs/cli.md#experimental-external-read-consumption).

The producer/read exercises and their joint reassessment are complete. They create
no additional freeze or compatibility commitment. Active scope and sequencing
belong to [roadmap #85](https://github.com/packetlss/compliance/issues/85) and its
latest superseding comments, as routed above. The former consolidation gate is no
longer the forward roadmap.

## Legacy identity-algorithm freeze lifecycle

These rules describe the legacy cryptographic contracts; they are not a successor
identity roadmap. ADR 0025 retires the application-level provenance chains.

For cryptographic identity algorithms:

1. pre-freeze identifiers are provisional development contracts;
2. unqualified `/v1` is reserved for the first explicitly frozen immutable version of an algorithm;
3. pre-freeze algorithms use development identifiers such as `/v1alpha1`;
4. pre-freeze digests/generated artifacts may be regenerated after reviewed semantic changes;
5. after `/v1` freeze, domain normalization, canonical byte representation, digest construction, inclusion/ordering rules, and normative vectors are immutable; and
6. an identity-affecting semantic change after freeze requires a new major algorithm identifier.

For semantic JSON digests, contract-specific domain normalization occurs before RFC 8785/JCS serialization. JCS defines canonical JSON bytes; it does not decide domain semantics such as array ordering or field inclusion.

Before freeze, technical `BaselineOverlay.spec.extends` is the bounded
exception: complete exact parent pins are an unordered set and are sorted by
their JCS bytes only for the technical overlay semantic projection. Technical
operations retain authored order. This clarification does not normalize other
arrays, `RequirementBaseline` inheritance, technology-neutral policy, or raw
source-tree identity.

Raw source-tree, executable, wheel/archive and other byte/path digest algorithms retain their own exact construction and do not use JCS merely because they are content-addressed.

## Implemented legacy core

The current core consists of:

- the `compliance` CLI/tooling;
- ordinary technical `Baseline` / `BaselineOverlay` assessment;
- optional requirement/realization objective assurance;
- arbitrary independently named/digested policy sources;
- inventory/groups/assignments;
- required typed evidence and pass/fail/unknown evaluation;
- waivers and policy diff;
- provenance-bearing assessment plans/results; and
- assessment plans as the external-adapter handoff.

Missing/inconclusive required evidence is `unknown`; authored implementation state is not evidence; source/file order is not precedence; divergent same-identity definitions fail.
Every declared evidence dependency is required and carries no optionality
discriminator. The typed envelope has no normative collector-supplied
`integrity.digest`; the unchanged complete-document and evidence-set digest
algorithms provide assessment snapshot identity.

In-core configuration intents/compiler/renderers/configuration artifact families/backend apply authority are removed and have no ADR 0007 successor.

## Implemented legacy experimental contracts

These contracts are implemented, but their representations are not frozen. The
[system architecture](ARCHITECTURE.md) states their current responsibilities;
component contracts below define local details without creating compatibility promises.

| Contract | Current scope and detailed authority |
| --- | --- |
| Configuration and provenance | `project-config/v1alpha3`, `composition-lock/v1alpha1`, `assessment-provenance/v1alpha1`, `assessment-plan/v4`, `assessment-results/v4`; provisional composition/lock/plan/result algorithms. [Composition](../tooling/docs/composition.md), [artifact provenance](../tooling/docs/artifact-provenance.md), ADR 0007. |
| Exact history and current qualification | Exact retained bound plan/result pairs, intrinsic and mandatory relational validation, immutable outcomes, separate alignment/timeliness/waiver qualification. No retention obligation or latest-state store. ADR 0011 and [artifact provenance](../tooling/docs/artifact-provenance.md). |
| Parameters and freshness | ParameterPolicy solely owns explicit pinned declarations, bindings, descendant tailoring and contributions, selected through separate `parameterPolicyRefs`; realization-owned and direct technical Checks own typed symbolic consumption links, including policy-owned effective `max_age`. Atomic values are the default; explicit string-only additive-set opt-in has one compatible declaration/base, canonical union and complete attribution. Fixed bases permit valid tailoring and independently applicable contributions; no sealing. ADRs 0012/0020/0024 and [policy parameters](../tooling/docs/policy-parameters.md). |
| Typed namespaces and schema URIs | Typed resource lookup, dot-separated kebab-case policy IDs, owner-local snake_case slots/properties and Evidence `/vN` dispatch. Control lookup uses stable ID with exact version/fingerprint metadata. Technical and RequirementBaseline assignment pins share fail-closed collision admission. No alias, precedence, network lookup or implicit normalization. ADR 0019. |
| Authored policy/check meaning | Required baseline titles and Control title/purpose are identity-bearing authored meaning, frozen into plans for offline interpretation and never executable inputs. ADR 0017. |
| Assessment explanation | Result-owned unsuccessful dependency dispositions and safe criterion-error codes; exact dependency joins to plan-owned meaning. No copied policy/check prose or combined explanation identity. ADR 0018. |
| Inventory and Evidence producers | Subject identity/labels supply governed facts; attributes remain adapter-specific. Typed Evidence uses the seven-field envelope and descriptive observation units. Schema-permitted extensions remain preserved and identity-bearing, but undeclared facts cannot become criterion inputs. [Producer interface](../tooling/docs/producer-interface.md), [artifact provenance](../tooling/docs/artifact-provenance.md). |
| Optional Requirement/Realization assurance | Exactly-one applicable realization, adoption, `based_on`, typed parameter links, complete required Check membership, distinct implementation gaps and evidence-derived roll-up remain experimental. No core realization classification enum; confidentiality is a source/acquisition/access/deployment boundary. [Control realization](../tooling/docs/control-realization.md). |
| Frozen operation representation | Embedded plan operation, `member_plan_digest`, selector-sensitive `operation_id`, operation-bound plan IDs and exact slot accounting. Complete accounting is separate from success; results reference their exact plan. ADR 0016 and [operation accounting](../tooling/docs/operation-accounting.md). |
| Framework declaration and satisfaction | Separate durable governance ledger with four basis categories and ephemeral `satisfied` / `not_satisfied` / `not_established` interpretation. Exact declaration, frozen scope anchor and required retained support; no declaration content in ordinary plans/results. ADRs 0021/0022 and [CLI](../tooling/docs/cli.md). |
| Operator/read responses | Purpose-specific Inventory, Coverage, Assessment, mappings, Framework and Policy Diff JSON; derived and non-persisted, not artifact families or assessment inputs. [CLI](../tooling/docs/cli.md). |

Schema-contract URIs and versions are provisional before explicit freeze and may be
replaced in place through coordinated reviewed migration. After explicit schema
freeze, compatible evolution may retain the URI; incompatible evolution requires a
new schema-contract version. Historical artifacts retain their meaning under their
historical tooling. Current grammar, schema count, module shape and successful
interface exercises do not establish freeze eligibility.

`control-library` is the maintained reusable semantic source name, distinct from its
component path and `compliance-control-library` distribution. `project-registry`
selects projects without composing policy; its data/location is nonsemantic.
`composition-lock` is the complete expected-composition abstraction. These current
names do not create aliases for retired vocabulary or compatibility commitments.

## Implemented ADR 0024 legacy migration

[ADR 0024](adr/0024-objective-assurance-and-parameter-policy.md) under
[#192](https://github.com/packetlss/compliance/issues/192) has **Tranche A implemented
under #199 and Tranche B implemented under #201**. The ParameterPolicy ownership and
frozen representation are current experimental contracts; predecessor artifacts
require historical tooling.

That migration retains optional Objective assurance, exact zero/one/multiple
realization resolution and conservative implemented Check outcomes. It removes
`satisfaction.allOf`, constant RequirementBaseline membership `required: true`,
fabricated adoption and absence-as-Assessment-FAIL. Implementation gaps remain
unsuccessful required-policy states, separately accountable from evidence outcomes,
refusal, unassigned Coverage and explicit N/A. ADR 0023 meanings remain frozen.

RequirementBaseline becomes Objective grouping only. Explicitly assigned
ParameterPolicy owns declarations, bind/tailor derivation and additive contributions;
Check authors own exact typed consumption on both realization and direct technical
paths. Contribution-only policy has no Objective/Requirement assessment row.
Atomic defaults, explicit string-set union, complete attribution, stale-pin failure,
policy-owned freshness and order independence remain unchanged.

Retain source facts once in exact plans and independently reconstruct derived
parameter summaries; preserve authored expectations and validate materialized
inputs. Legacy identity architecture remains; the coordinated migration changed
member-plan digests, operation IDs, bound plan IDs and result identities. No
schema/wire/algorithm freeze, alias, dual reader or historical
conversion follows. Historical artifacts keep their original tooling and meaning.

Follow-on A (assurance simplification) and B (parameter ownership/representation)
were implemented as coordinated valid checkpoints. Exact assignment relationships
and semantic rules are settled in ADR 0024; wire layout and field spellings remain
experimental.

## Historical/removed representations

Current tooling rejects predecessor `project-config/v1alpha1`,
`project-config/v1alpha2`, `release-lock/v1alpha2`, and assessment plan/results v1
and v3. Earlier incompatible experimental v4 representations likewise require their
historical tooling. There is no blanket v4 historical-reader promise.

Removed configuration intent/compiler/render artifacts, non-anchored latest-result
views, generic organizational/conclusion-producing assertions, the IAM service
assertion and the framework `external-judgment` category remain historical. Current
ADRs and contracts do not reinterpret their old artifacts. Git/releases and ADR
supersession records preserve their provenance.

## Legacy maturity guidance

### Former candidates, not successor commitments

These were legacy compatibility candidates/likely stable directions. They are not
an active freeze queue or a successor acceptance list; use ADR 0025's supersession
map to distinguish retained responsibilities from retired mechanisms.

- named policy-source composition by stable name + actual content digest;
- no source-order precedence and identical-only coalescing;
- content-addressed tooling/policy/evaluator/evidence provenance;
- tooling-owned inventory/assignment schema ownership;
- `Subject`, `InventoryGroup`, `PolicyAssignment`, and `Waiver` current core semantics;
- reusable technical `Control`, `Baseline`, and `BaselineOverlay` direction;
- typed evidence envelope/source-owned payload schemas;
- evaluator `{name, version, executableSha256}` execution identity;
- provider-neutral policy-source descriptor/archive construction;
- the retained `compliance` command grammar at a conceptual level.

None of these are frozen merely by this classification.

### Design pass required

Residual assurance questions, including methodology, sampling, N/A changes and
any direct result dependency graphs, require a new focused architecture promotion.
Any new common
abstraction, semantics or trust boundary requires renewed architecture review.
ADR 0021 resolves only the bounded project-governance declaration and ephemeral
satisfaction interpretation; external authority/recognition and generic
framework/GRC behavior remain outside current runtime authority.

### Experimental generated/public views

Machine-readable operator presentation objects, policy diff JSON shapes, and assessment views remain experimental unless separately frozen. Stable semantic exit behavior or invariants may be retained without freezing every JSON field.

## Release and repository boundaries

Repository co-location does not freeze contracts and does not merge release units.

- `compliance-tooling` distribution remains independently versioned/releasable.
- `control-library` remains independently digestible/releasable.
- `verification-policy` remains source-only with no current hosted release lane.
- real private environment sources remain outside the consolidated repository.

A future downstream release/productization program must choose explicit compatibility commitments from the post-consolidation contract state rather than inheriting stale workspace-era promises.

## Freezing a contract

A freeze review should define at minimum:

- exact normative semantics and authority boundaries;
- canonical representation/normalization where identity-bearing;
- fixed conformance vectors, including edge/failure cases;
- compatibility/evolution rules;
- public acquisition/distribution representation where relevant;
- downstream consumer evidence demonstrating operability; and
- explicit declaration of the compatibility commitment.

No current contract is promoted to a frozen `/v1` identity algorithm or blanket 1.0 compatibility surface by consolidation or retirement.
