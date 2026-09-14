// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// HTTP engine for the generated Pulumi Cloud SDK, built on
    /// <see cref="HttpClient"/>. Generated <c>*Api</c> methods build an
    /// <see cref="ApiRequest"/> and hand it to <see cref="Call{T}(ApiRequest)"/>;
    /// this class substitutes path parameters, encodes the query string, applies
    /// authentication and headers, serializes the body, performs the request, and
    /// deserializes the 2xx response into the requested type. Non-2xx responses and
    /// transport/serialization failures surface as <see cref="ApiException"/>.
    ///
    /// <para>The public API is synchronous, mirroring the Java SDK; requests are
    /// dispatched through the async <see cref="HttpClient"/> and awaited.</para>
    /// </summary>
    public sealed class ApiClient
    {
        private readonly ApiClientConfiguration configuration;
        private readonly HttpClient http;

        public ApiClient()
            : this(new ApiClientConfiguration())
        {
        }

        public ApiClient(ApiClientConfiguration configuration)
        {
            this.configuration = configuration;
            this.http = new HttpClient { Timeout = configuration.Timeout };
        }

        /// <summary>
        /// Constructs a client whose transport is the given <see cref="HttpMessageHandler"/>
        /// instead of the default one — a seam for tests to stub responses (including
        /// response headers) without a real network call. Not used by generated code.
        /// </summary>
        public ApiClient(ApiClientConfiguration configuration, HttpMessageHandler handler)
        {
            this.configuration = configuration;
            this.http = new HttpClient(handler) { Timeout = configuration.Timeout };
        }

        public ApiClientConfiguration Configuration => configuration;

        /// <summary>Perform a request whose response body is ignored (void operations).</summary>
        public void Call(ApiRequest request)
        {
            Execute(request, null);
        }

        /// <summary>
        /// Perform a request and deserialize the 2xx response into <typeparamref name="T"/>.
        /// When <typeparamref name="T"/> is <c>byte[]</c> or <c>string</c> the raw body is
        /// returned without JSON parsing; a 204 / empty body returns the default.
        /// </summary>
        public T Call<T>(ApiRequest request)
        {
            var result = Execute(request, typeof(T));
            return result == null ? default : (T)result;
        }

        /// <summary>
        /// Perform a request and return both the deserialized 2xx response body and the
        /// response's headers, converted by <paramref name="parseHeaders"/> — for operations
        /// whose response declares typed response headers. Kept as its own method
        /// (duplicating <see cref="Execute"/>'s body via <see cref="ExecuteWithHeaders"/>)
        /// rather than added as an optional code path on <see cref="Call{T}(ApiRequest)"/>,
        /// so every other generated method's call site is untouched.
        /// </summary>
        public ResponseWithHeaders<T, H> CallWithHeaders<T, H>(ApiRequest request, Func<System.Net.Http.Headers.HttpHeaders, H> parseHeaders)
        {
            var (body, headers) = ExecuteWithHeaders(request, typeof(T));
            return new ResponseWithHeaders<T, H>
            {
                Response = body == null ? default : (T)body,
                Headers = parseHeaders(headers),
            };
        }

        /// <summary>
        /// Perform a request and return just the response's headers, converted by
        /// <paramref name="parseHeaders"/> — for a no-body (e.g. 204) operation that still
        /// carries typed response headers.
        /// </summary>
        public H CallWithHeadersOnly<H>(ApiRequest request, Func<System.Net.Http.Headers.HttpHeaders, H> parseHeaders)
        {
            var (_, headers) = ExecuteWithHeaders(request, null);
            return parseHeaders(headers);
        }

        private object Execute(ApiRequest request, Type responseType)
        {
            var url = BuildUrl(request);

            using var message = new HttpRequestMessage(new HttpMethod(request.Method), url);

            var token = configuration.AccessToken?.Invoke();
            if (!string.IsNullOrEmpty(token))
            {
                message.Headers.TryAddWithoutValidation("Authorization", "token " + token);
            }
            message.Headers.TryAddWithoutValidation("X-Pulumi-Source", configuration.Source);
            message.Headers.TryAddWithoutValidation(
                "Accept",
                request.ProducesList.Count == 0 ? "application/json" : string.Join(", ", request.ProducesList));

            if (request.HasBody)
            {
                var contentType = request.ConsumesList.Count == 0 ? "application/json" : request.ConsumesList[0];
                if (contentType == "application/octet-stream" && request.BodyValue is byte[] bytes)
                {
                    message.Content = new ByteArrayContent(bytes);
                    message.Content.Headers.TryAddWithoutValidation("Content-Type", contentType);
                }
                else
                {
                    var json = JsonConvert.SerializeObject(request.BodyValue, Json.Settings);
                    message.Content = new StringContent(json, Encoding.UTF8, contentType);
                }
            }

            HttpResponseMessage response;
            try
            {
                response = http.SendAsync(message).GetAwaiter().GetResult();
            }
            catch (Exception e)
            {
                throw new ApiException(0, "Request to " + url + " failed: " + e.Message, url, null, null, e);
            }

            using (response)
            {
                var raw = response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult();
                var statusCode = (int)response.StatusCode;

                if (statusCode < 200 || statusCode >= 300)
                {
                    throw BuildError(statusCode, raw, url);
                }

                if (responseType == null || statusCode == 204 || raw == null || raw.Length == 0)
                {
                    return null;
                }

                if (responseType == typeof(byte[]))
                {
                    return raw;
                }

                var text = Encoding.UTF8.GetString(raw);
                if (responseType == typeof(string))
                {
                    return text;
                }

                try
                {
                    return JsonConvert.DeserializeObject(text, responseType, Json.Settings);
                }
                catch (Exception e)
                {
                    throw new ApiException(
                        statusCode,
                        "Failed to deserialize response from " + url + ": " + e.Message,
                        url,
                        null,
                        text,
                        e);
                }
            }
        }

        /// <summary>
        /// Same as <see cref="Execute"/>, but also returns the response's headers
        /// alongside the deserialized body — for operations whose response declares typed
        /// response headers.
        /// </summary>
        private (object Body, System.Net.Http.Headers.HttpHeaders Headers) ExecuteWithHeaders(ApiRequest request, Type responseType)
        {
            var url = BuildUrl(request);

            using var message = new HttpRequestMessage(new HttpMethod(request.Method), url);

            var token = configuration.AccessToken?.Invoke();
            if (!string.IsNullOrEmpty(token))
            {
                message.Headers.TryAddWithoutValidation("Authorization", "token " + token);
            }
            message.Headers.TryAddWithoutValidation("X-Pulumi-Source", configuration.Source);
            message.Headers.TryAddWithoutValidation(
                "Accept",
                request.ProducesList.Count == 0 ? "application/json" : string.Join(", ", request.ProducesList));

            if (request.HasBody)
            {
                var contentType = request.ConsumesList.Count == 0 ? "application/json" : request.ConsumesList[0];
                if (contentType == "application/octet-stream" && request.BodyValue is byte[] bytes)
                {
                    message.Content = new ByteArrayContent(bytes);
                    message.Content.Headers.TryAddWithoutValidation("Content-Type", contentType);
                }
                else
                {
                    var json = JsonConvert.SerializeObject(request.BodyValue, Json.Settings);
                    message.Content = new StringContent(json, Encoding.UTF8, contentType);
                }
            }

            HttpResponseMessage response;
            try
            {
                response = http.SendAsync(message).GetAwaiter().GetResult();
            }
            catch (Exception e)
            {
                throw new ApiException(0, "Request to " + url + " failed: " + e.Message, url, null, null, e);
            }

            using (response)
            {
                var raw = response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult();
                var statusCode = (int)response.StatusCode;
                var headers = response.Headers;

                if (statusCode < 200 || statusCode >= 300)
                {
                    throw BuildError(statusCode, raw, url);
                }

                if (responseType == null || statusCode == 204 || raw == null || raw.Length == 0)
                {
                    return (null, headers);
                }

                if (responseType == typeof(byte[]))
                {
                    return (raw, headers);
                }

                var text = Encoding.UTF8.GetString(raw);
                if (responseType == typeof(string))
                {
                    return (text, headers);
                }

                try
                {
                    return (JsonConvert.DeserializeObject(text, responseType, Json.Settings), headers);
                }
                catch (Exception e)
                {
                    throw new ApiException(
                        statusCode,
                        "Failed to deserialize response from " + url + ": " + e.Message,
                        url,
                        null,
                        text,
                        e);
                }
            }
        }

        private string BuildUrl(ApiRequest request)
        {
            var path = request.ResourcePath;
            foreach (var entry in request.PathParams)
            {
                // Uri.EscapeDataString encodes spaces as %20 and encodes '/',
                // matching the reference clients' quote(value, safe="").
                path = path.Replace("{" + entry.Key + "}", Uri.EscapeDataString(entry.Value));
            }

            var host = (configuration.Host ?? string.Empty).TrimEnd('/');
            var url = new StringBuilder(host).Append(path);
            var query = EncodeQuery(request.QueryParams);
            if (query.Length > 0)
            {
                url.Append('?').Append(query);
            }
            return url.ToString();
        }

        private static string EncodeQuery(Dictionary<string, List<string>> parameters)
        {
            var sb = new StringBuilder();
            foreach (var entry in parameters)
            {
                var key = Uri.EscapeDataString(entry.Key);
                foreach (var value in entry.Value)
                {
                    if (sb.Length > 0)
                    {
                        sb.Append('&');
                    }
                    sb.Append(key).Append('=').Append(Uri.EscapeDataString(value));
                }
            }
            return sb.ToString();
        }

        private static ApiException BuildError(int statusCode, byte[] raw, string url)
        {
            var rawBody = raw == null || raw.Length == 0 ? null : Encoding.UTF8.GetString(raw);
            JToken parsed = null;
            string message = null;
            if (rawBody != null)
            {
                try
                {
                    parsed = JToken.Parse(rawBody);
                    var m = parsed?["message"];
                    if (m != null && m.Type != JTokenType.Null)
                    {
                        message = m.ToString();
                    }
                }
                catch (JsonException)
                {
                    // Body was not JSON; fall back to the raw text below.
                }
            }
            message ??= rawBody ?? ("HTTP " + statusCode);
            return new ApiException(statusCode, "API error " + statusCode + ": " + message, url, parsed, rawBody, null);
        }
    }

    /// <summary>
    /// A single-value accessor for <see cref="System.Net.Http.Headers.HttpHeaders"/>, which
    /// (unlike Angular's <c>HttpHeaders</c>, the DOM's <c>Headers</c>, or Python's
    /// <c>http.client.HTTPMessage</c>) exposes only <c>TryGetValues</c> (multi-valued). Used
    /// by generated <c>parseHeaders</c> lambdas for operations declaring response headers.
    /// </summary>
    internal static class HttpHeadersExtensions
    {
        public static string GetFirstOrDefault(this System.Net.Http.Headers.HttpHeaders headers, string name)
        {
            if (headers.TryGetValues(name, out var values))
            {
                foreach (var value in values)
                {
                    return value;
                }
            }
            return null;
        }
    }
}
