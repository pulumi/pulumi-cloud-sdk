// Copyright 2026, Pulumi Corporation.  All rights reserved.

using Newtonsoft.Json;

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// Shared, pre-configured Newtonsoft.Json settings for the generated SDK.
    ///
    /// <para><see cref="NullValueHandling.Ignore"/> drops unset properties on
    /// serialization (matching the Python/TypeScript reference clients, which omit
    /// unset values on the wire). <c>DateParseHandling.None</c> leaves untyped
    /// JSON (<c>JToken</c> fields) exactly as received — typed
    /// <c>DateTimeOffset</c> properties are still parsed from ISO-8601 by their
    /// declared type. Polymorphic (discriminated-union) models resolve through the
    /// per-type <see cref="PolymorphicConverter"/> attached by the generator, not
    /// through Newtonsoft's <c>$type</c> metadata, which is therefore disabled.</para>
    /// </summary>
    public static class Json
    {
        /// <summary>The one settings instance used for all request/response (de)serialization.</summary>
        public static readonly JsonSerializerSettings Settings = new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Ignore,
            DateFormatHandling = DateFormatHandling.IsoDateFormat,
            DateParseHandling = DateParseHandling.None,
            MetadataPropertyHandling = MetadataPropertyHandling.Ignore,
        };

        /// <summary>A serializer built from <see cref="Settings"/>, for <c>JObject.FromObject</c> calls.</summary>
        public static readonly JsonSerializer Serializer = JsonSerializer.Create(Settings);
    }
}
