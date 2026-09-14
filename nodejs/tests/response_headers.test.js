// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Runtime tests for callWithOptionsAndHeaders / callWithOptionsAndHeadersOnly.
// Zero dependencies: node:test + a stubbed global fetch. Mirrors the style of
// tests/request.test.js.

const { test } = require("node:test");
const assert = require("node:assert/strict");

const { ApiClient, ApiClientConfiguration, ApiRequest } = require("../dist/index.js");

function parseHeaders(h) {
    return { eTag: h.get("ETag") ?? "", pulumiESCRevision: Number(h.get("Pulumi-ESC-Revision")) || 0 };
}

test("callWithOptionsAndHeaders resolves with both the parsed body and headers", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = async () =>
        new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "content-type": "application/json", ETag: "abc123", "Pulumi-ESC-Revision": "7" },
        });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "GET";
        req.setProduce("application/json");
        const result = await client.callWithOptionsAndHeaders("https://example.test/api/thing", req, parseHeaders);

        assert.deepEqual(result.response, { ok: true });
        assert.deepEqual(result.headers, { eTag: "abc123", pulumiESCRevision: 7 });
    } finally {
        globalThis.fetch = original;
    }
});

test("callWithOptionsAndHeaders runs fixup on the parsed body before resolving", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = async () =>
        new Response(JSON.stringify({ name: "widget" }), {
            status: 200,
            headers: { "content-type": "application/json", ETag: "xyz" },
        });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "GET";
        req.setProduce("application/json");
        let fixedUp;
        const result = await client.callWithOptionsAndHeaders(
            "https://example.test/api/thing",
            req,
            parseHeaders,
            (value) => {
                fixedUp = value;
                value.name = value.name.toUpperCase();
            },
        );

        assert.deepEqual(fixedUp, { name: "WIDGET" });
        assert.equal(result.response.name, "WIDGET");
        assert.equal(result.headers.eTag, "xyz");
    } finally {
        globalThis.fetch = original;
    }
});

test("callWithOptionsAndHeaders rejects with an ApiError on non-2xx", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = async () =>
        new Response(JSON.stringify({ code: 404, message: "not found" }), {
            status: 404,
            headers: { "content-type": "application/json" },
        });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "GET";
        req.setProduce("application/json");
        await assert.rejects(
            () => client.callWithOptionsAndHeaders("https://example.test/api/missing", req, parseHeaders),
            (err) => {
                assert.equal(err.name, "ApiError");
                assert.equal(err.status, 404);
                return true;
            },
        );
    } finally {
        globalThis.fetch = original;
    }
});

test("callWithOptionsAndHeadersOnly resolves with just the parsed headers, ignoring the body", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = async () =>
        new Response(null, {
            status: 204,
            headers: { ETag: "head-etag", "Pulumi-ESC-Revision": "3" },
        });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "HEAD";
        const result = await client.callWithOptionsAndHeadersOnly("https://example.test/api/thing", req, parseHeaders);

        assert.deepEqual(result, { eTag: "head-etag", pulumiESCRevision: 3 });
    } finally {
        globalThis.fetch = original;
    }
});

test("callWithOptionsAndHeadersOnly defaults missing headers to the zero value", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = async () => new Response(null, { status: 204, headers: {} });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "HEAD";
        const result = await client.callWithOptionsAndHeadersOnly("https://example.test/api/thing", req, parseHeaders);

        assert.deepEqual(result, { eTag: "", pulumiESCRevision: 0 });
    } finally {
        globalThis.fetch = original;
    }
});

test("callWithOptionsAndHeadersOnly defaults a malformed header to the zero value rather than NaN", async () => {
    // A malformed-but-present header must not silently produce NaN -- see
    // headerFieldValueExprTypescript's `|| 0` fallback in typescript.go.
    const original = globalThis.fetch;
    globalThis.fetch = async () =>
        new Response(null, {
            status: 204,
            headers: { ETag: "some-etag", "Pulumi-ESC-Revision": "not-a-number" },
        });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "HEAD";
        const result = await client.callWithOptionsAndHeadersOnly("https://example.test/api/thing", req, parseHeaders);

        assert.deepEqual(result, { eTag: "some-etag", pulumiESCRevision: 0 });
    } finally {
        globalThis.fetch = original;
    }
});

test("callWithOptionsAndHeadersOnly rejects with an ApiError on non-2xx", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = async () =>
        new Response(JSON.stringify({ code: 403, message: "forbidden" }), {
            status: 403,
            headers: { "content-type": "application/json" },
        });
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "HEAD";
        await assert.rejects(
            () => client.callWithOptionsAndHeadersOnly("https://example.test/api/thing", req, parseHeaders),
            (err) => {
                assert.equal(err.name, "ApiError");
                assert.equal(err.status, 403);
                return true;
            },
        );
    } finally {
        globalThis.fetch = original;
    }
});
