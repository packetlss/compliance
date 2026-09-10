#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=validation-common.sh
source "$SCRIPT_ROOT/validation-common.sh"
initialize_validation "$@"
MOCK_PROJECT="mock-fleet"
MOCK_PROJECT_ROOT="$DEV_ROOT/projects/$MOCK_PROJECT"
RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-development-projects.XXXXXX")"
MOCK_RUN_ROOT="$RUN_ROOT/mock-fleet"
cleanup() {
  rm -rf -- "$RUN_ROOT"
}
trap cleanup EXIT

mkdir -p \
  "$MOCK_RUN_ROOT/evidence" \
  "$MOCK_RUN_ROOT/empty-evidence" \
  "$MOCK_RUN_ROOT/plans" \
  "$MOCK_RUN_ROOT/results" \
  "$MOCK_RUN_ROOT/unknown-plans" \
  "$MOCK_RUN_ROOT/unknown-results"

cd "$ASSEMBLY_ROOT"
export UV_PROJECT_ENVIRONMENT="$RUN_ROOT/venv"
uv sync --project "$ASSEMBLY_ROOT/tooling" --frozen --python "$PYTHON_VERSION"
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; resolved $python_actual"

mock_cli=(tooling_run compliance --config "$ASSEMBLY_ROOT/compliance.yaml" --project "$MOCK_PROJECT")

printf '\n== Mock-fleet static contracts ==\n'
"${mock_cli[@]}" config validate
"${mock_cli[@]}" inventory validate
"${mock_cli[@]}" policy validate
"${mock_cli[@]}" waiver validate

printf '\n== Mock-fleet deterministic fixture collection ==\n'
tooling_run python tooling/collectors/mock-api/collect.py \
  "$MOCK_PROJECT_ROOT/fixtures" \
  "$MOCK_RUN_ROOT/evidence" \
  --collected-at "$FIXED_INSTANT"

printf '\n== Mock-fleet assessment plans and fixed-time results ==\n'
"${mock_cli[@]}" assessment run --all \
  --evidence "$MOCK_RUN_ROOT/evidence" \
  --plan-output "$MOCK_RUN_ROOT/plans" \
  --output "$MOCK_RUN_ROOT/results" \
  --at "$FIXED_INSTANT"
mock_anchor="$MOCK_RUN_ROOT/plans/cloud-account__aws-111122223333.json"
mapping_args=(--plan "$mock_anchor" --assessed-plans "$MOCK_RUN_ROOT/plans" \
  --results "$MOCK_RUN_ROOT/results" --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT")
"${mock_cli[@]}" assessment mappings "${mapping_args[@]}" \
  --format json > "$MOCK_RUN_ROOT/mappings.json"
"${mock_cli[@]}" assessment mappings "${mapping_args[@]}" \
  --group aws-production-accounts --format json > "$MOCK_RUN_ROOT/mappings-aws.json"
"${mock_cli[@]}" assessment mappings "${mapping_args[@]}" \
  --group production-saas-tenants --format json > "$MOCK_RUN_ROOT/mappings-saas.json"
"${mock_cli[@]}" assessment mappings "${mapping_args[@]}" \
  --reference AWS-Security-Hub:S3.1 --level technical \
  --format json > "$MOCK_RUN_ROOT/mappings-s3.json"

printf '\n== Mock-fleet missing-evidence behavior ==\n'
"${mock_cli[@]}" assessment run saas/acme-projects/company \
  --evidence "$MOCK_RUN_ROOT/empty-evidence" \
  --plan-output "$MOCK_RUN_ROOT/unknown-plans" \
  --output "$MOCK_RUN_ROOT/unknown-results" \
  --at "$FIXED_INSTANT"

printf '\n== Mock-fleet runtime assertions ==\n'
tooling_run python "$SOURCE_ROOT/scripts/development-projects/assert-mock-fleet.py" \
  --run-root "$MOCK_RUN_ROOT"

tooling_run python "$SOURCE_ROOT/scripts/development-projects/assert-provenance.py" \
  --assembly-root "$ASSEMBLY_ROOT" --run-root "$MOCK_RUN_ROOT" --project "$MOCK_PROJECT"

finish_validation
cleanup
[[ ! -e "$RUN_ROOT" ]] || fail "temporary generated outputs were not removed"
printf 'Project validation passed; generated outputs removed.\n'
