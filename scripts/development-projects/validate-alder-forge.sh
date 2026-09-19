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
"${cli[@]}" framework validate
"${cli[@]}" coverage list assets --format json > "$RUN_ROOT/coverage-assets.json"
"${cli[@]}" coverage explain entity/alder-forge-defence-systems --format json > "$RUN_ROOT/coverage-entity.json"

printf '\n== Alder Forge declared framework history ==\n'
mkdir -p "$RUN_ROOT/framework/evidence" "$RUN_ROOT/framework/plans" "$RUN_ROOT/framework/results"
for fixture in "$PROJECT_ROOT/fixtures/technical"; do
  tooling_run python tooling/collectors/mock-api/collect.py "$fixture" "$RUN_ROOT/framework/evidence" --collected-at "$FIXED_INSTANT"
done
"${cli[@]}" assessment run --group alder-forge-legal-entity \
  --group corporate-linux-build-systems --group critical-saas-administration \
  --evidence "$RUN_ROOT/framework/evidence" \
  --plan-output "$RUN_ROOT/framework/plans" --output "$RUN_ROOT/framework/results" --at "$FIXED_INSTANT"
framework_anchor="$RUN_ROOT/framework/plans/entity__alder-forge-defence-systems.json"
"${cli[@]}" framework status alder-forge-defstan-dcc-level3 --revision 2026-09 \
  --plan "$framework_anchor" --assessed-plans "$RUN_ROOT/framework/plans" \
  --results "$RUN_ROOT/framework/results" --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" \
  --format json > "$RUN_ROOT/framework-status.json"
"${cli[@]}" framework explain alder-forge-defstan-dcc-level3 --revision 2026-09 \
  --plan "$framework_anchor" --assessed-plans "$RUN_ROOT/framework/plans" \
  --results "$RUN_ROOT/framework/results" --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" \
  --format json > "$RUN_ROOT/framework-explanation.json"
"${cli[@]}" framework status alder-forge-defstan-dcc-level3 --revision 2026-09 \
  --plan "$framework_anchor" --assessed-plans "$RUN_ROOT/framework/plans" \
  --results "$RUN_ROOT/framework/results" --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" \
  > "$RUN_ROOT/framework-status.txt"
"${cli[@]}" framework explain alder-forge-defstan-dcc-level3 --revision 2026-09 \
  --plan "$framework_anchor" --assessed-plans "$RUN_ROOT/framework/plans" \
  --results "$RUN_ROOT/framework/results" --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" \
  > "$RUN_ROOT/framework-explanation.txt"

printf '\n== Alder Forge direct technical and MFA Objective checks ==\n'
mkdir -p "$RUN_ROOT/technical/evidence" "$RUN_ROOT/technical/plans" "$RUN_ROOT/technical/results"
tooling_run python tooling/collectors/mock-api/collect.py \
  "$PROJECT_ROOT/fixtures/technical" "$RUN_ROOT/technical/evidence" --collected-at "$FIXED_INSTANT"
for subject in host/alder-build-01 saas/alder-admin-tenant; do
  "${cli[@]}" assessment run "$subject" --evidence "$RUN_ROOT/technical/evidence" \
    --plan-output "$RUN_ROOT/technical/plans" --output "$RUN_ROOT/technical/results" \
    --at "$FIXED_INSTANT"
done

printf '\n== Alder Forge runtime assertions ==\n'
tooling_run python "$SOURCE_ROOT/scripts/development-projects/assert-alder-forge.py" \
  --run-root "$RUN_ROOT" --project-root "$PROJECT_ROOT" \
  --control-library-root "$ASSEMBLY_ROOT/policy-sources/control-library/policies"

finish_validation
cleanup
[[ ! -e "$RUN_ROOT" ]] || fail "temporary generated outputs were not removed"
printf 'Alder Forge project validation passed; generated outputs removed.\n'
