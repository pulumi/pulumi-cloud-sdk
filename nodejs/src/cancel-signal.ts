// Copyright 2026, Pulumi Corporation. All rights reserved.

import { Future } from "./future";

/**
 * Caller-side cancellation primitive for `Promise<T>` / `Future<T>`-shaped APIs.
 *
 * `guard(p)` returns a promise that adopts `p`'s settlement unless `cancel()`
 * fires first, in which case it rejects with `DOMException("...", "AbortError")`.
 *
 * The behavior depends on the input:
 *
 * - **`Future<T>`** (the runtime shape returned by every `apis.*` method): on
 *   cancel, `guard` rejects the Future directly. `ApiClient.callWithOptions`
 *   observes that rejection and aborts the underlying `fetch`, so the request is
 *   dropped on the wire.
 *
 * - **plain `Promise<T>`**: `Promise.race` against the cancel signal. The
 *   underlying work keeps running and the result is read but unobserved.
 *
 * Per-operation signals (search-as-you-type debounce, "stop loading" buttons)
 * construct their own `CancelSignal` instances and call `cancel()` directly.
 */
export class CancelSignal {
    private cancelled = false;
    private cancelReason?: DOMException;
    private rejectCancel!: (reason: DOMException) => void;
    // The cancel promise only ever rejects (or pends forever). Typed as
    // `Promise<never>` so `Promise.race` infers the input's value type.
    private readonly cancelPromise: Promise<never> = new Promise<never>((_, reject) => {
        this.rejectCancel = reject;
    });
    // Per-`guard(future)` abort callbacks. Each callback is added on
    // `guard(future)` and removed when the Future settles, so a long-lived
    // signal doesn't accumulate one Promise reaction per call (Promise
    // reactions can't be detached). `cancel()` iterates and clears the set.
    private readonly futureListeners = new Set<(reason: DOMException) => void>();

    constructor() {
        // Avoid the "unhandled rejection" warning that fires when nothing has
        // yet attached a `.catch` to `cancelPromise` at the time it rejects.
        // The dangling .catch is a no-op consumer; consumers of `guard()` /
        // `asPromise()` still see the rejection.
        this.cancelPromise.catch(() => undefined);
    }

    /**
     * Reject all pending and future `guard()`s on this signal with
     * `DOMException(reason, "AbortError")`. Idempotent: subsequent calls
     * are silent no-ops, so callers can safely cancel a signal that may
     * already have been cancelled.
     */
    cancel(reason?: string): void {
        if (this.cancelled) return;
        this.cancelled = true;
        this.cancelReason = new DOMException(reason ?? "Aborted", "AbortError");
        // Reject `cancelPromise` for any `Promise.race`-fallback consumers
        // and asPromise-observers, then drive every Future listener.
        this.rejectCancel(this.cancelReason);
        for (const listener of this.futureListeners) {
            listener(this.cancelReason);
        }
        this.futureListeners.clear();
    }

    /**
     * Race `p` against this signal. If `p` is a `Future`, drive cancellation by
     * rejecting the Future on `cancel()` — that propagates through the API
     * client to abort the wire request. Otherwise fall back to `Promise.race`
     * (the work keeps running unobserved).
     *
     * If `cancel()` is called *after* the input already settled, the resolved
     * value flows through unchanged: `Future.reject` is idempotent post-settle,
     * and `Promise.race` only honors the first settlement.
     */
    guard<T>(p: Promise<T> | Future<T>): Promise<T> {
        if (p instanceof Future) {
            if (this.cancelled && this.cancelReason) {
                // Pre-cancelled: reject immediately, no listener tracking
                // needed for a cancellation that has already fired.
                p.reject(this.cancelReason);
                return p;
            }
            const onAbort = (err: DOMException): void => {
                p.reject(err);
            };
            this.futureListeners.add(onAbort);
            // Remove the listener once the Future settles so a long-lived
            // signal doesn't keep dead callbacks for the rest of its life.
            p.then(
                () => {
                    this.futureListeners.delete(onAbort);
                },
                () => {
                    this.futureListeners.delete(onAbort);
                },
            );
            return p;
        }
        return Promise.race([p, this.cancelPromise]);
    }

    /**
     * Expose the underlying cancel promise for code that needs to observe
     * cancellation directly. The returned promise rejects with the cancel error
     * and never resolves.
     */
    asPromise(): Promise<never> {
        return this.cancelPromise;
    }
}
