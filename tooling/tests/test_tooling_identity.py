"""Executable cache integrity remains independent of cache byte identity."""
import importlib.util
import marshal
import tempfile
import unittest
from pathlib import Path

from tools.tooling_identity import ToolingIdentityError, _verify_bytecode


class InstalledBytecodeTests(unittest.TestCase):
    def test_verified_source_equivalence_and_tamper_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'tools/probe.py'
            source.parent.mkdir()
            source.write_text('"""Docstring."""\nassert True\nvalue = 42\n')
            payload = {'tools/probe.py': source.read_bytes()}
            for optimization in ('', '1', '2'):
                with self.subTest(optimization=optimization):
                    cache = Path(importlib.util.cache_from_source(str(source), optimization=optimization))
                    cache.parent.mkdir(exist_ok=True)
                    code = compile(source.read_bytes(), '/nonsemantic/build/probe.py', 'exec',
                                   dont_inherit=True, optimize=int(optimization or '0'))
                    header = importlib.util.MAGIC_NUMBER + (1).to_bytes(4, 'little') + b'x'*8
                    correct = header + marshal.dumps(code)
                    cache.write_bytes(correct)
                    _verify_bytecode(cache, root, payload)
                    malformed = (
                        header + marshal.dumps(compile('value = 999', str(source), 'exec')),
                        correct + b'trailing',
                        b'invalid',
                        header + marshal.dumps('not executable code'),
                    )
                    for data in malformed:
                        cache.write_bytes(data)
                        with self.assertRaises(ToolingIdentityError):
                            _verify_bytecode(cache, root, payload)
                    cache.write_bytes(correct)
                    with self.assertRaises(ToolingIdentityError):
                        _verify_bytecode(cache, root, {})
            legacy = source.with_suffix('.pyc')
            legacy.write_bytes(correct)
            with self.assertRaises(ToolingIdentityError):
                _verify_bytecode(legacy, root, payload)
