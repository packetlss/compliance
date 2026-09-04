#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=validation-common.sh
source "$SCRIPT_ROOT/validation-common.sh"
initialize_validation "$@"
PROJECT="server-personas"
PROJECT_ROOT="$DEV_ROOT/projects/$PROJECT"
RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-server-personas.XXXXXX")"
cleanup() {
  rm -rf -- "$RUN_ROOT"
}
trap cleanup EXIT

mkdir -p \
  "$RUN_ROOT/evidence" \
  "$RUN_ROOT/plans" \
  "$RUN_ROOT/results"

cd "$ASSEMBLY_ROOT"
export UV_PROJECT_ENVIRONMENT="$RUN_ROOT/venv"
uv sync --project "$ASSEMBLY_ROOT/tooling" --frozen --python "$PYTHON_VERSION"
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; resolved $python_actual"

cli=(tooling_run compliance --config "$ASSEMBLY_ROOT/compliance.yaml" --project "$PROJECT")

printf '\n== Server-personas static contracts ==\n'
"${cli[@]}" config validate
"${cli[@]}" inventory validate
"${cli[@]}" policy validate
"${cli[@]}" waiver validate
"${cli[@]}" waiver list --at "$FIXED_INSTANT" --format json > "$RUN_ROOT/waivers.json"

printf '\n== Server-personas deterministic fixture collection ==\n'
tooling_run python tooling/collectors/mock-api/collect.py \
  "$PROJECT_ROOT/fixtures" \
  "$RUN_ROOT/evidence" \
  --collected-at "$FIXED_INSTANT"

printf '\n== Standard and container assessments ==\n'
for subject in host/standard-app-01 host/container-app-01; do
  "${cli[@]}" assessment run "$subject" \
    --evidence "$RUN_ROOT/evidence" \
    --plan-output "$RUN_ROOT/plans" \
    --output "$RUN_ROOT/results" \
    --waivers "$PROJECT_ROOT/waivers" \
    --at "$FIXED_INSTANT"
done

printf '\n== Contradictory persona safe refusal ==\n'
"${cli[@]}" plan render host/persona-conflict-01 --output "$RUN_ROOT/plans"
set +e
"${cli[@]}" assessment run host/persona-conflict-01 \
  --evidence "$RUN_ROOT/evidence" \
  --plan-output "$RUN_ROOT/plans" \
  --output "$RUN_ROOT/results" \
  --waivers "$PROJECT_ROOT/waivers" \
  --at "$FIXED_INSTANT"
conflict_rc=$?
set -e
[[ "$conflict_rc" -eq 1 ]] || fail "persona conflict assessment exited $conflict_rc, expected 1"

printf '\n== Server-personas runtime assertions ==\n'
tooling_run python "$SOURCE_ROOT/scripts/development-projects/assert-server-personas.py" \
  --run-root "$RUN_ROOT"

finish_validation
cleanup
[[ ! -e "$RUN_ROOT" ]] || fail "temporary generated outputs were not removed"
printf 'Project validation passed; generated outputs removed.\n'
