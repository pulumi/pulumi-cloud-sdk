// Copyright 2026, Pulumi Corporation.  All rights reserved.

package com.pulumi.cloud.sdk;

// Round-trip tests for the `PermissionExpression` polymorphic hierarchy. Mirrors
// sdk/python/tests/test_permission_expression_roundtrip.py and
// sdk/nodejs/tests/permission_expression.test.js.
//
// `PermissionExpression` is the most complex generated shape: a recursive,
// discriminated composite whose fields are typed against *abstract* intermediates
// (PermissionBooleanExpression) while the concrete node type is carried on the
// wire in the `__type` discriminator. These tests build a deep heterogeneous
// tree, serialize it to JSON and back, and assert the reconstructed tree is
// structurally identical — exercising discriminator selection, recursion,
// abstract-field resolution, and primitive value fidelity.

import com.fasterxml.jackson.databind.exc.InvalidTypeIdException;
import com.pulumi.cloud.sdk.model.PermissionBooleanExpression;
import com.pulumi.cloud.sdk.model.PermissionExpression;
import com.pulumi.cloud.sdk.model.PermissionExpressionAnd;
import com.pulumi.cloud.sdk.model.PermissionExpressionEqual;
import com.pulumi.cloud.sdk.model.PermissionExpressionOr;
import com.pulumi.cloud.sdk.model.PermissionLiteralExpressionBool;
import com.pulumi.cloud.sdk.model.PermissionLiteralExpressionNumber;
import com.pulumi.cloud.sdk.model.PermissionLiteralExpressionString;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PermissionExpressionRoundTripTest {

    private static PermissionLiteralExpressionString str(String v) {
        var e = new PermissionLiteralExpressionString();
        e.value = v;
        return e;
    }

    private static PermissionLiteralExpressionNumber num(double v) {
        var e = new PermissionLiteralExpressionNumber();
        e.value = v;
        return e;
    }

    private static PermissionLiteralExpressionBool bool(boolean v) {
        var e = new PermissionLiteralExpressionBool();
        e.value = v;
        return e;
    }

    private static PermissionExpressionEqual eq(PermissionExpression left, PermissionExpression right) {
        var e = new PermissionExpressionEqual();
        e.left = left;
        e.right = right;
        return e;
    }

    // A deep, heterogeneous PermissionExpression tree, matching the Python/Node
    // `build_tree()` helpers node-for-node in structure.
    private static PermissionExpressionAnd buildTree() {
        var and = new PermissionExpressionAnd();
        and.left = eq(str("prod"), str("prod"));

        var or = new PermissionExpressionOr();
        or.left = eq(num(42.5), num(42.5));
        or.right = eq(bool(true), bool(false));
        and.right = or;
        return and;
    }

    @Test
    void roundTripPreservesConcreteTypesAndValues() throws Exception {
        PermissionExpression original = buildTree();

        String json = Json.MAPPER.writeValueAsString(original);

        // The discriminator is written at each level.
        assertTrue(json.contains("\"__type\":\"PermissionExpressionAnd\""), json);
        assertTrue(json.contains("\"__type\":\"PermissionExpressionOr\""), json);
        assertTrue(json.contains("\"__type\":\"PermissionLiteralExpressionString\""), json);

        PermissionExpression parsed = Json.MAPPER.readValue(json, PermissionExpression.class);

        var and = assertInstanceOf(PermissionExpressionAnd.class, parsed);

        var left = assertInstanceOf(PermissionExpressionEqual.class, and.left);
        assertEquals("prod", assertInstanceOf(PermissionLiteralExpressionString.class, left.left).value);
        assertEquals("prod", assertInstanceOf(PermissionLiteralExpressionString.class, left.right).value);

        var or = assertInstanceOf(PermissionExpressionOr.class, and.right);
        var orLeft = assertInstanceOf(PermissionExpressionEqual.class, or.left);
        assertEquals(42.5, assertInstanceOf(PermissionLiteralExpressionNumber.class, orLeft.left).value);

        var orRight = assertInstanceOf(PermissionExpressionEqual.class, or.right);
        assertTrue(assertInstanceOf(PermissionLiteralExpressionBool.class, orRight.left).value);
        assertEquals(false, assertInstanceOf(PermissionLiteralExpressionBool.class, orRight.right).value);
    }

    @Test
    void heterogeneousListRoundTrips() throws Exception {
        PermissionBooleanExpression a = buildTree();
        PermissionBooleanExpression b = eq(str("a"), str("b"));

        // Serialize with the declared element type (as a List<PermissionExpression>
        // field would), so Jackson writes the polymorphic type ids.
        var listType = Json.MAPPER.getTypeFactory()
                .constructCollectionType(java.util.List.class, PermissionExpression.class);
        String json = Json.MAPPER.writerFor(listType).writeValueAsString(java.util.List.of(a, b));
        java.util.List<PermissionExpression> parsed = Json.MAPPER.readValue(json, listType);

        assertEquals(2, parsed.size());
        assertInstanceOf(PermissionExpressionAnd.class, parsed.get(0));
        assertInstanceOf(PermissionExpressionEqual.class, parsed.get(1));
    }

    @Test
    void unknownDiscriminatorFails() {
        String json = "{\"__type\":\"NoSuchExpression\"}";
        assertThrows(InvalidTypeIdException.class,
                () -> Json.MAPPER.readValue(json, PermissionExpression.class));
    }
}
