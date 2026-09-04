# Compliance

`packetlss/compliance` is the **sole authoritative development and documentation repository for non-sensitive compliance source**.

All six migrated source domains are authoritative here:

- tooling under `tooling/`;
- reusable `shared-library` under `policy-sources/control-library/policies/`;
- source-only `verification-policy` under `policy-sources/verification-policy/policies/`;
- ordinary `mock-fleet` and `server-personas` projects under `projects/`;
- the synthetic IAM/private-boundary fixture under `verification/fixtures/iam-private-boundary/`; and
- canonical verification scenarios under `verification/scenarios/`.

The semantic composition remains:

```text
tooling + N named policy sources + project inputs
```

Repository layout is not semantic identity. Tooling and policy-source identities remain content-addressed; policy roots remain independently named/materialized; source/file order is nonsemantic; divergent same-identity definitions fail closed; and real private environment inputs remain outside this repository.

The IAM fixture is synthetic. Its `environment-private` source is physically materialized into a separate temporary root before execution; co-location is not treated as a real access-control boundary.

## Validation

Stable destination CI contexts are:

- `component-validation`
- `verification-scenarios`
- `installed-release-provenance`

`verification-scenarios` is the real canonical composed gate and owns all 20 retained public CLI leaves and 18 retained domain features. Normal validation uses one repository checkout and no historical sibling-repository App/PAT acquisition path.

## Architecture and workflow

Current normative architecture is local:

- `AGENTS.md` — persistent repository/agent instructions;
- `docs/ARCHITECTURE.md` — current system architecture;
- `docs/REPOSITORIES.md` — logical ownership/repository boundaries;
- `docs/DEVELOPMENT_WORKFLOW.md` — engineering lifecycle;
- `docs/CONTRACT_MATURITY.md` — compatibility/freeze rules;
- `docs/adr/` — accepted ADRs 0005–0008;
- `docs/history/pre-consolidation.md` — migration/history provenance;
- `docs/history/retirement-readiness.md` — one-time retirement/cutover evidence.

Historical `packetlss-labs` component repositories and `compliance-workspace` preserve pre-consolidation commits/issues/PRs/releases and are provenance only. They are being archived under #29; no active development or architecture work remains owned there.

Active future design/implementation work is owned by destination issues #31–#38. Real private environment repositories remain separate. Firewall/network-policy work remains out of scope unless explicitly reopened.

Normal development is:

```text
issue -> branch -> PR -> CI -> review -> human squash merge
```

Retirement controller #29 temporarily permits automatic squash merges only for bounded, nonsemantic documentation/routing/mechanical retirement PRs after exact-head CI is green. That exception ends when retirement is complete.