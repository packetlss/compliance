#!/usr/bin/env python3
"""Repository-owned development toolchain and validation entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
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


def setup(_: argparse.Namespace) -> int:
    p = pins(); os_name, arch, checksum_key, triple = target(); uv, opa = selected()
    install_uv(p, uv, triple)
    install_opa(p, opa, os_name, arch, checksum_key)
    env = os.environ.copy(); env["UV_PROJECT_ENVIRONMENT"] = str(ENV)
    run([str(uv), "sync", "--project", "tooling", "--frozen", "--python", p["PYTHON_VERSION"]], env=env)
    return doctor(argparse.Namespace())


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
    for first, second in portability_collisions(ROOT):
        errors.append(f"case/Unicode-normalized filename collision: {first} and {second}")
    for error in errors: print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


COMMANDS = {
    "tooling": ["python", "-m", "unittest", "discover", "-s", "tooling/tests", "-v"],
    "policy": ["python", "-m", "unittest", "discover", "-s", "policy-sources/control-library/tests", "-v"],
    "projects": ["python", "-m", "unittest", "discover", "-s", "tests/development-projects", "-v"],
    "iam": ["python", "-m", "unittest", "discover", "-s", "tests/iam-private-boundary", "-v"],
    "scenarios": ["python", "-m", "unittest", "discover", "-s", "verification/scenarios/scripts", "-p", "test_*.py", "-v"],
}
GATES = {"repository": "scripts/validate-repository.sh", "tooling": "tooling/scripts/validate-tooling.sh", "policy": "policy-sources/control-library/scripts/validate-shared-policy.sh", "verification-policy": "policy-sources/verification-policy/scripts/validate-verification-policy.sh", "projects": "scripts/validate-development-projects.sh", "iam": "scripts/validate-iam-private-boundary.sh", "scenarios": "scripts/validate-verification-scenarios.sh", "package": "tooling/scripts/validate-package.sh", "locked-artifacts": "tooling/scripts/validate-locked-artifacts-package.sh", "release-preparation": "tooling/scripts/validate-release-preparation.sh", "policy-release": "tooling/scripts/validate-policy-release-compatibility.sh"}


def check(args: argparse.Namespace) -> int:
    uv, opa = selected(); env = os.environ.copy(); env.update(UV_PROJECT_ENVIRONMENT=str(ENV), PATH=f"{opa.parent}:{env['PATH']}", PYTHONDONTWRITEBYTECODE="1")
    python_paths = {"projects": ROOT / "scripts/development-projects", "iam": ROOT / "scripts/iam-private-boundary", "scenarios": ROOT / "verification/scenarios/scripts"}
    if args.area in python_paths:
        env["PYTHONPATH"] = str(python_paths[args.area])
    base = [str(uv), "run", "--project", "tooling", "--frozen"]
    if args.selection:
        if args.area != "tooling": raise SystemExit("named selection is currently supported for tooling tests")
        for pattern in args.selection:
            command = [*base, "python", "-m", "unittest", "discover", "-s", "tooling/tests", "-p", pattern, "-v"]
            result = run(command, check=False, env=env).returncode
            if result: return result
        return 0
    return run([*base, *COMMANDS[args.area]], check=False, env=env).returncode


def gate(args: argparse.Namespace) -> int:
    uv, opa = selected(); env = os.environ.copy(); env.update(UV_PROJECT_ENVIRONMENT=str(ENV), PATH=f"{ROOT / 'toolchain/bin'}:{ENV / 'bin'}:{uv.parent}:{opa.parent}:{env['PATH']}", COMPLIANCE_PYTHON=str(ENV / "bin/python"))
    return run(["bash", GATES[args.area]], check=False, env=env).returncode


def readiness(_: argparse.Namespace) -> int:
    if not shutil.which("gh"): print("ERROR: gh is required", file=sys.stderr); return 1
    pr = json.loads(run(["gh", "pr", "view", "--json", "headRefOid,baseRefName,body,reviews,statusCheckRollup"], capture=True).stdout)
    base = run(["git", "ls-remote", "origin", f"refs/heads/{pr['baseRefName']}"], capture=True).stdout.split()[0]
    head = pr["headRefOid"]; body = pr.get("body") or ""; required = {"component-validation", "verification-scenarios", "installed-release-provenance", "macos-portability"}
    checks = {c.get("name"): c.get("conclusion") or c.get("state") for c in pr.get("statusCheckRollup", [])}
    reviewed = {line.split(":", 1)[0].strip(" -"): line.split(":", 1)[1].strip() for line in body.splitlines() if ":" in line}
    merge_base = run(["git", "merge-base", head, base], capture=True).stdout.strip()
    errors = []
    if merge_base != base: errors.append(f"candidate does not contain current base head {base}")
    if reviewed.get("Reviewed head") != head: errors.append("independent review is missing or stale")
    if not reviewed.get("Reviewer/provider") or reviewed.get("Outcome and finding disposition", "").lower() not in {"pass", "approved", "no findings"}: errors.append("independent review outcome is not accepted")
    for name in sorted(required):
        if checks.get(name) not in {"SUCCESS", "success"}: errors.append(f"required check {name}: {checks.get(name, 'missing')}")
    print(f"PR head: {head}\nBase head: {base}\nReviewed head: {reviewed.get('Reviewed head', 'missing')}")
    for name in sorted(required): print(f"{name}: {checks.get(name, 'missing')}")
    for error in errors: print(f"NOT READY: {error}", file=sys.stderr)
    if not errors: print("READY: point-in-time evidence is exact-head and green")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("setup").set_defaults(func=setup); sub.add_parser("doctor").set_defaults(func=doctor); sub.add_parser("readiness").set_defaults(func=readiness)
    p = sub.add_parser("check"); p.add_argument("area", choices=COMMANDS); p.add_argument("selection", nargs=argparse.REMAINDER); p.set_defaults(func=check)
    p = sub.add_parser("gate"); p.add_argument("area", choices=GATES); p.set_defaults(func=gate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__": raise SystemExit(main())
