from __future__ import annotations

import math
import unittest

from tools._canonical_json import canonical_json_bytes
from tools.artifact_validation import _content_digest as validation_content_digest
from tools.policy_sources import policy_revision
from tools.render_plan import content_digest


class CanonicalJsonConformanceTests(unittest.TestCase):
    def test_rfc8785_primitive_serialization_sample(self) -> None:
        value = {
            "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
            "string": "€$\u000f\nA'B\"\\\\\"/",
            "literals": [None, True, False],
        }
        expected = (
            b'{"literals":[null,true,false],"numbers":[333333333.3333333,'
            b'1e+30,4.5,0.002,1e-27],"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"'
            b'\\\\\\\\\\"/"}'
        )
        self.assertEqual(canonical_json_bytes(value), expected)

    def test_rfc8785_utf16_property_order_sample(self) -> None:
        value = {
            "€": "Euro Sign",
            "\r": "Carriage Return",
            "דּ": "Hebrew Letter Dalet With Dagesh",
            "1": "One",
            "😀": "Emoji: Grinning Face",
            "\u0080": "Control",
            "ö": "Latin Small Letter O With Diaeresis",
        }
        expected = (
            b'{"\\r":"Carriage Return","1":"One","\xc2\x80":"Control",'
            b'"\xc3\xb6":"Latin Small Letter O With Diaeresis",'
            b'"\xe2\x82\xac":"Euro Sign","\xf0\x9f\x98\x80":"Emoji: Grinning Face",'
            b'"\xef\xac\xb3":"Hebrew Letter Dalet With Dagesh"}'
        )
        self.assertEqual(canonical_json_bytes(value), expected)

    def test_rfc8785_number_edges_and_invalid_domain(self) -> None:
        self.assertEqual(
            canonical_json_bytes([-0.0, 5e-324, 1e30, 0.000001, 1e-7]),
            b"[0,5e-324,1e+30,0.000001,1e-7]",
        )
        for value in (math.nan, math.inf, -math.inf, 2**53):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonical_json_bytes(value)


class SemanticIdentityVectorTests(unittest.TestCase):
    # Fixed independently with the RFC 8785 Appendix A ECMAScript canonicalizer
    # and Node.js SHA-256, not with tools._canonical_json.
    def test_plan_content_and_validation_recomputation_vector(self) -> None:
        value = {"z": 1e-7, "a": "Å"}
        expected = "sha256:1531e7cc8993627321363a8b4aa683a03bd68205286da4a2b02e4bfe87c588a2"
        self.assertEqual(content_digest(value), expected)
        self.assertEqual(validation_content_digest(value), expected)

    def test_policy_revision_normalization_vector(self) -> None:
        revisions = [
            {"name": "zeta", "digest": "sha256:" + "f" * 64},
            {"name": "alpha", "digest": "sha256:" + "a" * 64},
        ]
        expected = "sha256:39af4e6a6f641753f24f564b899c7149f9f215e715ee538de221c49b4839c962"
        self.assertEqual(policy_revision(revisions), expected)
        self.assertEqual(policy_revision(list(reversed(revisions))), expected)


if __name__ == "__main__":
    unittest.main()
