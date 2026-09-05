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

for command in uv python sha256sum; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done

uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"

source_digest="$(python - "$TOOLING_ROOT" <<'PY'
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
from tools.tooling_source import tooling_source_digest

print(tooling_source_digest(Path(sys.argv[1])))
PY
)"

temporary="$(mktemp -d "${TMPDIR:-/tmp}/compliance-policy-source-conformance.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT
mkdir -p "$temporary/dist" "$temporary/runtime" "$temporary/no-provider-bin"

python "$TOOLING_ROOT/scripts/build-wheel.py" \
  --source-digest "$source_digest" \
  --output-dir "$temporary/dist"
set -- "$temporary/dist"/*.whl
[[ "$#" -eq 1 && -f "$1" ]] || fail "expected exactly one wheel"
wheel="$1"
wheel_sha="sha256:$(sha256sum "$wheel" | awk '{print $1}')"

python -m venv "$temporary/venv"
venv_python="$temporary/venv/bin/python"
python "$TOOLING_ROOT/scripts/install-locked-wheel.py" \
  --python "$venv_python" \
  --wheel "$wheel" \
  --cache-dir "$temporary/uv-cache"

cat > "$temporary/no-provider-bin/provider-command-disabled" <<'SH'
#!/usr/bin/env bash
echo "provider, download, and Git commands are disabled during installed-runtime validation" >&2
exit 97
SH
chmod +x "$temporary/no-provider-bin/provider-command-disabled"
for command in git gh curl wget; do
  ln -s provider-command-disabled "$temporary/no-provider-bin/$command"
done
runtime_path="$temporary/no-provider-bin:$PATH"

cd "$temporary/runtime"
printf '== Local installed-package generic policy-source conformance ==\n'
PATH="$runtime_path" "$venv_python" - "$source_digest" "$wheel_sha" <<'PY'
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import socket
import sys
import tarfile
from pathlib import Path

import yaml


def network_disabled(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("network access is disabled during installed-runtime validation")


socket.create_connection = network_disabled
socket.socket.connect = network_disabled

from tools.policy_source_release import (
    POLICY_SOURCE_ARCHIVE_FORMAT,
    POLICY_SOURCE_RELEASE_SCHEMA,
    load_policy_source_release,
    validate_policy_source_archive,
)
from tools.policy_sources import PolicySource, source_tree_digest
from tools.release import tooling_release_identity
from tools.composition import POLICY_SOURCE_DIGEST_ALGORITHM, COMPOSITION_LOCK_SCHEMA, load_composition_lock, require_composition
from tools.tooling_identity import actual_tooling_identity
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM

expected_source_digest, wheel_sha = sys.argv[1:]
runtime_root = Path.cwd()
release_dir = runtime_root / "synthetic-release"
source_tree = runtime_root / "producer-tree"
control = source_tree / "controls" / "minimal.rego"
control.parent.mkdir(parents=True)
control.write_text("package synthetic.minimum\n\ndefault allow := true\n", encoding="utf-8")
content_digest = source_tree_digest(source_tree)

# This tiny producer fixture intentionally uses no repository-owned policy content.
release_dir.mkdir()
archive_path = release_dir / "opaque-policy-source.asset"
with archive_path.open("wb") as raw:
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=raw,
        compresslevel=9,
        mtime=0,
    ) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name in ("policy/", "policy/controls/"):
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.mtime = 0
                archive.addfile(info)
            content = control.read_bytes()
            info = tarfile.TarInfo("policy/controls/minimal.rego")
            info.type = tarfile.REGTYPE
            info.mode = 0o644
            info.mtime = 0
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))

archive_sha = "sha256:" + hashlib.sha256(archive_path.read_bytes()).hexdigest()
manifest_path = release_dir / "policy-source-release-manifest.json"
manifest_document = {
    "schema": POLICY_SOURCE_RELEASE_SCHEMA,
    "distribution": "northwind-security/independent-policy-pack",
    "version": "9.8.7",
    "content": {
        "digest": content_digest,
        "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
    },
    "sourceMetadata": {
        "gitTag": "navigation-only",
        "gitCommit": "a" * 40,
    },
    "representations": [
        {
            "kind": "archive",
            "format": POLICY_SOURCE_ARCHIVE_FORMAT,
            "contentRoot": "policy",
            "filename": archive_path.name,
            "sha256": archive_sha,
        }
    ],
}
manifest_path.write_text(
    json.dumps(manifest_document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

checksums_path = release_dir / "SHA256SUMS"
checksum_entries = []
for path in (archive_path, manifest_path):
    checksum_entries.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
checksums_path.write_text("\n".join(checksum_entries) + "\n", encoding="utf-8")
for entry in checksums_path.read_text(encoding="utf-8").splitlines():
    expected, filename = entry.split("  ", 1)
    actual = hashlib.sha256((release_dir / filename).read_bytes()).hexdigest()
    assert actual == expected, (filename, expected, actual)

release = load_policy_source_release(manifest_path)
assert release.manifest_schema == POLICY_SOURCE_RELEASE_SCHEMA, release
assert release.distribution == "northwind-security/independent-policy-pack", release
assert release.content.digest == content_digest, release
assert len(release.representations) == 1, release

materialized = runtime_root / "materialized" / "arbitrary-source"
validation = validate_policy_source_archive(
    release,
    release.representations[0],
    archive_path,
    materialize_to=materialized,
)
assert validation.representation_sha256 == archive_sha, validation
assert validation.content_digest == content_digest, validation
assert validation.file_count == 1, validation
assert source_tree_digest(materialized) == content_digest
assert not (materialized / ".git").exists()

installed = tooling_release_identity()
assert installed.source_digest == expected_source_digest, installed
assert installed.source_digest_algorithm == TOOLING_SOURCE_DIGEST_ALGORITHM, installed
lock_document = {
    "schema": COMPOSITION_LOCK_SCHEMA,
    "expected": {
        "tooling": actual_tooling_identity(),
        "policySources": {"arbitrary-source": {"content": release.content.document()}},
    },
}
lock_path = runtime_root / "compliance.lock.yaml"
lock_path.write_text(yaml.safe_dump(lock_document, sort_keys=True), encoding="utf-8")
lock = load_composition_lock(lock_path)
report = require_composition((PolicySource("arbitrary-source", materialized),), lock=lock)
assert report["valid"] is True, report
assert report["errors"] == [], report

# Git navigation fields and provider/download acquisition details are not canonical.
without_git_metadata = copy.deepcopy(manifest_document)
without_git_metadata.pop("sourceMetadata")
without_git_path = release_dir / "without-git-metadata.json"
without_git_path.write_text(json.dumps(without_git_metadata), encoding="utf-8")
without_git = load_policy_source_release(without_git_path)
assert without_git.semantic_document() == release.semantic_document()
acquisition_metadata = {
    "provider": "not-canonical",
    "repository": "not-canonical",
    "downloadUrl": "https://invalid.example/not-consulted",
}
assert set(acquisition_metadata).isdisjoint(
    key
    for source in lock.semantic_document()["expected"]["policySources"].values()
    for key in source
)
semantic_text = json.dumps(lock.semantic_document(), sort_keys=True)
assert archive_sha not in semantic_text
assert manifest_document["sourceMetadata"]["gitCommit"] not in semantic_text
assert "invalid.example" not in semantic_text

print(f"tooling source:       {installed.source_digest}")
print(f"tooling wheel:        {wheel_sha}")
print(f"arbitrary producer:   {release.distribution} {release.version}")
print(f"representation bytes: {validation.representation_sha256}")
print(f"materialized content: {validation.content_digest}")
print(f"composition:          {report['compositionDigest']}")
PY

(
  cd synthetic-release
  sha256sum --check --strict SHA256SUMS
)

printf '\nLocal installed-package generic policy-source conformance passed.\n'
