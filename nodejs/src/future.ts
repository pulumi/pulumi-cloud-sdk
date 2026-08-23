// Copyright 2026, Pulumi Corporation. All rights reserved.

// A resolvable/rejectable Promise subclass. `apis.*` methods return a `Future`
// so callers can cancel an in-flight request (see CancelSignal) or resolve /
// reject it out of band. This is the standalone-SDK port of the console client's
// Future; the Angular/zone.js "fake listener" guard is intentionally dropped —
// the standalone SDK has no zone.js.

class FutureInner<T> extends Promise<T> {
    private timeoutId: ReturnType<typeof setTimeout> | undefined;
    private resolveCallback: (value?: T | PromiseLike<T>) => void;
    private rejectCallback: (reason?: any) => void;
    private m_resolved: boolean = false;

    constructor(state: any) {
        super((resolve, reject) => {
            state.resolveCallback = resolve;
            state.rejectCallback = reject;
        });

        this.resolveCallback = state.resolveCallback;
        this.rejectCallback = state.rejectCallback;
    }

    isResolved(): boolean {
        return this.m_resolved;
    }

    resolve(value?: T) {
        if (this.canResolve()) {
            this.cancelTimeout();

            this.resolveCallback(value);
        }
    }

    reject(reason?: any) {
        if (this.canResolve()) {
            this.cancelTimeout();

            this.rejectCallback(reason);
        }
    }

    setCancellationTimeout(timeout: number, reason?: any) {
        if (!this.m_resolved) {
            this.cancelTimeout();
            this.timeoutId = setTimeout(() => this.reject(reason), timeout);
        }
    }

    setResolveTimeout(value: T, timeout: number) {
        if (!this.m_resolved) {
            this.cancelTimeout();
            this.timeoutId = setTimeout(() => this.resolve(value), timeout);
        }
    }

    private cancelTimeout() {
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = undefined;
        }
    }

    private canResolve() {
        if (this.m_resolved) {
            return false;
        }

        this.m_resolved = true;
        return true;
    }
}

export class Future<T> extends FutureInner<T> {
    constructor() {
        super({});
    }

    static delayed<T>(timeout: number, value?: T): Future<T> {
        let res = new Future<T>();
        setTimeout(() => res.resolve(value), timeout);
        return res;
    }

    // Return a plain Promise for then/catch/finally so chaining doesn't try to
    // construct a Future (which takes no executor).
    static get [Symbol.species]() {
        return Promise;
    }

    get [Symbol.toStringTag]() {
        return "Future";
    }
}
