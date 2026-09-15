// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import org.junit.jupiter.api.Test;

import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import java.io.ByteArrayOutputStream;
import java.net.Authenticator;
import java.net.CookieHandler;
import java.net.ProxySelector;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpHeaders;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Flow;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

// Wire-level tests for request-body serialization. The runtime must honor the
// media type the generated code negotiated: JSON bodies are JSON-encoded, but
// an application/x-yaml (or other unencoded text) body is the document itself
// and must travel byte-for-byte — Jackson on a YAML string produces a quoted
// JSON scalar the server would parse as a plain string instead of a mapping.
// Mirrors sdk/python/tests/test_request_bodies.py.
class BodyEncodingTest {

    @Test
    void yamlBodyIsSentVerbatim() {
        var http = new CapturingHttpClient();
        var client = newClient(http);
        var definition = "values:\n  foo: bar\n";

        client.call(new ApiRequest("POST", "/environments/check")
                .consumes("application/x-yaml")
                .body(definition));

        assertArrayEquals(definition.getBytes(StandardCharsets.UTF_8), readBody(http.captured));
        assertEquals(Optional.of("application/x-yaml"), http.captured.headers().firstValue("Content-Type"));
    }

    @Test
    void jsonBodyIsJsonEncoded() {
        var http = new CapturingHttpClient();
        var client = newClient(http);

        client.call(new ApiRequest("POST", "/things")
                .consumes("application/json")
                .body(Map.of("name", "widget")));

        assertEquals("{\"name\":\"widget\"}", new String(readBody(http.captured), StandardCharsets.UTF_8));
        assertEquals(Optional.of("application/json"), http.captured.headers().firstValue("Content-Type"));
    }

    @Test
    void binaryBodyIsSentVerbatim() {
        var http = new CapturingHttpClient();
        var client = newClient(http);
        var bytes = new byte[]{0, 1, 'h', 'i'};

        client.call(new ApiRequest("POST", "/blobs")
                .consumes("application/octet-stream")
                .body(bytes));

        assertArrayEquals(bytes, readBody(http.captured));
        assertEquals(Optional.of("application/octet-stream"), http.captured.headers().firstValue("Content-Type"));
    }

    @Test
    void bodyDefaultsToJsonWhenNoConsumeIsDeclared() {
        var http = new CapturingHttpClient();
        var client = newClient(http);

        client.call(new ApiRequest("POST", "/things").body(Map.of("a", 1)));

        assertEquals("{\"a\":1}", new String(readBody(http.captured), StandardCharsets.UTF_8));
        assertEquals(Optional.of("application/json"), http.captured.headers().firstValue("Content-Type"));
    }

    private static ApiClient newClient(HttpClient http) {
        var config = new ApiClientConfiguration()
                .setHost("https://example.test/api")
                .setSource("test-src")
                .setTimeout(Duration.ofSeconds(8));
        return new ApiClient(config, http);
    }

    // Safe to join: BodyPublishers.ofByteArray publishes synchronously once
    // demand is signalled.
    private static byte[] readBody(HttpRequest request) {
        var publisher = request.bodyPublisher().orElse(null);
        if (publisher == null) {
            return new byte[0];
        }
        var out = new ByteArrayOutputStream();
        var done = new CompletableFuture<Void>();
        publisher.subscribe(new Flow.Subscriber<>() {
            @Override
            public void onSubscribe(Flow.Subscription subscription) {
                subscription.request(Long.MAX_VALUE);
            }

            @Override
            public void onNext(ByteBuffer item) {
                var chunk = new byte[item.remaining()];
                item.get(chunk);
                out.writeBytes(chunk);
            }

            @Override
            public void onError(Throwable throwable) {
                done.completeExceptionally(throwable);
            }

            @Override
            public void onComplete() {
                done.complete(null);
            }
        });
        done.join();
        return out.toByteArray();
    }

    private static final class CapturingHttpClient extends HttpClient {
        HttpRequest captured;

        @Override
        @SuppressWarnings("unchecked")
        public <T> HttpResponse<T> send(HttpRequest request, HttpResponse.BodyHandler<T> responseBodyHandler) {
            captured = request;
            return (HttpResponse<T>) new FakeResponse(request, "{}".getBytes(StandardCharsets.UTF_8));
        }

        @Override
        public <T> CompletableFuture<HttpResponse<T>> sendAsync(
                HttpRequest request, HttpResponse.BodyHandler<T> responseBodyHandler) {
            return CompletableFuture.completedFuture(send(request, responseBodyHandler));
        }

        @Override
        public <T> CompletableFuture<HttpResponse<T>> sendAsync(
                HttpRequest request,
                HttpResponse.BodyHandler<T> responseBodyHandler,
                HttpResponse.PushPromiseHandler<T> pushPromiseHandler) {
            return sendAsync(request, responseBodyHandler);
        }

        @Override
        public Optional<CookieHandler> cookieHandler() {
            return Optional.empty();
        }

        @Override
        public Optional<Duration> connectTimeout() {
            return Optional.empty();
        }

        @Override
        public Redirect followRedirects() {
            return Redirect.NEVER;
        }

        @Override
        public Optional<ProxySelector> proxy() {
            return Optional.empty();
        }

        @Override
        public SSLContext sslContext() {
            return null;
        }

        @Override
        public SSLParameters sslParameters() {
            return null;
        }

        @Override
        public Optional<Authenticator> authenticator() {
            return Optional.empty();
        }

        @Override
        public Version version() {
            return Version.HTTP_1_1;
        }

        @Override
        public Optional<Executor> executor() {
            return Optional.empty();
        }
    }

    // Not a record: java_sdk_tests compiles with --release 11.
    private static final class FakeResponse implements HttpResponse<byte[]> {
        private final HttpRequest request;
        private final byte[] body;

        FakeResponse(HttpRequest request, byte[] body) {
            this.request = request;
            this.body = body;
        }

        @Override
        public HttpRequest request() {
            return request;
        }

        @Override
        public byte[] body() {
            return body;
        }

        @Override
        public int statusCode() {
            return 200;
        }

        @Override
        public Optional<HttpResponse<byte[]>> previousResponse() {
            return Optional.empty();
        }

        @Override
        public HttpHeaders headers() {
            return HttpHeaders.of(Map.of(), (a, b) -> true);
        }

        @Override
        public Optional<javax.net.ssl.SSLSession> sslSession() {
            return Optional.empty();
        }

        @Override
        public URI uri() {
            return request.uri();
        }

        @Override
        public HttpClient.Version version() {
            return HttpClient.Version.HTTP_1_1;
        }
    }
}
