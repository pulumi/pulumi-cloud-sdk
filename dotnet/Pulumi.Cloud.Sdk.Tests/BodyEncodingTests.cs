// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Xunit;

namespace Pulumi.Cloud.Sdk.Tests
{
    /// <summary>
    /// Wire-level tests for request-body serialization. The runtime must honor
    /// the media type the generated code negotiated: JSON bodies are
    /// JSON-encoded, but an application/x-yaml (or other unencoded text) body is
    /// the document itself and must travel byte-for-byte — JsonConvert on a YAML
    /// string produces a quoted JSON scalar the server would parse as a plain
    /// string instead of a mapping. Mirrors sdk/python/tests/test_request_bodies.py.
    /// </summary>
    public class BodyEncodingTests
    {
        [Fact]
        public void YamlBodyIsSentVerbatim()
        {
            var handler = new CapturingHandler();
            var client = NewClient(handler);
            const string definition = "values:\n  foo: bar\n";

            client.Call(new ApiRequest("POST", "/environments/check")
                .Consumes("application/x-yaml")
                .Body(definition));

            Assert.Equal(Encoding.UTF8.GetBytes(definition), handler.CapturedBody);
            Assert.Equal("application/x-yaml", handler.CapturedContentType);
        }

        [Fact]
        public void JsonBodyIsJsonEncoded()
        {
            var handler = new CapturingHandler();
            var client = NewClient(handler);

            client.Call(new ApiRequest("POST", "/things")
                .Consumes("application/json")
                .Body(new Dictionary<string, string> { ["name"] = "widget" }));

            Assert.Equal("{\"name\":\"widget\"}", Encoding.UTF8.GetString(handler.CapturedBody));
            Assert.StartsWith("application/json", handler.CapturedContentType);
        }

        [Fact]
        public void BinaryBodyIsSentVerbatim()
        {
            var handler = new CapturingHandler();
            var client = NewClient(handler);
            var bytes = new byte[] { 0, 1, (byte)'h', (byte)'i' };

            client.Call(new ApiRequest("POST", "/blobs")
                .Consumes("application/octet-stream")
                .Body(bytes));

            Assert.Equal(bytes, handler.CapturedBody);
            Assert.Equal("application/octet-stream", handler.CapturedContentType);
        }

        [Fact]
        public void BodyDefaultsToJsonWhenNoConsumeIsDeclared()
        {
            var handler = new CapturingHandler();
            var client = NewClient(handler);

            client.Call(new ApiRequest("POST", "/things")
                .Body(new Dictionary<string, int> { ["a"] = 1 }));

            Assert.Equal("{\"a\":1}", Encoding.UTF8.GetString(handler.CapturedBody));
            Assert.StartsWith("application/json", handler.CapturedContentType);
        }

        private static ApiClient NewClient(HttpMessageHandler handler)
        {
            var config = new ApiClientConfiguration
            {
                Host = "https://example.test/api",
                Source = "test-src",
            };
            return new ApiClient(config, handler);
        }

        private sealed class CapturingHandler : HttpMessageHandler
        {
            public byte[] CapturedBody { get; private set; }
            public string CapturedContentType { get; private set; }

            protected override async Task<HttpResponseMessage> SendAsync(
                HttpRequestMessage request, CancellationToken cancellationToken)
            {
                CapturedBody = request.Content == null
                    ? Array.Empty<byte>()
                    : await request.Content.ReadAsByteArrayAsync(cancellationToken);
                CapturedContentType = request.Content?.Headers.ContentType?.ToString();
                return new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent("{}", Encoding.UTF8, "application/json"),
                };
            }
        }
    }
}
