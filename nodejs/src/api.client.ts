// Copyright 2026, Pulumi Corporation. All rights reserved.

// Hand-written, dependency-free runtime for the standalone Pulumi Cloud
// TypeScript SDK. The generated `api/*.ts` and `api.services.ts` target the
// `ApiClient` / `ApiRequest` / `ServerSentEventsStream` contract defined here.
// Unlike the Angular client in cmd/console2/src/proxy, this implementation uses
// only Node 22 globals (fetch, URL, URLSearchParams, ReadableStream,
// TextDecoder, AbortController, DOMException, Buffer) and has zero runtime
// dependencies.

import { Future } from "./future";

export type EnumOrString = number | string;
export type Lookup<T, U extends EnumOrString = string> = { [key in U]?: T };

/** Connection settings shared by every generated `apis.*` class. */
export class ApiClientConfiguration {
    constructor(
        /** API base URL, including the `/api/` prefix and a trailing slash,
         *  e.g. `https://api.pulumi.com/api/`. */
        public readonly apiHost: string = "https://api.pulumi.com/api/",
        /** Value sent as the `X-Pulumi-Source` header. */
        public readonly source: string = "pulumi-cloud-sdk",
        /** Returns the Pulumi access token, sent as `Authorization: token <token>`.
         *  Return `null` for unauthenticated requests. */
        public readonly getToken: () => string | null = () => null,
        /** API version negotiated via the `Accept: application/vnd.pulumi+<version>` header. */
        public readonly version: number = 8,
        /** Optional hook invoked with every settled error, in addition to the
         *  rejected Future. Throwing from it is swallowed. */
        public readonly errorHandler: (error: ApiError) => void = () => undefined,
    ) {}
}

/** Error thrown/rejected for a non-2xx response or a transport failure. */
export class ApiError extends Error {
    constructor(
        public readonly status: number,
        message: string,
        /** Parsed JSON error body, or the raw text, or undefined. */
        public readonly body: unknown,
        public readonly url: string,
    ) {
        super(`API error ${status}: ${message}`);
        this.name = "ApiError";
    }
}

/** Handle returned by streaming (SSE) operations. */
export interface ServerSentEventsStream<T> {
    /** Async iterable that yields each event as it arrives. Iteration ends on a
     *  fatal error (throws) or when `abort` is triggered (returns). */
    events: AsyncIterable<T>;
    /** Abort the SSE connection and end iteration. */
    abort: AbortController;
}

type ResponseKind = "json" | "binary" | "text";

/**
 * Media types whose body is raw bytes rather than a text or JSON document, and
 * which therefore have to be read as an ArrayBuffer. Mirrors
 * `analyzer.IsBinaryMediaType` in the code generator, which types the
 * corresponding operations as `Promise<ArrayBuffer>`. Also used for request
 * bodies, which are sent unencoded.
 */
const binaryMediaTypes = ["application/octet-stream", "application/x-tar"];

function isBinaryMediaType(mediaType: string): boolean {
    return binaryMediaTypes.includes(mediaType);
}

/**
 * Media types whose body is the text of the document itself, with no JSON
 * envelope to encode. Mirrors `analyzer.IsUnencodedTextMediaType` in the code
 * generator, which types the corresponding request bodies as `string` and makes
 * the Go dispatch read them verbatim.
 */
const unencodedTextMediaTypes = ["application/x-yaml", "application/yaml", "text/plain", "text/markdown"];

function isUnencodedTextMediaType(mediaType: string): boolean {
    return unencodedTextMediaTypes.includes(mediaType);
}

export class ApiClient {
    constructor(public configuration: ApiClientConfiguration = new ApiClientConfiguration()) {}

    /**
     * Issue an HTTP request and return a Future that resolves with the parsed
     * response body. `fixup` runs synchronously on the parsed body before the
     * Future resolves (e.g. `Type.fixupPrototype` to restore class prototypes on
     * plain JSON). Rejecting the returned Future (e.g. via `CancelSignal.guard`)
     * aborts the in-flight request on the wire.
     */
    callWithOptions<T>(path: string, requestOptions: ApiRequest, fixup?: (value: T) => void): Future<T> {
        const future = new Future<T>();
        const controller = new AbortController();

        // If the Future is rejected out of band (cancellation), abort the wire
        // request. Attaching this handler also marks the Future as observed so a
        // late rejection never surfaces as an unhandled rejection.
        future.then(
            () => undefined,
            () => controller.abort(),
        );

        const headers = this.baseHeaders(requestOptions);
        headers["Accept"] = `application/vnd.pulumi+${this.configuration.version}`;

        let responseKind: ResponseKind = "text";
        const binaryProduce = requestOptions.produces?.find(isBinaryMediaType);
        if (requestOptions.produces?.includes("application/json")) {
            headers["Accept"] = "application/json";
            responseKind = "json";
        } else if (binaryProduce !== undefined) {
            headers["Accept"] = binaryProduce;
            responseKind = "binary";
        }

        const body = this.encodeBody(requestOptions, headers);
        const url = this.buildUrl(path, requestOptions.queryParams);

        fetch(url, { method: requestOptions.method, headers, body, signal: controller.signal })
            .then(async (response) => {
                if (!response.ok) {
                    const err = await this.buildError(response, url);
                    if (!future.isResolved()) {
                        future.reject(err);
                        this.routeError(err);
                    }
                    return;
                }
                try {
                    const value = await this.parseResponseBody<T>(response, responseKind);
                    if (fixup) {
                        fixup(value);
                    }
                    future.resolve(value);
                } catch (err) {
                    const wrapped = new ApiError(response.status, String(err), undefined, url);
                    if (!future.isResolved()) {
                        future.reject(wrapped);
                        this.routeError(wrapped);
                    }
                }
            })
            .catch((err) => {
                // Network failure or abort. If the Future already settled (e.g. an
                // external cancel that triggered controller.abort), this is a no-op.
                if (!future.isResolved()) {
                    future.reject(err);
                }
            });

        return future;
    }

    /**
     * Open a Server-Sent Events stream. Returns a handle whose `events` async
     * iterable yields each parsed event; `abort` ends the stream. On a clean
     * server close the connection is transparently re-established (resuming from
     * the last event id); 4xx (except 429) are fatal, 429/5xx are retried.
     */
    async streamWithOptions<T>(
        path: string,
        requestOptions: ApiRequest,
        fixup?: (value: T) => void,
    ): Promise<ServerSentEventsStream<T>> {
        const abort = new AbortController();

        const headers = this.baseHeaders(requestOptions);
        headers["Accept"] = "text/event-stream";

        const method = requestOptions.method || "GET";
        const url = this.buildUrl(path, requestOptions.queryParams);

        async function* generate(): AsyncGenerator<T> {
            let lastEventId: string | undefined = headers["Last-Event-ID"];

            while (!abort.signal.aborted) {
                let response: Response;
                try {
                    const attemptHeaders = { ...headers };
                    if (lastEventId) {
                        attemptHeaders["Last-Event-ID"] = lastEventId;
                    }
                    response = await fetch(url, { method, headers: attemptHeaders, signal: abort.signal });
                } catch {
                    if (abort.signal.aborted) return;
                    await sleep(1000, abort.signal);
                    continue;
                }

                const contentType = response.headers.get("content-type") ?? "";
                if (!response.ok || !contentType.startsWith("text/event-stream")) {
                    if (response.status >= 400 && response.status < 500 && response.status !== 429) {
                        throw new ApiError(
                            response.status,
                            `SSE connection failed: ${response.statusText}`,
                            undefined,
                            url,
                        );
                    }
                    await sleep(1000, abort.signal);
                    continue;
                }

                if (!response.body) return;
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = "";

                try {
                    for (;;) {
                        const { done, value } = await reader.read();
                        if (done) break; // clean close -> reconnect
                        buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, "\n");

                        let sep: number;
                        while ((sep = buffer.indexOf("\n\n")) >= 0) {
                            const rawEvent = buffer.slice(0, sep);
                            buffer = buffer.slice(sep + 2);
                            const event = parseServerSentEvent(rawEvent);
                            if (event.id !== undefined) {
                                lastEventId = event.id;
                            }
                            if (event.data) {
                                const parsed = JSON.parse(event.data) as T;
                                if (fixup) {
                                    fixup(parsed);
                                }
                                yield parsed;
                            }
                        }
                    }
                } catch (err) {
                    if (abort.signal.aborted) return;
                    throw err;
                }
                // Clean close: loop and reconnect.
            }
        }

        return { events: generate(), abort };
    }

    private baseHeaders(requestOptions: ApiRequest): Record<string, string> {
        const headers: Record<string, string> = {};
        for (const [key, value] of Object.entries(requestOptions.headers)) {
            headers[key] = Array.isArray(value) ? value.join(", ") : value;
        }
        headers["X-Pulumi-Source"] = this.configuration.source;
        const token = this.configuration.getToken();
        if (token) {
            headers["Authorization"] = `token ${token}`;
        }
        return headers;
    }

    private buildUrl(path: string, queryParams: Lookup<string | string[]>): string {
        const search = new URLSearchParams();
        for (const [key, value] of Object.entries(queryParams ?? {})) {
            if (value === undefined || value === null) continue;
            if (Array.isArray(value)) {
                for (const item of value) {
                    search.append(key, item);
                }
            } else {
                search.append(key, value);
            }
        }
        const qs = search.toString();
        return qs ? `${path}?${qs}` : path;
    }

    private encodeBody(requestOptions: ApiRequest, headers: Record<string, string>): RequestInit["body"] {
        if (requestOptions.hasBodyParam) {
            const consume = requestOptions.consumes?.[0] ?? "application/json";
            if (isBinaryMediaType(consume) || isUnencodedTextMediaType(consume)) {
                // Send the body exactly as supplied. Raw bytes and unencoded text
                // differ in how a response is read, but as a request body neither
                // gets an encoding pass: JSON.stringify would quote and escape
                // text into something the server cannot parse.
                headers["Content-Type"] = consume;
                return requestOptions.body as RequestInit["body"];
            }
            headers["Content-Type"] = "application/json";
            return requestOptions.body == null ? "" : JSON.stringify(requestOptions.body, encodeBinaryValues);
        }

        if (requestOptions.hasFormParams) {
            headers["Content-Type"] = "application/x-www-form-urlencoded";
            const search = new URLSearchParams();
            for (const [key, value] of Object.entries(requestOptions.formParams ?? {})) {
                if (value === undefined || value === null) continue;
                if (Array.isArray(value)) {
                    for (const item of value) {
                        search.append(key, item);
                    }
                } else {
                    search.append(key, value);
                }
            }
            return search.toString();
        }

        if (requestOptions.consumes && requestOptions.consumes.length > 0) {
            headers["Content-Type"] = requestOptions.consumes[0];
        }
        return undefined;
    }

    private async parseResponseBody<T>(response: Response, kind: ResponseKind): Promise<T> {
        if (response.status === 204) {
            return undefined as T;
        }

        let contentType = response.headers.get("content-type");
        contentType = contentType ? contentType.split(";")[0].trim() : "";

        switch (contentType) {
            case "application/json":
                return (await response.json()) as T;

            case "application/octet-stream":
            case "application/x-tar":
                return (await response.arrayBuffer()) as T;

            case "application/x-yaml":
            case "text/plain":
            case "text/markdown":
            case "text/html":
                return (await response.text()) as T;

            case "":
                // No content-type (e.g. empty body). Honor the caller's expectation.
                if (kind === "binary") return (await response.arrayBuffer()) as T;
                return (await response.text()) as T;

            default:
                throw new TypeError(`Unsupported response content type (${contentType}).`);
        }
    }

    private async buildError(response: Response, url: string): Promise<ApiError> {
        let text = "";
        try {
            text = await response.text();
        } catch {
            // Keep the empty body.
        }
        let parsed: unknown;
        try {
            parsed = text ? JSON.parse(text) : undefined;
        } catch {
            parsed = undefined;
        }
        const message =
            parsed && typeof parsed === "object" && "message" in parsed
                ? String((parsed as { message: unknown }).message)
                : text || response.statusText;
        return new ApiError(response.status, message, parsed ?? text, url);
    }

    private routeError(error: ApiError): void {
        try {
            this.configuration.errorHandler(error);
        } catch {
            // A misbehaving handler must not escape; the Future is already settled.
        }
    }
}

/** Parameter carrier populated by generated code before a call. */
export class ApiRequest {
    method: string = "GET";

    formParams: Lookup<string | string[]> = {};
    queryParams: Lookup<string | string[]> = {};

    headers: Record<string, string | string[]> = {};

    body: any;

    consumes: string[] = [];
    produces: string[] = [];

    hasFormParams: boolean = false;
    hasBodyParam: boolean = false;

    public setConsume(type: string): void {
        this.consumes.push(type);
    }

    public setProduce(type: string): void {
        this.produces.push(type);
    }

    public setHeader(name: string, value: string | string[]): void {
        this.headers[name] = value;
    }

    public setFormParam(name: string, value: string): void {
        this.hasFormParams = true;
        ApiRequest.setParam(this.formParams, name, value);
    }

    public setQueryParam(name: string, value: any): void {
        if (value === null || value === undefined) return;
        if (Array.isArray(value)) {
            for (const item of value) {
                if (item === null || item === undefined) continue;
                ApiRequest.setParam(this.queryParams, name, String(item));
            }
        } else {
            ApiRequest.setParam(this.queryParams, name, String(value));
        }
    }

    private static setParam(params: Lookup<string | string[]>, name: string, value: string): void {
        if (value === null || value === undefined) return;

        const oldValue = params[name];
        if (oldValue) {
            if (Array.isArray(oldValue)) {
                oldValue.push(value);
            } else {
                params[name] = [oldValue, value];
            }
        } else {
            params[name] = value;
        }
    }
}

interface ParsedServerSentEvent {
    id?: string;
    event?: string;
    data?: string;
}

/** Parse one SSE event block (fields separated by newlines) per the WHATWG spec. */
function parseServerSentEvent(raw: string): ParsedServerSentEvent {
    const result: ParsedServerSentEvent = {};
    const dataLines: string[] = [];
    for (const line of raw.split("\n")) {
        if (line === "" || line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        let value = colon === -1 ? "" : line.slice(colon + 1);
        if (value.startsWith(" ")) value = value.slice(1);
        switch (field) {
            case "id":
                result.id = value;
                break;
            case "event":
                result.event = value;
                break;
            case "data":
                dataLines.push(value);
                break;
            default:
                // Ignore unknown fields (e.g. `retry`).
                break;
        }
    }
    if (dataLines.length > 0) {
        result.data = dataLines.join("\n");
    }
    return result;
}

/** Sleep for `ms`, resolving early if `signal` aborts. */
function sleep(ms: number, signal: AbortSignal): Promise<void> {
    return new Promise((resolve) => {
        if (signal.aborted) {
            resolve();
            return;
        }
        const timer = setTimeout(() => {
            signal.removeEventListener("abort", onAbort);
            resolve();
        }, ms);
        const onAbort = () => {
            clearTimeout(timer);
            resolve();
        };
        signal.addEventListener("abort", onAbort, { once: true });
    });
}

/**
 * JSON.stringify replacer that base64-encodes binary values, which is how the
 * API represents raw bytes in JSON (Go unmarshals a `[]byte` from a base64
 * string). Without it an ArrayBuffer serializes as `{}` and a typed array as an
 * index-keyed object, so the request carried no data at all — see issue #37343.
 * Generated models declare such fields as base64 `string` and need no
 * conversion; this covers a hand-built body that holds the bytes themselves.
 */
function encodeBinaryValues(_: string, value: unknown): unknown {
    if (value instanceof ArrayBuffer) {
        return Buffer.from(value).toString("base64");
    }

    if (ArrayBuffer.isView(value)) {
        return Buffer.from(value.buffer, value.byteOffset, value.byteLength).toString("base64");
    }

    return value;
}
