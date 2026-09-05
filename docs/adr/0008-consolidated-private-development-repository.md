# ADR 0008: Consolidate non-sensitive development in a private personal repository

- **Status:** Accepted
- **Original date:** 2026-09-04
- **Destination authority transfer:** 2026-09-04
- **T3 Code workflow refinement:** 2026-09-05
- **Historical source:** `packetlss-labs/compliance-workspace@098ef18c1384b34c532f705b3f5b3d1a25bd638f`, `docs/adr/0008-consolidated-private-development-repository.md`

This is the destination-owned normative restatement of accepted/amended workspace ADR 0008. It records the accepted repository decision and the now-implemented source layout without changing semantic or trust-boundary decisions.

## Decision

### Authoritative development repository

The private personal repository:

```text
packetlss/compliance
```

is the selected durable repository for consolidated **non-sensitive compliance development**. After the staged authority cutover, it is the sole active non-sensitive source-development repository. Repository identity does not replace content-addressed runtime, release, policy-source, or provenance identity.

The migration uses clean destination history. Historical component/workspace commits, issues, PRs, tags, GitHub Releases, and hosted assets remain in their original repositories and are not rewritten or republished.

### Durable source layout and semantic roots

The consolidated layout is:

```text
compliance/
├── tooling/
├── policy-sources/
│   ├── control-library/
│   │   └── policies/
│   └── verification-policy/
│       └── policies/
├── projects/
│   ├── mock-fleet/
│   └── server-personas/
├── verification/
│   ├── scenarios/
│   └── fixtures/
│       └── iam-private-boundary/
├── docs/
├── toolchain/
├── scripts/
├── tests/
└── .github/
```

Durable semantic/ownership boundaries are:

- `tooling/` is the explicit tooling source/build root;
- Python distribution identity remains `compliance-tooling` unless separately reviewed;
- `policy-sources/control-library/policies/` is independently named `shared-library`;
- `policy-sources/verification-policy/policies/` is independently named `verification-policy`;
- each `projects/<id>/` remains logically isolated;
- canonical composed verification is under `verification/scenarios/`; and
- the synthetic IAM proof remains a fixture whose `environment-private` policy source is separately materialized for execution.

There is no repository-wide aggregate policy tree and no source/file-order precedence. Exact-identical same-identity resources may coalesce; divergence fails visibly.

The repository root is not the Python project root; `tooling/` remains explicit.

### Relocation preserves semantic identity

Changing Git repository, owner, or enclosing directory does not by itself change semantic source identity. Migration proved unchanged root-relative tooling/policy content retains the applicable source-tree digest.

Git repository, owner, commit, checkout path, enclosing repository path, workspace pin, source order, acquisition URL, and transport representation remain noncanonical unless a separate contract explicitly consumes those exact bytes.

A pure relocation that changes semantic source identity is an architectural failure, not routine migration metadata.

### Real trust boundaries remain separate

Only non-sensitive source whose ownership/information-sharing boundary permits co-location belongs here.

Real private environments remain in separate authorized repositories/workspaces and execution contexts. Real private inventory, evidence, realizations, parameters, credentials, secrets, provider state, generated results, or operational data do not move into this repository.

The IAM fixture is synthetic. Its `policy/` tree may be stored under `verification/fixtures/iam-private-boundary/`, but validation must physically materialize it into a distinct temporary `environment-private` policy-source root and must not succeed through recursive central-checkout traversal. Co-location itself is not a trust boundary.

### Repository layout does not change release units

Preserve unless separately reviewed:

- `compliance-tooling` Python distribution and wheel/source provenance;
- the control-library policy-source distribution and provider-neutral descriptor/archive construction;
- generic policy-source release/archive schemas/validation owned by tooling;
- installed-package/no-Git provenance validation; and
- verification policy as a source-only internal named/digested source with no independent current hosted release lane.

Historical releases remain attached to their original repositories. This ADR does not define a new publisher, tag namespace, registry, signing/attestation system, or release coordinate.

### Development workflow and provider controls

Normal development uses one T3 Code project at the repository root and follows:

```text
read-only exploration
  -> implementation promotion packet
  -> durable issue when coordination requires one
  -> isolated worktree from current main
  -> focused implementation and local validation
  -> pull request linked to its issue/thread
  -> fresh-context exact-head review and CI
  -> human squash merge
```

Architecture, semantic, trust/repository/release, public or cross-component contract, dependent migration, and multi-session work requires a durable issue. A narrow one-worktree documentation, test, refactor, or mechanical change that changes no semantics or boundary may use its PR body as the implementation contract. T3-generated branch names are permitted because branch names are operational metadata; issues and PRs provide durable task identity.

Stable destination CI surfaces are:

```text
component-validation
verification-scenarios
installed-release-provenance
```

CI evidence and fresh-context review must cover the current head. Provider-enforced branch protection, rulesets, required-status enforcement, conversation-resolution enforcement, or similar plan-gated controls are optional operational hardening, not architecture prerequisites. Human final squash merge remains mandatory.

During repository retirement, destination issue #29 narrowly authorized automatic squash merges for bounded documentation/routing/mechanical retirement changes after exact-head CI was green. That exception expired when retirement completed and grants no current merge authority.

### No normal sibling-repository acquisition

Normal consolidated validation consumes co-located committed roots from one repository checkout. Migration-era `compliance-ci` sibling App credentials, PAT fallback, sibling clones, and repository-coordinate integration manifests are not part of target development CI.

A future genuine private/external consumer may use its own least-privilege acquisition mechanism without restoring sibling-development coupling.

### Active work is routed before archival

Historical repository issues are not left as active implementation authority when their source repository becomes provenance-only. ADR 0007 implementation is routed to destination #31–#36, detailed assurance design to destination #37, and the dormant product-DNA follow-up to destination #38. Stale workspace productization assumptions are closed rather than copied verbatim.

### ADR 0007 may follow source consolidation

Full v1alpha3/v4 implementation was not a prerequisite for co-location. Until bounded successor cutovers complete, current runtime contracts remain experimental migration inputs. Co-location must not silently absorb detailed assurance design from destination #37.

### Retirement

The workspace does not remain a second source-development root or mandatory downstream starter. After destination documentation/authority readiness and routing are complete, superseded component repositories are archived as historical provenance and `compliance-workspace` is archived last.

A future downstream starter should be designed from post-consolidation release contracts rather than preserving the transitional submodule workspace.

## Current migration evidence

The six migrated source domains have destination authority records in `docs/history/pre-consolidation.md`. Canonical integration now runs entirely from the destination checkout and owns all 20 retained public CLI leaves and 18 retained domain features. Normal validation contains no old sibling-repository acquisition path.

Retirement and final documentation/authority cutover completed under destination #29. The archived repositories remain historical provenance.

## Non-decisions

This ADR does not freeze contracts, change semantic digest/JCS rules, redesign assurance, change release coordinates/publication, move real private data, introduce apply/execution authority, or authorize firewall/network-policy work.
