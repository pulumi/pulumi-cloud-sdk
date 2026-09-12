# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Tests for ApiClient.call_api_with_headers and the generated
*_api_.py methods that call it for operations declaring typed response headers
(e.g. EnvironmentsApi.read_environment_esc_environments).

HTTP is stubbed by patching urlopen at the module level api_client imports it
into (`pulumi_cloud_sdk.api_client.urlopen`), the same seam call_api itself
goes through. No existing test in this suite stubs HTTP (test_public_api_live
hits the real network instead), so this establishes the pattern for
call_api_with_headers specifically.
"""

import json
import sys
import unittest
from email.message import Message
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

# tests/ -> python/ (the dir that contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pulumi_cloud_sdk import ApiClient, Configuration, ResponseWithHeaders  # noqa: E402
from pulumi_cloud_sdk.apis import EnvironmentsApi  # noqa: E402
from pulumi_cloud_sdk.models import HeadersForEnvironmentOp, UpdateEnvironmentResponse  # noqa: E402


class _FakeHTTPResponse(BytesIO):
    """Minimal stand-in for http.client.HTTPResponse: readable body plus a
    real email.message.Message for .headers, so `.get(name)` behaves exactly
    like the real thing. Usable as the context manager urlopen() returns."""

    def __init__(self, body: bytes, headers: dict):
        super().__init__(body)
        self.headers = Message()
        for key, value in headers.items():
            self.headers[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _make_api() -> EnvironmentsApi:
    return EnvironmentsApi(api_client=ApiClient(Configuration()))


class ResponseHeadersTest(unittest.TestCase):
    def test_body_operation_parses_response_and_headers(self):
        api = _make_api()
        fake_response = _FakeHTTPResponse(
            json.dumps({"diagnostics": []}).encode("utf-8"),
            {"content-type": "application/json", "ETag": "abc123", "Pulumi-ESC-Revision": "7"},
        )
        with patch("pulumi_cloud_sdk.api_client.urlopen", return_value=fake_response):
            result = api.update_environment_esc_environments("acme", "proj", "env", "values: {}")

        self.assertIsInstance(result, ResponseWithHeaders)
        self.assertIsInstance(result.response, UpdateEnvironmentResponse)
        self.assertIsInstance(result.headers, HeadersForEnvironmentOp)
        self.assertEqual(result.headers.e_tag, "abc123")
        self.assertEqual(result.headers.pulumi_e_s_c_revision, 7)

    def test_no_body_operation_resolves_to_just_the_headers(self):
        api = _make_api()
        fake_response = _FakeHTTPResponse(b"", {"ETag": "head-etag", "Pulumi-ESC-Revision": "3"})
        with patch("pulumi_cloud_sdk.api_client.urlopen", return_value=fake_response):
            result = api.head_environment_esc_environments("acme", "proj", "env")

        self.assertIsInstance(result, HeadersForEnvironmentOp)
        self.assertEqual(result.e_tag, "head-etag")
        self.assertEqual(result.pulumi_e_s_c_revision, 3)

    def test_missing_headers_default_to_the_zero_value(self):
        api = _make_api()
        fake_response = _FakeHTTPResponse(b"", {})
        with patch("pulumi_cloud_sdk.api_client.urlopen", return_value=fake_response):
            result = api.head_environment_esc_environments("acme", "proj", "env")

        self.assertEqual(result.e_tag, "")
        self.assertEqual(result.pulumi_e_s_c_revision, 0)

    def test_malformed_header_defaults_to_the_zero_value_rather_than_raising(self):
        # A malformed-but-present header must not fail an otherwise-successful
        # call -- see parse_number_header in api_client.py.
        api = _make_api()
        fake_response = _FakeHTTPResponse(b"", {"ETag": "some-etag", "Pulumi-ESC-Revision": "not-a-number"})
        with patch("pulumi_cloud_sdk.api_client.urlopen", return_value=fake_response):
            result = api.head_environment_esc_environments("acme", "proj", "env")

        self.assertEqual(result.e_tag, "some-etag")
        self.assertEqual(result.pulumi_e_s_c_revision, 0)


if __name__ == "__main__":
    unittest.main()
