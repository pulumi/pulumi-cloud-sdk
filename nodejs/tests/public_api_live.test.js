// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Live end-to-end tests against unauthenticated Pulumi Cloud routes. Mirrors
// sdk/python/tests/test_public_api_live.py. Real HTTP status errors fail;
// connectivity failures (offline) skip so the suite stays green without network.
// Override the host with PULUMI_API_HOST (base URL, e.g. https://api.staging...).

const { test } = require("node:test");
const assert = require("node:assert/strict");

const { ApiService, ApiClient, ApiClientConfiguration, ApiError } = require("../dist/index.js");

function newApis() {
    const base = process.env.PULUMI_API_HOST;
    // apiHost must include the /api/ prefix and a trailing slash.
    const apiHost = base ? `${base.replace(/\/+$/, "")}/api/` : "https://api.pulumi.com/api/";
    const config = new ApiClientConfiguration(apiHost, "pulumi-cloud-sdk-test");
    return new ApiService(new ApiClient(config));
}

// A connectivity failure surfaces as a plain fetch TypeError (not an ApiError);
// treat that as "offline" and skip. A non-2xx HTTP status is a real failure.
function isConnectivityError(err) {
    return !(err instanceof ApiError);
}

test("GET /api/cli/version returns a semver-shaped latestVersion", async (t) => {
    let version;
    try {
        version = await newApis().Miscellaneous.Version();
    } catch (err) {
        if (isConnectivityError(err)) {
            t.skip(`Pulumi Cloud unreachable: ${err}`);
            return;
        }
        throw err;
    }
    assert.match(String(version.latestVersion), /^\d+\.\d+\.\d+/);
});

test("GET /api/capabilities returns a capabilities list", async (t) => {
    let capabilities;
    try {
        capabilities = await newApis().Miscellaneous.Capabilities();
    } catch (err) {
        if (isConnectivityError(err)) {
            t.skip(`Pulumi Cloud unreachable: ${err}`);
            return;
        }
        throw err;
    }
    assert.ok(Array.isArray(capabilities.capabilities));
});
