#!/usr/bin/env bash
set -euo pipefail

VERIFY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY_ROOT="$(cd -- "$VERIFY_ROOT/../.." && pwd)"
# shellcheck disable=SC1091
source "$REPOSITORY_ROOT/toolchain/versions.env"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ "$#" == 0 ]] || fail "usage: $0"
TOOLING_INPUT="$REPOSITORY_ROOT/tooling"
CONTROL_LIBRARY_INPUT="$REPOSITORY_ROOT/policy-sources/control-library"

for command in git uv opa tar; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done
[[ -f "$TOOLING_INPUT/pyproject.toml" ]] \
  || fail "co-located tooling root is unavailable: $TOOLING_INPUT"
[[ -d "$CONTROL_LIBRARY_INPUT/policies" ]] \
  || fail "co-located control-library policy root is unavailable: $CONTROL_LIBRARY_INPUT/policies"

assert_repository_clean() {
  local status
  status="$(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=all)"
  [[ -z "$status" ]] \
    || fail "destination repository has tracked or unignored changes: $status"
}

repository_actual="$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)"
if [[ -n "${COMPLIANCE_VERIFICATION_POLICY_SHA:-}" ]]; then
  [[ "$repository_actual" == "$COMPLIANCE_VERIFICATION_POLICY_SHA" ]] \
    || fail "destination revision mismatch: expected $COMPLIANCE_VERIFICATION_POLICY_SHA, found $repository_actual"
fi
assert_repository_clean

uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"
opa_actual="$(opa version | awk -F': ' '/^Version:/{print $2}')"
[[ "$opa_actual" == "$OPA_VERSION" ]] || fail "OPA $OPA_VERSION is required; found $opa_actual"

RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-verification-policy-validation.XXXXXX")"
cleanup() { rm -rf -- "$RUN_ROOT"; }
trap cleanup EXIT
EXPORT_ROOT="$RUN_ROOT/source"
mkdir "$EXPORT_ROOT"
# Consume only the three explicit component roots from the same committed
# destination revision. Local edits are not consumed, and Git is unnecessary
# after export.
git -C "$REPOSITORY_ROOT" archive "$repository_actual" \
  toolchain tooling policy-sources/control-library policy-sources/verification-policy \
  | tar -x -C "$EXPORT_ROOT"
TOOLING_ROOT="$EXPORT_ROOT/tooling"
export COMPLIANCE_CONTROL_LIBRARY_ROOT="$EXPORT_ROOT/policy-sources/control-library"
POLICY_ROOT="$EXPORT_ROOT/policy-sources/verification-policy"
export UV_PROJECT_ENVIRONMENT="$RUN_ROOT/venv"
export PYTHONDONTWRITEBYTECODE=1
tooling_run() { uv run --project "$TOOLING_ROOT" --frozen "$@"; }
uv sync --project "$TOOLING_ROOT" --frozen --python "$PYTHON_VERSION"
python_actual="$(tooling_run python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] || fail "Python $PYTHON_VERSION is required; found $python_actual"
printf 'Destination revision: %s\n' "$repository_actual"
printf 'Semantic source: verification-policy (%s)\n' \
  'policy-sources/verification-policy/policies/'
printf 'Tooling root: tooling/ (same destination revision)\n'
printf 'Control-library root: policy-sources/control-library/ (same destination revision)\n'
printf 'Toolchain: Python %s, uv %s, OPA %s\n' \
  "$PYTHON_VERSION" "$UV_VERSION" "$OPA_VERSION"

printf '\n== Partial source ownership boundary ==\n'
tooling_run python "$POLICY_ROOT/scripts/check-source-boundary.py" "$POLICY_ROOT/policies"

printf '\n== Deterministic source-tree identity ==\n'
policy_digest="$(tooling_run python - "$POLICY_ROOT/policies" <<'PY'
import sys
from pathlib import Path

from tools.policy_sources import source_tree_digest

print(source_tree_digest(Path(sys.argv[1])))
PY
)"
materialized_policy_root="$RUN_ROOT/materialized/verification-policy/policies"
mkdir -p "$materialized_policy_root"
cp -R "$POLICY_ROOT/policies/." "$materialized_policy_root/"
materialized_policy_digest="$(tooling_run python - "$materialized_policy_root" <<'PY'
import sys
from pathlib import Path

from tools.policy_sources import source_tree_digest

print(source_tree_digest(Path(sys.argv[1])))
PY
)"
[[ "$materialized_policy_digest" == "$policy_digest" ]] \
  || fail "materialized policy content digest differs from owning source"
printf 'Policy source content digest: %s\n' "$policy_digest"

printf '\n== All resources, schemas, references, and Rego entrypoints ==\n'
# An empty temporary cwd prevents unrelated configuration discovery. Both named
# policy roots are explicit; no inventory, assignments, or consumer project is needed.
(cd "$RUN_ROOT" && tooling_run compliance policy validate \
  --policy-source "control-library=$COMPLIANCE_CONTROL_LIBRARY_ROOT/policies" \
  --policy-source "verification-policy=$materialized_policy_root" --format json)
printf '\n== Repository-owned source and negative contract tests ==\n'
tooling_run python -m unittest discover -s "$POLICY_ROOT/tests" -p 'test_verification_policy_source.py' -v

printf '\n== Post-validation source and cleanliness ==\n'
tooling_run python "$POLICY_ROOT/scripts/check-source-boundary.py" "$POLICY_ROOT/policies"
[[ "$(git -C "$REPOSITORY_ROOT" rev-parse HEAD)" == "$repository_actual" ]] \
  || fail "destination revision changed during validation"
assert_repository_clean
cleanup
[[ ! -e "$RUN_ROOT" ]] || fail "temporary outputs were not removed"
printf 'Destination checkout clean; temporary outputs removed.\nVerification-policy validation passed.\n'
