# Verification Scenarios and Assurance Narratives

Status: **Accepted direction; first scenario implemented, broader migration proposed (v0.3)**
Last updated: **2026-09-04**

This document defines how runnable examples should prove implemented behavior
while remaining recognizable as credible operational situations. It also
defines how those scenarios explain the path from an external requirement to
company policy, normal operating practice, technical realization, evidence,
and a current assessment without overstating the resulting assurance claim.

The verification strategy and first scenario migration are accepted. Current
repository coordinates are transitional; the final consolidated repository
name and directory layout are intentionally undecided. No new policy resource
kind is introduced here.

## 1. Separate verification from discovery

The project suite serves four different purposes:

| Project role | Purpose | Stability expectation |
|---|---|---|
| **Verification scenario** | Prove accepted contracts through deterministic end-to-end behavior | Release-gated and intentionally stable |
| **Development project** | Discover missing behavior and exercise evolving designs | May change as proposals are explored |
| **Boundary example** | Prove a collection, privacy, repository, or information-sharing boundary | Stable where the boundary matters; not necessarily deterministic |
| **External example** | Give users an idiomatic, copyable starting point using supported releases | Downstream compatibility-tested documentation, never a core release input |

A project may help with more than one role, but its primary role must be
explicit. A development project must not silently become the normative
contract merely because the verification runner currently uses it. Conversely,
a verification scenario should not absorb experimental behavior before that
behavior is accepted and documented.

External examples are deliberately downstream of released tooling and policy.
They may reuse the same public contracts and operational stories, but their
primary test is whether a user can understand, adapt, and maintain them. Core
tooling, shared policy, and verification scenarios must not import or otherwise
depend on an external example. Verification scenarios remain the release gate;
external examples maintain their own supported-release compatibility matrix.

Policy follows the same logical separation. Verification scenarios consume the
released shared-policy library plus verification-only policy containing
synthetic company baselines, edge cases, and test mappings. A starter workspace
instead pins the shared-policy library plus a separately released,
customer-shaped example-company policy. The verification and example policy
sources never depend on one another. In the current transitional layout,
`compliance-control-library` owns the released reusable policy and
`compliance-verification-policy` owns the retained synthetic verification
resources. Those named sources remain independently identified and digested if
their non-sensitive development source is later co-located.

The current `compliance-verification-scenarios` integration owner contains the
first stable project: a deterministic Linux hardening rollout with
a complete company access realization, a waiver, missing-evidence outcomes,
and a persona conflict. The current mock-fleet and server-personas projects
remain development examples.
The tooling-owned synthetic macOS fixture retains typed evidence and policy
lineage coverage without observing a developer host. The public IAM project is
a synthetic need-to-know and multi-source materialization proof; real private
environment repositories remain separate. These fixtures remain useful while
dedicated verification scenarios are introduced incrementally.

Current development projects are materialized under the transitional
`compliance-development-projects` coordinate. A clonable downstream starter and
example-company policy remain future product work. Their repository names,
placement, and migration timing are not decided here and do not alter the
accepted project-isolation and policy-source dependency boundaries.

## 2. Scenario first, feature mapped

Verification projects should tell a coherent operational story rather than be
named after isolated implementation mechanisms. A scenario may prove several
features, and one important feature may appear in several scenarios. A separate
coverage catalog should map every implemented feature to at least one primary
scenario so incidental coverage is never mistaken for an explicit contract.

Candidate scenario families include:

- managed developer workstations;
- a production cloud and SaaS estate;
- standard and specialized Linux platform personas;
- a restricted identity and access environment;
- policy promotion between reviewed releases; and
- collector failure and evidence-contract upgrades.

The scenario data should be synthetic but operationally credible. Identities,
ownership, group structure, desired settings, evidence, deviations, waivers,
and failure causes should resemble situations an operator could encounter.
Examples must not contain real credentials, customer data, or restricted
implementation details merely to appear realistic.

## 3. Verification quality contract

Every verification scenario must:

1. use the public CLI and the normal schemas, planner, evaluator, persistence,
   and explanation boundaries without test-only shortcuts;
2. run offline with deterministic fixtures, controlled assessment times, and
   no dependency on current host state;
3. assert machine-readable semantics, schema validity, digests, roll-ups, and
   important refusal behavior instead of relying only on terminal text;
4. include credible positive, negative, unknown, invalid, or refusal cases as
   appropriate to the contract being demonstrated;
5. document every intentional failure and its expected status or exit code;
6. keep generated evidence, plans, results, and any separate external-adapter
   output disposable and out of Git; and
7. preserve project, policy-source, and information-sharing boundaries even
   when several scenario projects share one repository.

Human output remains important for demonstration. It should be generated from
the same run and exposed through focused `--show` selections. Complete golden
transcripts should be used sparingly because cosmetic output changes are a
poor substitute for structured contract assertions.

## 4. Internal policy and external assurance chain

Scenarios should begin with the real concern being solved. That concern may be
an internal hardening or operational need, an external obligation, or both.
External frameworks are not mandatory policy parents, and internal objectives
must not acquire invented external wrappers merely to enter the assurance
model.

When an external requirement is broad, the scenario should make the reviewed
company interpretation and complete implementation chain visible:

```text
Internal concern -> company objective or technical baseline
External requirement and scope -> reviewed company interpretation -> company objective
Company objective -> intended operating practice and ownership
Company objective -> selected environment ControlRealization
Realization -> independently attributable technical controls
Technical controls -> optional external-adapter delivery workflow
Technical controls -> typed evidence and current results
Results -> conservative requirement and requirement-baseline roll-up
Assessment -> deviations, waivers, unknowns, and uncovered gaps
```

A standalone company technical baseline may skip the objective and realization
layers when it makes only independently attributable desired-state claims. It
can still carry optional technical mappings to external requirements. A
company `ControlRequirement` can have no external references, map to several,
or be one of several company objectives needed to interpret and fulfill one
broad external requirement.

These layers support different claims:

| Layer | Defensible claim |
|---|---|
| Framework coverage | Which versioned requirements are included, omitted, or determined not applicable within the declared scope |
| Company intent | Which technology-neutral outcome the organization adopted |
| Operating practice | How people, platforms, ownership, and change processes are intended to implement that outcome |
| Technical realization | Which exact checks are asserted to prove the objective in one environment |
| Current assessment | What sufficiently fresh evidence currently proves, disproves, or leaves unknown |
| Parent alignment | Whether inherited technical policy is unaltered, tailored, substituted, excluded, or supplemented |
| Exception state | Which current failures are explicitly waived without becoming passes |

Overlapping concerns should reuse stable policy objects rather than duplicate
logic. The same control result may support company hardening, an operational
objective, and several external mappings while retaining every provenance
path. Identical definitions coalesce; different parameters or desired states
remain explicit conflicts and are never resolved by framework, assignment,
source, or file order.

An objective-level result requires a complete, selected realization and its
declared satisfaction rule. A technical `external_refs` mapping remains
supporting traceability and cannot by itself establish the objective. A
passing company assessment with tailoring or exclusions cannot be presented as
unaltered parent-framework conformance.

Whole-framework fulfillment is an even broader claim. It requires a declared
framework version and scope, a complete inventory of applicable requirements,
visible omissions and approved not-applicable determinations, and defensible
results for every required objective. A small illustrative automation profile
or a collection of passing mapped checks must never be labelled certification,
legal compliance, or complete framework conformance.

## 5. Operating practice is explicit but not yet a resource

The intended way of working connects governance intent to everyday operation.
For example, a centrally governed access objective may be implemented through
reviewed identity-provider groups, an approved access-change workflow, SSSD
domain configuration, SSH authorization rules, and restrictions on local
interactive accounts.

For technical portions, scenarios should show that the assessment plan retains
the stable control IDs, fingerprints, resolved parameters, lineage, and
provenance needed by an external adapter, and how separately collected
actual-state evidence is evaluated. External output is neither execution proof
nor compliance evidence. For operational or
procedural portions, the scenario must name the authoritative record and check
that would support the claim, or mark the portion as unverified.

For the initial scenario suite, this operating practice belongs in the
scenario narrative. Each relevant README should state:

- the internal concern and, when present, the external requirement, version,
  and assessment scope;
- the company's interpretation and intended outcome;
- the normal ownership, approval, change, and remediation workflow;
- the automated realization, resolved desired controls, and evidence sources;
- any manual, procedural, or otherwise unverified assurance; and
- the exact limits of the automated claim.

Documentation does not turn an unevidenced process into a passing control. If a
human workflow must become part of the objective-level assessment, it needs an
appropriate evidence contract and independently attributable check, or it must
remain an explicit assurance gap.

A machine-readable `OperatingPractice` resource or a joined command such as an
assurance explanation may be considered later. Both remain proposals until
scenario use demonstrates stable identity, ownership, versioning, evidence,
and reporting requirements that cannot be met by the existing requirement,
realization, plan, and explanation contracts.

## 6. Repository and project organization

Repository consolidation should follow ownership and information-sharing
boundaries, not create one repository per feature. A future example repository
may contain several independently configured projects when they share the same
maintainers and visibility. Each project must retain its own `compliance.yaml`,
inventory, assignments, waivers, private policy inputs, and generated paths;
a project registry still selects exactly one project at a time.

Likewise, development projects may be consolidated into one development
repository while remaining separate logical projects. They should not become
one large catalog whose assignments and expected results interact merely for
convenience. Any future real host-observation collector and an independently
versioned restricted policy source should remain separate where combining them
would stop exercising the boundary they exist to prove.

Development topology is governed by workspace
[ADR 0005](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/adr/0005-content-addressed-development-boundaries.md).
The current system [architecture](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/ARCHITECTURE.md)
and [repository map](https://github.com/packetlss-labs/compliance-workspace/blob/main/docs/REPOSITORIES.md)
distinguish logical integration ownership from repository placement and preserve
real information-sharing boundaries.

The tooling feature catalog records the retained 21 CLI leaves and 19 domain
features. Scenario issue #11 owns the final coordinated cutover and must select
the final producer/consumer revisions without making an adapter a prerequisite
for assessment.

The first migration created `projects/linux-hardening-rollout` inside
`compliance-verification-scenarios`; the server-personas development input now
lives in `compliance-development-projects`. The stable project is the primary
path for requirement pass/unknown roll-up, waiver application, invalid persona
resolution, and joined explanations. Fixed
collection and evaluation instants make freshness and waiver behavior
repeatable. `examples/feature-coverage.json` assigns every registered CLI and
domain feature to exactly one primary scenario and records which remaining
owners are still development or boundary projects.

## 7. Scenario README contract

A maintained verification scenario README should contain:

1. the operational story and governed-subject scope;
2. authoritative inventory sources and trusted policy-selecting attributes;
3. assigned company policy and any external-framework scope;
4. the intended operating practice and its owners;
5. technical realization, collectors, and any external-adapter boundary;
6. deterministic commands and expected results;
7. intentional deviations, waivers, failures, unknowns, and invalid cases;
8. the primary feature coverage provided by the scenario; and
9. explicit limitations on assurance, privacy, and production applicability.

This narrative complements machine-readable plans and results. It must not
invent provenance or conclusions that those artifacts do not support.
