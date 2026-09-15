// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

import com.fasterxml.jackson.annotation.JsonAutoDetect;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.PropertyAccessor;
import com.fasterxml.jackson.databind.BeanDescription;
import com.fasterxml.jackson.databind.DeserializationConfig;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonDeserializer;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.deser.BeanDeserializerModifier;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.pulumi.cloud.sdk.model.EscSchemaSchema;

/**
 * Shared, pre-configured Jackson {@link ObjectMapper} for the generated SDK.
 *
 * <p>The generated model classes expose {@code public} fields with no getters or
 * setters, so field visibility is opened up and getter auto-detection is turned
 * off. {@code NON_NULL} inclusion drops unset fields on serialization (matching
 * the Python/TypeScript reference clients, which omit unset values on the wire),
 * and {@link JavaTimeModule} renders {@link java.time.ZonedDateTime} as ISO-8601
 * strings rather than numeric timestamps.
 */
public final class Json {
    /** The one mapper instance used for all request/response (de)serialization. */
    public static final ObjectMapper MAPPER = JsonMapper.builder()
            .addModule(new JavaTimeModule())
            .addModule(escSchemaSchemaModule())
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS)
            .serializationInclusion(JsonInclude.Include.NON_NULL)
            .visibility(PropertyAccessor.FIELD, JsonAutoDetect.Visibility.ANY)
            .visibility(PropertyAccessor.GETTER, JsonAutoDetect.Visibility.NONE)
            .visibility(PropertyAccessor.IS_GETTER, JsonAutoDetect.Visibility.NONE)
            .build();

    /**
     * Wires {@link EscSchemaSchema.Deserializer} in for every reference to
     * {@code EscSchemaSchema} (a direct field, or an element of a {@code List}/{@code Map}
     * property) — its wire representation may legally be a bare boolean, a legacy JSON Schema
     * shorthand for {@code {always: true}} / {@code {never: true}} instead of an object. This
     * is a one-off fixup for this specific model, not a general mechanism.
     *
     * <p>A {@link BeanDeserializerModifier} is used instead of a class-level
     * {@code @JsonDeserialize} on {@code EscSchemaSchema} itself: {@code modifyDeserializer}
     * hands back the plain bean deserializer Jackson already built for the type, which
     * {@code EscSchemaSchema.Deserializer}'s fallback path (the "normal" object case)
     * delegates to directly. A class-level annotation has no such escape hatch — its own
     * fallback would re-resolve to the same annotated deserializer and recurse forever.
     */
    private static SimpleModule escSchemaSchemaModule() {
        SimpleModule module = new SimpleModule();
        module.setDeserializerModifier(new BeanDeserializerModifier() {
            @Override
            public JsonDeserializer<?> modifyDeserializer(
                    DeserializationConfig config, BeanDescription beanDesc, JsonDeserializer<?> deserializer) {
                if (beanDesc.getBeanClass() == EscSchemaSchema.class) {
                    return new EscSchemaSchema.Deserializer(deserializer);
                }
                return deserializer;
            }
        });
        return module;
    }

    private Json() {}
}
