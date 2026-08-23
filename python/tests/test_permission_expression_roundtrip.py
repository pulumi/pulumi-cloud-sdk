# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Round-trip tests for the ``PermissionExpression`` polymorphic hierarchy.

``PermissionExpression`` is the most complex generated shape: a recursive,
discriminated composite whose fields are typed against *abstract* intermediates
(``PermissionBooleanExpression``, ``PermissionContextExpression``,
``PermissionLiteralExpression``) while the concrete node type is carried on the
wire in the ``__type`` discriminator. These tests build a deep heterogeneous
tree, serialize it through ``PulumiModelEncoder`` + JSON, deserialize it back,
and assert the reconstructed tree is structurally identical — exercising
discriminator selection, recursion, abstract-field resolution, and primitive
value fidelity.
"""

import json
import sys
import unittest
from pathlib import Path

# Make `import pulumi_cloud_sdk` resolve no matter where the test is invoked
# from, without requiring an editable installation: tests/ -> python/ (the dir that
# contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pulumi_cloud_sdk import models as m  # noqa: E402
# noinspection PyProtectedMember
from pulumi_cloud_sdk._support import default_encoder  # noqa: E402


def build_tree() -> "m.PermissionExpressionAnd":
    """A deep, heterogeneous PermissionExpression tree (~6 levels)."""
    return m.PermissionExpressionAnd(
        left=m.PermissionExpressionEqual(
            left=m.PermissionLiteralExpressionString(value="prod"),
            right=m.PermissionLiteralExpressionString(value="prod"),
        ),
        right=m.PermissionExpressionOr(
            left=m.PermissionExpressionNot(
                node=m.PermissionExpressionHasTag(
                    node=m.PermissionExpressionEqual(
                        # A Tag expression is a general PermissionExpression, so it
                        # is a valid operand of Equal (whose left/right accept any
                        # PermissionExpression). Tag is NOT a context expression.
                        left=m.PermissionExpressionTag(
                            context=m.PermissionExpressionTeam(),
                            key="owner",
                        ),
                        right=m.PermissionLiteralExpressionNumber(value=42.5),
                    ),
                    # HasTag.context requires a PermissionContextExpression subtype
                    # (Environment / InsightsAccount / Stack / Team).
                    context=m.PermissionExpressionTeam(),
                    key="team",
                ),
            ),
            right=m.PermissionExpressionEqual(
                left=m.PermissionLiteralExpressionBool(value=True),
                right=m.PermissionLiteralExpressionBool(value=False),
            ),
        ),
    )


def wire_roundtrip(obj, response_type: str):
    """Serialize -> JSON string -> parse -> deserialize, as over the network."""
    payload = json.dumps(default_encoder.sanitize_for_serialization(obj))
    return default_encoder.deserialize(json.loads(payload), response_type)


class PermissionExpressionRoundTripTest(unittest.TestCase):
    def test_deep_tree_roundtrip_is_identical(self):
        original = build_tree()
        restored = wire_roundtrip(original, "PermissionExpression")

        # Deep structural equality (generated __eq__ compares __dict__ recursively).
        self.assertEqual(original, restored)
        # The root deserialized to the correct concrete subtype.
        self.assertIsInstance(restored, m.PermissionExpressionAnd)

    def test_concrete_types_selected_at_each_level(self):
        restored = wire_roundtrip(build_tree(), "PermissionExpression")

        self.assertIsInstance(restored.left, m.PermissionExpressionEqual)
        self.assertIsInstance(restored.left.left, m.PermissionLiteralExpressionString)
        self.assertIsInstance(restored.right, m.PermissionExpressionOr)

        not_node = restored.right.left
        self.assertIsInstance(not_node, m.PermissionExpressionNot)
        has_tag = not_node.node
        self.assertIsInstance(has_tag, m.PermissionExpressionHasTag)
        self.assertIsInstance(has_tag.context, m.PermissionExpressionTeam)
        self.assertEqual(has_tag.key, "team")

        # Bind each intermediate to a local before drilling deeper: `has_tag.node`
        # is declared as the abstract PermissionBooleanExpression (which has no
        # `left`), so the operand is only reachable after narrowing the local to
        # the concrete PermissionExpressionEqual.
        inner_equal = has_tag.node
        self.assertIsInstance(inner_equal, m.PermissionExpressionEqual)

        tag = inner_equal.left
        self.assertIsInstance(tag, m.PermissionExpressionTag)
        self.assertIsInstance(tag.context, m.PermissionExpressionTeam)
        self.assertEqual(tag.key, "owner")

    def test_wire_shape_carries_discriminator_and_values(self):
        wire = default_encoder.sanitize_for_serialization(build_tree())

        self.assertEqual(wire["__type"], "PermissionExpressionAnd")
        self.assertEqual(wire["left"]["__type"], "PermissionExpressionEqual")
        self.assertEqual(wire["left"]["left"]["__type"], "PermissionLiteralExpressionString")
        self.assertEqual(wire["left"]["left"]["value"], "prod")
        self.assertEqual(wire["right"]["__type"], "PermissionExpressionOr")
        self.assertEqual(
            wire["right"]["left"]["node"]["node"]["left"]["__type"],
            "PermissionExpressionTag",
        )
        self.assertEqual(
            wire["right"]["left"]["node"]["context"]["__type"],
            "PermissionExpressionTeam",
        )

    def test_primitive_value_types_preserved(self):
        restored = wire_roundtrip(build_tree(), "PermissionExpression")

        string_lit = restored.left.left
        number_lit = restored.right.left.node.node.right
        bool_lit_true = restored.right.right.left
        bool_lit_false = restored.right.right.right

        self.assertIsInstance(string_lit.value, str)
        self.assertEqual(string_lit.value, "prod")

        self.assertIsInstance(number_lit.value, float)
        self.assertEqual(number_lit.value, 42.5)

        self.assertIsInstance(bool_lit_true.value, bool)
        self.assertIs(bool_lit_true.value, True)
        self.assertIs(bool_lit_false.value, False)

    def test_deserialize_via_abstract_intermediate(self):
        # A field typed as the abstract PermissionBooleanExpression must still
        # resolve to the concrete subtype via the inherited discriminator.
        original = m.PermissionExpressionOr(
            left=m.PermissionExpressionEqual(
                left=m.PermissionLiteralExpressionString(value="a"),
                right=m.PermissionLiteralExpressionString(value="b"),
            ),
            right=m.PermissionExpressionNot(
                node=m.PermissionExpressionHasTag(key="k"),
            ),
        )
        restored = wire_roundtrip(original, "PermissionBooleanExpression")

        self.assertIsInstance(restored, m.PermissionExpressionOr)
        self.assertEqual(original, restored)

    def test_heterogeneous_list_roundtrip(self):
        items = [
            m.PermissionLiteralExpressionString(value="s"),
            m.PermissionLiteralExpressionNumber(value=7.0),
            m.PermissionExpressionTeam(),
            build_tree(),
        ]
        payload = json.dumps([default_encoder.sanitize_for_serialization(i) for i in items])
        restored = default_encoder.deserialize(json.loads(payload), "list[PermissionExpression]")

        self.assertEqual(len(restored), 4)
        self.assertIsInstance(restored[0], m.PermissionLiteralExpressionString)
        self.assertIsInstance(restored[1], m.PermissionLiteralExpressionNumber)
        self.assertIsInstance(restored[2], m.PermissionExpressionTeam)
        self.assertIsInstance(restored[3], m.PermissionExpressionAnd)
        self.assertEqual(items, restored)

    def test_unknown_discriminator_raises(self):
        with self.assertRaises(ValueError):
            default_encoder.deserialize({"__type": "NoSuchExpression"}, "PermissionExpression")

    def test_empty_leaf_node_roundtrip(self):
        # A concrete node with no own fields still carries its discriminator.
        original = m.PermissionExpressionTeam()
        wire = default_encoder.sanitize_for_serialization(original)
        self.assertEqual(wire, {"__type": "PermissionExpressionTeam"})

        restored = default_encoder.deserialize(wire, "PermissionExpression")
        self.assertIsInstance(restored, m.PermissionExpressionTeam)
        self.assertEqual(original, restored)


if __name__ == "__main__":
    unittest.main()
