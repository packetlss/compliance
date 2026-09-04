"""Content-addressed identity for the OPA executable used by assessment runtime."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class EvaluatorIdentityError(ValueError):
    """The selected evaluator cannot be identified exactly."""


@dataclass(frozen=True)
class EvaluatorIdentity:
    name: str
    version: str
    executable_sha256: str

    def document(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "executableSha256": self.executable_sha256,
        }


def _resolve_executable(executable: str) -> Path:
    selected = shutil.which(executable)
    if selected is None:
        candidate = Path(executable).expanduser()
        if candidate.is_file():
            selected = str(candidate)
    if selected is None:
        raise EvaluatorIdentityError(f"OPA executable is unavailable: {executable!r}")
    path = Path(selected).resolve()
    if not path.is_file():
        raise EvaluatorIdentityError(f"OPA executable is not a regular file: {path}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _opa_version(path: Path) -> str:
    process = subprocess.run(
        [str(path), "version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip() or "unknown error"
        raise EvaluatorIdentityError(f"cannot read OPA version from {path}: {detail}")
    version: str | None = None
    for line in process.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == "version":
            version = value.strip()
            break
    if version is None or SEMVER_RE.fullmatch(version) is None:
        raise EvaluatorIdentityError(
            f"OPA version output lacks a strict semantic version: {process.stdout!r}"
        )
    return version


def resolve_opa_evaluator(
    executable: str = "opa",
) -> tuple[EvaluatorIdentity, str]:
    """Identify OPA and return the exact resolved path to use for evaluation."""
    path = _resolve_executable(executable)
    identity = EvaluatorIdentity(
        name="opa",
        version=_opa_version(path),
        executable_sha256=_sha256(path),
    )
    if not DIGEST_RE.fullmatch(identity.executable_sha256):
        raise EvaluatorIdentityError("computed OPA executable digest is invalid")
    return identity, str(path)


def opa_evaluator_identity(executable: str = "opa") -> EvaluatorIdentity:
    """Return version and digest for the exact OPA executable selected for execution."""
    identity, _ = resolve_opa_evaluator(executable)
    return identity
