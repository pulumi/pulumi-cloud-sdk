// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Thrown for a non-2xx HTTP response, a transport failure, or a
 * serialization/deserialization error. Unchecked so generated method signatures
 * stay free of {@code throws} clauses.
 */
public class ApiException extends RuntimeException {
    private static final long serialVersionUID = 1L;

    private final int statusCode;
    private final String url;
    private final transient JsonNode body;
    private final String rawBody;

    public ApiException(int statusCode, String message, String url, JsonNode body, String rawBody, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
        this.url = url;
        this.body = body;
        this.rawBody = rawBody;
    }

    /** HTTP status code, or 0 for a transport/serialization failure. */
    public int getStatusCode() {
        return statusCode;
    }

    public String getUrl() {
        return url;
    }

    /** Parsed JSON error body, or {@code null} if the body was absent or not JSON. */
    public JsonNode getBody() {
        return body;
    }

    /** Raw response body text, or {@code null}. */
    public String getRawBody() {
        return rawBody;
    }
}
