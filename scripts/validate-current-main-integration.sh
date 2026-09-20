#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
workflow="${1:-$root/.github/workflows/current-main-integration.yml}"

fail() {
  printf 'current-main integration validation failed: %s\n' "$*" >&2
  exit 1
}

[[ -f "$workflow" ]] || fail "workflow is missing: $workflow"

job_block() {
  local job="$1"
  awk -v job="$job" '
    $0 == "  " job ":" { found=1; next }
    found && $0 ~ /^  [A-Za-z0-9_-]+:$/ { exit }
    found { print }
  ' "$workflow"
}

permission_block() {
  awk '
    $0 == "    permissions:" { found=1; next }
    found && $0 ~ /^    [A-Za-z0-9_-]+:/ { exit }
    found { print }
  '
}

require_absent() {
  local expression="$1" message="$2"
  if grep -nE "$expression" "$workflow"; then
    fail "$message"
  fi
}

require_candidate_job() {
  local name="$1" block permissions
  block="$(job_block "$name")"
  [[ -n "$block" ]] || fail "candidate job is missing: $name"
  [[ "$(printf '%s\n' "$block" | grep -xc '    permissions:' || true)" == 1 ]] \
    || fail "$name must declare exactly one permissions map"
  permissions="$(printf '%s\n' "$block" | permission_block)"
  [[ "$permissions" == '      contents: read' ]] \
    || fail "$name must have exactly contents: read permission"
  printf '%s\n' "$block" | grep -q 'persist-credentials: false' \
    || fail "$name must disable checkout credential persistence"
  if printf '%s\n' "$block" | grep -nE "GH_TOKEN|GITHUB_TOKEN|GH_PAT|PERSONAL_ACCESS_TOKEN|APP_TOKEN|actions/create-github-app-token|secrets|$credential_expression"; then
    fail "$name must not receive a credential"
  fi
}

require_trusted_job() {
  local name="$1" expected_permissions="$2" block permissions
  block="$(job_block "$name")"
  [[ -n "$block" ]] || fail "trusted job is missing: $name"
  [[ "$(printf '%s\n' "$block" | grep -xc '    permissions:' || true)" == 1 ]] \
    || fail "$name must declare exactly one permissions map"
  permissions="$(printf '%s\n' "$block" | permission_block)"
  [[ "$permissions" == "$expected_permissions" ]] \
    || fail "$name must have only its accepted permissions"
  if printf '%s\n' "$block" | grep -nE 'actions/checkout|(^|[^A-Za-z])git[[:space:]]+(fetch|checkout|merge|rebase|push)|scripts/|toolchain/|GITHUB_WORKSPACE'; then
    fail "$name must not checkout or execute candidate code"
  fi
}

credential_expression='\$\{\{[^}]*([Gg][Ii][Tt][Hh][Uu][Bb]|[Ss][Ee][Cc][Rr][Ee][Tt][Ss])'

require_absent 'pull_request_target' 'must not use pull_request_target'
require_absent '(^|[[:space:]])git[[:space:]]+push([[:space:]]|$)' 'must not push a synthetic candidate'
require_absent 'gh[[:space:]]+pr[[:space:]]+merge|/merges([[:space:]]|$)' 'must not automate merge'
require_absent 'git[[:space:]]+(branch|update-ref|rebase)' 'must not mutate persistent branches or refs'

for candidate in component-validation verification-scenarios installed-release-provenance macos-portability; do
  require_candidate_job "$candidate"
done

require_trusted_job resolve $'      contents: read\n      statuses: write'
require_trusted_job publish '      statuses: write'
resolve="$(job_block resolve)"
printf '%s\n' "$resolve" | grep -qx '      contents: read' \
  || fail 'resolve must retain contents: read for trusted API resolution'
publish="$(job_block publish)"
if printf '%s\n' "$publish" | grep -qx '      contents: read'; then
  fail 'publish must not receive repository contents permission'
fi

token_expression="GH_TOKEN|GITHUB_TOKEN|GH_PAT|PERSONAL_ACCESS_TOKEN|APP_TOKEN|actions/create-github-app-token|secrets|$credential_expression"
token_bindings="$(grep -nE "$token_expression" "$workflow" || true)"
[[ "$(printf '%s\n' "$token_bindings" | sed '/^$/d' | wc -l | tr -d ' ')" == 3 ]] \
  || fail 'workflow credentials must be limited to the three trusted GH_TOKEN bindings'
resolve_tokens="$(printf '%s\n' "$resolve" | grep -E "$token_expression" || true)"
resolve_expected="$(printf '%s\n' "$resolve" | grep -E '^[[:space:]]+GH_TOKEN: \$\{\{ github\.token \}\}[[:space:]]*$' || true)"
[[ "$resolve_tokens" == "$resolve_expected" ]] \
  || fail 'resolve must use only explicit GH_TOKEN bindings'
[[ "$(printf '%s\n' "$resolve_expected" | sed '/^$/d' | wc -l | tr -d ' ')" == 2 ]] \
  || fail 'resolve must contain exactly two GH_TOKEN bindings'
publish_tokens="$(printf '%s\n' "$publish" | grep -E "$token_expression" || true)"
publish_expected="$(printf '%s\n' "$publish" | grep -E '^[[:space:]]+GH_TOKEN: \$\{\{ github\.token \}\}[[:space:]]*$' || true)"
[[ "$publish_tokens" == "$publish_expected" ]] \
  || fail 'publish must use only its explicit GH_TOKEN binding'
[[ "$(printf '%s\n' "$publish_expected" | sed '/^$/d' | wc -l | tr -d ' ')" == 1 ]] \
  || fail 'publish must contain exactly one GH_TOKEN binding'

printf 'current-main integration workflow validation passed\n'
