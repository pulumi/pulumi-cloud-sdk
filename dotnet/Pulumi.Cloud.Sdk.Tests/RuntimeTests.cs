// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System.Collections.Generic;
using Pulumi.Cloud.Sdk.Models;
using Xunit;

namespace Pulumi.Cloud.Sdk.Tests
{
    /// <summary>Query-string encoding and enum wire-value rendering.</summary>
    public class RuntimeTests
    {
        [Fact]
        public void QueryParamEncoding()
        {
            var request = new ApiRequest("GET", "/x")
                .QueryParam("list", new List<string> { "a", "b" })
                .QueryParam("flag", true)
                .QueryParam("missing", null)
                .QueryParam("kind", Sensitivity.Sensitive);

            Assert.Equal(new List<string> { "a", "b" }, request.QueryParams["list"]);
            Assert.Equal(new List<string> { "true" }, request.QueryParams["flag"]);
            Assert.False(request.QueryParams.ContainsKey("missing"));
            // String enums render via their [EnumMember] wire value, not the C# name.
            Assert.Equal(new List<string> { "sensitive" }, request.QueryParams["kind"]);
        }

        [Fact]
        public void PathParamNullIgnored()
        {
            var request = new ApiRequest("GET", "/x/{id}")
                .PathParam("id", null);
            Assert.False(request.PathParams.ContainsKey("id"));
        }
    }
}
