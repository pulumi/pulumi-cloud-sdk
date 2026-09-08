# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Exercises the shared ``_support.py`` wildcard-subtype fallback path directly,
via hand-rolled root/subtype classes mirroring exactly what the generator
emits (see cmd/pulumi-codegen/cmd/python.go emitWildcardSubtypeClass and
emitDiscriminatorMachinery's fixup_prototype). A real generated fixture isn't
available here: the model that motivated wildcardSubtype = true
(CopilotDirectSkillCall) is ``visibility = Internal`` and never reaches the
public spec's Python generator.
"""

import sys
import unittest
from pathlib import Path

# Make `import pulumi_cloud_sdk` resolve no matter where the test is invoked
# from, without requiring an editable installation: tests/ -> python/ (the dir
# that contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# noinspection PyProtectedMember
from pulumi_cloud_sdk._support import PulumiAutoModelEncoder, default_encoder  # noqa: E402


class WildcardTestModel(PulumiAutoModelEncoder):
    __swagger_types__ = {
        "__DISCRIMINATOR_VALUE__": "str",
    }
    __attribute_map__ = {
        "__DISCRIMINATOR_VALUE__": "kind",
    }

    DISCRIMINATOR = "kind"
    __DISCRIMINATOR_VALUE__ = "WildcardTestModel"

    def __init__(self):
        super().__init__()

    @staticmethod
    def fixup_prototype(data, default_value=None):
        klass_name = getattr(data, "kind", None)
        if not klass_name:
            klass_name = data.get("kind", default_value)

        if klass_name == "known":
            return WildcardTestModelKnown

        return WildcardTestModelUnknown


class WildcardTestModelKnown(WildcardTestModel):
    __swagger_types__ = {
        "value": "str",
        "__DISCRIMINATOR_VALUE__": "str",
    }
    __attribute_map__ = {
        "value": "value",
        "__DISCRIMINATOR_VALUE__": "kind",
    }

    __DISCRIMINATOR_VALUE__ = "known"

    def __init__(self, value=None):
        super().__init__()
        self.value = value


class WildcardTestModelUnknown(WildcardTestModel):
    __WILDCARD_SUBTYPE__ = True

    def __init__(self, discriminator=None, raw=None, **kwargs):
        super().__init__(**kwargs)
        self._discriminator = discriminator
        self._raw = raw

    @property
    def discriminator(self):
        return self._discriminator

    @property
    def raw(self):
        return self._raw


class WildcardSubtypeSupportTest(unittest.TestCase):
    def test_unknown_discriminator_value_produces_wildcard_fallback(self):
        restored = default_encoder.deserialize({"kind": "mystery", "extra": 42}, WildcardTestModel)

        self.assertIsInstance(restored, WildcardTestModelUnknown)
        self.assertEqual(restored.discriminator, "mystery")
        self.assertEqual(restored.raw, {"kind": "mystery", "extra": 42})

    def test_known_discriminator_value_still_resolves_normally(self):
        restored = default_encoder.deserialize({"kind": "known", "value": "a"}, WildcardTestModel)

        self.assertIsInstance(restored, WildcardTestModelKnown)
        self.assertEqual(restored.value, "a")

    def test_serializing_unknown_fails_loudly_instead_of_emitting_wrong_shape(self):
        restored = default_encoder.deserialize({"kind": "mystery", "extra": 42}, WildcardTestModel)

        with self.assertRaises(TypeError) as ctx:
            default_encoder.sanitize_for_serialization(restored)

        self.assertIn("deserialize-only", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
