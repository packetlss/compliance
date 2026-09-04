#!/usr/bin/env bash
set -euo pipefail

TOOLING_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

# shellcheck disable=SC1091
source "$TOOLING_ROOT/scripts/ci-versions.env"
for command in git uv opa; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done

uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"
opa_actual="$(opa version | awk -F': ' '/^Version:/{print $2}')"
[[ "$opa_actual" == "$OPA_VERSION" ]] || fail "OPA $OPA_VERSION is required; found ${opa_actual:-unknown}"

tooling_actual="$(git -C "$TOOLING_ROOT" rev-parse HEAD)"
if [[ -n "${COMPLIANCE_TOOLING_SHA:-}" ]]; then
  [[ "$tooling_actual" == "$COMPLIANCE_TOOLING_SHA" ]] \
    || fail "tooling revision mismatch: expected $COMPLIANCE_TOOLING_SHA, found $tooling_actual"
fi
printf 'Tooling revision: %s\n' "$tooling_actual"
printf 'Toolchain: Python %s, uv %s, OPA %s\n' "$PYTHON_VERSION" "$UV_VERSION" "$OPA_VERSION"

assert_tooling_clean() {
  local status
  status="$(git -C "$TOOLING_ROOT" status --porcelain --untracked-files=all)"
  if [[ -n "$status" ]]; then
    printf '%s\n' "$status" >&2
    fail "tooling has tracked or unignored changes; commit before running the canonical gate"
  fi
}
assert_tooling_clean
cd "$TOOLING_ROOT"
export PYTHONDONTWRITEBYTECODE=1
uv sync --project "$TOOLING_ROOT" --frozen --python "$PYTHON_VERSION"
python_actual="$(uv run --project "$TOOLING_ROOT" --frozen python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; resolved $python_actual"

printf '\n== Tooling unit and contract suite ==\n'
uv run --project "$TOOLING_ROOT" --frozen python -m unittest discover -s tests -v

[[ "$(git -C "$TOOLING_ROOT" rev-parse HEAD)" == "$tooling_actual" ]] \
  || fail "tooling revision changed during validation"
assert_tooling_clean
printf 'Tooling validation passed; repository clean.\n'
