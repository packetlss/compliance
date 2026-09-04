#!/usr/bin/env bash
set -euo pipefail

POLICY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$POLICY_ROOT/scripts/ci-versions.env"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

for command in python cmp sha256sum; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

python_actual="$(python -c 'import platform; print(platform.python_version())')"
[[ "$python_actual" == "$PYTHON_VERSION" ]] \
  || fail "Python $PYTHON_VERSION is required; found $python_actual"

python - <<'PY'
from tools.policy_source_release import POLICY_SOURCE_RELEASE_SCHEMA

assert POLICY_SOURCE_RELEASE_SCHEMA == "compliance.example/policy-source-release-manifest/v1"
PY

source_git_sha="${COMPLIANCE_CONTROL_LIBRARY_SHA:-}"
[[ "$source_git_sha" =~ ^[0-9a-f]{40}$ ]] \
  || fail "COMPLIANCE_CONTROL_LIBRARY_SHA must be the exact 40-hex source revision"
alternate_git_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
[[ "$alternate_git_sha" != "$source_git_sha" ]] \
  || alternate_git_sha="cccccccccccccccccccccccccccccccccccccccc"

release_version="$(tr -d '\n' < "$POLICY_ROOT/release/VERSION")"
release_tag="v$release_version"
temporary="$(mktemp -d "${TMPDIR:-/tmp}/control-library-release.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT

descriptor_only="$temporary/descriptor-only"
archive_release="$temporary/archive-release"
alternate_release="$temporary/alternate-release"
materialized_dir="$temporary/materialized/policy"
mkdir -p "$temporary/no-git-bin" "$materialized_dir"
cp -R "$POLICY_ROOT/policies/." "$materialized_dir/"

cat > "$temporary/no-git-bin/git" <<'SH'
#!/usr/bin/env bash
echo "git must not be invoked by policy-source release preparation" >&2
exit 97
SH
chmod +x "$temporary/no-git-bin/git"
release_path="$temporary/no-git-bin:$PATH"

printf '== Generic release/archive unit tests ==\n'
python -m unittest discover -s "$POLICY_ROOT/tests" -p 'test_policy_release.py' -v

printf '\n== Descriptor-only preparation without Git metadata ==\n'
PATH="$release_path" python "$POLICY_ROOT/scripts/policy-release.py" prepare \
  --version "$release_version" \
  --output-dir "$descriptor_only" \
  > "$temporary/descriptor.json"
PATH="$release_path" python "$POLICY_ROOT/scripts/policy-release.py" verify \
  --release-dir "$descriptor_only" \
  --policy-root "$materialized_dir" \
  > "$temporary/descriptor-verified.json"
cmp --silent "$temporary/descriptor.json" "$temporary/descriptor-verified.json" \
  || fail "descriptor prepare and verify returned different manifests"
descriptor_files="$(find "$descriptor_only" -maxdepth 1 -type f -exec basename {} \; | sort | tr '\n' ' ')"
[[ "$descriptor_files" == "SHA256SUMS policy-source-release-manifest.json " ]] \
  || fail "unexpected descriptor-only payload: $descriptor_files"
(
  cd "$descriptor_only"
  sha256sum --check --strict SHA256SUMS
)

printf '\n== Generic archive representation with optional source metadata ==\n'
PATH="$release_path" python "$POLICY_ROOT/scripts/policy-release.py" prepare \
  --version "$release_version" \
  --git-tag "$release_tag" \
  --git-commit "$source_git_sha" \
  --archive \
  --output-dir "$archive_release" \
  > "$temporary/archive.json"
PATH="$release_path" python "$POLICY_ROOT/scripts/policy-release.py" verify \
  --release-dir "$archive_release" \
  --policy-root "$materialized_dir" \
  > "$temporary/archive-verified.json"
cmp --silent "$temporary/archive.json" "$temporary/archive-verified.json" \
  || fail "archive prepare and verify returned different manifests"
archive_files="$(
  find "$archive_release" -maxdepth 1 -type f -exec basename {} \; \
    | sort \
    | tr '\n' ' '
)"
expected_archive_files="SHA256SUMS compliance-control-library-${release_version}.tar.gz policy-source-release-manifest.json "
[[ "$archive_files" == "$expected_archive_files" ]] \
  || fail "unexpected archive payload: $archive_files"
(
  cd "$archive_release"
  sha256sum --check --strict SHA256SUMS
)

printf '\n== Source metadata remains noncanonical ==\n'
PATH="$release_path" python "$POLICY_ROOT/scripts/policy-release.py" prepare \
  --version "$release_version" \
  --git-tag "$release_tag" \
  --git-commit "$alternate_git_sha" \
  --archive \
  --output-dir "$alternate_release" \
  > "$temporary/alternate.json"
cmp --silent \
  "$archive_release/compliance-control-library-${release_version}.tar.gz" \
  "$alternate_release/compliance-control-library-${release_version}.tar.gz" \
  || fail "Git metadata changed generic archive representation bytes"

POLICY_ROOT="$POLICY_ROOT" python - \
  "$descriptor_only/policy-source-release-manifest.json" \
  "$archive_release/policy-source-release-manifest.json" \
  "$alternate_release/policy-source-release-manifest.json" \
  "$archive_release/compliance-control-library-${release_version}.tar.gz" \
  "$materialized_dir" \
  "$source_git_sha" \
  "$alternate_git_sha" \
  "$release_version" <<'PY'
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path(os.environ["POLICY_ROOT"])
sys.path.insert(0, str(root / "scripts"))
from policy_release import canonical_content_identity
from tools.policy_source_release import (
    normalize_policy_source_release,
    validate_policy_source_archive,
)
from tools.policy_sources import source_tree_digest

(
    descriptor_path,
    archive_manifest_path,
    alternate_path,
    archive_representation_path,
    materialized_path,
    source_sha,
    alternate_sha,
    version,
) = sys.argv[1:]
descriptor = json.loads(Path(descriptor_path).read_text(encoding="utf-8"))
archive_manifest = json.loads(
    Path(archive_manifest_path).read_text(encoding="utf-8")
)
alternate = json.loads(Path(alternate_path).read_text(encoding="utf-8"))
canonical_digest = source_tree_digest(Path(materialized_path))

for manifest in (descriptor, archive_manifest, alternate):
    assert manifest["schema"] == "compliance.example/policy-source-release-manifest/v1"
    assert manifest["distribution"] == "compliance-control-library"
    assert manifest["version"] == version
    assert manifest["content"] == {
        "digest": canonical_digest,
        "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
    }

assert canonical_content_identity(descriptor) == canonical_content_identity(
    archive_manifest
)
assert canonical_content_identity(archive_manifest) == canonical_content_identity(
    alternate
)
assert "sourceMetadata" not in descriptor
assert "representations" not in descriptor
assert archive_manifest["sourceMetadata"] == {
    "gitTag": f"v{version}",
    "gitCommit": source_sha,
}
assert alternate["sourceMetadata"] == {
    "gitTag": f"v{version}",
    "gitCommit": alternate_sha,
}

release = normalize_policy_source_release(archive_manifest)
representation = release.representations[0]
assert representation.format == "compliance.example/policy-source-archive/v1"
assert representation.content_root == "policy"
assert representation.filename == f"compliance-control-library-{version}.tar.gz"
assert representation.sha256 != canonical_digest
validation = validate_policy_source_archive(
    release,
    representation,
    Path(archive_representation_path),
)
assert validation.content_digest == canonical_digest
assert release.release_lock_policy_source() == {
    "distribution": "compliance-control-library",
    "version": version,
    "content": archive_manifest["content"],
}

provider_fields = {
    "publisher",
    "provider",
    "githubReleaseId",
    "repositoryUrl",
    "downloadUrl",
    "actionsRunId",
}
for manifest in (descriptor, archive_manifest, alternate):
    assert provider_fields.isdisjoint(manifest)
PY

printf '\nGeneric control-library release validation passed for %s.\n' "$release_version"
python - "$archive_release/policy-source-release-manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"Canonical policy digest: {manifest['content']['digest']}")
print(f"Archive representation: {manifest['representations'][0]['sha256']}")
PY
