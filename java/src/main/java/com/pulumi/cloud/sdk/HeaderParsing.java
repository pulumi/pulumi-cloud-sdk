// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import java.net.http.HttpHeaders;

/**
 * Header-value parsing helpers for generated {@code *Api} methods whose response
 * declares typed response headers. {@link HttpHeaders#firstValue} already gives a
 * single-value accessor, but every numeric/boolean conversion still needs a
 * default for a missing or unparsable header — {@code Long.parseLong(null)}, or a
 * malformed value, would otherwise throw.
 */
public final class HeaderParsing {
    private HeaderParsing() {
    }

    public static String stringOrDefault(HttpHeaders headers, String name) {
        return headers.firstValue(name).orElse("");
    }

    public static boolean parseBoolean(HttpHeaders headers, String name) {
        return headers.firstValue(name).map(Boolean::parseBoolean).orElse(false);
    }

    public static int parseInt(HttpHeaders headers, String name) {
        return headers.firstValue(name).map(v -> {
            try {
                return Integer.parseInt(v);
            } catch (NumberFormatException e) {
                return 0;
            }
        }).orElse(0);
    }

    public static long parseLong(HttpHeaders headers, String name) {
        return headers.firstValue(name).map(v -> {
            try {
                return Long.parseLong(v);
            } catch (NumberFormatException e) {
                return 0L;
            }
        }).orElse(0L);
    }

    public static float parseFloat(HttpHeaders headers, String name) {
        return headers.firstValue(name).map(v -> {
            try {
                return Float.parseFloat(v);
            } catch (NumberFormatException e) {
                return 0f;
            }
        }).orElse(0f);
    }

    public static double parseDouble(HttpHeaders headers, String name) {
        return headers.firstValue(name).map(v -> {
            try {
                return Double.parseDouble(v);
            } catch (NumberFormatException e) {
                return 0.0;
            }
        }).orElse(0.0);
    }
}
