# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Live tests against unauthenticated Pulumi Cloud API routes.

These exercise the full client path end-to-end — build request, real HTTP call,
deserialize the JSON response into the generated model — against endpoints that
require no access token:

  * ``GET /api/cli/version``   -> AppCLIVersionResponse   (MiscellaneousApi.version)
  * ``GET /api/capabilities``  -> AppCapabilitiesResponse  (MiscellaneousApi.capabilities)

Both are declared ``@PulumiPermissionsCheck(noAuthorizationRequired = true)`` in
the IDL, so no credentials are sent.

Because they reach the public internet they are *skipped* (not failed) when the
network is unavailable, so offline / sandboxed runs stay green. Point them at a
different backend with ``PULUMI_API_HOST`` (e.g. a staging host).
"""

import os
import re
import sys
import unittest
import urllib.error
from pathlib import Path

# Make `import pulumi_cloud_sdk` resolve regardless of the invocation directory:
# tests/ -> python/ (the dir that contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pulumi_cloud_sdk import ApiClient, Configuration, models  # noqa: E402
from pulumi_cloud_sdk.apis import MiscellaneousApi  # noqa: E402


# Endpoints can be slow from CI; keep the ceiling modest so a hang skips quickly.
_REQUEST_TIMEOUT = 20


def _make_client() -> ApiClient:
    config = Configuration()
    host = os.environ.get("PULUMI_API_HOST")
    if host:
        config.host = host
    # No access_token set -> no Authorization header is sent.
    return ApiClient(config)


class PublicApiLiveTest(unittest.TestCase):
    def setUp(self):
        self.api = MiscellaneousApi(api_client=_make_client())

    def _call(self, fn):
        """Invoke a live endpoint, skipping the test on connectivity failure."""
        try:
            return fn(_request_timeout=_REQUEST_TIMEOUT)
        except urllib.error.HTTPError as e:  # a real HTTP status error is a failure
            self.fail(f"unexpected HTTP {e.code} calling public endpoint: {e}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # no network
            self.skipTest(f"network unavailable: {e}")

    def test_cli_version(self):
        resp = self._call(self.api.version)

        self.assertIsInstance(resp, models.AppCLIVersionResponse)
        # The latest CLI version is always populated and looks like a semver.
        self.assertIsInstance(resp.latest_version, str)
        self.assertTrue(resp.latest_version, "latest_version should be non-empty")
        self.assertRegex(resp.latest_version, r"^\d+\.\d+\.\d+")

    def test_capabilities(self):
        resp = self._call(self.api.capabilities)

        self.assertIsInstance(resp, models.AppCapabilitiesResponse)
        # `capabilities` deserializes into a list of the nested model type.
        self.assertIsInstance(resp.capabilities, list)
        for cap in resp.capabilities:
            self.assertIsInstance(cap, models.AppAPICapabilityConfig)


if __name__ == "__main__":
    unittest.main()
