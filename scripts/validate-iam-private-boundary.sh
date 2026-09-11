#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_ROOT="$SOURCE_ROOT/scripts/iam-private-boundary"
ASSEMBLY_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-iam-boundary-assembly.XXXXXX")"
RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-iam-boundary-run.XXXXXX")"
REPOSITORY_REVISION=""
cleanup() {
  rm -rf -- "$ASSEMBLY_ROOT" "$RUN_ROOT"
}
trap cleanup EXIT

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH="$SCRIPT_ROOT" "${COMPLIANCE_PYTHON:-python3}" -m unittest discover \
  -s "$SOURCE_ROOT/tests/iam-private-boundary" -p 'test_*.py' -v

"${COMPLIANCE_PYTHON:-python3}" "$SCRIPT_ROOT/validation_inputs.py" assemble --root "$ASSEMBLY_ROOT"

# shellcheck source=../toolchain/versions.env
source "$SOURCE_ROOT/toolchain/versions.env"
for command in git uv opa tar; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done
REPOSITORY_REVISION="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
if [[ -n "${COMPLIANCE_IAM_PRIVATE_BOUNDARY_SHA:-}" ]]; then
  [[ "$REPOSITORY_REVISION" == "$COMPLIANCE_IAM_PRIVATE_BOUNDARY_SHA" ]] \
    || fail "destination revision mismatch: expected $COMPLIANCE_IAM_PRIVATE_BOUNDARY_SHA, found $REPOSITORY_REVISION"
fi
uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION required; found $uv_actual"
opa_actual="$(opa version | awk -F': ' '/^Version:/{print $2}')"
[[ "$opa_actual" == "$OPA_VERSION" ]] || fail "OPA $OPA_VERSION required; found $opa_actual"

FIXTURE_ROOT="$ASSEMBLY_ROOT/verification/fixtures/iam-private-boundary"
PRIVATE_ROOT="$ASSEMBLY_ROOT/external-sources/environment-private"
CONTROL_LIBRARY_ROOT="$ASSEMBLY_ROOT/policy-sources/control-library/policies"
VERIFICATION_ROOT="$ASSEMBLY_ROOT/policy-sources/verification-policy/policies"
CONFIG="$FIXTURE_ROOT/compliance.yaml"
FIXED_INSTANT="2026-09-01T00:00:00Z"

mkdir -p "$RUN_ROOT/evidence" "$RUN_ROOT/plans" "$RUN_ROOT/results"
export UV_PROJECT_ENVIRONMENT="$RUN_ROOT/venv"
uv sync --project "$ASSEMBLY_ROOT/tooling" --frozen --python "$PYTHON_VERSION"
tooling_run() {
  uv run --project "$ASSEMBLY_ROOT/tooling" --frozen "$@"
}
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] \
  || fail "Python $PYTHON_VERSION is required; resolved $python_actual"

printf '\n== IAM independent-source layout ==\n'
printf 'Destination revision: %s\n' "$REPOSITORY_REVISION"
printf 'Temporary non-Git assembly: %s\n' "$ASSEMBLY_ROOT"
printf 'control-library: %s\n' "$CONTROL_LIBRARY_ROOT"
printf 'verification-policy: %s\n' "$VERIFICATION_ROOT"
printf 'environment-private: %s\n' "$PRIVATE_ROOT"
[[ ! -e "$FIXTURE_ROOT/policy" ]] \
  || fail "fixture policy remained available to the execution assembly"

cli=(tooling_run compliance --config "$CONFIG")

printf '\n== IAM static contracts ==\n'
"${cli[@]}" config show --format json > "$RUN_ROOT/config.json"
"${cli[@]}" config validate
"${cli[@]}" inventory validate
"${cli[@]}" policy validate

printf '\n== IAM deterministic evidence and assessment ==\n'
tooling_run python tooling/collectors/mock-api/collect.py \
  "$FIXTURE_ROOT/fixtures" \
  "$RUN_ROOT/evidence" \
  --collected-at "$FIXED_INSTANT"
"${cli[@]}" assessment run host/restricted-linux-01 \
  --evidence "$RUN_ROOT/evidence" \
  --plan-output "$RUN_ROOT/plans" \
  --output "$RUN_ROOT/results" \
  --at "$FIXED_INSTANT"
"${cli[@]}" assessment status \
  --plan "$RUN_ROOT/plans/host__restricted-linux-01.json" \
  --assessed-plans "$RUN_ROOT/plans" --results "$RUN_ROOT/results" \
  --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" \
  --format json > "$RUN_ROOT/status.json"
"${cli[@]}" assessment mappings \
  --plan "$RUN_ROOT/plans/host__restricted-linux-01.json" \
  --assessed-plans "$RUN_ROOT/plans" --results "$RUN_ROOT/results" \
  --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" \
  --format json > "$RUN_ROOT/mappings.json"
"${cli[@]}" assessment explain host/restricted-linux-01 \
  --plan "$RUN_ROOT/plans/host__restricted-linux-01.json" \
  --assessed-plans "$RUN_ROOT/plans" --results "$RUN_ROOT/results" \
  --at "$FIXED_INSTANT" --as-of "$FIXED_INSTANT" > "$RUN_ROOT/explain.txt"

printf '\n== IAM runtime and provenance assertions ==\n'
tooling_run python "$SCRIPT_ROOT/assert-iam-private-boundary.py" \
  --assembly-root "$ASSEMBLY_ROOT" \
  --run-root "$RUN_ROOT"

tooling_run python "$SCRIPT_ROOT/assert-v4-cases.py" \
  --assembly-root "$ASSEMBLY_ROOT" \
  --run-root "$RUN_ROOT"

"${COMPLIANCE_PYTHON:-python3}" "$SCRIPT_ROOT/validation_inputs.py" verify --root "$ASSEMBLY_ROOT"
[[ "$(git -C "$SOURCE_ROOT" rev-parse HEAD)" == "$REPOSITORY_REVISION" ]] \
  || fail "destination revision changed during IAM validation"
status="$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=all)"
[[ -z "$status" ]] || {
  printf '%s\n' "$status" >&2
  fail "destination checkout became dirty during IAM validation"
}
generated="$(find "$SOURCE_ROOT/verification/fixtures/iam-private-boundary" "$ASSEMBLY_ROOT" \
  -type f -path '*/generated/*' -print)"
[[ -z "$generated" ]] || fail "generated IAM artifacts escaped temporary outputs: $generated"

cleanup
[[ ! -e "$ASSEMBLY_ROOT" && ! -e "$RUN_ROOT" ]] \
  || fail "temporary IAM assembly or generated output was not removed"
printf 'IAM private-boundary validation passed; temporary outputs removed.\n'
