# Tooling validation ownership

Run the source gate from a clean, committed tooling checkout:

```sh
./scripts/validate-tooling.sh
```

From the repository root run `scripts/dev setup`; root `toolchain/versions.env` is the sole pin authority. Use `scripts/dev doctor` for read-only diagnosis.
Run the managed installed operator entrypoint from that root with
`scripts/dev cli config list` (and the same prefix for other `compliance`
arguments). An independently installed product continues to use
`compliance ...` directly.
The gate performs frozen dependency setup, runs the complete tooling component
suite, and checks this repository's revision and cleanliness before and after.
It works at any checkout location, including a direct Git worktree. It neither
discovers nor validates a parent repository or sibling checkout. The optional
`COMPLIANCE_TOOLING_SHA` environment variable asserts an exact candidate head.
GitHub Actions supplies that head and retains the `tooling-validation` check.
It uses only the normal read-only token for this repository.

For an edit/test cycle before committing, run:

```sh
uv sync --frozen --python 3.13.15
uv run --frozen python -m unittest discover -s tests
```

Append `-v` to the native `unittest` command for per-test debugging. The
canonical gate likewise keeps successful runner output compact while preserving
native diagnostics on failure.

## Component fixtures and retained contracts

`tests/contract_fixtures.py` authors disposable synthetic resources; it never
reads an external project or policy repository. Its seven small control
manifests, three evidence schemas, ten small baselines,
one requirement, two realizations, and three minimal CLI projects provide only
the inputs needed by tooling contracts. The existing tooling-owned macOS
inventory fixture supplies DAG/assignment inputs. The names reused by older
tests are test identifiers, not copies of policy decisions or private data.

The fixture's small policy schemas exercise tooling's generic schema loader,
schema selection, JSON-pointer errors, and parameter validation. They are not
mirrors of the reusable library's authoritative schemas. Those schemas and
policy contents are validated by their owning producer gate and the composed
scenario lane. Tooling's retained packaged schemas and repository/package
mirror checks continue to run in the complete unit suite.

Component coverage retains CLI parsing/discovery and explicit source overrides;
inventory/DAG/lifecycle behavior; planner and overlay resolution; evaluator and
unknown/refusal behavior; waiver lifecycle; assessment artifacts; exact source
provenance and source-order invariance; identical-only coalescing and divergent
resource/schema refusal; policy diffs; and JCS/digest/composition-lock contracts.
The example diff-set generator receives local synthetic plans in its focused
test. Collector enumeration remains tooling-owned.
No component test invokes the complete feature runner. A focused negative test
proves the retired direct-script paths are no longer operator entry points while
their internal implementation remains importable by the unified CLI.

Each fixture uses `TemporaryDirectory` with unittest cleanup registered before
construction. CLI-generated artifacts are temporary too. No generated fixture,
policy, plan, or result is written into the checkout.

## Composed assertions and their owners

The complete feature suite is owned by
[`verification/scenarios`](../../verification/scenarios/integration/README.md).
Its gate owns composed integration and explicit immutable input selection. The retained
tooling catalog contains 24 public CLI leaves and 19 domain features. The
co-located scenario project consumes the current committed destination revision;
component tests do not depend back on its feature manifest.

Repository coordinates and revisions are review metadata, not canonical semantic identity. Destination [ADR 0005](../../docs/adr/0005-content-addressed-development-boundaries.md) and the current [repository map](../../docs/REPOSITORIES.md) govern topology while retaining logical ownership and content-addressed inputs.

The following old tooling assertions are no longer component gates:

| Old test or assertion | Canonical owner |
|---|---|
| `test_complete_synthetic_example_suite` and the shell's full feature invocation | Scenario `scripts/validate-scenarios.sh`, complete feature suite |
| `test_linux_rollout_selects_leaf_policy_and_rejects_overlap` | Scenario deterministic rollout assertions and feature suite; generic overlapping-assignment refusal remains a local planner test |
| `test_policy_validate_assembles_verification_source`, `test_repository_examples_use_canonical_artifact_directories`, `test_migrated_projects_assemble_both_policy_roles` | Scenario project registry/configuration and full feature suite; local CLI/config-discovery contracts remain |
| External evidence/overlay enumeration in `test_registered_examples_cover_extensible_implementation_sets` | Scenario full feature coverage; tooling collector enumeration remains local |
| `test_every_policy_unit_is_classified_exactly_once`, `test_roles_and_actions_preserve_dependency_direction`, `test_embedded_external_mappings_are_complete` | Control-library classification/resource validation and verification-policy resource validation |
| `test_migrated_resources_preserve_classified_content`, `test_retired_resources_are_absent_and_explained`, `test_classified_source_migration_has_no_pending_actions` | Control-library classification manifest/source-boundary checks; immutable migration evidence and verification-policy source identity remain producer-owned |

Historical configuration-removal validation and cutover records retain their
original issue references. Current composed validation belongs to the destination
scenario gate and its checked-in feature catalog.

## Separate package and release gates

The `tooling-package-validation` workflow tests the installed package on the
sole supported minor, Python 3.13, using exact Python 3.13.15 from
root `toolchain/versions.env`. The single job runs the locked-artifact,
annotated-tag, release-preparation, and local generic policy-source conformance
gates exactly once. Supporting another minor requires an explicit metadata and
CI decision. Run the relevant scripts separately using the pinned toolchain:

```sh
bash scripts/validate-package.sh
bash scripts/validate-locked-artifacts-package.sh
COMPLIANCE_TOOLING_SHA="$(git rev-parse HEAD)" bash scripts/validate-release-preparation.sh
bash scripts/validate-policy-release-compatibility.sh
```

These release scripts support Apple Bash 3.2/native utilities and Ubuntu Linux. The policy-source compatibility script is provider-neutral and fully
local. It installs the candidate wheel and validates a tooling-owned minimal
generic descriptor/archive round trip with Git, provider commands, and network
access disabled during runtime. It does not download a hosted producer release
or require cross-repository credentials. Producer-specific pre-freeze formats
are reproduced with the corresponding historical tooling and release state.
All four scripts export exact, hash-bearing runtime requirements from
`tooling/uv.lock`, install them in an external virtual environment, and then
install the candidate wheel with dependency resolution disabled. The package
gate covers both an initially empty dedicated uv cache and a fresh environment
using the populated cache.

## V4 conformance

`test_assessment_v4.py` exercises required-evidence routing/refusal, all-candidate
validation, ambiguity/coalescing, independent controls, selected factual temporal
provenance, exact evaluator identity, exact applied-waiver binding, explicit result
identity projection, intrinsic/relational validation, and path/order independence.
Mutation vectors cover complete selected and unselected documents, stable dependency
attribution, actual evaluation composition, nonidentity enforcement, operation-bound
plans, catalog-independent waiver behavior, compact roll-ups, and foreign pair
refusal. `test_assessment_v4_cli.py` uses real OPA and the public
CLI for unlocked/direct/locked equivalence, explanations and refusal without
replacement. The package gate repeats that CLI proof with the installed wheel,
verified local receipt and Git/network unavailable via
`scripts/check-installed-assessment.py`. Existing JCS, domain, roll-up, scenario
and successor locked-artifact gates remain required by impact. Operation tests derive
query-time timeliness and waiver qualification only from retained results paired with
their exact assessed plans.
