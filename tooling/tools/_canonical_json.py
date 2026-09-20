"""Private RFC 8785/JCS serialization for semantic identity hashing."""

from __future__ import annotations

from typing import Any

import rfc8785


def unique_object(pairs):
    """Reject duplicate members before a JSON document can lose their meaning."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('ambiguous duplicate JSON member')
        result[key] = value
    return result


def canonical_json_bytes(value: Any) -> bytes:
    """Return the RFC 8785/JCS UTF-8 representation of a JSON value."""
    return rfc8785.dumps(value)
