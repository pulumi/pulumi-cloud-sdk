# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Wire-level tests for request-body serialization and response decoding.

The runtime must honor the media type the generated code negotiated: JSON
bodies are JSON-encoded, but an ``application/x-yaml`` (or other unencoded
text) body is the document itself and must travel byte-for-byte. ``json.dumps``
on a YAML string produces a quoted JSON scalar that the server would parse as
a plain string instead of a mapping. Mirrors sdk/nodejs/tests/request.test.js.
"""

import json
import sys
import unittest
from pathlib import Path

# tests/ -> python/ (the dir that contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pulumi_cloud_sdk.api_client import ApiClient  # noqa: E402
from pulumi_cloud_sdk.configuration import Configuration  # noqa: E402


class FakeResponse:
    def __init__(self, body: bytes, content_type: str):
        self._body = body
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class CapturingTransport:
    def __init__(self, response: FakeResponse):
        self.request = None
        self._response = response

    def __call__(self, request, timeout):
        self.request = request
        return self._response


def new_client(response: FakeResponse) -> tuple[ApiClient, CapturingTransport]:
    transport = CapturingTransport(response)
    config = Configuration()
    config.host = "https://example.test/api"
    return ApiClient(config, transport=transport), transport


class RequestBodyTest(unittest.TestCase):
    def test_yaml_body_is_sent_verbatim(self):
        client, transport = new_client(FakeResponse(b"{}", "application/json"))
        definition = "values:\n  foo: bar\n"

        client.call_api(
            "/environments/check",
            "POST",
            header_params={"Content-Type": "application/x-yaml"},
            body=definition,
        )

        self.assertEqual(transport.request.data, definition.encode("utf-8"))
        self.assertEqual(transport.request.get_header("Content-type"), "application/x-yaml")

    def test_json_body_is_json_encoded(self):
        client, transport = new_client(FakeResponse(b"{}", "application/json"))

        client.call_api(
            "/things",
            "POST",
            header_params={"Content-Type": "application/json"},
            body={"name": "widget"},
        )

        self.assertEqual(json.loads(transport.request.data), {"name": "widget"})
        self.assertEqual(transport.request.get_header("Content-type"), "application/json")

    def test_binary_body_is_sent_verbatim(self):
        client, transport = new_client(FakeResponse(b"{}", "application/json"))

        client.call_api(
            "/blobs",
            "POST",
            header_params={"Content-Type": "application/octet-stream"},
            body=b"\x00\x01hi",
        )

        self.assertEqual(transport.request.data, b"\x00\x01hi")

    def test_bytes_in_json_body_are_base64(self):
        client, transport = new_client(FakeResponse(b"{}", "application/json"))

        client.call_api(
            "/things",
            "POST",
            header_params={"Content-Type": "application/json"},
            body={"data": b"hi"},
        )

        self.assertEqual(json.loads(transport.request.data), {"data": "aGk="})

    def test_base64_string_deserializes_to_bytes_fields(self):
        from pulumi_cloud_sdk._support import default_encoder

        self.assertEqual(default_encoder.deserialize("aGk=", "bytes"), b"hi")

    def test_body_defaults_to_json_when_no_content_type(self):
        client, transport = new_client(FakeResponse(b"{}", "application/json"))

        client.call_api("/things", "POST", body={"a": 1})

        self.assertEqual(json.loads(transport.request.data), {"a": 1})
        self.assertEqual(transport.request.get_header("Content-type"), "application/json")

class ResponseDecodingTest(unittest.TestCase):
    def test_yaml_response_is_returned_as_text(self):
        # json.loads on a YAML document either fails or quietly succeeds on a
        # document that happens to be a valid JSON scalar.
        document = "values:\n  foo: bar\n"
        client, _ = new_client(FakeResponse(document.encode("utf-8"), "application/x-yaml"))

        result = client.call_api("/environments/read", "GET", response_type="str")

        self.assertEqual(result, document)

    def test_markdown_response_is_returned_as_text(self):
        client, _ = new_client(FakeResponse(b"# Title\n", "text/markdown; charset=utf-8"))

        result = client.call_api("/readme", "GET", response_type="str")

        self.assertEqual(result, "# Title\n")

    def test_json_string_response_is_still_json_decoded(self):
        client, _ = new_client(FakeResponse(b'"a plain string"', "application/json"))

        result = client.call_api("/version", "GET", response_type="str")

        self.assertEqual(result, "a plain string")

    def test_binary_response_is_returned_as_bytes(self):
        client, _ = new_client(FakeResponse(b"\x00\x01hi", "application/octet-stream"))

        result = client.call_api("/blob", "GET", response_type="str")

        self.assertEqual(result, b"\x00\x01hi")


if __name__ == "__main__":
    unittest.main()
