#!/usr/bin/env bash
set -euo pipefail

TOOLING_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
REPOSITORY_ROOT="$(cd -- "$TOOLING_ROOT/.." && pwd)"
# shellcheck disable=SC1091
source "$REPOSITORY_ROOT/toolchain/versions.env"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

command -v uv >/dev/null 2>&1 || fail "uv is required"
command -v python >/dev/null 2>&1 || fail "python is required"
uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"

temporary="$(mktemp -d "${TMPDIR:-/tmp}/compliance-locked-artifacts.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT
mkdir -p "$temporary/dist" "$temporary/runtime/project/materialized/shared"

source_digest="$(python - "$TOOLING_ROOT" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from tools.tooling_source import tooling_source_digest
print(tooling_source_digest(Path(sys.argv[1])))
PY
)"
python "$TOOLING_ROOT/scripts/build-wheel.py" \
  --source-digest "$source_digest" \
  --output-dir "$temporary/dist"
set -- "$temporary/dist"/*.whl
[[ "$#" -eq 1 && -f "$1" ]] || fail "expected exactly one wheel"
wheel="$1"
[[ "$(basename "$wheel")" == compliance_tooling-*.whl ]] || fail "expected compliance_tooling wheel name"
wheel_sha="sha256:$(sha256sum "$wheel" | awk '{print $1}')"

python -m venv "$temporary/venv"
venv_python="$temporary/venv/bin/python"
venv_compliance="$temporary/venv/bin/compliance"
python "$TOOLING_ROOT/scripts/install-locked-wheel.py" \
  --python "$venv_python" \
  --wheel "$wheel" \
  --cache-dir "$temporary/uv-cache"

# All installed-package imports below must resolve from the wheel, not the source checkout.
cd "$temporary/runtime"

# Exercise native v4 construction, loading and locked equivalence using only installed modules.
"$venv_python" -I "$TOOLING_ROOT/scripts/check-installed-assessment.py"
printf 'Installed successor locked-artifact validation passed.\n'
