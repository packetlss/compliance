import unittest
from v4_cli_fixture import prove_v4_cli

class AssessmentV4CliTests(unittest.TestCase):
    def test_unlocked_direct_locked_cli_and_historical_provenance(self):
        self.assertEqual(prove_v4_cli(), 'source')
