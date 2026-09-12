#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY_ROOT="$(cd -- "$SOURCE_ROOT/../.." && pwd)"
if [[ "$#" != 2 || "$1" != "--integration-root" ]]; then
  printf 'Usage: %s --integration-root TEMPORARY_ASSEMBLY\n' "$0" >&2
  exit 1
fi
INTEGRATION_ROOT="$(cd -- "$2" && pwd)"
SCENARIOS_ROOT="$INTEGRATION_ROOT/verification/scenarios"
TOOLING_ROOT="$INTEGRATION_ROOT/tooling"
PROJECT="linux-hardening-rollout"
PROJECT_ROOT="$SCENARIOS_ROOT/projects/$PROJECT"
FIXED_INSTANT="2026-09-01T00:00:00Z"
RUN_ROOT=""

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

tooling_run() {
  uv run --project "$TOOLING_ROOT" --frozen "$@"
}

cleanup() {
  [[ -z "$RUN_ROOT" ]] || rm -rf "$RUN_ROOT"
}

trap cleanup EXIT

"${COMPLIANCE_PYTHON:-python3}" "$SOURCE_ROOT/scripts/integration.py" verify --root "$INTEGRATION_ROOT"
[[ -f "$PROJECT_ROOT/compliance.yaml" ]] || fail "scenario project not found: $PROJECT_ROOT"

# shellcheck disable=SC1091
source "$REPOSITORY_ROOT/toolchain/versions.env"

require_command git
require_command uv
require_command opa

uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"

opa_version_output="$(opa version)"
opa_actual="$(awk -F': ' '/^Version:/{print $2; exit}' <<<"$opa_version_output")"
[[ "$opa_actual" == "$OPA_VERSION" ]] || fail "OPA $OPA_VERSION is required; found ${opa_actual:-unknown}"

destination_actual="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)"
printf 'Destination revision: %s\n' "$destination_actual"
printf 'Deterministic instant:   %s\n' "$FIXED_INSTANT"
printf 'Toolchain: Python %s, uv %s, OPA %s\n' "$PYTHON_VERSION" "$UV_VERSION" "$OPA_VERSION"

assert_destination_clean() {
  local status
  status="$(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=all)"
  if [[ -n "$status" ]]; then
    printf '%s\n' "$status" >&2
    fail "destination source checkout has tracked or unignored changes"
  fi
}

assert_scenarios_clean() {
  assert_destination_clean
  local generated
  generated="$(find "$SOURCE_ROOT/projects" "$SCENARIOS_ROOT/projects" \
    -type f -path '*/generated/*' -print)"
  [[ -z "$generated" ]] || fail "generated artifacts escaped the temporary output directory: $generated"
}

assert_retired_configuration_surfaces_absent() {
  [[ ! -d "$INTEGRATION_ROOT/projects/configuration-demo" ]] ||
    fail "retired configuration-demo project is present"
  if grep -Eq '^[[:space:]]+configuration-demo:' "$INTEGRATION_ROOT/compliance.yaml"; then
    fail "retired configuration-demo project remains registered"
  fi

  local policy_configuration_inputs
  policy_configuration_inputs="$(find \
    "$INTEGRATION_ROOT/policy-sources/control-library/policies" \
    "$INTEGRATION_ROOT/policy-sources/verification-policy/policies" \
    -type f \( -path '*/configuration-intents/*' -o -iname '*configuration-intent*' \) \
    -print)"
  [[ -z "$policy_configuration_inputs" ]] ||
    fail "retired configuration-intent policy input is present: $policy_configuration_inputs"

  local configuration_output_paths
  configuration_output_paths="$(find \
    "$SCENARIOS_ROOT/projects" \
    "$INTEGRATION_ROOT/projects" \
    "$INTEGRATION_ROOT/verification/fixtures/iam-private-boundary" \
    -type f -name 'compliance.yaml' \
    -exec grep -l -E '^[[:space:]]+configuration:' {} \;)"
  [[ -z "$configuration_output_paths" ]] ||
    fail "retired configuration artifact output path is present: $configuration_output_paths"

  [[ ! -e "$TOOLING_ROOT/tools/configuration.py" ]] ||
    fail "retired in-core configuration implementation is present"
  local configuration_artifact_schemas
  configuration_artifact_schemas="$(find "$TOOLING_ROOT/tools/schemas" -type f \
    \( -name 'configuration-plan*.json' \
       -o -name 'configuration-render-result*.json' \
       -o -name 'configuration-explanation*.json' \) -print)"
  [[ -z "$configuration_artifact_schemas" ]] ||
    fail "retired configuration artifact schema is present: $configuration_artifact_schemas"

  local cli_help
  cli_help="$(tooling_run compliance --help)"
  if grep -Eq '^[[:space:]]+configuration[[:space:]]' <<<"$cli_help"; then
    fail "retired configuration command remains in the public CLI"
  fi
}

assert_scenarios_clean

RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-linux-hardening-rollout.XXXXXX")"
mkdir -p \
  "$RUN_ROOT/evidence" \
  "$RUN_ROOT/plans" \
  "$RUN_ROOT/results"

cd "$INTEGRATION_ROOT"
# These existing tooling interfaces use the explicit registry and temporary outputs.
export COMPLIANCE_EXAMPLE_PROJECT_REGISTRY="$INTEGRATION_ROOT/compliance.yaml"
export PYTHONDONTWRITEBYTECODE=1
export UV_PROJECT_ENVIRONMENT="$RUN_ROOT/venv"
uv sync --project "$TOOLING_ROOT" --frozen --python "$PYTHON_VERSION"
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; resolved $python_actual"
assert_retired_configuration_surfaces_absent

printf '\n== Static scenario contracts ==\n'
tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" config validate
tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" inventory validate
tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" policy validate
tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" waiver validate
tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" waiver list \
  --at "$FIXED_INSTANT" --format json > "$RUN_ROOT/waivers.json"

printf '\n== Deterministic fixture collection ==\n'
tooling_run python "$TOOLING_ROOT"/collectors/mock-api/collect.py \
  "$PROJECT_ROOT/fixtures" \
  "$RUN_ROOT/evidence" \
  --collected-at "$FIXED_INSTANT"

printf '\n== Fixed-time assessments ==\n'
for subject in host/standard-app-01 host/container-app-01; do
  tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" assessment run "$subject" \
    --evidence "$RUN_ROOT/evidence" \
    --plan-output "$RUN_ROOT/plans" \
    --output "$RUN_ROOT/results" \
    --waivers "$PROJECT_ROOT/waivers" \
    --at "$FIXED_INSTANT"
done

printf '\n== Contradictory persona safe refusal ==\n'
tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" plan render \
  host/persona-conflict-01 --output "$RUN_ROOT/plans"
if tooling_run compliance --config "$INTEGRATION_ROOT/compliance.yaml" --project "$PROJECT" assessment run \
  host/persona-conflict-01 \
  --evidence "$RUN_ROOT/evidence" \
  --plan-output "$RUN_ROOT/plans" \
  --output "$RUN_ROOT/results" \
  --waivers "$PROJECT_ROOT/waivers" \
  --at "$FIXED_INSTANT"; then
  fail "contradictory persona assessment unexpectedly succeeded"
fi
printf '\n== Machine-readable scenario assertions ==\n'
tooling_run python "$SCENARIOS_ROOT/scripts/assert-linux-hardening-rollout.py" \
  --scenario-root "$PROJECT_ROOT" \
  --run-root "$RUN_ROOT"
tooling_run python "$SCENARIOS_ROOT/scripts/assert-v4-composition.py" \
  --scenario-root "$PROJECT_ROOT" \
  --run-root "$RUN_ROOT"

tooling_run python "$SCENARIOS_ROOT/scripts/assert-policy-parameters.py" --integration-root "$INTEGRATION_ROOT"
tooling_run python "$SCENARIOS_ROOT/scripts/assert-semantic-anchors.py" \
  --integration-root "$INTEGRATION_ROOT" \
  --private-source "$INTEGRATION_ROOT/external-sources/environment-private"

tooling_run python "$SCENARIOS_ROOT/projects/authorized-software-composition/assert-scenario.py" \
  --integration-root "$INTEGRATION_ROOT"

printf '\n== Feature ownership/completeness integration ==\n'
tooling_run python "$TOOLING_ROOT"/examples/verify_examples.py --output "$RUN_ROOT/features"

printf '\n== Post-validation revisions and cleanliness ==\n'
"${COMPLIANCE_PYTHON:-python3}" "$SOURCE_ROOT/scripts/integration.py" verify --root "$INTEGRATION_ROOT"
assert_scenarios_clean
cleanup
[[ ! -e "$RUN_ROOT" ]] || fail "temporary generated outputs were not removed"
printf 'Scenario checkouts clean; temporary generated outputs removed: %s\n' "$RUN_ROOT"
RUN_ROOT=""

printf 'Deterministic verification-scenario validation passed.\n'
