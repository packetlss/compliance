#!/usr/bin/env bash
# Shared setup for the repository's focused project validators.

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

tooling_run() {
  uv run --project "$ASSEMBLY_ROOT/tooling" --frozen "$@"
}

assert_projects_clean() {
  local status generated
  status="$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=all)"
  [[ -z "$status" ]] || {
    printf '%s\n' "$status" >&2
    fail "destination checkout is dirty: $SOURCE_ROOT"
  }
  generated="$(find "$SOURCE_ROOT/projects" "$ASSEMBLY_ROOT/projects" -type f -path '*/generated/*' -print)"
  [[ -z "$generated" ]] || fail "generated artifacts escaped temporary outputs: $generated"
}

initialize_validation() {
  [[ "$#" == 2 && "$1" == --assembly-root ]] || fail "expected --assembly-root TEMPORARY_ASSEMBLY"
  SOURCE_ROOT="$(cd -- "$SCRIPT_ROOT/../.." && pwd)"
  ASSEMBLY_ROOT="$(cd -- "$2" && pwd)"
  DEV_ROOT="$ASSEMBLY_ROOT"
  FIXED_INSTANT="2026-09-01T00:00:00Z"
  export PYTHONDONTWRITEBYTECODE=1
  python3 "$SOURCE_ROOT/scripts/development-projects/validation_inputs.py" verify --root "$ASSEMBLY_ROOT"
  # shellcheck source=../../toolchain/versions.env
  source "$SOURCE_ROOT/toolchain/versions.env"
  local command uv_actual opa_actual
  for command in git uv opa tar; do
    command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
  done
  REPOSITORY_REVISION="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
  if [[ -n "${COMPLIANCE_DEVELOPMENT_PROJECTS_SHA:-}" ]]; then
    [[ "$REPOSITORY_REVISION" == "$COMPLIANCE_DEVELOPMENT_PROJECTS_SHA" ]] \
      || fail "destination revision mismatch: expected $COMPLIANCE_DEVELOPMENT_PROJECTS_SHA, found $REPOSITORY_REVISION"
  fi
  uv_actual="$(uv --version | awk '{print $2}')"
  [[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION required; found $uv_actual"
  opa_actual="$(opa version | awk -F': ' '/^Version:/{print $2}')"
  [[ "$opa_actual" == "$OPA_VERSION" ]] || fail "OPA $OPA_VERSION required; found $opa_actual"
  assert_projects_clean
  printf 'Destination revision: %s\n' "$REPOSITORY_REVISION"
  printf 'Explicit roots: tooling/, policy-sources/control-library/, policy-sources/verification-policy/, projects/\n'
  printf 'Deterministic instant: %s\n' "$FIXED_INSTANT"
}

finish_validation() {
  python3 "$SOURCE_ROOT/scripts/development-projects/validation_inputs.py" verify --root "$ASSEMBLY_ROOT"
  [[ "$(git -C "$SOURCE_ROOT" rev-parse HEAD)" == "$REPOSITORY_REVISION" ]] \
    || fail "destination revision changed during validation"
  assert_projects_clean
}
