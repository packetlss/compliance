#!/usr/bin/env python3
"""Repository-owned development toolchain and validation entrypoint."""
from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
import platform
import re
import unicodedata
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get("COMPLIANCE_DEV_CACHE", Path.home() / ".cache/compliance-dev"))
ENV = ROOT / ".dev" / "venv"
SETUP_LOCK = ROOT / ".dev" / "setup.lock"
READINESS_STAMP = ROOT / ".dev" / "setup-readiness.json"
LOCK_HELD_ENV = "COMPLIANCE_DEV_SETUP_LOCK_HELD"
READINESS_INPUTS = (
    ROOT / "toolchain/versions.env",
    ROOT / "tooling/pyproject.toml",
    ROOT / "tooling/uv.lock",
)


def pins() -> dict[str, str]:
    values = {}
    for line in (ROOT / "toolchain/versions.env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def target() -> tuple[str, str, str, str]:
    system, machine = platform.system(), platform.machine().lower()
    mapping = {
        ("Darwin", "arm64"): ("darwin", "arm64", "OPA_DARWIN_ARM64_STATIC_SHA256", "aarch64-apple-darwin"),
        ("Linux", "x86_64"): ("linux", "amd64", "OPA_LINUX_AMD64_STATIC_SHA256", "x86_64-unknown-linux-gnu"),
    }
    if (system, machine) not in mapping:
        raise SystemExit(f"unsupported development platform: {system}/{machine}; supported: Darwin/arm64, Linux/x86_64")
    return mapping[(system, machine)]


def normalized_name_collisions(names: list[str]) -> list[tuple[str, str]]:
    """Report names that collide on common case/Unicode-normalizing filesystems."""
    seen: dict[tuple[str, str], str] = {}
    collisions = []
    for relative in sorted(names):
        parent, _, name = relative.rpartition("/")
        key = (unicodedata.normalize("NFC", parent).casefold(), unicodedata.normalize("NFC", name).casefold())
        if key in seen and seen[key] != relative:
            collisions.append((seen[key], relative))
        else:
            seen[key] = relative
    return collisions


def portability_collisions(root: Path) -> list[tuple[str, str]]:
    return normalized_name_collisions([path.relative_to(root).as_posix() for path in root.rglob("*")])


def run(argv: list[str], *, check: bool = True, capture: bool = False, env=None):
    return subprocess.run(argv, cwd=ROOT, check=check, text=True,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None, env=env)


def version(argv: list[str]) -> str | None:
    try:
        return run(argv, capture=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def selected() -> tuple[Path, Path]:
    p = pins()
    uv = CACHE / f"uv-{p['UV_VERSION']}" / "uv"
    opa = CACHE / f"opa-{p['OPA_VERSION']}" / f"{target()[0]}-{target()[1]}" / "opa"
    return uv, opa


def readiness_metadata() -> dict[str, object]:
    """Return the inputs that make this worktree's managed environment valid."""
    return {
        "version": 1,
        "inputs": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in READINESS_INPUTS
        },
    }


def read_readiness_stamp() -> dict[str, object] | None:
    try:
        value = json.loads(READINESS_STAMP.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def readiness_errors(*, require_stamp: bool = True) -> list[str]:
    """Check managed-tool readiness without creating or changing any state."""
    p = pins()
    try:
        _, _, _, _ = target()
    except SystemExit as error:
        return [str(error)]
    uv, opa = selected()
    python = ENV / "bin/python"
    entrypoint = ENV / "bin/compliance"
    checks = (
        ("uv", uv, version([str(uv), "--version"]), f"uv {p['UV_VERSION']}"),
        ("OPA", opa, version([str(opa), "version"]), f"Version: {p['OPA_VERSION']}"),
        ("Python", python, version([str(python), "-c", "import platform; print(platform.python_version())"]), p["PYTHON_VERSION"]),
    )
    errors = [
        f"{name} {expected} is not selected; run scripts/dev setup"
        for name, _, actual, expected in checks
        if actual is None or expected not in actual
    ]
    if not entrypoint.is_file() or not os.access(entrypoint, os.X_OK):
        errors.append("managed compliance entry point is missing; run scripts/dev setup")
    if require_stamp and read_readiness_stamp() != readiness_metadata():
        errors.append("managed environment is missing or stale for current inputs; run scripts/dev setup")
    return errors


@contextlib.contextmanager
def setup_lock():
    """Serialize setup and setup-aware commands within one worktree."""
    SETUP_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with SETUP_LOCK.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield lock
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def managed_command_lock():
    """Hold setup protection, while permitting nested managed commands to run."""
    if os.environ.get(LOCK_HELD_ENV) == "1":
        yield None
        return
    with setup_lock() as lock:
        yield lock


def write_readiness_stamp() -> None:
    """Atomically publish readiness only after a successful setup validation."""
    temporary = READINESS_STAMP.with_suffix(".tmp")
    temporary.write_text(json.dumps(readiness_metadata(), sort_keys=True) + "\n")
    temporary.replace(READINESS_STAMP)


def portability_errors() -> list[str]:
    return [
        f"case/Unicode-normalized filename collision: {first} and {second}"
        for first, second in portability_collisions(ROOT)
    ]


def fetch(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(".download")
    try:
        urllib.request.urlretrieve(url, partial)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def install_uv(p: dict[str, str], uv: Path, triple: str) -> None:
    if (version([str(uv), "--version"]) or "").startswith(f"uv {p['UV_VERSION']} "):
        return
    base = f"https://github.com/astral-sh/uv/releases/download/{p['UV_VERSION']}"
    archive_name = f"uv-{triple}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / archive_name
        checksums = Path(tmp) / "sha256.sum"
        fetch(f"{base}/{archive_name}", archive)
        fetch(f"{base}/sha256.sum", checksums)
        expected = next((line.split()[0] for line in checksums.read_text().splitlines() if line.endswith(archive_name)), None)
        actual = hashlib.sha256(archive.read_bytes()).hexdigest()
        if not expected or actual != expected:
            raise SystemExit(f"uv checksum mismatch for {archive_name}")
        with tarfile.open(archive, "r:gz") as bundle:
            member = next(m for m in bundle.getmembers() if Path(m.name).name == "uv")
            source = bundle.extractfile(member)
            assert source
            uv.parent.mkdir(parents=True, exist_ok=True)
            uv.write_bytes(source.read())
            uv.chmod(0o755)


def install_opa(p: dict[str, str], opa: Path, os_name: str, arch: str, checksum_key: str) -> None:
    if opa.exists() and hashlib.sha256(opa.read_bytes()).hexdigest() == p[checksum_key]:
        return
    fetch(f"https://github.com/open-policy-agent/opa/releases/download/v{p['OPA_VERSION']}/opa_{os_name}_{arch}_static", opa)
    actual = hashlib.sha256(opa.read_bytes()).hexdigest()
    if actual != p[checksum_key]:
        opa.unlink(missing_ok=True)
        raise SystemExit(f"OPA checksum mismatch: expected {p[checksum_key]}, found {actual}")
    opa.chmod(0o755)


def setup_under_lock() -> int:
    """Prepare the environment while the caller holds ``setup_lock``."""
    if not readiness_errors():
        return 0
    # A stamp must never describe an environment while it is being changed.
    READINESS_STAMP.unlink(missing_ok=True)
    p = pins(); os_name, arch, checksum_key, triple = target(); uv, opa = selected()
    try:
        install_uv(p, uv, triple)
        install_opa(p, opa, os_name, arch, checksum_key)
        env = os.environ.copy(); env["UV_PROJECT_ENVIRONMENT"] = str(ENV)
        run([str(uv), "sync", "--project", "tooling", "--frozen", "--python", p["PYTHON_VERSION"]], env=env)
    except subprocess.CalledProcessError as error:
        print(
            f"ERROR: managed setup failed (exit {error.returncode}); "
            "the requested command was not run",
            file=sys.stderr,
        )
        return error.returncode or 1
    if errors := readiness_errors(require_stamp=False):
        print("ERROR: managed setup did not produce a ready environment:", file=sys.stderr)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if errors := portability_errors():
        print("ERROR: managed setup did not pass repository portability checks:", file=sys.stderr)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    write_readiness_stamp()
    return 0


def setup(args: argparse.Namespace) -> int:
    """Prepare this worktree's environment, serializing all mutable setup work."""
    if getattr(args, "target", "main") == "successor":
        print("Successor foundation uses Python 3 standard library and Git; run scripts/dev foundation.")
        return 0
    with setup_lock():
        return setup_under_lock()


def doctor(_: argparse.Namespace) -> int:
    p = pins(); os_name, arch, _, _ = target(); uv, opa = selected(); errors = []
    uv_v = version([str(uv), "--version"])
    opa_v = version([str(opa), "version"])
    py = ENV / "bin/python"
    py_v = version([str(py), "-c", "import platform; print(platform.python_version())"])
    print(f"platform: {platform.system()}/{platform.machine()} ({os_name}/{arch})")
    for name, path, actual, expected in (("uv", uv, uv_v, f"uv {p['UV_VERSION']}"), ("OPA", opa, opa_v, f"Version: {p['OPA_VERSION']}"), ("Python", py, py_v, p["PYTHON_VERSION"])):
        print(f"{name}: {path} [{actual or 'missing'}]")
        if actual is None or expected not in actual:
            errors.append(f"{name} {expected} is not selected; run scripts/dev setup")
    entrypoint = ENV / "bin/compliance"
    print(f"compliance: {entrypoint} [{'ready' if entrypoint.is_file() and os.access(entrypoint, os.X_OK) else 'missing'}]")
    if not entrypoint.is_file() or not os.access(entrypoint, os.X_OK):
        errors.append("managed compliance entry point is missing; run scripts/dev setup")
    if read_readiness_stamp() != readiness_metadata():
        errors.append("managed environment is missing or stale for current inputs; run scripts/dev setup")
    errors.extend(portability_errors())
    for error in errors: print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


def ensure_ready_under_lock() -> int:
    """Repair this worktree only after the caller has acquired ``setup_lock``."""
    if not readiness_errors():
        return 0
    return setup_under_lock()


COMMANDS = {
    "tooling": ["python", "-m", "unittest", "discover", "-s", "tooling/tests"],
    "policy": ["python", "-m", "unittest", "discover", "-s", "policy-sources/control-library/tests"],
    "projects": ["python", "-m", "unittest", "discover", "-s", "tests/development-projects"],
    "iam": ["python", "-m", "unittest", "discover", "-s", "tests/iam-private-boundary"],
    "scenarios": ["python", "-m", "unittest", "discover", "-s", "verification/scenarios/scripts", "-p", "test_*.py"],
}
GATES = {"repository": "scripts/validate-repository.sh", "tooling": "tooling/scripts/validate-tooling.sh", "policy": "policy-sources/control-library/scripts/validate-shared-policy.sh", "verification-policy": "policy-sources/verification-policy/scripts/validate-verification-policy.sh", "projects": "scripts/validate-development-projects.sh", "iam": "scripts/validate-iam-private-boundary.sh", "scenarios": "scripts/validate-verification-scenarios.sh", "package": "tooling/scripts/validate-package.sh", "locked-artifacts": "tooling/scripts/validate-locked-artifacts-package.sh", "release-preparation": "tooling/scripts/validate-release-preparation.sh", "policy-release": "tooling/scripts/validate-policy-release-compatibility.sh"}


def check(args: argparse.Namespace) -> int:
    with managed_command_lock():
        if result := ensure_ready_under_lock():
            return result
        uv, opa = selected(); env = os.environ.copy(); env.update(UV_PROJECT_ENVIRONMENT=str(ENV), PATH=f"{opa.parent}:{env['PATH']}", PYTHONDONTWRITEBYTECODE="1", **{LOCK_HELD_ENV: "1"})
        python_paths = {"projects": ROOT / "scripts/development-projects", "iam": ROOT / "scripts/iam-private-boundary", "scenarios": ROOT / "verification/scenarios/scripts"}
        if args.area in python_paths:
            env["PYTHONPATH"] = str(python_paths[args.area])
        base = [str(uv), "run", "--project", "tooling", "--frozen"]
        if args.selection:
            if args.area != "tooling": raise SystemExit("named selection is currently supported for tooling tests")
            for pattern in args.selection:
                command = [*base, *COMMANDS[args.area], "-p", pattern]
                if args.verbose:
                    command.append("-v")
                result = run(command, check=False, env=env).returncode
                if result: return result
            return 0
        command = [*base, *COMMANDS[args.area]]
        if args.verbose:
            command.append("-v")
        return run(command, check=False, env=env).returncode


def gate(args: argparse.Namespace) -> int:
    with managed_command_lock():
        if result := ensure_ready_under_lock():
            return result
        uv, opa = selected(); env = os.environ.copy(); env.update(UV_PROJECT_ENVIRONMENT=str(ENV), PATH=f"{ROOT / 'toolchain/bin'}:{ENV / 'bin'}:{uv.parent}:{opa.parent}:{env['PATH']}", COMPLIANCE_PYTHON=str(ENV / "bin/python"), **{LOCK_HELD_ENV: "1"})
        return run(["bash", GATES[args.area]], check=False, env=env).returncode


def cli(arguments: list[str]) -> int:
    """Replace this process with the managed product CLI from the repository root."""
    with managed_command_lock() as lock:
        if result := ensure_ready_under_lock():
            return result
        _, opa = selected()
        python = ENV / "bin/python"
        entrypoint = ENV / "bin/compliance"
        required = (python, entrypoint, opa)
        if any(not path.is_file() or not os.access(path, os.X_OK) for path in required):
            print(
                "ERROR: managed development environment is unavailable; "
                "run scripts/dev setup",
                file=sys.stderr,
            )
            return 1
        env = os.environ.copy()
        env["PATH"] = os.pathsep.join(
            (str(opa.parent), str(ENV / "bin"), env.get("PATH", ""))
        )
        env[LOCK_HELD_ENV] = "1"
        # execve bypasses the context manager's cleanup, so keep the advisory
        # lock open in the product process until the managed command exits.
        if lock is not None:
            os.set_inheritable(lock.fileno(), True)
        os.chdir(ROOT)
        os.execve(str(entrypoint), [str(entrypoint), *arguments], env)
    raise AssertionError("execve returned unexpectedly")


REQUIRED_HEAD_CONTEXTS = {
    "component-validation",
    "verification-scenarios",
    "installed-release-provenance",
    "macos-portability",
}
INTEGRATION_CONTEXT = "integration-current-main"
SUCCESS_STATES = {"SUCCESS", "success"}
BASE_DESCRIPTION = re.compile(r"base=([0-9a-f]{40})")

# Deliberately bounded bootstrap routing, not a configurable impact framework.
# A separately reviewed executable contract must extend the successor scope and
# both head/integration responsibilities together before application work lands.
SUCCESSOR_FILES = {
    "successor/AGENTS.md", "successor/README.md",
    "docs/SUCCESSOR_ARCHITECTURE.md", "docs/adr/0025-trusted-snapshot-successor.md",
}
SHARED_FILES = {
    "AGENTS.md", "README.md", "t3.json", "scripts/dev", "toolchain/dev.py",
    "scripts/validate-repository.sh", "docs/ARCHITECTURE.md",
    "docs/CONTRACT_MATURITY.md", "docs/DEVELOPMENT_WORKFLOW.md", "docs/REPOSITORIES.md",
    ".github/ISSUE_TEMPLATE/implementation.md", ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/destination-validation.yml",
    ".github/workflows/current-main-integration.yml",
    "tests/toolchain/test_dev.py", "tests/toolchain/test_lanes.py",
    "tests/toolchain/test_canonical_validation_output.py",
}


def integration_target(value: object) -> str:
    if value not in ("main", "successor"):
        raise SystemExit(f"ERROR: unsupported integration target {value!r}; expected main or successor")
    return str(value)


def legacy_required(target_ref: str, paths: list[str]) -> bool:
    integration_target(target_ref)
    if target_ref == "main":
        return True
    refused = sorted(set(paths) - SUCCESSOR_FILES - SHARED_FILES)
    if refused:
        raise SystemExit(
            "ERROR: successor bootstrap scope refuses: " + ", ".join(refused)
            + ". Legacy application/build/fixture changes require a separately reviewed "
            "cross-boundary contract; executable successor scope and real checks belong to #209."
        )
    return bool(set(paths) & SHARED_FILES)


def changed_paths(base: str, head: str) -> list[str]:
    for sha in (base, head):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise SystemExit("ERROR: scope requires exact 40-hex base and head SHAs")
    # No rename detection: both sides of a move must pass scope admission.
    output = run(["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"], capture=True).stdout
    return [path for path in output.split("\0") if path]


def route(args: argparse.Namespace) -> int:
    required = legacy_required(args.target, changed_paths(args.base, args.head))
    print(f"target={args.target}\nlegacy={str(required).lower()}")
    return 0


def foundation(_: argparse.Namespace) -> int:
    """Real bootstrap infrastructure tests, without installing the legacy stack."""
    return run([sys.executable, "-m", "unittest", "discover", "-s", "tests/toolchain",
                "-p", "test_lanes.py"], check=False).returncode


def task(args: argparse.Namespace) -> int:
    base = current_base({"baseRefName": args.target})
    print(f"Integration target: {args.target}\nCurrent integration base: {base}")
    print(f"Create a new T3 worktree from this verified {args.target} revision; target its PR at {args.target}.")
    if args.target == "successor":
        print("Requires recorded post-merge #208 activation. Read successor/AGENTS.md at that revision.")
    return 0


def status_name(status: dict[str, object]) -> str | None:
    """Return the shared name from a check-run or legacy commit-status shape."""
    value = status.get("name") or status.get("context")
    return value if isinstance(value, str) else None


def status_result(status: dict[str, object]) -> str | None:
    """Return the shared conclusion/state from a check-run or commit-status."""
    value = status.get("conclusion") or status.get("state")
    return value if isinstance(value, str) else None


def status_description(status: dict[str, object]) -> str | None:
    value = status.get("description")
    return value if isinstance(value, str) else None


def integration_base(status: dict[str, object]) -> str | None:
    """Read the deliberately narrow, machine-readable integration base binding."""
    description = status_description(status)
    if description is None:
        return None
    match = BASE_DESCRIPTION.fullmatch(description.strip())
    return match.group(1) if match else None


def latest_named_status(statuses: list[dict[str, object]], name: str) -> dict[str, object] | None:
    """Return the API's newest matching context (GitHub returns statuses newest first)."""
    return next((status for status in statuses if status_name(status) == name), None)


def current_base(pr: dict[str, object]) -> str:
    base_ref = integration_target(pr.get("baseRefName"))
    output = run(["git", "ls-remote", "origin", f"refs/heads/{base_ref}"], capture=True).stdout.split()
    if not output or not re.fullmatch(r"[0-9a-f]{40}", output[0]):
        raise SystemExit(f"ERROR: could not resolve current base ref {base_ref}")
    return output[0]


def trusted_legacy_required(target_ref: str, base: str, paths: list[str]) -> bool:
    """Use the reviewed target's classifier, never the proposed checkout's policy."""
    if integration_target(target_ref) == "main":
        return True
    payload = json.loads(run([
        "gh", "api", f"repos/{{owner}}/{{repo}}/contents/toolchain/dev.py?ref={base}",
    ], capture=True).stdout)
    source = base64.b64decode(payload["content"]).decode("utf-8")
    # Only the fixed file at exact trusted B is loaded. __main__ is not invoked;
    # the stdlib-only classifier consumes filenames, not proposed file contents.
    namespace = {"__name__": "trusted_target_scope", "__file__": str(ROOT / "toolchain/dev.py")}
    exec(compile(source, f"{base}:toolchain/dev.py", "exec"), namespace)
    return namespace["legacy_required"](target_ref, paths)


def commit_statuses(head: str) -> list[dict[str, object]]:
    """Read legacy commit statuses, whose descriptions bind integration to a base."""
    payload = json.loads(run(["gh", "api", f"repos/{{owner}}/{{repo}}/commits/{head}/status"], capture=True).stdout)
    statuses = payload.get("statuses", [])
    return [status for status in statuses if isinstance(status, dict)] if isinstance(statuses, list) else []


def locally_contains_base(head: str, base: str) -> bool:
    """Return true only when local Git can prove that base is an ancestor of head.

    ``base`` is deliberately resolved from the remote without updating local refs.
    A stale PR checkout may not have that object, in which case ``merge-base``
    exits nonzero. That is not an error for readiness: it simply means the fast
    ancestry proof is unavailable and exact integration evidence is required.
    """
    try:
        result = run(["git", "merge-base", "--is-ancestor", base, head], check=False, capture=True)
    except OSError:
        return False
    return result.returncode == 0


def readiness(args: argparse.Namespace) -> int:
    if not shutil.which("gh"):
        print("ERROR: gh is required", file=sys.stderr)
        return 1
    pr = json.loads(run(["gh", "pr", "view", "--json", "number,state,headRefOid,baseRefName,body,reviews,statusCheckRollup,files,changedFiles"], capture=True).stdout)
    head = pr.get("headRefOid")
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        print("ERROR: PR head is missing or invalid", file=sys.stderr)
        return 1
    target_ref = integration_target(pr.get("baseRefName"))
    if getattr(args, "target", None) not in (None, target_ref):
        print("NOT READY: requested target differs from the PR target", file=sys.stderr)
        return 1
    if len(pr.get("files", [])) != pr.get("changedFiles"):
        print("NOT READY: incomplete changed-file metadata; cannot establish affected responsibilities", file=sys.stderr)
        return 1
    base = current_base(pr)
    required = set(REQUIRED_HEAD_CONTEXTS) if trusted_legacy_required(
        target_ref, base, [entry["path"] for entry in pr.get("files", [])]
    ) else set()
    if target_ref == "successor":
        required.add("successor-foundation")
    context = f"integration-current-{target_ref}"
    body = pr.get("body") or ""
    rollup = [status for status in pr.get("statusCheckRollup", []) if isinstance(status, dict)]
    # Reject ambiguous duplicate contexts instead of accepting whichever comes last.
    checks = {}
    for status in rollup:
        name = status_name(status)
        if name:
            checks[name] = status_result(status) if name not in checks else "ambiguous duplicate"
    reviewed = {line.split(":", 1)[0].strip(" -"): line.split(":", 1)[1].strip() for line in body.splitlines() if ":" in line}
    errors = []
    if pr.get("state") != "OPEN":
        errors.append("PR is not open")
    if reviewed.get("Reviewed target") != target_ref:
        errors.append("independent review target is missing or stale after retargeting")
    contains_base = locally_contains_base(head, base)
    integration = None
    if not contains_base:
        # Check-runs and commit-statuses use different field names. The legacy
        # status endpoint is authoritative for the status description we bind.
        integration = latest_named_status(commit_statuses(head), context)
        if integration is None:
            errors.append(f"current-base integration evidence is missing for {base}")
        elif status_result(integration) not in SUCCESS_STATES:
            errors.append(f"current-base integration: {status_result(integration) or 'missing'}")
        elif integration_base(integration) != base:
            errors.append(f"current-base integration is not bound to current base {base}")
    if reviewed.get("Reviewed head") != head:
        errors.append("independent review is missing or stale")
    if not reviewed.get("Reviewer/provider") or reviewed.get("Outcome and finding disposition", "").lower() not in {"pass", "approved", "no findings"}:
        errors.append("independent review outcome is not accepted")
    for name in sorted(required):
        if checks.get(name) not in SUCCESS_STATES:
            errors.append(f"required check {name}: {checks.get(name, 'missing')}")
    print(f"Integration target: {target_ref}\nPR head: {head}\nBase head: {base}\nReviewed head: {reviewed.get('Reviewed head', 'missing')}")
    for name in sorted(required):
        print(f"{name}: {checks.get(name, 'missing')}")
    if not contains_base:
        print(f"{context}: {status_result(integration) if integration else 'missing'}")
        print(f"Integration base: {integration_base(integration) if integration else 'missing'}")
    # A read-only readiness observation must end at the same open H/target/B.
    final = json.loads(run(["gh", "pr", "view", str(pr["number"]), "--json",
                           "state,headRefOid,baseRefName"], capture=True).stdout)
    if (final.get("state"), final.get("headRefOid"), final.get("baseRefName")) != ("OPEN", head, target_ref):
        errors.append("PR closed, head changed or target changed during readiness; retry")
    elif current_base(final) != base:
        errors.append("target base advanced during readiness; refresh integration evidence")
    for error in errors:
        print(f"NOT READY: {error}", file=sys.stderr)
    if not errors:
        print("READY: exact PR-head evidence and current-base integration evidence are green")
    return 1 if errors else 0


def integration(args: argparse.Namespace) -> int:
    """Explicitly request trusted current-base integration; never alter the branch."""
    if not shutil.which("gh"):
        print("ERROR: gh is required", file=sys.stderr)
        return 1
    pr = json.loads(run(["gh", "pr", "view", "--json", "number,headRefOid,baseRefName"], capture=True).stdout)
    number, head = pr.get("number"), pr.get("headRefOid")
    if not isinstance(number, int) or not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        print("ERROR: current PR number or head is missing or invalid", file=sys.stderr)
        return 1
    base = current_base(pr)
    target_ref = integration_target(pr.get("baseRefName"))
    if getattr(args, "target", None) not in (None, target_ref):
        print("ERROR: requested target differs from the PR target", file=sys.stderr)
        return 1
    print(f"Requesting integration-current-{target_ref} for PR #{number}: head={head} base={base}")
    # The file must be registered on default main, but execution comes from the
    # actual trusted target, so successor-owned checks can evolve on successor.
    result = run([
        "gh", "workflow", "run", "current-main-integration.yml", "--ref", target_ref,
        "-f", f"pr_number={number}",
    ], check=False)
    if result.returncode:
        print("ERROR: could not dispatch current-base integration", file=sys.stderr)
        return result.returncode or 1
    print("Requested trusted integration workflow; run scripts/dev readiness after it completes.")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "cli":
        return cli(sys.argv[2:])
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("setup"); p.add_argument("--target", choices=("main", "successor"), default="main"); p.set_defaults(func=setup)
    sub.add_parser("doctor").set_defaults(func=doctor)
    sub.add_parser("foundation", help="test bootstrap infrastructure without the legacy stack").set_defaults(func=foundation)
    p = sub.add_parser("task", help="resolve the explicit task target without changing refs"); p.add_argument("--target", choices=("main", "successor"), required=True); p.set_defaults(func=task)
    p = sub.add_parser("route", help="check bounded PR scope at exact revisions"); p.add_argument("--target", choices=("main", "successor"), required=True); p.add_argument("--base", required=True); p.add_argument("--head", required=True); p.set_defaults(func=route)
    for command, function in (("readiness", readiness), ("integration", integration)):
        p = sub.add_parser(command); p.add_argument("--target", choices=("main", "successor")); p.set_defaults(func=function)
    sub.add_parser("cli", help="run the managed compliance CLI from the repository root")
    p = sub.add_parser("check"); p.add_argument("--verbose", action="store_true", help="show every test while it runs"); p.add_argument("area", choices=COMMANDS); p.add_argument("selection", nargs=argparse.REMAINDER); p.set_defaults(func=check)
    p = sub.add_parser("gate"); p.add_argument("area", choices=GATES); p.set_defaults(func=gate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__": raise SystemExit(main())
