// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import java.time.Duration;
import java.util.function.Supplier;

/**
 * Connection settings shared by every generated {@code *Api} class.
 *
 * <p>{@code host} is the API origin (no {@code /api} suffix — the generated
 * resource paths already start with {@code /api/...}). {@code accessToken}
 * supplies the Pulumi access token sent as {@code Authorization: token <token>};
 * it is a {@link Supplier} so a rotating token can be re-read per request. Return
 * {@code null} for unauthenticated requests.
 */
public class ApiClientConfiguration {
    private String host = "https://api.pulumi.com";
    private Supplier<String> accessToken = () -> null;
    private String source = "pulumi-cloud-sdk";
    private Duration timeout = Duration.ofSeconds(60);

    public String getHost() {
        return host;
    }

    public ApiClientConfiguration setHost(String host) {
        this.host = host;
        return this;
    }

    public Supplier<String> getAccessToken() {
        return accessToken;
    }

    /** Set a static access token (sent as {@code Authorization: token <token>}). */
    public ApiClientConfiguration setAccessToken(String accessToken) {
        this.accessToken = () -> accessToken;
        return this;
    }

    /** Set a dynamic access-token supplier, re-read on every request. */
    public ApiClientConfiguration setAccessToken(Supplier<String> accessToken) {
        this.accessToken = accessToken != null ? accessToken : () -> null;
        return this;
    }

    public String getSource() {
        return source;
    }

    public ApiClientConfiguration setSource(String source) {
        this.source = source;
        return this;
    }

    public Duration getTimeout() {
        return timeout;
    }

    public ApiClientConfiguration setTimeout(Duration timeout) {
        this.timeout = timeout;
        return this;
    }
}
