// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;
using Newtonsoft.Json.Linq;

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// Thrown for a non-2xx HTTP response, a transport failure, or a
    /// serialization/deserialization error.
    /// </summary>
    public sealed class ApiException : Exception
    {
        /// <summary>HTTP status code, or 0 for a transport/serialization failure.</summary>
        public int StatusCode { get; }

        public string Url { get; }

        /// <summary>Parsed JSON error body, or <c>null</c> if the body was absent or not JSON.</summary>
        public JToken Body { get; }

        /// <summary>Raw response body text, or <c>null</c>.</summary>
        public string RawBody { get; }

        public ApiException(int statusCode, string message, string url, JToken body, string rawBody, Exception inner)
            : base(message, inner)
        {
            StatusCode = statusCode;
            Url = url;
            Body = body;
            RawBody = rawBody;
        }
    }
}
