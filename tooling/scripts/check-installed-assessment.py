#!/usr/bin/env python3
"""Use only installed runtime modules in the public v4 CLI conformance proof."""
from pathlib import Path
import runpy
import socket
from unittest.mock import patch

proof = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tests/v4_cli_fixture.py'))['prove_v4_cli']
with patch.object(socket, 'create_connection', side_effect=AssertionError('runtime network')):
    assert proof() == 'installed-wheel'
print('Installed v4: exact wheel, actual composition, selected temporal facts, locked equivalence, refusal, and no-Git proof passed.')
