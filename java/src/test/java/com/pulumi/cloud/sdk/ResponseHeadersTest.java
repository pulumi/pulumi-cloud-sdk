// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

// Tests for ApiClient.callWithHeaders/callWithHeadersOnly and the generated
// EnvironmentsApi methods that call them for operations declaring typed response
// headers. java.net.http.HttpClient has no client-side mocking seam (unlike
// .NET's HttpMessageHandler or Node's fetch), so HTTP is stubbed by an embedded
// com.sun.net.httpserver.HttpServer bound to a loopback port instead, with
// ApiClientConfiguration pointed at it -- exercising the real HTTP stack
// end-to-end rather than intercepting at the client layer.

import com.pulumi.cloud.sdk.api.EnvironmentsApi;
import com.pulumi.cloud.sdk.model.HeadersForEnvironmentOp;
import com.pulumi.cloud.sdk.model.UpdateEnvironmentResponse;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ResponseHeadersTest {

    private HttpServer server;
    private EnvironmentsApi api;

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        server.start();
        ApiClientConfiguration configuration = new ApiClientConfiguration()
                .setHost("http://localhost:" + server.getAddress().getPort());
        api = new EnvironmentsApi(new ApiClient(configuration));
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    // headers is a flat list of alternating name/value pairs.
    private void respond(String body, String... headers) {
        server.createContext("/", exchange -> {
            for (int i = 0; i + 1 < headers.length; i += 2) {
                exchange.getResponseHeaders().add(headers[i], headers[i + 1]);
            }
            byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });
    }

    @Test
    void bodyOperationParsesResponseAndHeaders() {
        respond("{\"diagnostics\":[]}", "ETag", "abc123", "Pulumi-ESC-Revision", "7");

        ResponseWithHeaders<UpdateEnvironmentResponse, HeadersForEnvironmentOp> result =
                api.updateEnvironment_esc_environments("acme", "proj", "env", "values: {}");

        assertTrue(result.response.diagnostics.isEmpty());
        assertEquals("abc123", result.headers.eTag);
        assertEquals(7L, result.headers.pulumiESCRevision);
    }

    @Test
    void noBodyOperationResolvesToJustTheHeaders() {
        respond("", "ETag", "head-etag", "Pulumi-ESC-Revision", "3");

        HeadersForEnvironmentOp result = api.headEnvironment_esc_environments("acme", "proj", "env");

        assertEquals("head-etag", result.eTag);
        assertEquals(3L, result.pulumiESCRevision);
    }

    @Test
    void missingHeadersDefaultToTheZeroValue() {
        respond("");

        HeadersForEnvironmentOp result = api.headEnvironment_esc_environments("acme", "proj", "env");

        assertEquals("", result.eTag);
        assertEquals(0L, result.pulumiESCRevision);
    }

    @Test
    void malformedHeaderDefaultsToTheZeroValueRatherThanThrowing() {
        // A malformed-but-present header must not fail an otherwise-successful
        // call -- see HeaderParsing.parseLong.
        respond("", "ETag", "some-etag", "Pulumi-ESC-Revision", "not-a-number");

        HeadersForEnvironmentOp result = api.headEnvironment_esc_environments("acme", "proj", "env");

        assertEquals("some-etag", result.eTag);
        assertEquals(0L, result.pulumiESCRevision);
    }
}
