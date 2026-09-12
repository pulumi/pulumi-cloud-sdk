// Copyright 2026, Pulumi Corporation.  All rights reserved.

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// Pairs a deserialized response body with typed response headers, mirroring
    /// <c>apitype.ResponseWithHeaders[R, H]</c> (Go) / <c>ResponseWithHeaders&lt;R, H&gt;</c>
    /// (TypeScript) / <c>ResponseWithHeaders[R, H]</c> (Python). Returned by generated
    /// <c>*Api</c> methods for operations whose response declares response headers.
    /// Declared in the top-level <c>Pulumi.Cloud.Sdk</c> namespace (alongside
    /// <see cref="ApiClient"/>) so generated code in <c>Pulumi.Cloud.Sdk.Api</c> resolves
    /// it via enclosing-namespace lookup, the same way it already resolves
    /// <see cref="ApiClient"/> and <see cref="ApiRequest"/> with no extra <c>using</c>.
    /// </summary>
    public sealed class ResponseWithHeaders<R, H>
    {
        public R Response { get; set; }
        public H Headers { get; set; }
    }
}
