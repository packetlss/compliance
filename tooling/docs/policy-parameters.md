# Explicit governed parameters

The current experimental contract implements [ADR 0024](../../docs/adr/0024-objective-assurance-and-parameter-policy.md)
Tranche B under [#201](https://github.com/packetlss/compliance/issues/201).
`ParameterPolicy` is the sole active owner of governed parameter declarations,
base binding, descendant tailoring, ancestry and additive contributions.
Objectives, RequirementBaselines, technical Baselines and ControlRealizations do
not own parameter values.

## Resource and applicability

A `ParameterPolicy` is addressed by exact `metadata.id@revision`. A declaration is
owner-local and contains its typed JSON Schema, exact `schema_digest`, binding mode
and any explicitly permitted descendant binders. Stable slot identity is
`(ParameterPolicy metadata.id, slot)`; the exact source link additionally pins the
owner revision/content, declaration and schema.

`PolicyAssignment.spec.parameterPolicyRefs` is the only applicability surface for
ParameterPolicy. It is separate from `baselineRefs`; either collection or both may
be present, but at least one governed reference is required. Loading a resource,
authoring a consumer link or targeting a contribution does not make a policy
applicable. There is no ambient lookup, automatic owner import, registry, default,
source order, assignment order, ancestry precedence or specificity rule.

A contribution-only ParameterPolicy is valid. Its applicability adds a value
contribution only: it creates no Objective, Check, assessment row or synthetic N/A.

## Derivation

An exact `extends` edge pins the parent policy reference and content digest.
`parameter_operations` contain an owner-local operation ID, `bind` or `tailor`, an
exact source declaration link and `expected_parent_fingerprint`. Bind supplies an
open base. Tailor additionally retains authored `from`, `to` and deviation facts.
The runtime validates each authored expectation and exact pin; stale, missing,
ambiguous or incompatible state fails before an assessable plan exists.

Values are typed JSON and atomic by default. Ordinary arrays remain atomic.
Duration declarations may opt into the existing positive integral `s`, `m`, `h`
or `d` representation; materialized values use canonical seconds while authored
values remain retained facts.

Only a string-array declaration with `composition.kind: additive-set` composes.
Its effective value is the tailored base union every independently applicable
compatible contribution. Members use exact JSON-string equality, deduplicate and
sort by UTF-8 bytes. A contribution targets the stable owner ID and owner-local
slot; it neither activates nor pins the target declaration, binds or tailors the
base, suppresses another contribution, or establishes precedence. Every origin and
applicability path remains attributable.

## Consumption

The object that authors a Check owns its symbolic `parameter_links`:

- `ControlRealization` owns links for Objective-backed Checks.
- `Baseline` or `BaselineOverlay` owns links for direct technical Checks.

Each link pins the exact ParameterPolicy declaration and the exact destination
instance, implementation interface and destination. Supported destinations include
JSON object paths in technical parameters, named Evidence input values and
dependency freshness such as `max_age`. One slot may fan out through several
explicit links. Links apply the typed resolved value directly; they provide no
expressions, interpolation, reducers or transformations.

The planner materializes final technical and Evidence inputs. Assessment evaluates
only those exact plan inputs and never re-resolves current ParameterPolicy.
Technical Baselines remain independently resolved and do not merge additively.

## Frozen plan and history

The v4 plan retains one `parameters` object with:

- exact selected ParameterPolicy documents, content digests and policy-source
  attribution;
- every explicit group/assignment/ParameterPolicy applicability path; and
- each exact direct-consumer ancestry document and its authored symbolic links.

Declarations, schema documents, ancestry, bind/tailor operations, authored
expectations, contributions and origins are retained inside those exact source
documents. Final materialized values remain in their technical or Evidence
destinations as required execution facts, not as a second parameter authority.
The plan does not persist duplicate effective-state, derivation-state,
before/after, member-origin, contribution-owner or consumption-value summaries.

Artifact admission independently reconstructs ancestry, operations, effective
values, canonical additive union, complete contribution membership and attribution,
consumer interfaces and materialized destinations from these retained historical
facts. It verifies exact source pins and provenance without consulting current
policy, inventory or Evidence. An outer artifact digest is insufficient. Artifacts
using the superseded RequirementBaseline-owned representation are rejected by the
current reader and remain meaningful only with their historical tooling.

Coverage is a current, ephemeral projection of applicability, resolution,
contributions and consumer effects. Historical explanation and Policy Diff use the
validated frozen plan/result only. Policy Diff reconstructs effective parameter
changes while keeping identity/context churn distinct from effective-policy change.

## Maintained proofs

The authorized-software scenario assigns an explicit base ParameterPolicy and an
independently applicable database contribution, then materializes the canonical
`auditd,curl,postgresql` set into a direct technical Check. Removing the contribution
leaves the base valid and observed PostgreSQL produces an Evidence-derived FAIL;
removing the required base prevents assessment planning.

The IAM/private-boundary scenario assigns a 24h base and explicitly tailors it to
1h in the private source. The same realization-owned links fan out to four required
freshness destinations. Private acquisition, Evidence selection and Assessment
meaning are unchanged; independently applicable divergent ancestor and descendant
policies conflict, and source relocation/order remains nonsemantic.

The representation and identity algorithms remain experimental and pre-freeze.
This cutover deliberately changes member-plan, operation, bound-plan and result
identities where the committed representation changes; it defines no aliases,
dual readers or cross-version equivalence.
