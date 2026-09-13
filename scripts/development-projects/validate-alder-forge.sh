#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=validation-common.sh
source "$SCRIPT_ROOT/validation-common.sh"
initialize_validation "$@"

PROJECT="alder-forge-dcc-level3"
PROJECT_ROOT="$DEV_ROOT/projects/$PROJECT"
RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-alder-forge.XXXXXX")"
cleanup() {
  rm -rf -- "$RUN_ROOT"
}
trap cleanup EXIT

cd "$ASSEMBLY_ROOT"
export UV_PROJECT_ENVIRONMENT="$RUN_ROOT/venv"
uv sync --project "$ASSEMBLY_ROOT/tooling" --frozen --python "$PYTHON_VERSION"
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; resolved $python_actual"

cli=(tooling_run compliance --config "$ASSEMBLY_ROOT/compliance.yaml" --project "$PROJECT")

printf '\n== Alder Forge static contracts and current views ==\n'
"${cli[@]}" config validate
"${cli[@]}" inventory validate
"${cli[@]}" policy validate
"${cli[@]}" waiver validate
"${cli[@]}" coverage list assets --format json > "$RUN_ROOT/coverage-assets.json"
"${cli[@]}" coverage explain entity/alder-forge-defence-systems --format json > "$RUN_ROOT/coverage-entity.json"

printf '\n== Alder Forge bounded organisational assertion snapshots ==\n'
for case in certification board-direction risk-assessment software-review awareness-training; do
  case_root="$RUN_ROOT/organization/$case"
  mkdir -p "$case_root/evidence" "$case_root/plans" "$case_root/results"
  tooling_run python tooling/collectors/mock-api/collect.py \
    "$PROJECT_ROOT/fixtures/organization-assertions/$case" "$case_root/evidence" \
    --collected-at "$FIXED_INSTANT"
  "${cli[@]}" assessment run entity/alder-forge-defence-systems \
    --evidence "$case_root/evidence" --plan-output "$case_root/plans" \
    --output "$case_root/results" --at "$FIXED_INSTANT"
done

printf '\n== Alder Forge direct technical and MFA Objective checks ==\n'
mkdir -p "$RUN_ROOT/technical/evidence" "$RUN_ROOT/technical/plans" "$RUN_ROOT/technical/results"
tooling_run python tooling/collectors/mock-api/collect.py \
  "$PROJECT_ROOT/fixtures/technical" "$RUN_ROOT/technical/evidence" --collected-at "$FIXED_INSTANT"
for subject in host/alder-build-01 saas/alder-admin-tenant; do
  "${cli[@]}" assessment run "$subject" --evidence "$RUN_ROOT/technical/evidence" \
    --plan-output "$RUN_ROOT/technical/plans" --output "$RUN_ROOT/technical/results" \
    --at "$FIXED_INSTANT"
done

printf '\n== Alder Forge frozen historical explanation and mappings ==\n'
anchor="$RUN_ROOT/organization/certification/plans/entity__alder-forge-defence-systems.json"
history=(--plan "$anchor" --assessed-plans "$RUN_ROOT/organization/certification/plans" \
  --results "$RUN_ROOT/organization/certification/results" --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT")
"${cli[@]}" assessment explain entity/alder-forge-defence-systems "${history[@]}" \
  --format json > "$RUN_ROOT/entity-explain.json"
"${cli[@]}" assessment mappings "${history[@]}" --format json > "$RUN_ROOT/entity-mappings.json"

printf '\n== Alder Forge runtime assertions ==\n'
tooling_run python "$SOURCE_ROOT/scripts/development-projects/assert-alder-forge.py" \
  --run-root "$RUN_ROOT" --project-root "$PROJECT_ROOT" \
  --control-library-root "$ASSEMBLY_ROOT/policy-sources/control-library/policies"

finish_validation
cleanup
[[ ! -e "$RUN_ROOT" ]] || fail "temporary generated outputs were not removed"
printf 'Alder Forge project validation passed; generated outputs removed.\n'
