# Linux hardening rollout verification scenario

Status: **Stable deterministic verification scenario**

This project models a fictitious platform team rolling out company Linux
hardening and centrally governed access across standard application and
container-runtime servers. It uses normal inventory, policy, realization,
evidence, waiver, assessment-plan, and assessment-result contracts. The
provenance-bearing assessment plan is the handoff to any separately implemented
configuration or policy adapter; this scenario does not implement or execute
one.

## Scope and authoritative inventory

The governed scope contains three synthetic active `linux-host` subjects. A
reviewed projection from `mock-server-inventory` supplies the trusted
`platform`, `server-persona`, `feature-container-runtime`, and `iam-profile`
labels. Collectors observe packages, sysctls, and access configuration; they do
not select policy.

- `host/standard-app-01` is a standard application server in a staged rollout.
- `host/container-app-01` is a specialized container-runtime host.
- `host/persona-conflict-01` deliberately carries contradictory persona labels.

The group hierarchy is:

```text
company-assets
└── linux-servers
    ├── standard-application-servers
    └── container-runtime-servers
```

## Company policy and external assurance

Every Linux server receives the standalone company operations baseline and the
company identity/access objective baseline. The persona leaf selects one
hardening baseline:

```text
Illustrative Linux server benchmark
  -> company Linux server hardening
     -> company container-runtime host

Company Linux server operations

Company identity and access objectives
  -> centrally governed role access requirement
     -> company Linux technical realization
```

The operations baseline is first-class internal policy and needs no regulatory
wrapper. The access objective is also company policy; its optional
`example-regulatory-framework:IAM-01` reference demonstrates traceability to a
broad external requirement. The declared external scope is only that one
mapping for the synthetic Linux hosts. The illustrative source has no versioned
framework catalog, so it cannot demonstrate complete framework coverage and
this scenario makes no certification, legal-compliance, or whole-framework
claim. The illustrative Linux benchmark references show parent alignment only.

The scenario assembles reusable controls and schemas from `control-library`
with the complete synthetic baseline, requirement, and realization family from
`verification-policy`. It does not consume the IAM project's restricted
environment-private source.

## Intended operating practice

The platform operations team owns hardened base images and the package/sysctl
delivery workflow. The company IAM team owns centrally governed operator-group
membership, the SSSD domain integration, and access-remediation guidance.
Security risk owners approve bounded waivers. Normal changes are reviewed in
the relevant policy or delivery root before rollout. A separately
versioned delivery adapter may consume the resolved assessment plan, but owns
its backend-specific mapping, credentials, state, approval, and execution.

The access realization requires SSSD, the approved company domain, the
`company-linux-operators` SSH group, and no unmanaged interactive local
accounts. This scenario evaluates normalized actual-state evidence separately
from resolved policy. It does not yet evidence access-request approval,
periodic human access review, image promotion, or configuration-application
records; those remain explicit assurance gaps rather than implied passes.
Neither the plan nor any downstream adapter output would prove remediation or
successful application.

## Deterministic run

Run the canonical destination gate from the repository root. It assembles the
committed source into a temporary non-Git root and fixes the instant shown below
so evidence freshness and waiver lifecycle behavior remain reproducible:

```sh
bash scripts/validate-verification-scenarios.sh
```

The container subject has eight technical passes and one passing objective. Its
assessment plan retains the stable control IDs, resolved parameters, definition
fingerprints, lineage, policy-source digests, and provenance for `auditd`,
`containerd`, ASLR, and the tailored IPv4-forwarding decision. These fields are
the external-adapter handoff; the plan itself makes no application claim.

The project uses `project-config/v1alpha3` without an authored tooling-schema
path. Plans and results use v4 and record the actual source/editable tooling and
named policy composition at planning and evaluation, the exact evaluator,
complete subject evidence snapshot, factual successful evidence selections, and
applied-waiver provenance. Expected composition enforcement remains separate
from those actual facts. The canonical gate proves that locking identical actual
inputs leaves the semantic plan ID unchanged and that mismatches refuse before
domain execution.

The standard subject deliberately lacks `auditd` and all access evidence. The
exact audit-package failure becomes `WAIVED` at the fixed instant while the
four access checks and their objective remain `UNKNOWN`. Its assessment and
resolved plan still retain the unchanged policy; removal of generated
configuration is not remediation and does not alter those outcomes.

## Durable deviation and safe refusal

The container baseline changes IPv4 forwarding from `0` to `1`, records
`DEV-LINUX-CONTAINER-001`, and adds `containerd`. The assessment plan and
assessment explanation expose the pinned parent fingerprint, exact before/after
criteria, approval, review date, and baseline/control/source provenance.

The third subject deliberately selects both sibling persona assignments:

```sh
uv run compliance --project linux-hardening-rollout plan render \
  host/persona-conflict-01
uv run compliance --project linux-hardening-rollout plan show \
  host/persona-conflict-01
```

The incompatible forwarding definitions make resolution invalid. Assignment,
source, and file order never choose a winner, and a waiver cannot repair the
classification error.

## Primary feature coverage

This scenario is the primary verification owner for trusted persona selection,
baseline inheritance and tailoring, requirement realization, pass/unknown
roll-up, resolved Linux package/sysctl controls, assessment-plan adapter handoff,
exact waivers, invalid sibling-policy conflicts, and joined assessment
explanations. The machine-readable ownership catalog lives in the co-located
tooling root at `tooling/examples/feature-coverage.json`; the
final catalog contains 20 public CLI leaves and 18 domain features, each with
exactly one primary owner.

All identities and observations are synthetic. Fixtures contain no credentials,
customer data, or environment-private implementation details. The separate IAM
project remains the verification boundary for multi-source restricted policy.

The ADR 0012 canonical extension uses separately copied public and private policy
roots. It preserves ordinary technical policy ages, then explicitly tailors the
private objective freshness from 24h to 1h without changing realization bytes.
Independent ancestor-plus-descendant selection is invalid; missing evidence is
unknown after resolution; absent realization keeps its existing not-implemented
coverage. These synthetic results establish no external framework claim.
