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
- `t3.json` — shared T3 Code worktree setup and validation shortcuts;
- `docs/history/pre-consolidation.md` — migration/history provenance;
- `docs/history/retirement-readiness.md` — one-time retirement/cutover evidence.

Historical `packetlss-labs` component repositories and `compliance-workspace` are archived provenance preserving pre-consolidation commits, issues, PRs, and releases. No active development or architecture work remains owned there.

Active future design/implementation work is owned by destination issues #31–#38. Real private environment repositories remain separate. Firewall/network-policy work remains out of scope unless explicitly reopened.

Normal T3 Code development is:

```text
read-only exploration
  -> promotion packet
  -> issue when durable coordination is required
  -> isolated implementation worktree
  -> PR
  -> fresh-context review + exact-head CI
  -> human squash merge
```

Narrow nonsemantic work may use its PR body as the implementation contract. All merges require human final authority; the completed repository-retirement exception is no longer active.
