#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY_ROOT="$(cd -- "$SOURCE_ROOT/../.." && pwd)"
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
[[ "$#" == 0 ]] || fail "usage: $0"
TOOLING_INPUT="$REPOSITORY_ROOT/tooling"
# shellcheck disable=SC1091
source "$REPOSITORY_ROOT/toolchain/versions.env"

for command in git uv opa tar; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done
[[ -f "$TOOLING_INPUT/pyproject.toml" ]] \
  || fail "co-located tooling root is unavailable: $TOOLING_INPUT"
uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"
opa_actual="$(opa version | awk -F': ' '/^Version:/{print $2}')"
[[ "$opa_actual" == "$OPA_VERSION" ]] || fail "OPA $OPA_VERSION is required; found ${opa_actual:-unknown}"

repository_actual="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)"
if [[ -n "${COMPLIANCE_CONTROL_LIBRARY_SHA:-}" ]]; then
  [[ "$repository_actual" == "$COMPLIANCE_CONTROL_LIBRARY_SHA" ]] \
    || fail "destination revision mismatch: expected $COMPLIANCE_CONTROL_LIBRARY_SHA, found $repository_actual"
fi
assert_repository_clean() {
  local repository_status
  repository_status="$(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=all)"
  [[ -z "$repository_status" ]] \
    || fail "destination repository has tracked or unignored changes: $repository_status"
}
assert_repository_clean
printf 'Destination revision: %s\n' "$repository_actual"
printf 'Semantic source: control-library (%s)\n' \
  'policy-sources/control-library/policies/'
printf 'Tooling root: tooling/ (same destination revision)\n'
printf 'Toolchain: Python %s, uv %s, OPA %s\n' "$PYTHON_VERSION" "$UV_VERSION" "$OPA_VERSION"

temporary="$(mktemp -d "${TMPDIR:-/tmp}/control-library-validation.XXXXXX")"
cleanup() { rm -rf -- "$temporary"; }
trap cleanup EXIT
EXPORT_ROOT="$temporary/source"
mkdir "$EXPORT_ROOT"
# Consume only the two component roots from the same committed destination
# revision. Local edits and Python environments are not consumed, and Git is
# not needed after export.
git -C "$REPOSITORY_ROOT" archive "$repository_actual" \
  toolchain tooling policy-sources/control-library | tar -x -C "$EXPORT_ROOT"
TOOLING_ROOT="$EXPORT_ROOT/tooling"
POLICY_ROOT="$EXPORT_ROOT/policy-sources/control-library"
export UV_PROJECT_ENVIRONMENT="$temporary/venv"
export PYTHONDONTWRITEBYTECODE=1
tooling_run() { uv run --project "$TOOLING_ROOT" --frozen "$@"; }
cd "$POLICY_ROOT"
uv sync --project "$TOOLING_ROOT" --frozen --python "$PYTHON_VERSION"
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; resolved $python_actual"

printf '\n== Library resources, schemas, references and source boundary ==\n'
tooling_run python -m unittest discover -s "$POLICY_ROOT/tests" -p 'test_policy_resources.py'

printf '\n== Generic control-library source/release/archive contract ==\n'
COMPLIANCE_CONTROL_LIBRARY_SHA="$repository_actual" \
  tooling_run bash "$POLICY_ROOT/scripts/validate-policy-release.sh"

printf '\n== Control-library Rego formatting ==\n'
opa fmt --diff --fail "$POLICY_ROOT/policies/controls"
printf '\n== Control-library Rego tests ==\n'
opa test "$POLICY_ROOT/policies/controls"

[[ "$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)" == "$repository_actual" ]] \
  || fail "destination revision changed during validation"
assert_repository_clean
cleanup
[[ ! -e "$temporary" ]] || fail "temporary validation outputs were not removed"
printf 'Destination checkout clean; temporary outputs removed.\n'
printf 'Standard control-library validation passed.\n'
