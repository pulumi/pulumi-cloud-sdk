# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Tests for query-parameter serialization in the HTTP client.

The wire form must match the reference clients: booleans as lowercase
``true``/``false``, list-valued params as repeated keys, enums by their value,
``None`` dropped.
"""

import sys
import unittest
from urllib.parse import parse_qs
from pathlib import Path

# tests/ -> python/ (the dir that contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# noinspection PyProtectedMember
from pulumi_cloud_sdk.api_client import _encode_query, _query_param_value  # noqa: E402
from pulumi_cloud_sdk import models as m  # noqa: E402


class QueryParamTest(unittest.TestCase):
    def test_bool_is_lowercase(self):
        # str(True) would be "True" — the bug this guards against.
        self.assertEqual(_query_param_value(True), "true")
        self.assertEqual(_query_param_value(False), "false")

    def test_scalars(self):
        self.assertEqual(_query_param_value("prod"), "prod")
        self.assertEqual(_query_param_value(42), "42")
        self.assertEqual(_query_param_value(3.5), "3.5")

    def test_enum_uses_value(self):
        # AutoEnumEncoder members serialize to their wire value.
        perm = m.EnvironmentPermission.None_
        self.assertEqual(_query_param_value(perm), perm.value)
        self.assertEqual(_query_param_value(perm), "none")

    def test_encode_drops_none_and_encodes_bool(self):
        qs = _encode_query({"dryRun": True, "org": "acme", "cursor": None})
        parsed = parse_qs(qs)
        self.assertEqual(parsed["dryRun"], ["true"])
        self.assertEqual(parsed["org"], ["acme"])
        self.assertNotIn("cursor", parsed)

    def test_list_becomes_repeated_keys(self):
        qs = _encode_query({"facet": ["a", "b", "c"]})
        # Repeated keys, not a stringified list.
        self.assertNotIn("%5B", qs)  # no "[" from str([...])
        self.assertEqual(parse_qs(qs)["facet"], ["a", "b", "c"])

    def test_list_of_ints(self):
        qs = _encode_query({"type": [1, 2, 3]})
        self.assertEqual(parse_qs(qs)["type"], ["1", "2", "3"])

    def test_special_chars_are_percent_encoded(self):
        qs = _encode_query({"q": "a b&c=d"})
        self.assertEqual(parse_qs(qs)["q"], ["a b&c=d"])

    def test_empty_query(self):
        self.assertEqual(_encode_query({}), "")
        self.assertEqual(_encode_query({"x": None}), "")


if __name__ == "__main__":
    unittest.main()
