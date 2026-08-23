// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

// Unit tests for ApiRequest query/path parameter rendering. Mirrors
// sdk/python/tests/test_query_params.py: booleans render lowercase, enums via
// their wire value, dates as ISO-8601, nulls are dropped, and collections become
// repeated keys. The test lives in the runtime package so it can read the
// package-private param maps.

import com.pulumi.cloud.sdk.model.MemberAction;
import org.junit.jupiter.api.Test;

import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;

class QueryParamTest {

    @Test
    void booleansRenderLowercase() {
        var req = new ApiRequest("GET", "/api/x").queryParam("flag", true).queryParam("off", false);
        assertEquals(List.of("true"), req.queryParams.get("flag"));
        assertEquals(List.of("false"), req.queryParams.get("off"));
    }

    @Test
    void enumsRenderTheirWireValue() {
        var req = new ApiRequest("GET", "/api/x").queryParam("action", MemberAction.Add);
        assertEquals(List.of("add"), req.queryParams.get("action"));
    }

    @Test
    void datesRenderIso8601() {
        var when = ZonedDateTime.of(2024, 7, 3, 10, 26, 40, 0, ZoneOffset.UTC);
        var req = new ApiRequest("GET", "/api/x").queryParam("since", when);
        assertEquals(List.of("2024-07-03T10:26:40Z"), req.queryParams.get("since"));
    }

    @Test
    void nullsAreDropped() {
        var req = new ApiRequest("GET", "/api/x").queryParam("missing", null).pathParam("p", null);
        assertNull(req.queryParams.get("missing"));
        assertFalse(req.pathParams.containsKey("p"));
    }

    @Test
    void collectionsBecomeRepeatedKeys() {
        var req = new ApiRequest("GET", "/api/x").queryParam("tag", List.of("a", "b", "c"));
        assertEquals(List.of("a", "b", "c"), req.queryParams.get("tag"));
    }
}
