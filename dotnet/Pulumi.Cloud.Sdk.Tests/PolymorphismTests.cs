// Copyright 2026, Pulumi Corporation.  All rights reserved.

using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Pulumi.Cloud.Sdk.Models;
using Xunit;

namespace Pulumi.Cloud.Sdk.Tests
{
    /// <summary>
    /// Exercises the hand-written <see cref="PolymorphicConverter"/> across the two
    /// shapes it must handle: a flat abstract-root union with recursive fields
    /// (PermissionExpression) and a nested family with a concrete branch-terminal
    /// type (TransferEntity). All cases assert that the discriminator resolves
    /// regardless of its position in the JSON object.
    /// </summary>
    public class PolymorphismTests
    {
        private static T RoundTrip<T>(T value)
        {
            var json = JsonConvert.SerializeObject(value, Json.Settings);
            return JsonConvert.DeserializeObject<T>(json, Json.Settings)!;
        }

        [Fact]
        public void RecursiveUnionRoundTrips()
        {
            PermissionExpression expr = new PermissionExpressionEqual
            {
                Left = new PermissionLiteralExpressionString { Value = "a" },
                Right = new PermissionLiteralExpressionBool { Value = true },
            };

            var json = JsonConvert.SerializeObject(expr, Json.Settings);
            Assert.Contains("\"__type\":\"PermissionExpressionEqual\"", json);
            Assert.Contains("\"__type\":\"PermissionLiteralExpressionString\"", json);

            var back = JsonConvert.DeserializeObject<PermissionExpression>(json, Json.Settings);
            var eq = Assert.IsType<PermissionExpressionEqual>(back);
            // Recursive polymorphic fields must survive the round trip.
            Assert.IsType<PermissionLiteralExpressionString>(eq.Left);
            Assert.IsType<PermissionLiteralExpressionBool>(eq.Right);
            Assert.Equal("a", ((PermissionLiteralExpressionString)eq.Left).Value);
        }

        [Fact]
        public void DiscriminatorResolvesWhenNotFirst()
        {
            // __type appears last at every level; Newtonsoft/Jackson allow this,
            // and the converter must too (unlike System.Text.Json on net8).
            const string json =
                "{\"left\":{\"value\":\"a\",\"__type\":\"PermissionLiteralExpressionString\"}," +
                "\"right\":{\"value\":true,\"__type\":\"PermissionLiteralExpressionBool\"}," +
                "\"__type\":\"PermissionExpressionEqual\"}";

            var back = JsonConvert.DeserializeObject<PermissionExpression>(json, Json.Settings);
            var eq = Assert.IsType<PermissionExpressionEqual>(back);
            Assert.IsType<PermissionLiteralExpressionString>(eq.Left);
            Assert.IsType<PermissionLiteralExpressionBool>(eq.Right);
        }

        [Fact]
        public void NestedFamilyBranchTerminalRoundTrips()
        {
            TransferEntity entity = new TransferEntity.Environment.Rename
            {
                RenameAs = new TransferEntity.Environment
                {
                    ProjectName = "proj",
                    EnvironmentName = "env",
                },
            };

            var json = JsonConvert.SerializeObject(entity, Json.Settings);
            Assert.Contains("\"kind\":\"TransferEntityEnvironmentRename\"", json);
            Assert.Contains("\"kind\":\"TransferEntityEnvironment\"", json);

            var back = JsonConvert.DeserializeObject<TransferEntity>(json, Json.Settings);
            var rename = Assert.IsType<TransferEntity.Environment.Rename>(back);
            // The nested renameAs is typed Environment and the wire value is the
            // branch type itself ("TransferEntityEnvironment") — it must resolve to
            // Environment, not recurse into Rename.
            var inner = Assert.IsType<TransferEntity.Environment>(rename.RenameAs);
            Assert.Equal("proj", inner.ProjectName);
            Assert.Equal("env", inner.EnvironmentName);
        }

        [Fact]
        public void UnsetPropertiesAreOmitted()
        {
            var literal = new PermissionLiteralExpressionString();
            var json = JObject.Parse(JsonConvert.SerializeObject(literal, Json.Settings));
            // value is null -> omitted; only the discriminator remains.
            Assert.False(json.ContainsKey("value"));
            Assert.Equal("PermissionLiteralExpressionString", json["__type"]!.ToString());
        }
    }
}
