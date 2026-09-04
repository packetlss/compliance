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
require_file tooling/AGENTS.md
require_file tooling/pyproject.toml
require_file tooling/uv.lock
require_file tooling/scripts/ci-versions.env
require_file tooling/scripts/validate-tooling.sh
require_file tooling/scripts/validate-package.sh
require_file tooling/scripts/validate-locked-artifacts-package.sh
require_file tooling/scripts/validate-release-preparation.sh
require_file tooling/scripts/validate-policy-release-compatibility.sh
require_file policy-sources/control-library/AGENTS.md
require_file policy-sources/control-library/README.md
require_file policy-sources/control-library/release/VERSION
require_file policy-sources/control-library/scripts/ci-versions.env
require_file policy-sources/control-library/scripts/validate-shared-policy.sh
require_file policy-sources/control-library/scripts/validate-policy-release.sh
require_file policy-sources/control-library/tests/test_policy_resources.py
require_file policy-sources/control-library/tests/test_policy_release.py
require_file policy-sources/control-library/policies/controls/common/result.rego
require_file policy-sources/control-library/policies/schemas/policy/control.schema.json
require_file policy-sources/verification-policy/AGENTS.md
require_file policy-sources/verification-policy/README.md
require_file policy-sources/verification-policy/scripts/ci-versions.env
require_file policy-sources/verification-policy/scripts/check-source-boundary.py
require_file policy-sources/verification-policy/scripts/validate-verification-policy.sh
require_file policy-sources/verification-policy/tests/test_verification_policy_source.py
require_file policy-sources/verification-policy/policies/baselines/managed-workstation.json
require_file projects/AGENTS.md
require_file projects/README.md
require_file projects/.gitignore
require_file projects/mock-fleet/compliance.yaml
require_file projects/server-personas/compliance.yaml
require_file scripts/validate-development-projects.sh
require_file scripts/development-projects/validation_inputs.py
require_file scripts/development-projects/validate-all-development-projects.sh
require_file tests/development-projects/test_validation_inputs.py
require_file validation/development-projects/compliance.yaml

[[ ! -e pyproject.toml ]] || fail "repository root must not be a Python project"
[[ ! -e uv.lock ]] || fail "repository root must not own a uv lock"
[[ ! -e .gitmodules ]] || fail "submodules are not part of the consolidated target"

expected_toolchain='PYTHON_VERSION=3.13.15
UV_VERSION=0.12.5
OPA_VERSION=1.18.2
OPA_LINUX_AMD64_STATIC_SHA256=9903e5125ac281104f2c4b7371d10cc3b74a98933743fcbfc174f9bf0ab20de8'
actual_toolchain="$(cat toolchain/versions.env)"
[[ "$actual_toolchain" == "$expected_toolchain" ]] || fail "toolchain/versions.env does not match the accepted migration toolchain"

# The retained tooling-local pins are digest-preserving migration content, not a
# second repository-level toolchain owner. Require them to match the root pins.
tooling_toolchain="$(grep -v '^[[:space:]]*#' tooling/scripts/ci-versions.env | sed '/^[[:space:]]*$/d')"
[[ "$tooling_toolchain" == "$expected_toolchain" ]] || fail "tooling-local pins differ from the repository toolchain"
verification_toolchain="$(grep -v '^[[:space:]]*#' policy-sources/verification-policy/scripts/ci-versions.env | sed '/^[[:space:]]*$/d')"
[[ "$verification_toolchain" == "$expected_toolchain" ]] || fail "verification-policy pins differ from the repository toolchain"

# Migration stage 5 permits exactly the independently named shared-library and
# verification-policy producers plus the two ordinary project roots.
[[ -d policy-sources/control-library/policies ]] \
  || fail "shared-library semantic policy root is missing"
[[ -d policy-sources/verification-policy/policies ]] \
  || fail "verification-policy semantic policy root is missing"
unexpected_policy_source="$(
  find policy-sources -mindepth 1 -maxdepth 1 \
    ! -name control-library ! -name verification-policy -print -quit
)"
[[ -z "$unexpected_policy_source" ]] \
  || fail "unapproved policy source root appeared: $unexpected_policy_source"
[[ ! -e policy-sources/control-library/.github ]] \
  || fail "nested historical workflow metadata must not become active destination CI"
[[ ! -e policy-sources/control-library/scripts/tooling-contract.env ]] \
  || fail "control-library validation must consume the co-located tooling root"
[[ ! -e policy-sources/verification-policy/.github ]] \
  || fail "nested historical workflow metadata must not become active destination CI"
[[ ! -e policy-sources/verification-policy/release ]] \
  || fail "verification policy must remain source-only without a release producer"
[[ ! -e policy-sources/verification-policy/scripts/tooling-contract.env ]] \
  || fail "verification-policy validation must consume co-located component roots"

unexpected_project_entry="$(
  find projects -mindepth 1 -maxdepth 1 \
    ! -name .gitignore ! -name AGENTS.md ! -name README.md \
    ! -name mock-fleet ! -name server-personas -print -quit
)"
[[ -z "$unexpected_project_entry" ]] \
  || fail "unapproved ordinary project entry appeared: $unexpected_project_entry"
[[ ! -e validation/dependencies.json ]] \
  || fail "historical repository-coordinate project dependency manifest must not be active"
[[ ! -e verification ]] \
  || fail "source root 'verification' appeared before its bounded migration stage updated repository validation"

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

printf 'repository validation passed\n'
