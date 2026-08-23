// Copyright 2026, Pulumi Corporation.  All rights reserved.

// Round-trip tests for the `PermissionExpression` polymorphic hierarchy.
// Mirrors sdk/python/tests/test_permission_expression_roundtrip.py.
//
// `PermissionExpression` is the most complex generated shape: a recursive,
// discriminated composite whose fields are typed against *abstract*
// intermediates (`PermissionBooleanExpression`, `PermissionContextExpression`,
// `PermissionLiteralExpression`) while the concrete node type is carried on the
// wire in the `__type` discriminator. These tests build a deep heterogeneous
// tree, serialize it to JSON and back, and assert the reconstructed tree is
// structurally identical — exercising discriminator selection, recursion,
// abstract-field resolution, and primitive value fidelity.

const { test } = require("node:test");
const assert = require("node:assert/strict");

const { Models } = require("../dist/index.js");

// A deep, heterogeneous PermissionExpression tree (~6 levels), matching the
// Python `build_tree()` helper node-for-node.
function buildTree() {
    return Models.PermissionExpressionAnd.newInstance({
        left: Models.PermissionExpressionEqual.newInstance({
            left: Models.PermissionLiteralExpressionString.newInstance({ value: "prod" }),
            right: Models.PermissionLiteralExpressionString.newInstance({ value: "prod" }),
        }),
        right: Models.PermissionExpressionOr.newInstance({
            left: Models.PermissionExpressionNot.newInstance({
                node: Models.PermissionExpressionHasTag.newInstance({
                    node: Models.PermissionExpressionEqual.newInstance({
                        left: Models.PermissionLiteralExpressionNumber.newInstance({ value: 42.5 }),
                        right: Models.PermissionLiteralExpressionNumber.newInstance({ value: 42.5 }),
                    }),
                    context: Models.PermissionExpressionTag.newInstance({
                        context: Models.PermissionExpressionTeam.newInstance({}),
                        key: "owner",
                    }),
                    key: "team",
                }),
            }),
            right: Models.PermissionExpressionEqual.newInstance({
                left: Models.PermissionLiteralExpressionBool.newInstance({ value: true }),
                right: Models.PermissionLiteralExpressionBool.newInstance({ value: false }),
            }),
        }),
    });
}

// Serialize -> JSON string -> parse -> deserialize, as over the network.
function wireRoundtrip(obj, baseType) {
    const payload = JSON.stringify(obj);
    return Models[baseType].newInstance(JSON.parse(payload));
}

test("deep tree round-trips to a structurally identical tree", () => {
    const original = buildTree();
    const restored = wireRoundtrip(original, "PermissionExpression");

    // Deep structural equality, including reconstructed prototypes.
    assert.deepStrictEqual(restored, original);
    // The root deserialized to the correct concrete subtype.
    assert.ok(restored instanceof Models.PermissionExpressionAnd);
});

test("concrete types are selected at each level of the tree", () => {
    const restored = wireRoundtrip(buildTree(), "PermissionExpression");

    assert.ok(restored.left instanceof Models.PermissionExpressionEqual);
    assert.ok(restored.left.left instanceof Models.PermissionLiteralExpressionString);
    assert.ok(restored.right instanceof Models.PermissionExpressionOr);

    const notNode = restored.right.left;
    assert.ok(notNode instanceof Models.PermissionExpressionNot);
    const hasTag = notNode.node;
    assert.ok(hasTag instanceof Models.PermissionExpressionHasTag);
    assert.ok(hasTag.node instanceof Models.PermissionExpressionEqual);
    assert.ok(hasTag.context instanceof Models.PermissionExpressionTag);
    assert.ok(hasTag.context.context instanceof Models.PermissionExpressionTeam);
    assert.equal(hasTag.key, "team");
    assert.equal(hasTag.context.key, "owner");
});

test("wire shape carries the discriminator and primitive values", () => {
    const wire = JSON.parse(JSON.stringify(buildTree()));

    assert.equal(wire.__type, "PermissionExpressionAnd");
    assert.equal(wire.left.__type, "PermissionExpressionEqual");
    assert.equal(wire.left.left.__type, "PermissionLiteralExpressionString");
    assert.equal(wire.left.left.value, "prod");
    assert.equal(wire.right.__type, "PermissionExpressionOr");
    assert.equal(wire.right.left.node.context.context.__type, "PermissionExpressionTeam");
});

test("primitive value types are preserved through the round-trip", () => {
    const restored = wireRoundtrip(buildTree(), "PermissionExpression");

    const stringLit = restored.left.left;
    const numberLit = restored.right.left.node.node.left;
    const boolLitTrue = restored.right.right.left;
    const boolLitFalse = restored.right.right.right;

    assert.equal(typeof stringLit.value, "string");
    assert.equal(stringLit.value, "prod");

    assert.equal(typeof numberLit.value, "number");
    assert.equal(numberLit.value, 42.5);

    assert.equal(typeof boolLitTrue.value, "boolean");
    assert.equal(boolLitTrue.value, true);
    assert.equal(boolLitFalse.value, false);
});

test("deserializing through an abstract intermediate resolves the subtype", () => {
    // A tree deserialized through the abstract `PermissionBooleanExpression`
    // base must still resolve to the concrete subtype via the inherited
    // discriminator at every level.
    const original = Models.PermissionExpressionOr.newInstance({
        left: Models.PermissionExpressionEqual.newInstance({
            left: Models.PermissionLiteralExpressionString.newInstance({ value: "a" }),
            right: Models.PermissionLiteralExpressionString.newInstance({ value: "b" }),
        }),
        right: Models.PermissionExpressionNot.newInstance({
            node: Models.PermissionExpressionHasTag.newInstance({ key: "k" }),
        }),
    });
    const restored = wireRoundtrip(original, "PermissionBooleanExpression");

    assert.ok(restored instanceof Models.PermissionExpressionOr);
    assert.deepStrictEqual(restored, original);
});

test("a heterogeneous list of expressions round-trips", () => {
    const items = [
        Models.PermissionLiteralExpressionString.newInstance({ value: "s" }),
        Models.PermissionLiteralExpressionNumber.newInstance({ value: 7 }),
        Models.PermissionExpressionTeam.newInstance({}),
        buildTree(),
    ];
    const payload = JSON.stringify(items);
    const restored = JSON.parse(payload).map((i) => Models.PermissionExpression.newInstance(i));

    assert.equal(restored.length, 4);
    assert.ok(restored[0] instanceof Models.PermissionLiteralExpressionString);
    assert.ok(restored[1] instanceof Models.PermissionLiteralExpressionNumber);
    assert.ok(restored[2] instanceof Models.PermissionExpressionTeam);
    assert.ok(restored[3] instanceof Models.PermissionExpressionAnd);
    assert.deepStrictEqual(restored, items);
});

test("an empty leaf node serializes to just its discriminator", () => {
    // A concrete node with no own fields still carries its discriminator.
    const original = Models.PermissionExpressionTeam.newInstance({});
    const wire = JSON.parse(JSON.stringify(original));
    assert.deepStrictEqual(wire, { __type: "PermissionExpressionTeam" });

    const restored = Models.PermissionExpression.newInstance(wire);
    assert.ok(restored instanceof Models.PermissionExpressionTeam);
    assert.deepStrictEqual(restored, original);
});

test("an unknown discriminator falls back to the base type without throwing", () => {
    // Unlike the Python encoder (which raises on an unknown `__type`), the
    // generated TypeScript `setPrototype` switch has no default case, so an
    // unrecognized discriminator is left as the abstract base rather than
    // rejected. Pin that behavior so a future change is a conscious one.
    let restored;
    assert.doesNotThrow(() => {
        restored = Models.PermissionExpression.newInstance({ __type: "NoSuchExpression" });
    });
    assert.equal(restored.getDiscriminator(), "NoSuchExpression");
    assert.equal(Object.getPrototypeOf(restored), Models.PermissionExpression.prototype);
});
