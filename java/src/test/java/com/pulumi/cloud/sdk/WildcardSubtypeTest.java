// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

// Hand-rolled Jackson-only test for the wildcardSubtype = true `defaultImpl`
// mechanism (see cmd/pulumi-codegen/cmd/java.go emitClassDecl /
// emitWildcardSubtypeModel). Unlike Python/C#, Java has no shared runtime file
// backing this feature -- it's Jackson's native `defaultImpl` -- so this is
// belt-and-suspenders coverage proving the generated shape round-trips through
// the real Json.MAPPER, on top of the codegen-output assertions in
// cmd/pulumi-codegen/cmd/java_test.go.

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.annotation.JsonTypeName;
import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WildcardSubtypeTest {

    @JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "kind", visible = true, defaultImpl = WildcardTestBase.Unknown.class)
    @JsonSubTypes({
            @JsonSubTypes.Type(value = WildcardTestBase.Known.class)
    })
    static class WildcardTestBase {

        @JsonTypeName("known")
        static class Known extends WildcardTestBase {
            public String value;
        }

        static class Unknown extends WildcardTestBase {
            public final String discriminator;
            public final JsonNode raw;

            @JsonCreator(mode = JsonCreator.Mode.DELEGATING)
            Unknown(JsonNode raw) {
                this.raw = raw;
                this.discriminator = raw.hasNonNull("kind") ? raw.get("kind").asText() : null;
            }

            @JsonValue
            public JsonNode toJson() {
                throw new UnsupportedOperationException(
                        "cannot serialize " + getClass().getSimpleName()
                                + ": it captures an unrecognized discriminator value (wildcardSubtype) and is deserialize-only");
            }
        }
    }

    @Test
    void unknownDiscriminatorValueProducesWildcardFallback() throws Exception {
        String json = "{\"kind\":\"mystery\",\"extra\":42}";

        WildcardTestBase parsed = Json.MAPPER.readValue(json, WildcardTestBase.class);

        var unknown = assertInstanceOf(WildcardTestBase.Unknown.class, parsed);
        assertEquals("mystery", unknown.discriminator);
        assertEquals(42, unknown.raw.get("extra").asInt());
    }

    @Test
    void knownDiscriminatorValueStillResolvesNormally() throws Exception {
        String json = "{\"kind\":\"known\",\"value\":\"a\"}";

        WildcardTestBase parsed = Json.MAPPER.readValue(json, WildcardTestBase.class);

        var known = assertInstanceOf(WildcardTestBase.Known.class, parsed);
        assertEquals("a", known.value);
    }

    @Test
    void serializingUnknownFailsLoudlyInsteadOfEmittingWrongShape() throws Exception {
        WildcardTestBase parsed = Json.MAPPER.readValue("{\"kind\":\"mystery\",\"extra\":42}", WildcardTestBase.class);
        var unknown = assertInstanceOf(WildcardTestBase.Unknown.class, parsed);

        var thrown = assertThrows(JsonMappingException.class, () -> Json.MAPPER.writeValueAsString(unknown));
        assertTrue(thrown.getMessage().contains("deserialize-only"), thrown.toString());
    }
}
