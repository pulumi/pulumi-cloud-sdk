// Copyright 2026, Pulumi Corporation.  All rights reserved.

using System;
using System.Reflection;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace Pulumi.Cloud.Sdk
{
    /// <summary>
    /// Names the discriminator property of a discriminated-union hierarchy. Emitted
    /// by the generator on the ROOT of the hierarchy and inherited by every
    /// subtype — the C# analog of Jackson's
    /// <c>@JsonTypeInfo(property = "…")</c>.
    /// </summary>
    [AttributeUsage(AttributeTargets.Class, Inherited = true)]
    public sealed class JsonDiscriminatorAttribute : Attribute
    {
        public string PropertyName { get; }

        public JsonDiscriminatorAttribute(string propertyName)
        {
            PropertyName = propertyName;
        }
    }

    /// <summary>
    /// Registers a candidate concrete subtype on a polymorphic base — the C# analog
    /// of a single <c>@JsonSubTypes.Type</c> entry. The generator emits one per
    /// concrete type in the base's subtree; the wire value for each comes from that
    /// type's <see cref="JsonSubTypeNameAttribute"/>.
    /// </summary>
    [AttributeUsage(AttributeTargets.Class, AllowMultiple = true, Inherited = false)]
    public sealed class JsonSubTypeAttribute : Attribute
    {
        public Type Subtype { get; }

        public JsonSubTypeAttribute(Type subtype)
        {
            Subtype = subtype;
        }
    }

    /// <summary>
    /// The discriminator wire value for a concrete type — the C# analog of Jackson's
    /// <c>@JsonTypeName</c>. Read on deserialization to resolve the type and written
    /// on serialization to emit the discriminator.
    /// </summary>
    [AttributeUsage(AttributeTargets.Class, Inherited = false)]
    public sealed class JsonSubTypeNameAttribute : Attribute
    {
        public string TypeName { get; }

        public JsonSubTypeNameAttribute(string typeName)
        {
            TypeName = typeName;
        }
    }

    /// <summary>
    /// Newtonsoft converter that resolves a discriminated union by reading its
    /// discriminator property (at any position in the object) and mapping the value
    /// to the concrete type registered via <see cref="JsonSubTypeAttribute"/> /
    /// <see cref="JsonSubTypeNameAttribute"/>. On write it emits the discriminator
    /// for the runtime type. It is attached to a hierarchy's root by the generator
    /// and inherited by every subtype.
    ///
    /// <para>Recursion is broken with the canonical per-thread <c>CanRead</c> /
    /// <c>CanWrite</c> toggle: after resolving the concrete type, the converter
    /// suppresses itself for exactly the one nested (de)serialization of that type,
    /// so its own members are handled by the default contract while any polymorphic
    /// fields WITHIN it (including recursive references back to the same union) are
    /// still routed through the converter.</para>
    /// </summary>
    public sealed class PolymorphicConverter : JsonConverter
    {
        [ThreadStatic]
        private static bool _skipRead;

        [ThreadStatic]
        private static bool _skipWrite;

        public override bool CanRead
        {
            get
            {
                if (_skipRead)
                {
                    _skipRead = false;
                    return false;
                }
                return true;
            }
        }

        public override bool CanWrite
        {
            get
            {
                if (_skipWrite)
                {
                    _skipWrite = false;
                    return false;
                }
                return true;
            }
        }

        // Attachment is attribute-scoped (the generator only places this converter on
        // hierarchy types), so it converts whatever it is asked to.
        public override bool CanConvert(Type objectType) => true;

        public override object ReadJson(JsonReader reader, Type objectType, object existingValue, JsonSerializer serializer)
        {
            if (reader.TokenType == JsonToken.Null)
            {
                return null;
            }

            var jo = JObject.Load(reader);

            var target = objectType;
            var discriminator = FindDiscriminatorName(objectType);
            if (discriminator != null)
            {
                var token = jo[discriminator];
                if (token != null)
                {
                    var resolved = ResolveSubType(objectType, token.ToString());
                    if (resolved != null)
                    {
                        target = resolved;
                    }
                }
            }

            _skipRead = true;
            try
            {
                using (var subReader = jo.CreateReader())
                {
                    return serializer.Deserialize(subReader, target);
                }
            }
            finally
            {
                // Defensive: clear in case the nested deserialize never consulted CanRead.
                _skipRead = false;
            }
        }

        public override void WriteJson(JsonWriter writer, object value, JsonSerializer serializer)
        {
            if (value == null)
            {
                writer.WriteNull();
                return;
            }

            var type = value.GetType();

            JObject jo;
            _skipWrite = true;
            try
            {
                jo = JObject.FromObject(value, serializer);
            }
            finally
            {
                _skipWrite = false;
            }

            var discriminator = FindDiscriminatorName(type);
            var nameAttr = type.GetCustomAttribute<JsonSubTypeNameAttribute>(false);
            if (discriminator != null && nameAttr != null)
            {
                jo.Remove(discriminator);
                jo.AddFirst(new JProperty(discriminator, nameAttr.TypeName));
            }

            jo.WriteTo(writer);
        }

        private static string FindDiscriminatorName(Type type)
        {
            for (var t = type; t != null; t = t.BaseType)
            {
                var attr = t.GetCustomAttribute<JsonDiscriminatorAttribute>(false);
                if (attr != null)
                {
                    return attr.PropertyName;
                }
            }
            return null;
        }

        // Resolve a discriminator value to a concrete type within baseType's subtree.
        // The base itself is a candidate when it is a concrete branch type (carries a
        // JsonSubTypeName); the [JsonSubType] entries cover its descendants.
        private static Type ResolveSubType(Type baseType, string value)
        {
            var self = baseType.GetCustomAttribute<JsonSubTypeNameAttribute>(false);
            if (self != null && self.TypeName == value)
            {
                return baseType;
            }

            foreach (var sub in baseType.GetCustomAttributes<JsonSubTypeAttribute>(false))
            {
                var name = sub.Subtype.GetCustomAttribute<JsonSubTypeNameAttribute>(false);
                if (name != null && name.TypeName == value)
                {
                    return sub.Subtype;
                }
            }
            return null;
        }
    }
}
