# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Guards EscSchemaSchema's legacy wire shorthand: JSON Schema's bare ``true``/``false``
instead of an object, meaning ``{always: true}`` / ``{never: true}`` (see
cmd/pulumi-codegen/cmd/python.go emitEscSchemaSchemaFixupWire and _support.py's
PulumiModelEncoder.__deserialize_model, which calls it before treating the payload as
a dict). Mirrors cmd/console2/src/proxy/esc-schema-schema-wire-bool-fixup.spec.ts.
"""

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


class EscSchemaSchemaWireBoolTest(unittest.TestCase):
    def test_true_shorthand_produces_always(self):
        restored = default_encoder.deserialize(True, "EscSchemaSchema")

        self.assertIsInstance(restored, m.EscSchemaSchema)
        self.assertTrue(restored.always)
        self.assertFalse(restored.never)

    def test_false_shorthand_produces_never(self):
        restored = default_encoder.deserialize(False, "EscSchemaSchema")

        self.assertIsInstance(restored, m.EscSchemaSchema)
        self.assertTrue(restored.never)
        self.assertFalse(restored.always)

    def test_ordinary_object_still_deserializes_normally(self):
        restored = default_encoder.deserialize({"type": "string"}, "EscSchemaSchema")

        self.assertEqual(restored.type, "string")
        self.assertFalse(restored.always)
        self.assertFalse(restored.never)

    def test_shorthand_resolves_when_nested_inside_another_model(self):
        restored = default_encoder.deserialize({"schema": True}, "ContextSchema")

        self.assertIsInstance(restored, m.ContextSchema)
        self.assertTrue(restored.schema.always)

    def test_shorthand_resolves_inside_a_list_element(self):
        restored = default_encoder.deserialize({"anyOf": [True, False, {"type": "string"}]}, "EscSchemaSchema")

        self.assertEqual(len(restored.any_of), 3)
        self.assertTrue(restored.any_of[0].always)
        self.assertTrue(restored.any_of[1].never)
        self.assertEqual(restored.any_of[2].type, "string")

    def test_shorthand_resolves_at_a_map_position(self):
        restored = default_encoder.deserialize({"properties": {"foo": True, "bar": False}}, "EscSchemaSchema")

        self.assertTrue(restored.properties["foo"].always)
        self.assertTrue(restored.properties["bar"].never)

    def test_shorthand_resolves_two_levels_deep(self):
        restored = default_encoder.deserialize(
            {"properties": {"foo": {"anyOf": [True, {"type": "string"}]}}}, "EscSchemaSchema"
        )

        foo = restored.properties["foo"]
        self.assertTrue(foo.any_of[0].always)
        self.assertEqual(foo.any_of[1].type, "string")


if __name__ == "__main__":
    unittest.main()
