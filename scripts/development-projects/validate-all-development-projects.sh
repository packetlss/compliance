#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
ASSEMBLY_ROOT=""
OWN_ASSEMBLY=false
cleanup() {
  if [[ "$OWN_ASSEMBLY" == true && -n "$ASSEMBLY_ROOT" ]]; then
    rm -rf -- "$ASSEMBLY_ROOT"
  fi
}
trap cleanup EXIT

source_root="$(cd -- "$SCRIPT_ROOT/../.." && pwd)"
removed_pattern='configuration-demo|configuration[[:space:]]+(plan|render|show|explain)|configuration-(plan|render-result|explanation)|--adapter|[Aa]nsible|cloud-init|[Tt]erraform|rendered backend|backend artifacts'
removed_matches="$(
  git -C "$source_root" grep -n -E "$removed_pattern" \
    -- projects validation/development-projects scripts/development-projects \
       tests/development-projects \
       ':(exclude)scripts/development-projects/validate-all-development-projects.sh' || true
)"
if [[ -n "$removed_matches" ]]; then
  printf '%s\n' "$removed_matches" >&2
  printf 'ERROR: removed configuration-generation surface remains in active source\n' >&2
  exit 1
fi
[[ ! -e "$source_root/projects/configuration-demo" ]] || {
  printf 'ERROR: removed project root still exists\n' >&2
  exit 1
}
[[ ! -e "$source_root/scripts/development-projects/assert-configuration-demo.py" ]] || {
  printf 'ERROR: removed project assertion still exists\n' >&2
  exit 1
}

PYTHONPATH="$SCRIPT_ROOT" "${COMPLIANCE_PYTHON:-python3}" -m unittest discover \
  -s "$source_root/tests/development-projects" -p 'test_*.py' -v
if [[ "$#" == 2 && "$1" == --assembly-root ]]; then
  ASSEMBLY_ROOT="$2"
elif [[ "$#" == 0 ]]; then
  ASSEMBLY_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-project-validation.XXXXXX")"
  OWN_ASSEMBLY=true
  "${COMPLIANCE_PYTHON:-python3}" "$SCRIPT_ROOT/validation_inputs.py" assemble --root "$ASSEMBLY_ROOT"
else
  printf 'Usage: %s [--assembly-root TEMPORARY_ASSEMBLY]\n' "$0" >&2
  exit 1
fi
"$SCRIPT_ROOT/validate-development-projects.sh" --assembly-root "$ASSEMBLY_ROOT"
"$SCRIPT_ROOT/validate-server-personas.sh" --assembly-root "$ASSEMBLY_ROOT"
cleanup
if [[ "$OWN_ASSEMBLY" == true && -e "$ASSEMBLY_ROOT" ]]; then
  printf 'ERROR: temporary assembly was not removed\n' >&2
  exit 1
fi

printf 'All consolidated development-project validation passed.\n'
