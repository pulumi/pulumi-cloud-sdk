// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Mutable carrier populated by a generated {@code *Api} method before it hands
 * the request to {@link ApiClient}. Holds the HTTP verb, the templated resource
 * path ({@code /api/.../{param}}), the categorized parameters, the request body,
 * and the negotiated media types.
 */
public final class ApiRequest {
    final String method;
    final String resourcePath;
    final Map<String, String> pathParams = new LinkedHashMap<>();
    final Map<String, List<String>> queryParams = new LinkedHashMap<>();
    final List<String> consumes = new ArrayList<>();
    final List<String> produces = new ArrayList<>();
    Object body;
    boolean hasBody;

    public ApiRequest(String method, String resourcePath) {
        this.method = method;
        this.resourcePath = resourcePath;
    }

    /** Bind a {@code {name}} path segment. Null values are ignored. */
    public ApiRequest pathParam(String name, Object value) {
        if (value != null) {
            pathParams.put(name, stringify(value));
        }
        return this;
    }

    /**
     * Append a query parameter. Null values are dropped; collections and arrays
     * are emitted as repeated keys ({@code k=a&k=b}); booleans render lowercase,
     * enums via their wire value, and dates as ISO-8601 — matching the reference
     * clients.
     */
    public ApiRequest queryParam(String name, Object value) {
        if (value == null) {
            return this;
        }
        if (value instanceof Collection<?>) {
            for (Object item : (Collection<?>) value) {
                addQuery(name, item);
            }
        } else if (value instanceof Object[]) {
            for (Object item : (Object[]) value) {
                addQuery(name, item);
            }
        } else {
            addQuery(name, value);
        }
        return this;
    }

    public ApiRequest body(Object body) {
        this.body = body;
        this.hasBody = true;
        return this;
    }

    public ApiRequest consumes(String mediaType) {
        consumes.add(mediaType);
        return this;
    }

    public ApiRequest produces(String mediaType) {
        produces.add(mediaType);
        return this;
    }

    private void addQuery(String name, Object value) {
        if (value == null) {
            return;
        }
        queryParams.computeIfAbsent(name, k -> new ArrayList<>()).add(stringify(value));
    }

    // String.valueOf covers all wire renderings we need: Boolean -> "true"/"false",
    // enum -> its value() (via the generated toString), ZonedDateTime -> ISO-8601,
    // numbers and Strings as-is.
    private static String stringify(Object value) {
        return String.valueOf(value);
    }
}
