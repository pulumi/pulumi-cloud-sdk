// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Pulumi.Cloud.Sdk.Api;
using Pulumi.Cloud.Sdk.Models;
using Xunit;

namespace Pulumi.Cloud.Sdk.Tests
{
    /// <summary>
    /// Tests for <see cref="ApiClient.CallWithHeaders{T,H}"/>/<see cref="ApiClient.CallWithHeadersOnly{H}"/>
    /// and the generated <c>EnvironmentsApi</c> methods that call them for operations declaring
    /// typed response headers. HTTP is stubbed via the <see cref="HttpMessageHandler"/> test seam
    /// on <see cref="ApiClient"/>, mirroring the Node.js/Python suites' fake-transport pattern for
    /// this same feature.
    /// </summary>
    public class ResponseHeadersTests
    {
        private sealed class StubHandler : HttpMessageHandler
        {
            private readonly HttpStatusCode statusCode;
            private readonly string body;
            private readonly (string Name, string Value)[] headers;

            public StubHandler(HttpStatusCode statusCode, string body, params (string Name, string Value)[] headers)
            {
                this.statusCode = statusCode;
                this.body = body;
                this.headers = headers;
            }

            protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            {
                var response = new HttpResponseMessage(statusCode)
                {
                    Content = new StringContent(body ?? string.Empty),
                };
                foreach (var (name, value) in headers)
                {
                    response.Headers.TryAddWithoutValidation(name, value);
                }
                return Task.FromResult(response);
            }
        }

        private static EnvironmentsApi MakeApi(HttpMessageHandler handler)
        {
            var client = new ApiClient(new ApiClientConfiguration(), handler);
            return new EnvironmentsApi(client);
        }

        [Fact]
        public void BodyOperationParsesResponseAndHeaders()
        {
            var api = MakeApi(new StubHandler(
                HttpStatusCode.OK,
                "{\"diagnostics\":[]}",
                ("ETag", "abc123"),
                ("Pulumi-ESC-Revision", "7")));

            var result = api.UpdateEnvironment_esc_environments("acme", "proj", "env", "values: {}");

            Assert.NotNull(result.Response);
            Assert.Empty(result.Response.Diagnostics);
            Assert.Equal("abc123", result.Headers.ETag);
            Assert.Equal(7L, result.Headers.PulumiESCRevision);
        }

        [Fact]
        public void NoBodyOperationResolvesToJustTheHeaders()
        {
            var api = MakeApi(new StubHandler(
                HttpStatusCode.OK,
                "",
                ("ETag", "head-etag"),
                ("Pulumi-ESC-Revision", "3")));

            var result = api.HeadEnvironment_esc_environments("acme", "proj", "env");

            Assert.Equal("head-etag", result.ETag);
            Assert.Equal(3L, result.PulumiESCRevision);
        }

        [Fact]
        public void MissingHeadersDefaultToTheZeroValue()
        {
            var api = MakeApi(new StubHandler(HttpStatusCode.OK, ""));

            var result = api.HeadEnvironment_esc_environments("acme", "proj", "env");

            Assert.Equal("", result.ETag);
            Assert.Equal(0L, result.PulumiESCRevision);
        }

        [Fact]
        public void MalformedHeaderDefaultsToTheZeroValueRatherThanThrowing()
        {
            // A malformed-but-present header must not fail an otherwise-successful
            // call -- see long.TryParse's use in headerFieldValueExprCSharp.
            var api = MakeApi(new StubHandler(
                HttpStatusCode.OK,
                "",
                ("ETag", "some-etag"),
                ("Pulumi-ESC-Revision", "not-a-number")));

            var result = api.HeadEnvironment_esc_environments("acme", "proj", "env");

            Assert.Equal("some-etag", result.ETag);
            Assert.Equal(0L, result.PulumiESCRevision);
        }
    }
}
