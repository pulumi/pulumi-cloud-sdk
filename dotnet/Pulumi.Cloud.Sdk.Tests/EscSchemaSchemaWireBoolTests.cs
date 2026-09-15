// Copyright 2026, Pulumi Corporation.  All rights reserved.

using Newtonsoft.Json;
using Pulumi.Cloud.Sdk.Models;
using Xunit;

namespace Pulumi.Cloud.Sdk.Tests
{
    /// <summary>
    /// Guards EscSchemaSchema's legacy wire shorthand: JSON Schema's bare <c>true</c>/<c>false</c>
    /// instead of an object, meaning <c>{always: true}</c> / <c>{never: true}</c> (see
    /// cmd/pulumi-codegen/cmd/dotnet.go emitEscSchemaSchemaConverter, wired in via the
    /// class-level <c>[JsonConverter]</c> on the generated <see cref="EscSchemaSchema.Converter"/>).
    /// Mirrors cmd/console2/src/proxy/esc-schema-schema-wire-bool-fixup.spec.ts.
    /// </summary>
    public class EscSchemaSchemaWireBoolTests
    {
        [Fact]
        public void TrueShorthandProducesAlways()
        {
            var schema = JsonConvert.DeserializeObject<EscSchemaSchema>("true", Json.Settings)!;

            Assert.True(schema.Always);
            Assert.False(schema.Never);
        }

        [Fact]
        public void FalseShorthandProducesNever()
        {
            var schema = JsonConvert.DeserializeObject<EscSchemaSchema>("false", Json.Settings)!;

            Assert.True(schema.Never);
            Assert.False(schema.Always);
        }

        [Fact]
        public void OrdinaryObjectStillDeserializesNormally()
        {
            var schema = JsonConvert.DeserializeObject<EscSchemaSchema>("{\"type\":\"string\"}", Json.Settings)!;

            Assert.Equal("string", schema.Type);
            Assert.False(schema.Always);
            Assert.False(schema.Never);
        }

        [Fact]
        public void ShorthandResolvesWhenNestedInsideAnotherModel()
        {
            var ctx = JsonConvert.DeserializeObject<ContextSchema>("{\"schema\":true}", Json.Settings)!;

            Assert.True(ctx.Schema.Always);
        }

        [Fact]
        public void ShorthandResolvesInsideAListElement()
        {
            const string json = "{\"anyOf\":[true,false,{\"type\":\"string\"}]}";

            var schema = JsonConvert.DeserializeObject<EscSchemaSchema>(json, Json.Settings)!;

            Assert.Equal(3, schema.AnyOf.Count);
            Assert.True(schema.AnyOf[0].Always);
            Assert.True(schema.AnyOf[1].Never);
            Assert.Equal("string", schema.AnyOf[2].Type);
        }

        [Fact]
        public void NullResolvesWhenNestedInsideAListElement()
        {
            const string json = "{\"anyOf\":[null,{\"type\":\"string\"}]}";

            var schema = JsonConvert.DeserializeObject<EscSchemaSchema>(json, Json.Settings)!;

            Assert.Equal(2, schema.AnyOf.Count);
            Assert.Null(schema.AnyOf[0]);
            Assert.Equal("string", schema.AnyOf[1].Type);
        }

        [Fact]
        public void NullResolvesWhenNestedInsideADictionaryValue()
        {
            const string json = "{\"properties\":{\"foo\":null}}";

            var schema = JsonConvert.DeserializeObject<EscSchemaSchema>(json, Json.Settings)!;

            Assert.Null(schema.Properties["foo"]);
        }

        [Fact]
        public void OrdinaryObjectStillSerializesAsAnObject()
        {
            var value = new EscSchemaSchema { Type = "string" };

            var json = JsonConvert.SerializeObject(value, Json.Settings);

            Assert.Contains("\"type\":\"string\"", json);
        }
    }
}
