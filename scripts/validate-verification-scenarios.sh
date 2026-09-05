#!/usr/bin/env bash
set -euo pipefail

SOURCE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SCENARIO_ROOT="$SOURCE_ROOT/verification/scenarios"
ASSEMBLY_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/compliance-scenario-assembly.XXXXXX")"

cleanup() {
  rm -rf -- "$ASSEMBLY_ROOT"
}
trap cleanup EXIT

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for command in git tar uv opa; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done

destination_revision="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
if [[ -n "${COMPLIANCE_VERIFICATION_SCENARIOS_SHA:-}" ]]; then
  [[ "$destination_revision" == "$COMPLIANCE_VERIFICATION_SCENARIOS_SHA" ]] \
    || fail "destination revision mismatch: expected $COMPLIANCE_VERIFICATION_SCENARIOS_SHA, found $destination_revision"
fi

export PYTHONDONTWRITEBYTECODE=1
"${COMPLIANCE_PYTHON:-python3}" -m unittest discover -s "$SCENARIO_ROOT/scripts" -p 'test_*.py' -v
"${COMPLIANCE_PYTHON:-python3}" "$SCENARIO_ROOT/scripts/integration.py" assemble --root "$ASSEMBLY_ROOT"
bash "$SCENARIO_ROOT/scripts/validate-scenarios.sh" \
  --integration-root "$ASSEMBLY_ROOT"

cleanup
[[ ! -e "$ASSEMBLY_ROOT" ]] || fail "temporary scenario assembly was not removed"
printf 'Canonical verification-scenario gate passed; temporary assembly removed.\n'
