// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Runtime tests for the request path: query-parameter encoding, auth/source
// headers, and body serialization. Mirrors sdk/python/tests/test_query_params.py.
// Zero dependencies: node:test + a stubbed global fetch.

const { test } = require("node:test");
const assert = require("node:assert/strict");

const { ApiClient, ApiClientConfiguration, ApiRequest } = require("../dist/index.js");

function jsonResponse(body, status = 200) {
    return new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
    });
}

async function capture(config, buildRequest, path) {
    const original = globalThis.fetch;
    let captured;
    globalThis.fetch = async (url, init) => {
        captured = { url, init };
        return jsonResponse({ ok: true });
    };
    try {
        const client = new ApiClient(config);
        const req = new ApiRequest();
        buildRequest(req);
        const result = await client.callWithOptions(path, req);
        return { captured, result };
    } finally {
        globalThis.fetch = original;
    }
}

test("repeated query keys, lowercase booleans, and skipped undefined", async () => {
    const config = new ApiClientConfiguration("https://example.test/api/", "test-src", () => "tok123", 8);
    const { captured, result } = await capture(
        config,
        (req) => {
            req.method = "GET";
            req.setProduce("application/json");
            req.setQueryParam("tag", ["a", "b"]);
            req.setQueryParam("flag", true);
            req.setQueryParam("missing", undefined);
        },
        "https://example.test/api/things",
    );

    assert.deepEqual(result, { ok: true });
    const url = new URL(captured.url);
    assert.deepEqual(url.searchParams.getAll("tag"), ["a", "b"]);
    assert.equal(url.searchParams.get("flag"), "true");
    assert.equal(url.searchParams.has("missing"), false);
});

test("auth, source, and accept headers are applied", async () => {
    const config = new ApiClientConfiguration("https://example.test/api/", "test-src", () => "tok123", 8);
    const { captured } = await capture(
        config,
        (req) => {
            req.method = "GET";
            req.setProduce("application/json");
        },
        "https://example.test/api/thing",
    );

    assert.equal(captured.init.headers["Authorization"], "token tok123");
    assert.equal(captured.init.headers["X-Pulumi-Source"], "test-src");
    assert.equal(captured.init.headers["Accept"], "application/json");
});

test("no Authorization header when the token is null", async () => {
    const config = new ApiClientConfiguration("https://example.test/api/", "test-src", () => null, 8);
    const { captured } = await capture(
        config,
        (req) => {
            req.method = "GET";
            req.setProduce("application/json");
        },
        "https://example.test/api/thing",
    );

    assert.equal("Authorization" in captured.init.headers, false);
});

test("JSON body is serialized with the right content-type", async () => {
    const config = new ApiClientConfiguration("https://example.test/api/", "test-src", () => "tok", 8);
    const { captured } = await capture(
        config,
        (req) => {
            req.method = "POST";
            req.setConsume("application/json");
            req.setProduce("application/json");
            req.body = { name: "widget", count: 3 };
            req.hasBodyParam = true;
        },
        "https://example.test/api/things",
    );

    assert.equal(captured.init.method, "POST");
    assert.equal(captured.init.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(captured.init.body), { name: "widget", count: 3 });
});

test("binary body values are base64-encoded, not dropped", async () => {
    // Raw bytes are base64 on the wire. A bare JSON.stringify renders an
    // ArrayBuffer as `{}` and a typed array as an index-keyed object, so the
    // request carried no usable data (#37343). A view must contribute only its
    // own bytes, and an already-base64 string must pass through untouched.
    const config = new ApiClientConfiguration("https://example.test/api/", "test-src", () => "tok", 8);
    const { captured } = await capture(
        config,
        (req) => {
            req.method = "POST";
            req.setConsume("application/json");
            req.setProduce("application/json");
            req.body = {
                buffer: new Uint8Array([104, 105]).buffer,
                typed: new Uint8Array([1, 2, 3]),
                view: new Uint8Array([0, 0, 104, 105]).subarray(2),
                nested: { list: [new Uint8Array([104, 105]).buffer] },
                alreadyEncoded: "aGk=",
            };
            req.hasBodyParam = true;
        },
        "https://example.test/api/things",
    );

    assert.deepEqual(JSON.parse(captured.init.body), {
        buffer: "aGk=",
        typed: "AQID",
        view: "aGk=",
        nested: { list: ["aGk="] },
        alreadyEncoded: "aGk=",
    });
});

test("an application/x-tar response is read as raw bytes, not text", async () => {
    // A download's body *is* the bytes — unlike a byte[] inside a JSON
    // document, which is base64 (#37343). Reading it as text would corrupt any
    // byte that isn't valid UTF-8, so the client asks for the binary media type
    // and hands back an ArrayBuffer.
    const bytes = new Uint8Array([0x1f, 0x8b, 0x00, 0xff]);
    const original = globalThis.fetch;
    let captured;
    globalThis.fetch = async (url, init) => {
        captured = { url, init };
        return new Response(bytes, { status: 200, headers: { "content-type": "application/x-tar" } });
    };
    try {
        const client = new ApiClient(new ApiClientConfiguration());
        const req = new ApiRequest();
        req.method = "GET";
        req.setProduce("application/x-tar");
        const result = await client.callWithOptions("https://example.test/api/download", req);

        assert.equal(captured.init.headers["Accept"], "application/x-tar");
        assert.ok(result instanceof ArrayBuffer);
        assert.deepEqual(new Uint8Array(result), bytes);
    } finally {
        globalThis.fetch = original;
    }
});

test("non-2xx rejects with an ApiError carrying the parsed body", async () => {
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
            () => client.callWithOptions("https://example.test/api/missing", req),
            (err) => {
                assert.equal(err.name, "ApiError");
                assert.equal(err.status, 404);
                assert.equal(err.body.message, "not found");
                return true;
            },
        );
    } finally {
        globalThis.fetch = original;
    }
});
