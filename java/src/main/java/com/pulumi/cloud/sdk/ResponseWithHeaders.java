// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

/**
 * Pairs a deserialized response body with typed response headers, mirroring
 * {@code apitype.ResponseWithHeaders[R, H]} (Go) / {@code ResponseWithHeaders<R, H>}
 * (TypeScript / .NET) / {@code ResponseWithHeaders[R, H]} (Python). Returned by
 * generated {@code *Api} methods for operations whose response declares response
 * headers.
 */
public final class ResponseWithHeaders<R, H> {
    public final R response;
    public final H headers;

    public ResponseWithHeaders(R response, H headers) {
        this.response = response;
        this.headers = headers;
    }
}
