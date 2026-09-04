#!/usr/bin/env bash
set -euo pipefail

TOOLING_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$TOOLING_ROOT/scripts/ci-versions.env"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for command in uv python sha256sum cmp; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] \
  || fail "uv $UV_VERSION is required; found $uv_actual"

git_commit="${COMPLIANCE_TOOLING_SHA:-}"
[[ "$git_commit" =~ ^[0-9a-f]{40}$ ]] \
  || fail "set COMPLIANCE_TOOLING_SHA to an exact 40-hex source revision for metadata testing"

release_version="$(python - "$TOOLING_ROOT/pyproject.toml" <<'PY'
import sys
import tomllib
from pathlib import Path
print(tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])
PY
)"
release_tag="v$release_version"

temporary="$(mktemp -d "${TMPDIR:-/tmp}/compliance-tooling-release.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT
generic_dir="$temporary/generic"
metadata_dir="$temporary/with-git-metadata"
runtime_dir="$temporary/runtime"
mkdir -p "$runtime_dir" "$temporary/no-git-bin"

cat > "$temporary/no-git-bin/git" <<'SH'
#!/usr/bin/env bash
echo "git must not be invoked by generic release preparation" >&2
exit 97
SH
chmod +x "$temporary/no-git-bin/git"
release_path="$temporary/no-git-bin:$PATH"

printf '== Generic release preparation without Git metadata ==\n'
PATH="$release_path" uv run --project "$TOOLING_ROOT" --frozen python \
  "$TOOLING_ROOT/scripts/tooling-release.py" prepare \
  --output-dir "$generic_dir" \
  > "$temporary/generic-manifest.json"
PATH="$release_path" uv run --project "$TOOLING_ROOT" --frozen python \
  "$TOOLING_ROOT/scripts/tooling-release.py" verify \
  --release-dir "$generic_dir" \
  > "$temporary/generic-verified.json"
cmp "$temporary/generic-manifest.json" "$temporary/generic-verified.json"

printf '\n== Optional Git source metadata does not alter canonical source/wheel identity ==\n'
PATH="$release_path" uv run --project "$TOOLING_ROOT" --frozen python \
  "$TOOLING_ROOT/scripts/tooling-release.py" prepare \
  --git-tag "$release_tag" \
  --git-commit "$git_commit" \
  --output-dir "$metadata_dir" \
  > "$temporary/metadata-manifest.json"
PATH="$release_path" uv run --project "$TOOLING_ROOT" --frozen python \
  "$TOOLING_ROOT/scripts/tooling-release.py" verify \
  --release-dir "$metadata_dir" >/dev/null

for release_dir in "$generic_dir" "$metadata_dir"; do
  mapfile -t payload_files < <(
    find "$release_dir" -maxdepth 1 -type f -printf '%f\n' | sort
  )
  expected_files=(
    SHA256SUMS
    "compliance_tooling-${release_version}-py3-none-any.whl"
    tooling-release-manifest.json
  )
  [[ "${payload_files[*]}" == "${expected_files[*]}" ]] \
    || fail "unexpected release payload: ${payload_files[*]}"
  (
    cd "$release_dir"
    sha256sum --check --strict SHA256SUMS
  )
done

wheel="$generic_dir/compliance_tooling-${release_version}-py3-none-any.whl"
python -m venv "$temporary/venv"
venv_python="$temporary/venv/bin/python"
venv_compliance="$temporary/venv/bin/compliance"
uv pip install --python "$venv_python" "$wheel"

cd "$runtime_dir"
PATH="$release_path" "$venv_compliance" --version > version.txt
PATH="$release_path" "$venv_compliance" version --format json > identity.json

"$venv_python" - \
  "$generic_dir/tooling-release-manifest.json" \
  "$metadata_dir/tooling-release-manifest.json" \
  "$runtime_dir/identity.json" \
  "$runtime_dir/version.txt" \
  "$git_commit" \
  "$release_tag" \
  "$OPA_VERSION" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.release_artifacts import validate_release_manifest
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM

(
    generic_path,
    metadata_path,
    identity_path,
    version_path,
    source_sha,
    release_tag,
    opa_version,
) = sys.argv[1:]
generic = json.loads(Path(generic_path).read_text(encoding="utf-8"))
with_metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
identity = json.loads(Path(identity_path).read_text(encoding="utf-8"))
version_text = Path(version_path).read_text(encoding="utf-8").strip()

validate_release_manifest(generic)
validate_release_manifest(with_metadata)
for manifest in (generic, with_metadata):
    assert manifest["schema"] == "compliance.example/tooling-release-manifest/v2", manifest
    assert manifest["distribution"] == "compliance-tooling", manifest
    assert manifest["cli"] == "compliance", manifest
    assert manifest["source"]["digest"].startswith("sha256:"), manifest
    assert manifest["source"]["digestAlgorithm"] == TOOLING_SOURCE_DIGEST_ALGORITHM, manifest
    assert manifest["artifact"]["kind"] == "python-wheel", manifest
    assert manifest["artifact"]["sha256"].startswith("sha256:"), manifest
    assert manifest["testedOpaVersion"] == opa_version, manifest

assert "sourceMetadata" not in generic, generic
assert with_metadata["sourceMetadata"] == {
    "gitTag": release_tag,
    "gitCommit": source_sha,
}, with_metadata
assert generic["source"] == with_metadata["source"], (generic, with_metadata)
assert generic["artifact"] == with_metadata["artifact"], (generic, with_metadata)

assert identity["schema"] == "compliance.example/tooling-release-metadata/v2", identity
assert identity["distribution"] == generic["distribution"], identity
assert identity["cli"] == generic["cli"], identity
assert identity["version"] == generic["version"], identity
assert identity["source_digest"] == generic["source"]["digest"], identity
assert identity["source_digest_algorithm"] == TOOLING_SOURCE_DIGEST_ALGORITHM, identity
assert identity["tested_opa_version"] == generic["testedOpaVersion"], identity
assert identity["build_kind"] == "release", identity
assert generic["source"]["digest"] in version_text, version_text
assert source_sha not in version_text, version_text

provider_fields = {
    "publisher", "provider", "githubReleaseId", "repositoryUrl",
    "downloadUrl", "actionsRunId",
}
for manifest in (generic, with_metadata):
    assert provider_fields.isdisjoint(manifest), manifest
PY

printf 'Content-addressed tooling release preparation passed for %s.\n' "$release_version"
