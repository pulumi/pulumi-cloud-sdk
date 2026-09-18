// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

// Hand-rolled Jackson-only test for EscSchemaSchema's legacy bare-boolean wire shorthand
// (JSON Schema's `true`/`false` for {always: true} / {never: true} instead of an object).
// See cmd/pulumi-codegen/cmd/java.go's emitEscSchemaSchemaDeserializer and Json.java's
// BeanDeserializerModifier wiring. Unlike WildcardSubtypeTest's feature, this one isn't
// Jackson-native, so this proves the generated Deserializer + Json.java plumbing actually
// round-trips through the real Json.MAPPER, both directly and nested inside another model.

import com.pulumi.cloud.sdk.model.ContextSchema;
import com.pulumi.cloud.sdk.model.EscSchemaSchema;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class EscSchemaSchemaWireBoolTest {

    @Test
    void trueShorthandProducesAlways() throws Exception {
        EscSchemaSchema parsed = Json.MAPPER.readValue("true", EscSchemaSchema.class);

        assertTrue(parsed.always);
        assertFalse(parsed.never);
    }

    @Test
    void falseShorthandProducesNever() throws Exception {
        EscSchemaSchema parsed = Json.MAPPER.readValue("false", EscSchemaSchema.class);

        assertFalse(parsed.always);
        assertTrue(parsed.never);
    }

    @Test
    void ordinaryObjectStillDeserializesNormally() throws Exception {
        EscSchemaSchema parsed = Json.MAPPER.readValue("{\"type\":\"string\"}", EscSchemaSchema.class);

        assertEquals("string", parsed.type_);
        assertFalse(parsed.always);
        assertFalse(parsed.never);
    }

    @Test
    void shorthandResolvesWhenNestedInsideAnotherModel() throws Exception {
        ContextSchema parsed = Json.MAPPER.readValue("{\"schema\":true}", ContextSchema.class);

        assertTrue(parsed.schema.always);
    }

    @Test
    void shorthandResolvesInsideAListElement() throws Exception {
        String json = "{\"anyOf\":[true,false,{\"type\":\"string\"}]}";

        EscSchemaSchema parsed = Json.MAPPER.readValue(json, EscSchemaSchema.class);

        assertEquals(3, parsed.anyOf.size());
        assertTrue(parsed.anyOf.get(0).always);
        assertTrue(parsed.anyOf.get(1).never);
        assertEquals("string", parsed.anyOf.get(2).type_);
    }

    @Test
    void shorthandResolvesAtAMapPosition() throws Exception {
        String json = "{\"properties\":{\"foo\":true,\"bar\":false}}";

        EscSchemaSchema parsed = Json.MAPPER.readValue(json, EscSchemaSchema.class);

        assertTrue(parsed.properties.get("foo").always);
        assertTrue(parsed.properties.get("bar").never);
    }

    @Test
    void shorthandResolvesTwoLevelsDeep() throws Exception {
        String json = "{\"properties\":{\"foo\":{\"anyOf\":[true,{\"type\":\"string\"}]}}}";

        EscSchemaSchema parsed = Json.MAPPER.readValue(json, EscSchemaSchema.class);

        EscSchemaSchema foo = parsed.properties.get("foo");
        assertTrue(foo.anyOf.get(0).always);
        assertEquals("string", foo.anyOf.get(1).type_);
    }

    @Test
    void ordinaryObjectStillSerializesAsAnObject() throws Exception {
        EscSchemaSchema value = new EscSchemaSchema();
        value.type_ = "string";

        String json = Json.MAPPER.writeValueAsString(value);

        assertTrue(json.contains("\"type\":\"string\""), json);
    }
}
