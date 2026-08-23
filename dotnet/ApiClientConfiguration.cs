// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// Connection settings shared by every generated <c>*Api</c> class.
    ///
    /// <para><see cref="Host"/> is the API origin (no <c>/api</c> suffix — the
    /// generated resource paths already start with <c>/api/...</c>).
    /// <see cref="AccessToken"/> supplies the Pulumi access token sent as
    /// <c>Authorization: token &lt;token&gt;</c>; it is a delegate so a rotating
    /// token can be re-read per request. Return <c>null</c> for unauthenticated
    /// requests.</para>
    /// </summary>
    public sealed class ApiClientConfiguration
    {
        public string Host { get; set; } = "https://api.pulumi.com";

        public Func<string> AccessToken { get; set; } = () => null;

        public string Source { get; set; } = "pulumi-cloud-sdk";

        public TimeSpan Timeout { get; set; } = TimeSpan.FromSeconds(60);

        /// <summary>Set a static access token (sent as <c>Authorization: token &lt;token&gt;</c>).</summary>
        public ApiClientConfiguration WithAccessToken(string token)
        {
            AccessToken = () => token;
            return this;
        }

        /// <summary>Set a dynamic access-token supplier, re-read on every request.</summary>
        public ApiClientConfiguration WithAccessToken(Func<string> token)
        {
            AccessToken = token ?? (() => null);
            return this;
        }
    }
}
