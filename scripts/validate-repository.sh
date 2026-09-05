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
require_file t3.json
require_file .github/ISSUE_TEMPLATE/implementation.md
require_file .github/PULL_REQUEST_TEMPLATE.md
require_file docs/adr/README.md
require_file docs/history/pre-consolidation.md
require_file toolchain/versions.env
require_file tooling/AGENTS.md
require_file tooling/pyproject.toml
require_file tooling/uv.lock
require_file scripts/dev
require_file toolchain/dev.py
require_file toolchain/bin/sha256sum
require_file tests/toolchain/test_dev.py
require_file tooling/scripts/validate-tooling.sh
require_file tooling/scripts/validate-package.sh
require_file tooling/scripts/validate-locked-artifacts-package.sh
require_file tooling/scripts/validate-release-preparation.sh
require_file tooling/scripts/validate-policy-release-compatibility.sh
require_file policy-sources/control-library/AGENTS.md
require_file policy-sources/control-library/README.md
require_file policy-sources/control-library/release/VERSION
require_file policy-sources/control-library/scripts/validate-shared-policy.sh
require_file policy-sources/control-library/scripts/validate-policy-release.sh
require_file policy-sources/control-library/tests/test_policy_resources.py
require_file policy-sources/control-library/tests/test_policy_release.py
require_file policy-sources/control-library/policies/controls/common/result.rego
require_file policy-sources/control-library/policies/schemas/policy/control.schema.json
require_file policy-sources/verification-policy/AGENTS.md
require_file policy-sources/verification-policy/README.md
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
require_file verification/fixtures/iam-private-boundary/AGENTS.md
require_file verification/fixtures/iam-private-boundary/README.md
require_file verification/fixtures/iam-private-boundary/.gitignore
require_file verification/fixtures/iam-private-boundary/compliance.yaml
require_file verification/fixtures/iam-private-boundary/assignments/identity-access-objectives.yaml
require_file verification/fixtures/iam-private-boundary/fixtures/linux-access-api.json
require_file verification/fixtures/iam-private-boundary/fixtures/technical-results-failing.json
require_file verification/fixtures/iam-private-boundary/inventory/groups/company-assets.yaml
require_file verification/fixtures/iam-private-boundary/inventory/groups/restricted-linux-systems.yaml
require_file verification/fixtures/iam-private-boundary/inventory/subjects/restricted-linux.yaml
require_file verification/fixtures/iam-private-boundary/policy/realizations/restricted/restricted-linux-role-based-access.json
require_file scripts/validate-iam-private-boundary.sh
require_file scripts/iam-private-boundary/validation_inputs.py
require_file scripts/iam-private-boundary/assert-iam-private-boundary.py
require_file scripts/iam-private-boundary/run-direct-rollup.py
require_file tests/iam-private-boundary/test_validation_inputs.py
require_file verification/scenarios/AGENTS.md
require_file verification/scenarios/README.md
require_file verification/scenarios/.gitignore
require_file verification/scenarios/compliance.yaml
require_file verification/scenarios/integration/README.md
require_file verification/scenarios/integration/compliance.yaml
require_file verification/scenarios/projects/linux-hardening-rollout/compliance.yaml
require_file verification/scenarios/scripts/integration.py
require_file verification/scenarios/scripts/test_integration.py
require_file verification/scenarios/scripts/assert-linux-hardening-rollout.py
require_file verification/scenarios/scripts/validate-scenarios.sh
require_file scripts/validate-verification-scenarios.sh

[[ ! -e pyproject.toml ]] || fail "repository root must not be a Python project"
[[ ! -e uv.lock ]] || fail "repository root must not own a uv lock"
[[ ! -e .gitmodules ]] || fail "submodules are not part of the consolidated target"

"${COMPLIANCE_PYTHON:-python3}" -m json.tool t3.json >/dev/null \
  || fail "t3.json is not valid JSON"
"${COMPLIANCE_PYTHON:-python3}" -m unittest discover -s tests/toolchain -v

if grep -nE 'COMPLIANCE_CI_|PERSONAL_ACCESS_TOKEN|GH_PAT|GH_TOKEN|packetlss-labs/compliance-' t3.json; then
  fail "T3 project configuration must not contain historical acquisition or credentials"
fi

expected_toolchain='PYTHON_VERSION=3.13.15
UV_VERSION=0.12.5
OPA_VERSION=1.18.2
OPA_LINUX_AMD64_STATIC_SHA256=9903e5125ac281104f2c4b7371d10cc3b74a98933743fcbfc174f9bf0ab20de8
OPA_DARWIN_ARM64_STATIC_SHA256=3ffa2af6a3b9ccff5d171d061d27990db5ad8cc5c10214c7eeeabc0f29ca11cf'
actual_toolchain="$(cat toolchain/versions.env)"
[[ "$actual_toolchain" == "$expected_toolchain" ]] || fail "toolchain/versions.env does not match the accepted migration toolchain"

# Migration stage 6a permits exactly the independently named shared-library and
# verification-policy producers, two ordinary project roots, and the approved
# synthetic IAM fixture. environment-private exists only as a temporary,
# independently copied execution root.
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
[[ -d verification/fixtures/iam-private-boundary ]] \
  || fail "approved IAM private-boundary fixture is missing"
unexpected_verification_entry="$(
  find verification -mindepth 1 -maxdepth 1 ! -name fixtures ! -name scenarios -print -quit
)"
[[ -z "$unexpected_verification_entry" ]] \
  || fail "unapproved verification root appeared: $unexpected_verification_entry"
unexpected_fixture_entry="$(
  find verification/fixtures -mindepth 1 -maxdepth 1 \
    ! -name iam-private-boundary -print -quit
)"
[[ -z "$unexpected_fixture_entry" ]] \
  || fail "unapproved verification fixture appeared: $unexpected_fixture_entry"
[[ -d verification/scenarios ]] \
  || fail "canonical verification scenario root is missing"
[[ ! -e verification/scenarios/.github ]] \
  || fail "nested historical scenario workflow metadata must not become active destination CI"
[[ ! -e verification/scenarios/integration/components.json ]] \
  || fail "historical scenario repository-coordinate manifest must not remain active"
[[ ! -e verification/scenarios/projects/linux-hardening-rollout/generated ]] \
  || fail "generated scenario evidence, plans, and results must remain untracked"
[[ ! -e verification/fixtures/iam-private-boundary/.github ]] \
  || fail "nested historical IAM workflow metadata must not become active destination CI"
[[ ! -e verification/fixtures/iam-private-boundary/generated ]] \
  || fail "generated IAM evidence, plans, and results must remain untracked"
[[ ! -e external-sources ]] \
  || fail "environment-private must exist only as a separate temporary validation root"

restricted_in_central="$(
  grep -R -l --fixed-strings 'restricted.linux.central-role-access' \
    policy-sources/control-library/policies \
    policy-sources/verification-policy/policies || true
)"
[[ -z "$restricted_in_central" ]] || {
  printf '%s\n' "$restricted_in_central" >&2
  fail "restricted IAM realization must not be copied into central policy sources"
}

unexpected_sensitive_file="$(
  find verification/fixtures/iam-private-boundary -type f \
    \( -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.tfstate' \
       -o -name '.env' -o -name 'credentials' -o -name 'secrets.*' \) \
    -print -quit
)"
[[ -z "$unexpected_sensitive_file" ]] \
  || fail "sensitive or provider-state file entered the synthetic IAM fixture: $unexpected_sensitive_file"

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

active_validation_paths=(.github/workflows scripts verification/scenarios/scripts)
if grep -R --exclude='validate-repository.sh' -nE \
  'COMPLIANCE_CI_|PERSONAL_ACCESS_TOKEN|GH_PAT|GH_TOKEN|actions/create-github-app-token|packetlss-labs/compliance-' \
  "${active_validation_paths[@]}"; then
  fail "active validation must not retain historical sibling acquisition or credentials"
fi
if grep -R --exclude='validate-repository.sh' -nE \
  '(^|[[:space:]])git[[:space:]]+clone([[:space:]]|$)' \
  "${active_validation_paths[@]}"; then
  fail "active validation must not clone historical component repositories"
fi

printf 'repository validation passed\n'
