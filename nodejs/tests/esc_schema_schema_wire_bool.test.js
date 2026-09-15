// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Guards EscSchemaSchema's legacy wire shorthand: JSON Schema's bare `true`/`false`
// instead of an object, meaning {always: true} / {never: true} (see
// cmd/pulumi-codegen/cmd/typescript.go emitEscSchemaSchemaFixupWire /
// emitEscSchemaSchemaWireCoercion). Mirrors
// cmd/console2/src/proxy/esc-schema-schema-wire-bool-fixup.spec.ts.

const { test } = require("node:test");
const assert = require("node:assert/strict");

const { Models } = require("../dist/index.js");

test("fixupWire coerces true into {always: true}", () => {
    const schema = Models.EscSchemaSchema.fixupWire(true);

    assert.ok(schema instanceof Models.EscSchemaSchema);
    assert.equal(schema.always, true);
    assert.ok(!schema.never);
});

test("fixupWire coerces false into {never: true}", () => {
    const schema = Models.EscSchemaSchema.fixupWire(false);

    assert.ok(schema instanceof Models.EscSchemaSchema);
    assert.equal(schema.never, true);
    assert.ok(!schema.always);
});

test("fixupWire leaves an already-object schema untouched", () => {
    const schema = Models.EscSchemaSchema.newInstance({ type: "string" });

    assert.equal(Models.EscSchemaSchema.fixupWire(schema), schema);
});

test("coerces a nested boolean schema field (ContextSchema.schema)", () => {
    const ctx = Models.ContextSchema.newInstance({ schema: true });

    assert.ok(ctx.schema instanceof Models.EscSchemaSchema);
    assert.equal(ctx.schema.always, true);
});

test("coerces boolean shorthand array elements, including the falsy `false`", () => {
    const schema = Models.EscSchemaSchema.newInstance({
        anyOf: [true, false, { type: "string" }],
    });

    assert.ok(schema.anyOf[0] instanceof Models.EscSchemaSchema);
    assert.equal(schema.anyOf[0].always, true);
    assert.ok(schema.anyOf[1] instanceof Models.EscSchemaSchema);
    assert.equal(schema.anyOf[1].never, true);
    assert.equal(schema.anyOf[2].type, "string");
});

test("coerces boolean shorthand at a map position (properties)", () => {
    const schema = Models.EscSchemaSchema.newInstance({
        properties: { foo: true, bar: false },
    });

    assert.ok(schema.properties.foo instanceof Models.EscSchemaSchema);
    assert.equal(schema.properties.foo.always, true);
    assert.ok(schema.properties.bar instanceof Models.EscSchemaSchema);
    assert.equal(schema.properties.bar.never, true);
});

test("coerces a boolean shorthand nested two levels deep", () => {
    const schema = Models.EscSchemaSchema.newInstance({
        properties: { foo: { anyOf: [true, { type: "string" }] } },
    });

    const foo = schema.properties.foo;
    assert.ok(foo instanceof Models.EscSchemaSchema);
    assert.ok(foo.anyOf[0] instanceof Models.EscSchemaSchema);
    assert.equal(foo.anyOf[0].always, true);
    assert.equal(foo.anyOf[1].type, "string");
});
