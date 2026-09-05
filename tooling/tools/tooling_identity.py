"""Independently observed source identity or locally verified installed wheel provenance.

A receipt retains the exact wheel locally. It is installation evidence, not a
signature or defense against replacement of the interpreter/trust root itself.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import sys
import sysconfig
import zipfile
from email.parser import BytesParser
from importlib import metadata
from pathlib import Path, PurePosixPath

from .tooling_source import TOOLING_SOURCE_DIGEST_ALGORITHM, tooling_source_digest

RECEIPT_SCHEMA = "compliance.example/tooling-wheel-receipt/v1alpha1"
RECEIPT_FILENAME = "compliance-wheel-receipt.json"
WHEEL_FILENAME = "compliance-provenance.whl"
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ToolingIdentityError(ValueError):
    """Required actual tooling provenance is unavailable or inconsistent."""


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _distribution() -> tuple[metadata.Distribution, Path]:
    try:
        dist = metadata.distribution("compliance-tooling")
    except metadata.PackageNotFoundError as error:
        raise ToolingIdentityError("installed compliance-tooling distribution is missing") from error
    paths = [Path(dist.locate_file(item)).parent for item in (dist.files or [])
             if str(item).endswith(".dist-info/METADATA")]
    if len(paths) != 1:
        raise ToolingIdentityError("installed distribution lacks unique dist-info/RECORD metadata")
    return dist, paths[0].resolve()


def _record(data: bytes) -> dict[str, tuple[str, str]]:
    result = {}
    for row in csv.reader(io.StringIO(data.decode("utf-8"))):
        if len(row) != 3 or not row[0] or row[0] in result:
            raise ToolingIdentityError("invalid or duplicate RECORD entry")
        result[row[0]] = (row[1], row[2])
    return result


def _verify_bytes(data: bytes, entry: tuple[str, str], name: str) -> None:
    digest = "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    if entry != (digest, str(len(data))):
        raise ToolingIdentityError(f"RECORD hash/size mismatch: {name}")


def _wheel_payload(wheel: bytes, dist_info: str) -> tuple[dict[str, bytes], dict]:
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ToolingIdentityError("duplicate wheel archive entry")
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or path.as_posix() != name.rstrip('/'):
                raise ToolingIdentityError(f"unsafe wheel path: {name}")
        names = [name for name in names if not name.endswith("/")]
        record_name = f"{dist_info}/RECORD"
        if record_name not in names:
            raise ToolingIdentityError("wheel does not match installed distribution")
        record = _record(archive.read(record_name))
        if set(record) != set(names) or record[record_name] != ('', ''):
            raise ToolingIdentityError("wheel RECORD does not cover exact archive file set")
        payload = {}
        for name in names:
            data = archive.read(name)
            if name != record_name:
                _verify_bytes(data, record[name], name)
                installed_name = name
                data_prefix = dist_info.removesuffix('.dist-info') + '.data/'
                if name.startswith(data_prefix):
                    purelib_prefix = data_prefix + 'purelib/'
                    if not name.startswith(purelib_prefix):
                        raise ToolingIdentityError(f"unsupported wheel installation scheme: {name}")
                    installed_name = name.removeprefix(purelib_prefix)
                if installed_name in payload:
                    raise ToolingIdentityError(f"colliding wheel install path: {installed_name}")
                payload[installed_name] = data
        release = json.loads(payload['tools/release-metadata.json'])
        if (release.get('schema') != 'compliance.example/tooling-release-metadata/v2'
                or release.get('source_digest_algorithm') != TOOLING_SOURCE_DIGEST_ALGORITHM
                or not isinstance(release.get('source_digest'), str)
                or not _DIGEST.fullmatch(release['source_digest'])):
            raise ToolingIdentityError("wheel lacks canonical tooling source provenance")
        return payload, release


def _validate_installation(dist: metadata.Distribution, info: Path, wheel: bytes) -> dict:
    """Compare wheel RECORD payload bytes and revalidate installation RECORD files."""
    payload, release = _wheel_payload(wheel, info.name)
    wheel_metadata = BytesParser().parsebytes(payload[f'{info.name}/METADATA'])
    if wheel_metadata['Name'] != 'compliance-tooling' or wheel_metadata['Version'] != dist.version:
        raise ToolingIdentityError("receipt wheel distribution/version mismatch")
    if Path(dist.locate_file('tools/tooling_identity.py')).resolve() != Path(__file__).resolve():
        raise ToolingIdentityError("executing tooling is not the receipt-bound installed distribution")
    installed = _record((info / 'RECORD').read_bytes())
    root = info.parent
    for name, data in payload.items():
        # Wheel .data/purelib paths were mapped to their installed locations.
        target = root / name
        if name not in installed or target.is_symlink() or target.read_bytes() != data:
            raise ToolingIdentityError(f"installed file differs from wheel RECORD: {name}")
        _verify_bytes(data, installed[name], name)
    record_name = f'{info.name}/RECORD'
    if installed.get(record_name) != ('', ''):
        raise ToolingIdentityError("installed RECORD self entry is missing or invalid")
    for name, entry in installed.items():
        target = root / name
        resolved = target.resolve()
        if not resolved.is_relative_to(Path(sys.prefix).resolve()):
            raise ToolingIdentityError(f"installed RECORD path escapes environment: {name}")
        if target.is_symlink() or not target.is_file():
            raise ToolingIdentityError(f"installed RECORD file unavailable: {name}")
        if name == record_name or (name.endswith('.pyc') and entry == ('', '')):
            continue
        _verify_bytes(target.read_bytes(), entry, name)
    # Unrecorded runtime modules/schema files must not expand the validated wheel.
    for directory in ('tools', 'schemas'):
        for path in (root / directory).rglob('*'):
            if path.is_file() and not (path.suffix == '.pyc' and '__pycache__' in path.parts):
                name = path.relative_to(root).as_posix()
                if name not in installed:
                    raise ToolingIdentityError(f"unrecorded installed runtime file: {name}")
    return release


def create_wheel_receipt(wheel: Path) -> Path:
    """Installation hook: validate locally supplied wheel, then retain it with receipt."""
    dist, info = _distribution()
    data = wheel.read_bytes()
    _validate_installation(dist, info, data)
    receipt = {
        'schema': RECEIPT_SCHEMA,
        'distribution': 'compliance-tooling',
        'version': dist.version,
        'wheelSha256': _sha(data),
        'installedRecordSha256': _sha((info / 'RECORD').read_bytes()),
    }
    (info / WHEEL_FILENAME).write_bytes(data)
    target = info / RECEIPT_FILENAME
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return target


def _installed_identity() -> dict:
    dist, info = _distribution()
    for name in (RECEIPT_FILENAME, WHEEL_FILENAME, 'RECORD'):
        if (info / name).is_symlink():
            raise ToolingIdentityError(f"receipt/RECORD evidence must be a regular file: {name}")
    receipt = json.loads((info / RECEIPT_FILENAME).read_text())
    wheel = (info / WHEEL_FILENAME).read_bytes()
    expected = {
        'schema': RECEIPT_SCHEMA,
        'distribution': 'compliance-tooling',
        'version': dist.version,
        'wheelSha256': _sha(wheel),
        'installedRecordSha256': _sha((info / 'RECORD').read_bytes()),
    }
    if receipt != expected:
        raise ToolingIdentityError("installed-wheel receipt mismatch")
    release = _validate_installation(dist, info, wheel)
    return {
        'source': {'digestAlgorithm': TOOLING_SOURCE_DIGEST_ALGORITHM, 'digest': release['source_digest']},
        'execution': {'kind': 'installed-wheel', 'wheelSha256': _sha(wheel)},
    }


def actual_tooling_identity() -> dict:
    """Resolve from executing module location, never from a lock or Git metadata."""
    root = Path(__file__).resolve().parents[1]
    try:
        # A complete source/editable tree has canonical build inputs at its root.
        # A wheel installation cannot downgrade to source based on added files.
        try:
            dist, info = _distribution()
        except ToolingIdentityError:
            dist, info = None, None
        installed_roots = {Path(sysconfig.get_path(key)).resolve() for key in ("purelib", "platlib")}
        if root in installed_roots or (info is not None and root == info.parent):
            return _installed_identity()
        return {
            'source': {'digestAlgorithm': TOOLING_SOURCE_DIGEST_ALGORITHM, 'digest': tooling_source_digest(root)},
            'execution': {'kind': 'source'},
        }
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        raise ToolingIdentityError(f"actual tooling identity unavailable: {error}") from error
