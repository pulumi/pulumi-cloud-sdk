# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Tests for the ``_new_empty`` second constructor on ``PulumiAutoModelEncoder``.

``_new_empty`` builds a model instance with every field defaulted — numeric
fields to their zero, everything else to ``None`` — while skipping the
required-argument ``__init__`` and its non-null validation. It backs the
generated ``<field>__safederef`` / ``<field>__autoinit`` accessors, which need to
materialize a placeholder for an unset model-typed field without valid values for
the target model's required properties. These tests pin the default-by-type
matrix, the bypass of required-argument construction, inherited-field and
discriminator handling on polymorphic subtypes, and the underscore-origin field
regression (``$defs`` / ``$ref``).
"""

# The models named here must exist in the *public* OpenAPI spec
# (//specification:openapi_public), which is what the published SDKs are
# generated from — an internal- or admin-only model is not in this package.
import sys
import unittest
from pathlib import Path
from typing import Any

# tests/ -> python/ (the dir that contains the pulumi_cloud_sdk package).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pulumi_cloud_sdk import models as m  # noqa: E402
# noinspection PyProtectedMember
from pulumi_cloud_sdk._support import default_encoder  # noqa: E402


class NewEmptyTest(unittest.TestCase):
    def test_bypasses_required_argument_constructor(self):
        # These models have required properties, so the normal constructor rejects
        # a zero-argument call. _new_empty must still produce an instance. The
        # constructors are called through Any-typed references because the missing
        # arguments are the point of the test, not a type error to surface.
        user_info_ctor: Any = m.UserInfo
        repo_ctor: Any = m.AgentEntityRepository
        with self.assertRaises(TypeError):
            user_info_ctor()
        with self.assertRaises(TypeError):
            repo_ctor()

        self.assertIsInstance(m.UserInfo._new_empty(), m.UserInfo)
        self.assertIsInstance(
            m.AgentEntityRepository._new_empty(),
            m.AgentEntityRepository,
        )

    def test_bypasses_required_field_none_guard(self):
        # A required field's setter raises on None; _new_empty assigns the private
        # backing slot directly, so a required field — model-typed or scalar —
        # defaults to None without tripping the guard, and stays readable.
        pr = m.AgentEntityPR._new_empty()
        self.assertIsNone(pr.repo)  # required, model-typed

        repo = m.AgentEntityRepository._new_empty()
        self.assertIsNone(repo.name)  # required, str
        self.assertIsNone(repo.org)

    def test_default_values_by_type(self):
        # Numeric fields default to their zero; everything else (str, model
        # references, enums, Any) defaults to None.
        token = m.AccessToken._new_empty()
        self.assertEqual(token.last_used, 0)  # int
        self.assertEqual(token.expires, 0)  # int
        self.assertIs(token.admin, False)  # bool
        self.assertIsNone(token.id)  # str
        self.assertIsNone(token.name)  # str
        self.assertIsNone(token.role)  # model reference
        self.assertIsNone(token.type)  # enum

        timeouts = m.AppResCustomTimeouts._new_empty()
        self.assertEqual(timeouts.create, 0.0)  # float
        self.assertEqual(timeouts.read, 0.0)  # float

    def test_underscore_origin_field_names(self):
        # EscSchemaSchema has `defs`/`ref` fields normalized from the JSON `$defs`
        # / `$ref` keys. Their backing slots must be single-underscore (`_defs` /
        # `_ref`); a double underscore would be name-mangled and make _new_empty
        # write the wrong slot, so reading the property would raise AttributeError.
        schema = m.EscSchemaSchema._new_empty()
        self.assertIsNone(schema.defs)
        self.assertIsNone(schema.ref)
        # bool fields on the same model still default to False.
        self.assertIs(schema.unique_items, False)
        self.assertIs(schema.deprecated, False)

    def test_polymorphic_subtype_seeds_inherited_and_discriminator(self):
        # A discriminated concrete subtype seeds its inherited fields and still
        # serializes with the correct wire discriminator (a class attribute).
        node = m.PermissionExpressionAnd._new_empty()
        self.assertIsNone(node.left)  # inherited from PermissionBooleanExpressionBinary
        self.assertIsNone(node.right)

        wire = default_encoder.sanitize_for_serialization(node)
        self.assertEqual(wire["__type"], "PermissionExpressionAnd")

    def test_safederef_uses_new_empty_for_model_field(self):
        # __safederef of a model-typed field builds a defaulted instance of the
        # target type even when that type has required properties.
        pr = m.AgentEntityPR._new_empty()
        repo = pr.repo__safederef
        self.assertIsInstance(repo, m.AgentEntityRepository)
        self.assertIsNone(repo.name)

        # __autoinit stores the materialized value back on the parent.
        materialized = pr.repo__autoinit
        self.assertIs(pr.repo, materialized)


if __name__ == "__main__":
    unittest.main()
