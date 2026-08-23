// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

// Live end-to-end test against an unauthenticated Pulumi Cloud route. Mirrors
// sdk/python/tests/test_public_api_live.py and
// sdk/nodejs/tests/public_api_live.test.js. A real HTTP status error fails; a
// connectivity failure (offline) skips so the suite stays green without network.
// Override the host with PULUMI_API_HOST (base URL, e.g. https://api.staging...).

import com.pulumi.cloud.sdk.api.MiscellaneousApi;
import com.pulumi.cloud.sdk.model.AppCLIVersionResponse;
import org.junit.jupiter.api.Test;

import java.io.IOException;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assumptions.abort;

class PublicApiLiveTest {

    private static ApiClient client() {
        var config = new ApiClientConfiguration();
        String host = System.getenv("PULUMI_API_HOST");
        if (host != null && !host.isEmpty()) {
            config.setHost(host);
        }
        return new ApiClient(config);
    }

    @Test
    void versionReturnsSemver() {
        AppCLIVersionResponse response;
        try {
            response = new MiscellaneousApi(client()).version();
        } catch (ApiException e) {
            // statusCode == 0 means a transport failure (offline / DNS) -> skip.
            // A real HTTP status is a genuine failure and propagates.
            if (e.getStatusCode() == 0 && (e.getCause() == null || e.getCause() instanceof IOException)) {
                abort("Pulumi Cloud not reachable; skipping live test: " + e.getMessage());
            }
            throw e;
        }

        assertNotNull(response);
        assertNotNull(response.latestVersion);
        assertTrue(response.latestVersion.matches("\\d+\\.\\d+\\.\\d+.*"),
                "unexpected version string: " + response.latestVersion);
    }
}
