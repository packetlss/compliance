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
uv_actual="$(uv --version | awk '{print $2}')"
[[ "$uv_actual" == "$UV_VERSION" ]] || fail "uv $UV_VERSION is required; found $uv_actual"

temporary="$(mktemp -d "${TMPDIR:-/tmp}/compliance-locked-artifacts.XXXXXX")"
trap 'rm -rf "$temporary"' EXIT
mkdir -p "$temporary/dist" "$temporary/runtime/project/materialized/shared"

source_digest="$(python - "$TOOLING_ROOT" <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from tools.tooling_source import tooling_source_digest
print(tooling_source_digest(Path(sys.argv[1])))
PY
)"
python "$TOOLING_ROOT/scripts/build-wheel.py" \
  --source-digest "$source_digest" \
  --output-dir "$temporary/dist"
set -- "$temporary/dist"/*.whl
[[ "$#" -eq 1 && -f "$1" ]] || fail "expected exactly one wheel"
wheel="$1"
[[ "$(basename "$wheel")" == compliance_tooling-*.whl ]] || fail "expected compliance_tooling wheel name"
wheel_sha="sha256:$(sha256sum "$wheel" | awk '{print $1}')"

python -m venv "$temporary/venv"
venv_python="$temporary/venv/bin/python"
venv_compliance="$temporary/venv/bin/compliance"
python "$TOOLING_ROOT/scripts/install-locked-wheel.py" \
  --python "$venv_python" \
  --wheel "$wheel" \
  --cache-dir "$temporary/uv-cache"

# All installed-package imports below must resolve from the wheel, not the source checkout.
cd "$temporary/runtime"

project="$temporary/runtime/project"
mkdir -p \
  "$project/inventory" \
  "$project/assignments" \
  "$project/waivers" \
  "$project/generated/evidence" \
  "$project/generated/plans" \
  "$project/generated/results"
printf '%s\n' '{"synthetic":"materialized-policy"}' > "$project/materialized/shared/content.json"

policy_digest="$("$venv_python" - "$project/materialized/shared" <<'PY'
from pathlib import Path
import sys
from tools.policy_sources import source_tree_digest
print(source_tree_digest(Path(sys.argv[1])))
PY
)"
tooling_version="$("$venv_python" - "$source_digest" <<'PY'
import sys
from tools.release import tooling_release_identity
identity = tooling_release_identity()
assert identity.distribution == "compliance-tooling", identity
assert identity.schema == "compliance.example/tooling-release-metadata/v2", identity
assert identity.source_digest == sys.argv[1], identity
print(identity.version)
PY
)"

cat > "$project/compliance.yaml" <<YAML
schema: compliance.example/project-config/v1alpha2
policySources:
  - name: shared
    path: materialized/shared
    digest: $policy_digest
paths:
  inventory: inventory
  assignments: assignments
  evidence: generated/evidence
  plan: generated/plans
  results: generated/results
  waivers: waivers
YAML

cat > "$project/compliance.lock.yaml" <<YAML
schema: compliance.example/release-lock/v1alpha2
tooling:
  distribution: compliance-tooling
  version: $tooling_version
  source:
    digest: $source_digest
    digestAlgorithm: compliance.example/tooling-source-tree-digest/v1alpha1
  artifact:
    kind: python-wheel
    sha256: $wheel_sha
policySources:
  shared:
    distribution: compliance-policy
    version: 0.2.0
    content:
      digest: $policy_digest
      digestAlgorithm: compliance.example/policy-source-tree-digest/v1alpha1
YAML

mkdir -p "$temporary/no-git-bin"
cat > "$temporary/no-git-bin/git" <<'SH'
#!/usr/bin/env bash
echo "git must not be invoked by locked artifact runtime" >&2
exit 97
SH
chmod +x "$temporary/no-git-bin/git"

fake_opa="$temporary/opa"
cat > "$fake_opa" <<SH
#!/usr/bin/env sh
if [ "\${1:-}" = version ]; then
  printf 'Version: $OPA_VERSION\n'
  exit 0
fi
printf '{}\n'
SH
chmod +x "$fake_opa"

PATH="$temporary/no-git-bin:$PATH" "$venv_python" - "$project" "$fake_opa" "$wheel_sha" <<'PY'
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from tools.artifact_provenance import locked_artifact_provenance
from tools.artifact_validation import validate_assessment_plan
from tools.locked_artifacts import (
    ASSESSMENT_PLAN_V3,
    ASSESSMENT_RESULTS_V3,
    evaluate_plan_v3,
    render_plan_v3,
    validate_assessment_plan_any,
    validate_assessment_results_any,
)
from tools.project_config import load_config
from tools.render_plan import content_digest

project = Path(sys.argv[1]).resolve()
fake_opa = Path(sys.argv[2]).resolve()
expected_wheel_sha = sys.argv[3]
config = load_config(project / "compliance.yaml")
provenance = locked_artifact_provenance(config)
assert provenance.artifact_version == 3, provenance
assert provenance.distribution == "compliance-tooling", provenance
assert provenance.artifact_sha256 == expected_wheel_sha, provenance
assert provenance.source_digest.startswith("sha256:"), provenance

base_plan = {
    "schema": "compliance.example/assessment-plan/v1",
    "policy_revision": "sha256:" + "1" * 64,
    "policy_sources": [{"name": "shared", "digest": config.policy_sources[0].expected_digest}],
    "inventory_revision": "sha256:" + "3" * 64,
    "assignment_revision": "sha256:" + "4" * 64,
    "subject": {
        "schema": "compliance.example/inventory-subject/v1",
        "id": "host/example",
        "type": "linux-host",
        "status": "active",
        "labels": {},
        "inventory": {
            "source": "package-validation",
            "external_id": "example",
            "observed_at": "2026-08-29T00:00:00Z",
        },
    },
    "resolved_groups": [],
    "assignments": [],
    "resolved_baselines": [],
    "resolved_requirement_baselines": [],
    "requirements": [],
    "controls": [],
    "excluded_controls": [],
    "coverage": {
        "status": "unassigned",
        "assessable": False,
        "reason": "no-policy-assignment",
        "assignment_count": 0,
        "active_control_count": 0,
        "excluded_control_count": 0,
        "requirement_count": 0,
    },
    "resolution": {"status": "valid", "errors": []},
}
base_plan["id"] = content_digest(base_plan)
validate_assessment_plan(base_plan)
plan = render_plan_v3(lambda: copy.deepcopy(base_plan), provenance)
assert plan["schema"] == ASSESSMENT_PLAN_V3
assert plan["generator"]["source_digest"] == provenance.source_digest
assert plan["generator"]["artifact_sha256"] == expected_wheel_sha
assert plan["release_lock_digest"] == provenance.release_lock_digest
validate_assessment_plan_any(plan)


def fake_evaluate(projected, *_args, **kwargs):
    assert Path(kwargs["opa"]) == fake_opa
    return {
        "schema": "compliance.example/assessment-results/v1",
        "assessment_id": "assessment:" + projected["id"].removeprefix("sha256:")[:16],
        "evaluated_at": "2026-08-29T00:00:00Z",
        "plan_id": projected["id"],
        "policy_revision": projected["policy_revision"],
        "inventory_revision": projected["inventory_revision"],
        "assignment_revision": projected["assignment_revision"],
        "subject_id": projected["subject"]["id"],
        "summary": {"pass": 0, "fail": 0, "unknown": 0, "not_applicable": 0, "error": 0, "waived": 0},
        "requirement_summary": {"pass": 0, "fail": 0, "unknown": 0, "not_applicable": 0, "error": 0, "waived": 0},
        "requirement_baseline_summary": {"pass": 0, "fail": 0, "unknown": 0, "not_applicable": 0, "error": 0, "waived": 0},
        "results": [],
        "requirement_assessments": [],
        "requirement_baseline_assessments": [],
    }

results = evaluate_plan_v3(
    fake_evaluate,
    provenance,
    plan,
    project / "generated/evidence",
    (),
    opa=str(fake_opa),
)
assert results["schema"] == ASSESSMENT_RESULTS_V3
assert results["plan_id"] == plan["id"]
assert results["evaluator"]["name"] == "opa"
assert results["evaluator"]["executableSha256"].startswith("sha256:")
validate_assessment_results_any(results)

(project / "generated/plans/host__example.json").write_text(
    json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)

lock_path = project / "compliance.lock.yaml"
lock_text = lock_path.read_text(encoding="utf-8")
changed_wheel = "sha256:" + "d" * 64
lock_path.write_text(lock_text.replace(expected_wheel_sha, changed_wheel), encoding="utf-8")
new_provenance = locked_artifact_provenance(load_config(project / "compliance.yaml"))
assert new_provenance.release_lock_digest != provenance.release_lock_digest
PY

# Restore the original lock so the console validates and inspects the stored v3 plan.
python - "$project/compliance.lock.yaml" "$wheel_sha" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace("sha256:" + "d" * 64, sys.argv[2]))
PY
PATH="$temporary/no-git-bin:$PATH" "$venv_compliance" \
  --config "$project/compliance.yaml" \
  plan show host/example --format json > "$temporary/runtime/v3-plan-show.json"
PATH="$temporary/no-git-bin:$PATH" "$venv_compliance" \
  --config "$project/compliance.yaml" \
  policy diff "$project/generated/plans/host__example.json" \
  "$project/generated/plans/host__example.json" --format json \
  > "$temporary/runtime/v3-policy-diff.json"

"$venv_python" - "$temporary/runtime/v3-plan-show.json" "$temporary/runtime/v3-policy-diff.json" <<'PY'
import json
import sys
from pathlib import Path
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
diff = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
assert plan["schema"] == "compliance.example/assessment-plan/v3", plan
assert plan["generator"]["distribution"] == "compliance-tooling", plan
assert diff["summary"]["changed"] is False, diff
PY

printf 'Installed locked-artifact v3 validation passed.\n'
