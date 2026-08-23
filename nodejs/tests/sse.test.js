// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Exercises the Server-Sent Events runtime (streamWithOptions): events are
// parsed from a real text/event-stream response, yielded through the async
// iterable, and iteration ends when the stream is aborted. Zero dependencies:
// node:http as a local SSE source + node:test.

const { test } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");

const { ApiClient, ApiClientConfiguration, ApiRequest } = require("../dist/index.js");

test("streamWithOptions parses events and stops on abort", async () => {
    const server = http.createServer((_req, res) => {
        res.writeHead(200, {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            connection: "keep-alive",
        });
        res.write("id: 1\ndata: {\"n\":1}\n\n");
        res.write("id: 2\ndata: {\"n\":2}\n\n");
        // Keep the connection open; the client aborts once it has both events.
    });

    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const { port } = server.address();

    try {
        const client = new ApiClient(new ApiClientConfiguration(`http://127.0.0.1:${port}/`, "sse-test"));
        const req = new ApiRequest();
        req.method = "GET";
        req.setProduce("text/event-stream");

        // Tag each event via the fixup callback to prove it runs.
        const stream = await client.streamWithOptions(`http://127.0.0.1:${port}/events`, req, (evt) => {
            evt.seen = true;
        });

        const received = [];
        for await (const evt of stream.events) {
            received.push(evt);
            if (received.length === 2) {
                stream.abort.abort();
                break;
            }
        }

        assert.deepEqual(received, [
            { n: 1, seen: true },
            { n: 2, seen: true },
        ]);
    } finally {
        server.close();
    }
});
