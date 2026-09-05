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
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"

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

temporary="$(mktemp -d "${TMPDIR:-/tmp}/compliance-tooling-package.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT
mkdir -p "$temporary/dist" "$temporary/runtime" "$temporary/no-git-bin"

cat > "$temporary/no-git-bin/git" <<'SH'
#!/usr/bin/env bash
echo "git must not be invoked during installed-package validation" >&2
exit 97
SH
chmod +x "$temporary/no-git-bin/git"
runtime_path="$temporary/no-git-bin:$PATH"

python "$TOOLING_ROOT/scripts/build-wheel.py" \
  --source-digest "$source_digest" \
  --output-dir "$temporary/dist"
set -- "$temporary/dist"/*.whl
[[ "$#" -eq 1 && -f "$1" ]] || fail "expected exactly one wheel"
wheel="$1"
[[ "$(basename "$wheel")" == compliance_tooling-*.whl ]] || fail "expected compliance_tooling wheel name"
wheel_sha="sha256:$(sha256sum "$wheel" | awk '{print $1}')"

python - "$wheel" <<'PY'
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
import sys
import zipfile

wheel = Path(sys.argv[1])
with zipfile.ZipFile(wheel) as archive:
    metadata_paths = [
        name for name in archive.namelist()
        if name.endswith(".dist-info/METADATA")
    ]
    assert len(metadata_paths) == 1, metadata_paths
    metadata = BytesParser(policy=default).parsebytes(
        archive.read(metadata_paths[0])
    )
assert metadata["Requires-Python"].replace(" ", "") == ">=3.13,<3.14", metadata
PY

python -m venv "$temporary/cache-prime-venv"
python "$TOOLING_ROOT/scripts/install-locked-wheel.py" \
  --python "$temporary/cache-prime-venv/bin/python" \
  --wheel "$wheel" \
  --cache-dir "$temporary/uv-cache"

python -m venv "$temporary/venv"
venv_python="$temporary/venv/bin/python"
venv_compliance="$temporary/venv/bin/compliance"
python "$TOOLING_ROOT/scripts/install-locked-wheel.py" \
  --python "$venv_python" \
  --wheel "$wheel" \
  --cache-dir "$temporary/uv-cache"

cd "$temporary/runtime"
PATH="$runtime_path" "$venv_compliance" --version
PATH="$runtime_path" "$venv_compliance" version --format json > release-identity.json

PATH="$runtime_path" "$venv_python" - "$source_digest" "$OPA_VERSION" <<'PY'
from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import tarfile
from importlib import resources
from pathlib import Path

import tools
from tools.policy_source_release import (
    POLICY_SOURCE_ARCHIVE_FORMAT,
    POLICY_SOURCE_RELEASE_SCHEMA,
    normalize_policy_source_release,
    policy_source_release_schema_path,
    validate_policy_source_archive,
)
from tools.policy_sources import source_tree_digest
from tools.release import tooling_release_identity
from tools.composition import POLICY_SOURCE_DIGEST_ALGORITHM
from tools.tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM

expected_digest, expected_opa = sys.argv[1:]
identity = tooling_release_identity()
assert identity.schema == "compliance.example/tooling-release-metadata/v2", identity
assert identity.distribution == "compliance-tooling", identity
assert identity.cli == "compliance", identity
assert identity.source_digest == expected_digest, identity
assert identity.source_digest_algorithm == TOOLING_SOURCE_DIGEST_ALGORITHM, identity
assert identity.tested_opa_version == expected_opa, identity
assert identity.build_kind == "release", identity
assert identity.version != "uninstalled", identity

json_identity = json.loads(Path("release-identity.json").read_text(encoding="utf-8"))
assert json_identity == identity.document(), (json_identity, identity.document())

package_root = resources.files("tools")
assert not package_root.joinpath("configuration.py").is_file()
for relative in (
    "schemas/assessment-plan-v4.schema.json",
    "schemas/assessment-results-v4.schema.json",
    "schemas/project-config-v1alpha3.schema.json",
    "schemas/composition.schema.json",
    "schemas/composition-lock-v1alpha1.schema.json",
    "schemas/policy-diff-set.schema.json",
    "schemas/policy-diff.schema.json",
    "schemas/policy-source-release-manifest.schema.json",
    "schemas/tooling-release-manifest-v2.schema.json",
    "schemas/project-registry.schema.json",
):
    resource = package_root.joinpath(relative)
    assert resource.is_file(), relative
    json.loads(resource.read_text(encoding="utf-8"))

for removed in (
    "schemas/assessment-plan.schema.json",
    "schemas/assessment-plan-v3.schema.json",
    "schemas/assessment-results.schema.json",
    "schemas/assessment-results-v3.schema.json",
    "schemas/project-config.schema.json",
    "schemas/project-config-v1alpha2.schema.json",
    "schemas/release-lock-v1alpha2.schema.json",

    "schemas/workspace-config.schema.json",
    "schemas/configuration-explanation.schema.json",
    "schemas/configuration-explanation-v3.schema.json",
    "schemas/assessment-plan-v2.schema.json",
    "schemas/assessment-results-v2.schema.json",
    "schemas/configuration-explanation-v2.schema.json",
    "schemas/configuration-plan.schema.json",
    "schemas/configuration-plan-v3.schema.json",
    "schemas/configuration-plan-v2.schema.json",
    "schemas/configuration-render-result.schema.json",
    "schemas/configuration-render-result-v3.schema.json",
    "schemas/configuration-render-result-v2.schema.json",
    "schemas/release-lock.schema.json",
    "schemas/tooling-release-manifest.schema.json",
):
    assert not package_root.joinpath(removed).is_file(), removed

assert not any(
    "release-manifest" in resource.name and "legacy" in resource.name
    for resource in package_root.joinpath("schemas").iterdir()
), "installed package contains a producer-specific legacy release schema"

generic_release = normalize_policy_source_release({
    "schema": POLICY_SOURCE_RELEASE_SCHEMA,
    "distribution": "installed-package/arbitrary-source",
    "version": "1.2.3",
    "content": {
        "digest": "sha256:" + "0" * 64,
        "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
    },
})
assert generic_release.distribution == "installed-package/arbitrary-source", generic_release
assert generic_release.semantic_document() == {
    "distribution": "installed-package/arbitrary-source",
    "version": "1.2.3",
    "content": {
        "digest": "sha256:" + "0" * 64,
        "digestAlgorithm": "compliance.example/policy-source-tree-digest/v1alpha1",
    },
}, generic_release
assert policy_source_release_schema_path().is_file()

fixture_root = Path("generic-policy-source-fixture")
source_policy = fixture_root / "source-policy"
source_control = source_policy / "controls" / "installed.rego"
source_control.parent.mkdir(parents=True)
source_control.write_text(
    "package compliance.installed\n\ndefault result := true\n",
    encoding="utf-8",
)
policy_digest = source_tree_digest(source_policy)
archive_path = fixture_root / "opaque-policy-source.asset"
with archive_path.open("wb") as raw:
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=raw,
        compresslevel=9,
        mtime=0,
    ) as compressed:
        with tarfile.open(
            fileobj=compressed,
            mode="w",
            format=tarfile.PAX_FORMAT,
        ) as archive:
            for name in ("policy/", "policy/controls/"):
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.mtime = 0
                archive.addfile(info)
            content = source_control.read_bytes()
            info = tarfile.TarInfo("policy/controls/installed.rego")
            info.type = tarfile.REGTYPE
            info.mode = 0o644
            info.mtime = 0
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))

archive_digest = "sha256:" + hashlib.sha256(archive_path.read_bytes()).hexdigest()
archive_release = normalize_policy_source_release(
    {
        "schema": POLICY_SOURCE_RELEASE_SCHEMA,
        "distribution": "installed-package/archive-source",
        "version": "4.5.6",
        "content": {
            "digest": policy_digest,
            "digestAlgorithm": POLICY_SOURCE_DIGEST_ALGORITHM,
        },
        "representations": [
            {
                "kind": "archive",
                "format": POLICY_SOURCE_ARCHIVE_FORMAT,
                "contentRoot": "policy",
                "filename": archive_path.name,
                "sha256": archive_digest,
            }
        ],
    }
)
materialized_policy = fixture_root / "materialized-policy"
archive_result = validate_policy_source_archive(
    archive_release,
    archive_release.representations[0],
    archive_path,
    materialize_to=materialized_policy,
)
assert archive_result.representation_sha256 == archive_digest, archive_result
assert archive_result.content_digest == policy_digest, archive_result
assert archive_result.file_count == 1, archive_result
assert archive_result.materialized_path == materialized_policy.resolve(), archive_result
assert source_tree_digest(materialized_policy) == policy_digest
assert (
    materialized_policy / "controls" / "installed.rego"
).read_bytes() == source_control.read_bytes()
print(
    "installed generic policy-source archive: "
    f"{archive_digest} -> {policy_digest}"
)

site_packages = Path(tools.__file__).resolve().parents[1]
for relative in (
    "schemas/inventory/resource.schema.json",
    "schemas/waivers/resource.schema.json",
):
    path = site_packages / relative
    assert path.is_file(), path
    json.loads(path.read_text(encoding="utf-8"))
assert str(Path(tools.__file__).resolve()).startswith(str(Path(sys.prefix).resolve())), tools.__file__
PY

project="$temporary/runtime/project"
mkdir -p \
  "$project/inventory" "$project/assignments" "$project/waivers" "$project/policy" \
  "$project/generated/evidence" "$project/generated/plans" "$project/generated/results"

cat > "$project/compliance.yaml" <<'YAML'
schema: compliance.example/project-config/v1alpha3
policySources:
  - name: local
    path: policy
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
YAML
cat > "$project/inventory/subject.yaml" <<'YAML'
apiVersion: compliance.example/v1alpha1
kind: Subject
metadata:
  name: package-host
spec:
  id: host/package-host
  type: linux
  lifecycle: active
  source:
    name: package-validation
    externalId: package-host
    observedAt: "2026-08-29T00:00:00Z"
YAML
cat > "$project/inventory/group.yaml" <<'YAML'
apiVersion: compliance.example/v1alpha1
kind: InventoryGroup
metadata:
  name: package-hosts
spec:
  subjectRefs:
    - id: host/package-host
YAML
cat > "$project/assignments/package-assignment.yaml" <<'YAML'
apiVersion: compliance.example/v1alpha1
kind: PolicyAssignment
metadata:
  name: package-hosts-policy
spec:
  targetRef:
    kind: InventoryGroup
    name: package-hosts
  baselineRefs:
    - name: package-validation-baseline
      revision: v1
YAML
cat > "$project/waivers/package-waiver.yaml" <<'YAML'
apiVersion: compliance.example/v1alpha1
kind: Waiver
metadata:
  name: package-validation
spec:
  subjectRef:
    id: host/package-host
  controlRef:
    instanceId: package-validation/control
  validFrom: "2026-08-29T00:00:00Z"
  expiresAt: "2027-08-29T00:00:00Z"
  rationale: Standalone package validation fixture.
  owner: package-validation
  approval:
    reference: PACKAGE-VALIDATION
    approvedBy: package-validation
    approvedAt: "2026-08-28T00:00:00Z"
YAML

"$venv_compliance" --config "$project/compliance.yaml" config validate
"$venv_compliance" --no-config inventory validate --inventory "$project/inventory" --assignments "$project/assignments"
"$venv_compliance" --no-config waiver validate --waivers "$project/waivers"

cat > "$temporary/runtime/compliance.yaml" <<'YAML'
schema: compliance.example/project-registry/v1alpha1
defaultProject: installed
projects:
  installed:
    config: project/compliance.yaml
YAML
PATH="$runtime_path" "$venv_compliance" config validate
PATH="$runtime_path" "$venv_compliance" --project installed config show --format json > registry-show.json
PATH="$runtime_path" "$venv_compliance" config list --format json > registry-list.json
PATH="$runtime_path" "$venv_python" - <<'PY'
import json
from pathlib import Path
from tools.project_config import load_config, ProjectConfigError

registry = Path("compliance.yaml")
direct = load_config(Path("project/compliance.yaml"))
selected = load_config(registry)
assert selected.source == direct.source
assert selected.paths == direct.paths
assert selected.policy_sources == direct.policy_sources
shown = json.loads(Path("registry-show.json").read_text())
listed = json.loads(Path("registry-list.json").read_text())
assert shown["project_registry"] == str(registry.resolve()), shown
assert listed["schema"] == "compliance.example/project-registry-list/v1", listed
assert listed["selected_project"] == listed["default_project"] == "installed", listed
assert "workspace" not in shown and "workspace" not in listed
retired = Path("retired.yaml")
retired.write_text(registry.read_text().replace("project-registry/v1alpha1", "workspace-config/v1alpha1"))
try:
    load_config(retired)
except ProjectConfigError as error:
    assert "unsupported configuration schema" in str(error), error
else:
    raise AssertionError("retired registry discriminator was accepted")
PY

printf 'Standalone tooling package validation passed for Python %s.\n' \
  "$("$venv_python" -c 'import platform; print(platform.python_version())')"

# Prove actual installed composition and v4 assessment without Git.
"$temporary/venv/bin/python" -I "$TOOLING_ROOT/scripts/check-installed-composition.py"
PATH="$runtime_path" "$temporary/venv/bin/python" -I "$TOOLING_ROOT/scripts/check-installed-assessment.py"
