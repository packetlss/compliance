# Compliance

`packetlss/compliance` is the **sole authoritative development and documentation repository for non-sensitive compliance source**.

All six migrated source domains are authoritative here:

- tooling under `tooling/`;
- reusable `control-library` under `policy-sources/control-library/policies/`;
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
- `macos-portability`

`verification-scenarios` is the real canonical composed gate and owns all 21 retained public CLI leaves and 19 retained domain features. Normal validation uses one repository checkout and no historical sibling-repository App/PAT acquisition path.

From the repository root, `scripts/dev setup` creates this worktree's isolated environment and installs the repository-pinned Python, uv, and OPA without sudo or global package-manager changes. Downloads are cached outside semantic roots. Use `scripts/dev doctor` for read-only diagnosis.

Repository development and manual testing use the managed CLI adapter, which
runs the installed product entry point from the repository root with the pinned
toolchain:

```sh
scripts/dev cli config list
scripts/dev cli inventory list assets
scripts/dev cli coverage list assets
scripts/dev cli coverage explain cloud-account/aws-111122223333
```

Use `compliance ...` directly when exercising an independently installed
product. `scripts/dev cli` is only the repository-development invocation path.

Quick checks read the current working tree:

```sh
scripts/dev check tooling
scripts/dev check policy
scripts/dev check projects
scripts/dev check iam
scripts/dev check scenarios
```

Optional tooling test names may follow `scripts/dev check tooling`. Fast checks show a compact summary by default; use `scripts/dev check --verbose <area>` to show every test while debugging (for example, `scripts/dev check --verbose tooling test_canonical_json.py`). Canonical committed-input gates are explicit, for example `scripts/dev gate tooling`, `scripts/dev gate policy`, and `scripts/dev gate scenarios`. They refuse a dirty checkout and are selected by change impact or reproduction need. `scripts/dev readiness` reports current integration, exact-head review, and required CI evidence without mutating GitHub.

## Architecture and workflow

Current normative architecture is local:

- `AGENTS.md` — persistent repository/agent instructions;
- `docs/ARCHITECTURE.md` — current system architecture;
- `docs/REPOSITORIES.md` — logical ownership/repository boundaries;
- `docs/DEVELOPMENT_WORKFLOW.md` — engineering lifecycle;
- `docs/CONTRACT_MATURITY.md` — compatibility/freeze rules;
- `docs/adr/` — accepted ADRs 0005–0012 and 0016–0018;
- `t3.json` — shared T3 Code worktree setup and validation shortcuts;
- `docs/history/pre-consolidation.md` — migration/history provenance;
- `docs/history/retirement-readiness.md` — one-time retirement/cutover evidence.

Historical `packetlss-labs` component repositories and `compliance-workspace` are archived provenance preserving pre-consolidation commits, issues, PRs, and releases. No active development or architecture work remains owned there.

Current staged work is routed through [roadmap #85](https://github.com/packetlss/compliance/issues/85) and its promoted destination issues. Issues #31–#38 are completed or closed consolidation and architecture history, not active routing. Real private environment repositories remain separate. Firewall/network-policy work remains out of scope unless explicitly reopened.

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
