// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;

import java.io.IOException;
import java.lang.reflect.Type;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

/**
 * HTTP engine for the generated Pulumi Cloud SDK, built on the JDK
 * {@link HttpClient}. Generated {@code *Api} methods build an {@link ApiRequest}
 * and hand it to {@link #call(ApiRequest, TypeReference)}; this class substitutes
 * path parameters, encodes the query string, applies authentication and headers,
 * serializes the body, performs the request, and deserializes the 2xx response
 * into the requested type. Non-2xx responses and transport/serialization failures
 * surface as {@link ApiException}.
 */
public class ApiClient {
    private final ApiClientConfiguration configuration;
    private final HttpClient http;

    public ApiClient() {
        this(new ApiClientConfiguration());
    }

    public ApiClient(ApiClientConfiguration configuration) {
        this.configuration = configuration;
        this.http = HttpClient.newHttpClient();
    }

    public ApiClientConfiguration getConfiguration() {
        return configuration;
    }

    /** Perform a request whose response body is ignored (void operations). */
    public void call(ApiRequest request) {
        call(request, (TypeReference<Void>) null);
    }

    /**
     * Perform a request and deserialize the 2xx response into {@code responseType}.
     * When {@code responseType} is {@code byte[]} or {@code String} the raw body is
     * returned without JSON parsing; a {@code null} type (or a 204 / empty body)
     * returns {@code null}.
     */
    @SuppressWarnings("unchecked")
    public <T> T call(ApiRequest request, TypeReference<T> responseType) {
        String url = buildUrl(request);

        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(url)).timeout(configuration.getTimeout());

        String token = configuration.getAccessToken().get();
        if (token != null && !token.isEmpty()) {
            builder.header("Authorization", "token " + token);
        }
        builder.header("X-Pulumi-Source", configuration.getSource());
        builder.header("Accept", request.produces.isEmpty() ? "application/json" : String.join(", ", request.produces));

        byte[] bodyBytes = null;
        if (request.hasBody) {
            String contentType = request.consumes.isEmpty() ? "application/json" : request.consumes.get(0);
            builder.header("Content-Type", contentType);
            if ("application/octet-stream".equals(contentType) && request.body instanceof byte[]) {
                bodyBytes = (byte[]) request.body;
            } else {
                try {
                    bodyBytes = Json.MAPPER.writeValueAsBytes(request.body);
                } catch (IOException e) {
                    throw new ApiException(0, "Failed to serialize request body: " + e.getMessage(), url, null, null, e);
                }
            }
        }

        HttpRequest.BodyPublisher publisher = bodyBytes == null
                ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofByteArray(bodyBytes);
        builder.method(request.method, publisher);

        HttpResponse<byte[]> response;
        try {
            response = http.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
        } catch (IOException e) {
            throw new ApiException(0, "Request to " + url + " failed: " + e.getMessage(), url, null, null, e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new ApiException(0, "Request to " + url + " was interrupted", url, null, null, e);
        }

        int statusCode = response.statusCode();
        byte[] raw = response.body();

        if (statusCode < 200 || statusCode >= 300) {
            throw buildError(statusCode, raw, url);
        }

        if (responseType == null || statusCode == 204 || raw == null || raw.length == 0) {
            return null;
        }

        Type type = responseType.getType();
        if (type == byte[].class) {
            return (T) raw;
        }
        if (type == String.class) {
            return (T) new String(raw, StandardCharsets.UTF_8);
        }

        try {
            return Json.MAPPER.readValue(raw, responseType);
        } catch (IOException e) {
            throw new ApiException(statusCode, "Failed to deserialize response from " + url + ": " + e.getMessage(),
                    url, null, new String(raw, StandardCharsets.UTF_8), e);
        }
    }

    private String buildUrl(ApiRequest request) {
        String path = request.resourcePath;
        for (Map.Entry<String, String> entry : request.pathParams.entrySet()) {
            path = path.replace("{" + entry.getKey() + "}", encodePathSegment(entry.getValue()));
        }

        StringBuilder url = new StringBuilder(trimTrailingSlash(configuration.getHost())).append(path);
        String query = encodeQuery(request.queryParams);
        if (!query.isEmpty()) {
            url.append('?').append(query);
        }
        return url.toString();
    }

    private static String trimTrailingSlash(String host) {
        int end = host.length();
        while (end > 0 && host.charAt(end - 1) == '/') {
            end--;
        }
        return host.substring(0, end);
    }

    // Percent-encode a path segment, encoding spaces as %20 (not '+') and
    // encoding '/' — matching the reference clients' quote(value, safe="").
    private static String encodePathSegment(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static String encodeQuery(Map<String, List<String>> params) {
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, List<String>> entry : params.entrySet()) {
            String key = URLEncoder.encode(entry.getKey(), StandardCharsets.UTF_8);
            for (String value : entry.getValue()) {
                if (sb.length() > 0) {
                    sb.append('&');
                }
                sb.append(key).append('=').append(URLEncoder.encode(value, StandardCharsets.UTF_8));
            }
        }
        return sb.toString();
    }

    private static ApiException buildError(int statusCode, byte[] raw, String url) {
        String rawBody = raw == null || raw.length == 0 ? null : new String(raw, StandardCharsets.UTF_8);
        JsonNode parsed = null;
        String message = null;
        if (rawBody != null) {
            try {
                parsed = Json.MAPPER.readTree(rawBody);
                if (parsed != null && parsed.hasNonNull("message")) {
                    message = parsed.get("message").asText();
                }
            } catch (IOException ignored) {
                // Body was not JSON; fall back to the raw text below.
            }
        }
        if (message == null) {
            message = rawBody != null ? rawBody : "HTTP " + statusCode;
        }
        return new ApiException(statusCode, "API error " + statusCode + ": " + message, url, parsed, rawBody, null);
    }
}
