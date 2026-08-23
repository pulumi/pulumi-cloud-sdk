// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;
using Pulumi.Cloud.Sdk.Api;
using Pulumi.Cloud.Sdk.Models;
using Xunit;

namespace Pulumi.Cloud.Sdk.Tests
{
    // Live end-to-end test against an unauthenticated Pulumi Cloud route. Mirrors
    // sdk/java .../PublicApiLiveTest.java and the python/nodejs equivalents. A real
    // HTTP status error fails; a connectivity failure (offline) skips so the suite
    // stays green without network. Override the host with PULUMI_API_HOST (base
    // URL, e.g. https://api.staging.pulumi.com).
    public class PublicApiLiveTest
    {
        private static ApiClient Client()
        {
            var config = new ApiClientConfiguration();
            var host = Environment.GetEnvironmentVariable("PULUMI_API_HOST");
            if (!string.IsNullOrEmpty(host))
            {
                config.Host = host;
            }
            return new ApiClient(config);
        }

        [SkippableFact]
        public void VersionReturnsSemver()
        {
            AppCLIVersionResponse response;
            try
            {
                response = new MiscellaneousApi(Client()).Version();
            }
            catch (ApiException e) when (e.StatusCode == 0)
            {
                // StatusCode 0 means a transport failure (offline / DNS); skip so
                // the suite stays green without network. A real HTTP status is a
                // genuine failure and propagates.
                throw new SkipException("Pulumi Cloud not reachable; skipping live test: " + e.Message);
            }

            Assert.NotNull(response);
            Assert.NotNull(response.LatestVersion);
            Assert.Matches(@"^\d+\.\d+\.\d+.*", response.LatestVersion);
        }
    }
}
