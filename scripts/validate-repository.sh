#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

fail() {
  printf 'repository validation failed: %s\n' "$*" >&2
  exit 1
}

require_file() {
  [[ -f "$1" ]] || fail "required file is missing: $1"
}

require_file AGENTS.md
require_file README.md
require_file docs/adr/README.md
require_file docs/history/pre-consolidation.md
require_file toolchain/versions.env

[[ ! -e pyproject.toml ]] || fail "repository root must not be a Python project"
[[ ! -e uv.lock ]] || fail "repository root must not own a uv lock"
[[ ! -e .gitmodules ]] || fail "submodules are not part of the consolidated target"

expected_toolchain='PYTHON_VERSION=3.13.15
UV_VERSION=0.12.5
OPA_VERSION=1.18.2
OPA_LINUX_AMD64_STATIC_SHA256=9903e5125ac281104f2c4b7371d10cc3b74a98933743fcbfc174f9bf0ab20de8'
actual_toolchain="$(cat toolchain/versions.env)"
[[ "$actual_toolchain" == "$expected_toolchain" ]] || fail "toolchain/versions.env does not match the accepted migration toolchain"

# Stage 2 contains no migrated source. A later source-migration PR must update this
# validator atomically when it introduces one of these roots.
for source_root in tooling policy-sources projects verification; do
  [[ ! -e "$source_root" ]] || fail "source root '$source_root' appeared before its bounded migration stage updated repository validation"
done

if [[ -d .github/workflows ]]; then
  if grep -R -nE 'COMPLIANCE_CI_|PERSONAL_ACCESS_TOKEN|GH_PAT' .github/workflows; then
    fail "normal destination CI must not use sibling-acquisition or PAT credentials"
  fi
  if grep -R -nE 'packetlss-labs/compliance-' .github/workflows; then
    fail "normal destination CI must not acquire component source from packetlss-labs"
  fi
  if grep -R -nE '^[[:space:]]+repository:' .github/workflows; then
    fail "normal destination CI must use the current checkout rather than an explicit sibling repository checkout"
  fi
  if grep -R -nE '^[[:space:]]+paths(-ignore)?:' .github/workflows; then
    fail "required destination checks must report on every PR; workflow path filters are not allowed"
  fi
fi

printf 'repository bootstrap validation passed\n'
