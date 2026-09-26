# Compliance

`packetlss/compliance` is the **sole authoritative development and documentation repository for non-sensitive compliance source**.

The accepted [trusted-snapshot successor](docs/SUCCESSOR_ARCHITECTURE.md) is a
documentation/specification target under [ADR 0025](docs/adr/0025-trusted-snapshot-successor.md),
not an implemented replacement or a production platform choice. The source areas,
runtime behavior, packaging and validation described below remain **implemented
legacy** until explicitly reviewed migration:

- tooling under `tooling/`;
- reusable `control-library` under `policy-sources/control-library/policies/`;
- source-only `verification-policy` under `policy-sources/verification-policy/policies/`;
- ordinary `mock-fleet`, `server-personas` and `alder-forge-dcc-level3` projects under `projects/`;
- the synthetic IAM/private-boundary fixture under `verification/fixtures/iam-private-boundary/`; and
- canonical verification scenarios under `verification/scenarios/`.

Compliance resolves governed inventory and policy into exact assessment plans,
evaluates company-owned criteria against descriptive observations, and explains
immutable historical outcomes with separately derived current qualification.
Coverage explains current expected scope; framework satisfaction is bounded to an
exact governance declaration and its required support. Neither claims external
certification or continuous effectiveness.

The experimental [producer interface](tooling/docs/producer-interface.md) supports
schema discovery/export and document validation. External readers consume
[purpose-specific derived responses](tooling/docs/cli.md#experimental-external-read-consumption).

The semantic composition is:

```text
tooling + N named policy sources + project inputs
```

Repository layout is not semantic identity. Tooling and policy-source identities remain content-addressed; policy roots remain independently named/materialized; source/file order is nonsemantic; divergent same-identity definitions fail closed; and real private environment inputs remain outside this repository.

The IAM fixture is synthetic. Its `environment-private` source is physically materialized into a separate temporary root before execution; co-location is not treated as a real access-control boundary.

## Validation

Required legacy CI contexts for main (and affected shared infrastructure) are:

- `component-validation`
- `verification-scenarios`
- `installed-release-provenance`
- `macos-portability`

`verification-scenarios` is the real canonical composed gate and owns all 27 retained public CLI leaves and 19 retained domain features. Normal validation uses one repository checkout and no historical sibling-repository App/PAT acquisition path.

From the repository root, `scripts/dev setup` creates this worktree's isolated environment and installs the repository-pinned Python, uv, and OPA without sudo or global package-manager changes. Downloads are cached outside semantic roots. T3 offers explicit **Setup legacy worktree** and **Successor foundation** actions; automatic legacy setup on worktree creation is disabled so successor infrastructure does not install the legacy application stack. Repository-managed `check`, `gate`, and `cli` commands wait for that setup if it is in progress, or safely repair a missing or stale environment themselves. Use `scripts/dev doctor` for read-only diagnosis; it never repairs state.

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

Optional tooling test names may follow `scripts/dev check tooling`. Fast checks show a compact summary by default; use `scripts/dev check --verbose <area>` to show every test while debugging (for example, `scripts/dev check --verbose tooling test_canonical_json.py`). Canonical committed-input gates also use compact native runner output; rerun an underlying `unittest` command with `-v` or an OPA test with `--verbose` for detailed progress while debugging. Canonical committed-input gates are explicit, for example `scripts/dev gate tooling`, `scripts/dev gate policy`, and `scripts/dev gate scenarios`. They refuse a dirty checkout and are selected by change impact or reproduction need. `scripts/dev readiness` is read-only and reports exact-head review/head-CI plus current-base integration evidence; use `scripts/dev integration` to explicitly request the trusted synthetic current-base validation when an unchanged PR head no longer contains its base.

Successor-only bootstrap uses the real `successor-foundation` check; application,
acceptance and packaged-platform checks remain pending #209. Resolve each task's
actual target with `scripts/dev task --target main|successor`; after activation,
successor work branches from and targets successor. `scripts/dev foundation` uses
only infrastructure tools. See the [check matrix and activation checklist](docs/DEVELOPMENT_WORKFLOW.md#two-lane-validation-matrix).
Bootstrap merge alone does not activate the lane or unblock #209.

## Architecture and workflow

Architecture authority is routed locally:

- `AGENTS.md` — persistent repository/agent instructions;
- `docs/ARCHITECTURE.md` — implemented legacy architecture and successor routing;
- `docs/SUCCESSOR_ARCHITECTURE.md` — accepted target, acceptance stories, open decisions and bounded experiment specification;
- `docs/REPOSITORIES.md` — logical ownership/repository boundaries;
- `docs/DEVELOPMENT_WORKFLOW.md` — engineering lifecycle;
- `docs/CONTRACT_MATURITY.md` — compatibility/freeze rules;
- `docs/adr/` — decisions and supersession history, including successor ADR 0025 and retained ADR 0023 semantic foundation;
- `t3.json` — shared T3 Code worktree setup and validation shortcuts;
- `docs/history/pre-consolidation.md` — migration/history provenance;
- `docs/history/retirement-readiness.md` — one-time retirement/cutover evidence.

Historical `packetlss-labs` component repositories and `compliance-workspace` are archived provenance preserving pre-consolidation commits, issues, PRs, and releases. No active development or architecture work remains owned there.

Current staged work is routed through [roadmap #85](https://github.com/packetlss/compliance/issues/85) and its promoted destination issues. Real private environment repositories remain separate. Firewall/network-policy work remains out of scope unless explicitly reopened.

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

Narrow nonsemantic work may use its PR body as the implementation contract. All merges require human final authority.

<!-- Unmerged #208 activation probe: verify preserved main checks and trusted integration dispatch. -->
