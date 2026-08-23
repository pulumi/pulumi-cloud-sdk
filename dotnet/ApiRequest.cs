// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Runtime.Serialization;

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// Mutable carrier populated fluently by a generated <c>*Api</c> method before
    /// it hands the request to <see cref="ApiClient"/>. Holds the HTTP verb, the
    /// templated resource path (<c>/api/.../{param}</c>), the categorized
    /// parameters, the request body, and the negotiated media types.
    /// </summary>
    public sealed class ApiRequest
    {
        public string Method { get; }
        public string ResourcePath { get; }
        public Dictionary<string, string> PathParams { get; } = new Dictionary<string, string>();
        public Dictionary<string, List<string>> QueryParams { get; } = new Dictionary<string, List<string>>();
        public List<string> ConsumesList { get; } = new List<string>();
        public List<string> ProducesList { get; } = new List<string>();
        public object BodyValue { get; private set; }
        public bool HasBody { get; private set; }

        public ApiRequest(string method, string resourcePath)
        {
            Method = method;
            ResourcePath = resourcePath;
        }

        /// <summary>Bind a <c>{name}</c> path segment. Null values are ignored.</summary>
        public ApiRequest PathParam(string name, object value)
        {
            if (value != null)
            {
                PathParams[name] = Stringify(value);
            }
            return this;
        }

        /// <summary>
        /// Append a query parameter. Null values are dropped; collections and
        /// arrays are emitted as repeated keys (<c>k=a&amp;k=b</c>); booleans render
        /// lowercase, enums via their wire value, and dates as ISO-8601.
        /// </summary>
        public ApiRequest QueryParam(string name, object value)
        {
            if (value == null)
            {
                return this;
            }

            if (value is string s)
            {
                AddQuery(name, s);
            }
            else if (value is IEnumerable e)
            {
                foreach (var item in e)
                {
                    AddQuery(name, Stringify(item));
                }
            }
            else
            {
                AddQuery(name, Stringify(value));
            }
            return this;
        }

        public ApiRequest Body(object body)
        {
            BodyValue = body;
            HasBody = true;
            return this;
        }

        public ApiRequest Consumes(string mediaType)
        {
            ConsumesList.Add(mediaType);
            return this;
        }

        public ApiRequest Produces(string mediaType)
        {
            ProducesList.Add(mediaType);
            return this;
        }

        private void AddQuery(string name, string value)
        {
            if (value == null)
            {
                return;
            }
            if (!QueryParams.TryGetValue(name, out var list))
            {
                list = new List<string>();
                QueryParams[name] = list;
            }
            list.Add(value);
        }

        // Render a scalar value the way the reference clients do: booleans as
        // lowercase literals, DateTimeOffset as ISO-8601, string enums via their
        // [EnumMember] wire value (numeric for int-backed enums), everything else
        // via its invariant string form.
        private static string Stringify(object value)
        {
            switch (value)
            {
                case null:
                    return null;
                case bool b:
                    return b ? "true" : "false";
                case string s:
                    return s;
                case DateTimeOffset dto:
                    return dto.ToString("o", CultureInfo.InvariantCulture);
                case DateTime dt:
                    return dt.ToString("o", CultureInfo.InvariantCulture);
                case Enum e:
                    return EnumWireValue(e);
                default:
                    return Convert.ToString(value, CultureInfo.InvariantCulture);
            }
        }

        private static string EnumWireValue(Enum e)
        {
            var members = e.GetType().GetMember(e.ToString());
            if (members.Length > 0)
            {
                var attr = members[0].GetCustomAttribute<EnumMemberAttribute>();
                if (attr?.Value != null)
                {
                    return attr.Value;
                }
            }
            // int/long-backed enums carry no [EnumMember]; render their numeric value.
            return Convert.ToString(Convert.ToInt64(e), CultureInfo.InvariantCulture);
        }
    }
}
