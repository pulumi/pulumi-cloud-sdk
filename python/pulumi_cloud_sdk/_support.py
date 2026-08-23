# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Hand-written runtime support for the generated Pulumi Cloud Python SDK.

The generated model and API modules under ``models/`` and ``apis/`` are produced
by ``pulumi-codegen generate python`` (``make openapi_python``). Everything in
this module is authored by hand and provides the base classes plus the
``PulumiModelEncoder`` serialize/deserialize engine those generated modules
depend on.

``PulumiModelEncoder`` compiles and caches a dedicated serializer/deserializer
callback per (class, annotation) pair, so repeated serialization of the same
model shape avoids re-walking its type metadata — this is what keeps
serialization fast and correct across the large generated model surface.
"""

import inspect
import re
import sys
import threading
import typing
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pprint import pformat
from types import GenericAlias
from typing import Any, Optional, Type, TypeVar


utcTimezone = timezone(timedelta(), "Z")

# Preserves the caller's concrete type through `_new_empty` (typing.Self is 3.11+;
# the SDK targets 3.10). `SomeModel._new_empty()` is typed as `SomeModel`.
_ModelT = TypeVar("_ModelT", bound="PulumiAutoModelEncoder")

# Lazily-populated map of generated model/enum class name -> class object. Filled
# from the generated `models` package on first deserialization of a named type.
allModels: dict[str, type] = {}


def _resolve_model_class(name: str) -> Optional[type]:
    if not allModels:
        from . import models

        def _is_model(x: Any) -> bool:
            return inspect.isclass(x) and issubclass(x, (PulumiAutoModelEncoder, AutoEnumEncoder))

        for member_name, member in inspect.getmembers(models, _is_model):
            allModels[member_name] = member

    return allModels.get(name)


class AutoEnumEncoder(Enum):
    """Base class for every generated enum; compares and stringifies by value."""

    def __eq__(self, other: Any) -> bool:
        if type(other) is type(self):
            return self is other

        return self.value == other

    def __hash__(self) -> int:
        return self.value.__hash__()

    def __str__(self) -> str:
        return str(self.value)


class PulumiAutoModelEncoder(object):
    """
    Base class for every generated model.

    Subclasses declare ``__swagger_types__`` (attribute name -> type string) and
    ``__attribute_map__`` (attribute name -> wire JSON key). Polymorphic
    subclasses additionally declare ``DISCRIMINATOR`` (the wire field name),
    ``__DISCRIMINATOR_VALUE__`` (this class's discriminator value), and the
    ``fixup_prototype`` / ``_ensure_discriminator_hierarchy`` helpers.
    """

    def __init__(self) -> None:
        klass = type(self)
        state = klass.__dict__.get(PulumiModelEncoder.DEFAULT_STATE)
        if state is None:
            _, _, default_values = PulumiModelEncoder.infer_types_from_annotations(klass)

            for key, val in default_values.items():
                setattr(self, key, val)

            state = self.__dict__.copy()
            setattr(klass, PulumiModelEncoder.DEFAULT_STATE, state)
        else:
            self.__dict__.update(state)

    @classmethod
    def _new_empty(cls: Type[_ModelT]) -> _ModelT:
        """Second constructor: build an instance with every field defaulted
        (numeric fields to their zero, everything else to ``None``), skipping the
        required-argument ``__init__`` and its non-null validation.

        The generated ``<field>__safederef`` / ``<field>__autoinit`` accessors use
        this to materialize a placeholder for an unset model-typed field without
        needing valid values for the target model's required properties. Fields
        are assigned to their private (``_``-prefixed) slots directly so the
        per-property setters — which reject ``None`` on required fields — are
        bypassed. The polymorphic discriminator value is a class attribute and so
        is already present without being seeded here.
        """
        self = cls.__new__(cls)
        swagger_types, _, _ = PulumiModelEncoder.infer_types_from_annotations(cls)
        for attr, attr_type in swagger_types.items():
            if attr.startswith("__"):
                continue  # e.g. the __DISCRIMINATOR_VALUE__ marker; not an instance field.

            if attr_type == "bool":
                value: Any = False
            elif attr_type == "int":
                value = 0
            elif attr_type == "float":
                value = 0.0
            else:
                value = None

            setattr(self, "_" + attr, value)
        return self

    def _to_dict(self) -> dict[str, Any]:
        """Return the model properties as a dict keyed by attribute name."""
        result: dict[str, Any] = {}

        swagger_types, _, _ = PulumiModelEncoder.infer_types_from_annotations(type(self))

        for attr in swagger_types.keys():
            value = getattr(self, attr, None)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x._to_dict() if hasattr(x, "_to_dict") else x,
                    value,
                ))
            elif hasattr(value, "_to_dict"):
                result[attr] = value._to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1]._to_dict()) if hasattr(item[1], "_to_dict") else item,
                    value.items(),
                ))
            else:
                result[attr] = value

        return result

    def to_str(self) -> str:
        return pformat(self._to_dict())

    def __repr__(self) -> str:
        return self.to_str()

    @staticmethod
    def reverse_attribute_lookup(clz: Type, v: str, /) -> str:
        key = PulumiAutoModelEncoder.reverse_attribute_lookup_opt(clz, v)
        if not key:
            raise AttributeError(f"No attribute {v} with class {clz.__qualname__}")

        return key

    @staticmethod
    def reverse_attribute_lookup_opt(clz: Type, v: str, /) -> Optional[str]:
        _, attribute_map, _ = PulumiModelEncoder.infer_types_from_annotations(clz)
        for key, value in attribute_map.items():
            if value == v:
                return key

        return None


class PulumiModelEncoder(object):
    """
    Generic model encoder. Handles JSON encoding/decoding of generated models,
    driven by their ``__swagger_types__`` / ``__attribute_map__`` metadata, with
    a per-(class, annotation) cache of compiled serialize/deserialize callbacks.
    """

    SWAGGER_TYPES = "__swagger_types__"
    ATTRIBUTE_MAP = "__attribute_map__"
    DEFAULT_VALUES = "__default_values__"
    DEFAULT_STATE = "__default_state__"
    SKIP_ATTRIBUTES = "__skip_attributes__"

    PRIMITIVE_TYPES = (float, bool, bytes, str, int)
    PRIMITIVE_TYPES_EXT = (*PRIMITIVE_TYPES, datetime, date, Enum)
    NATIVE_TYPES_MAPPING = {
        "int": int,
        "long": int,
        "float": float,
        "str": str,
        "bool": bool,
        "bytes": bytes,
        "date": date,
        "datetime": datetime,
        "object": object,
        "Any": typing.Any,
        "dict": dict,
        "set": set,
        "list": list,
    }
    SIGNATURE_LOOKUP: dict[Type, inspect.Signature] = {}
    _deserializers: dict[Any, typing.Callable[[Any], Any]] = {}
    _serializers: dict[tuple, typing.Callable[[Any, bool, bool], Any]] = {}
    _lock = threading.RLock()

    def find_first_difference(self, obj1: Any, obj2: Any, /) -> Optional[str]:
        """Compares two objects, making sure they are identical at a deep level."""
        clz1 = type(obj1)
        clz2 = type(obj2)

        if issubclass(clz1, self.PRIMITIVE_TYPES_EXT) or issubclass(clz2, self.PRIMITIVE_TYPES_EXT):
            return None if obj1 == obj2 else f"<left is '{obj1}', right is '{obj2}'>"

        if obj1 is None:
            if obj2 is None:
                return None

            return f"<left is 'None', right is '{clz2.__qualname__}'>"

        if obj2 is None:
            return f"<left is '{clz1.__qualname__}', right is 'None'>"

        if issubclass(clz1, list) and issubclass(clz2, list):
            if len(obj1) != len(obj2):
                return f"<left len = {len(obj1)}, right len = {len(obj2)}>"

            for idx in range(len(obj1)):
                if diff := self.find_first_difference(obj1[idx], obj2[idx]):
                    return f"[{idx}].{diff}"

            return None

        if issubclass(clz1, set) and issubclass(clz2, set):
            for v in obj1:
                if v not in obj2:
                    return f"<left doesn't have {v}>"

            for v in obj2:
                if v not in obj1:
                    return f"<right doesn't have {v}>"

            return None

        if issubclass(clz1, tuple) and issubclass(clz2, tuple):
            if len(obj1) != len(obj2):
                return f"<left len = {len(obj1)}, right len = {len(obj2)}>"

            for idx in range(len(obj1)):
                if diff := self.find_first_difference(obj1[idx], obj2[idx]):
                    return f"({idx}).{diff}"

            return None

        if issubclass(clz1, dict) and issubclass(clz2, dict):
            for k, v in obj1.items():
                if k not in obj2:
                    return f"<right doesn't have {k}>"

                if diff := self.find_first_difference(v, obj2[k]):
                    return f"<{k}>.{diff}"

            for k, v in obj2.items():
                if k not in obj1:
                    return f"<left doesn't have {k}>"

            return None

        swagger_types, attribute_map, _ = PulumiModelEncoder.infer_types_from_annotations(clz1)

        if clz1 != clz2:
            if issubclass(clz1, clz2) or issubclass(clz2, clz1):
                # In case there's a proxy, match the fields.
                swagger_types2, attribute_map2, _ = PulumiModelEncoder.infer_types_from_annotations(clz2)
                if swagger_types != swagger_types2 or attribute_map != attribute_map2:
                    return f"<left is '{clz1.__qualname__}', right is '{clz2.__qualname__}'>"
            else:
                return f"<left is '{clz1.__qualname__}', right is '{clz2.__qualname__}'>"

        for attr in swagger_types.keys():
            v1 = getattr(obj1, attr, None)
            v2 = getattr(obj2, attr, None)

            if diff := self.find_first_difference(v1, v2):
                return f"{attr}.{diff}"

        return None

    def sanitize_for_serialization(
        self,
        obj: Any,
        /,
        *,
        type_annotation: str = None,
        keep_raw_values: bool = False,
        unwrap_enums: bool = False,
    ) -> Any:
        """
        Build a JSON-ready object.

        If obj is None, return None. Primitives pass through; datetime/date become
        ISO strings; lists/sets/tuples/dicts are sanitized element-wise; a model is
        converted to its wire-keyed properties dict.
        """
        if obj is None:
            return None

        klass = type(obj)
        if issubclass(klass, Enum):
            return obj if (keep_raw_values and not unwrap_enums) else obj.value

        key = (klass, type_annotation)

        callback = self._serializers.get(key)
        if callback is None:
            with PulumiModelEncoder._lock:
                callback = self._serializers.get(key)  # Recheck under lock
                if callback is None:
                    callback = self.__generate_serializer(klass, type_annotation or "")
                    self._serializers[key] = callback

        return callback(obj, keep_raw_values, unwrap_enums)

    def __generate_serializer(
        self,
        klass: Any,
        type_annotation: str,
        /,
    ) -> typing.Callable[[Any, bool, bool], Any]:
        if issubclass(klass, (datetime, date)):
            def _serialize_dates(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                if keep_raw_values:
                    return obj

                return obj.isoformat()

            return _serialize_dates

        if issubclass(klass, self.PRIMITIVE_TYPES):
            def _serialize_primitive_passthrough(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                return obj

            return _serialize_primitive_passthrough

        if issubclass(klass, list):
            if type_annotation.startswith("list[") and (match := re.match(r"list\[(.*)]", type_annotation)):
                elem_klass = match.group(1)
                if elem_klass in ["str", "int", "float", "bool", "bytes"]:
                    def _serialize_passthrough_list(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                        return list(obj)

                    return _serialize_passthrough_list

            def _serialize_list(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                results = []

                for val in obj:
                    if val is not None:
                        val_klass = type(val)
                        if issubclass(val_klass, Enum):
                            if not keep_raw_values:
                                val = val.value
                        elif not issubclass(val_klass, self.PRIMITIVE_TYPES):
                            val = self.sanitize_for_serialization(val, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums)

                    results.append(val)

                return results

            return _serialize_list

        if issubclass(klass, set):
            if type_annotation.startswith("set[") and (match := re.match(r"set\[(.*)]", type_annotation)):
                elem_klass = match.group(1)
                if elem_klass in ["str", "int", "float", "bool", "bytes"]:
                    def _serialize_set_primitive(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                        return {str(sub_obj): True for sub_obj in obj}

                    return _serialize_set_primitive

            def _serialize_set(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                return {self.sanitize_for_serialization(sub_obj, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums): True for sub_obj in obj}

            return _serialize_set

        if issubclass(klass, tuple):
            def _serialize_tuple(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                return tuple(self.sanitize_for_serialization(sub_obj, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums) for sub_obj in obj)

            return _serialize_tuple

        if issubclass(klass, dict):
            if type_annotation.startswith("dict[") and (match := re.match(r"dict\[([^,]*), (.*)]", type_annotation)):
                key_klass = match.group(1)
                value_klass = match.group(2)

                if key_klass == "str":
                    if value_klass in ["str", "int", "float", "bool", "bytes"]:
                        def _serialize_passthrough_dict(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                            return dict(obj)

                        return _serialize_passthrough_dict

                    def _serialize_dict_str(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                        obj_dict = {}
                        for key, val in obj.items():
                            if val is not None:
                                val_klass = type(val)
                                if issubclass(val_klass, Enum):
                                    if not keep_raw_values:
                                        val = val.value
                                elif not issubclass(val_klass, self.PRIMITIVE_TYPES):
                                    val = self.sanitize_for_serialization(val, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums)

                            obj_dict[key] = val

                        return obj_dict

                    return _serialize_dict_str

            def _serialize_dict(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
                obj_dict = {}
                for key, val in obj.items():
                    if not isinstance(key, str):
                        key = self.sanitize_for_serialization(key, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums)

                    if val is not None:
                        val_klass = type(val)
                        if issubclass(val_klass, Enum):
                            if unwrap_enums or not keep_raw_values:
                                val = val.value
                        elif not issubclass(val_klass, self.PRIMITIVE_TYPES):
                            val = self.sanitize_for_serialization(val, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums)

                    obj_dict[key] = val

                return obj_dict

            return _serialize_dict

        swagger_types, attribute_map, _ = PulumiModelEncoder.infer_types_from_annotations(klass)

        def _serialize_model(obj: Any, keep_raw_values: bool, unwrap_enums: bool, /) -> Any:
            obj_dict = {}
            for attr, attr_type in swagger_types.items():
                val = getattr(obj, attr, None)
                if val is not None:
                    val_klass = type(val)
                    if issubclass(val_klass, Enum):
                        if unwrap_enums or not keep_raw_values:
                            val = val.value
                    elif not issubclass(val_klass, self.PRIMITIVE_TYPES):
                        val = self.sanitize_for_serialization(val, type_annotation=attr_type, keep_raw_values=keep_raw_values, unwrap_enums=unwrap_enums)

                obj_dict[attribute_map[attr]] = val

            return obj_dict

        return _serialize_model

    def deserialize(self, response: Any, response_type: Any, /) -> Any:
        """
        Deserialize ``response`` into an instance of ``response_type``.

        ``response_type`` may be a class or a type-name string (e.g. 'Stack',
        'list[Stack]', 'dict[str, Stack]').
        """
        return self.__deserialize(response, response_type)

    def __deserialize(self, data: Any, klass: Any, /) -> Any:
        if data is None:
            return None

        callback = self._deserializers.get(klass)
        if callback is None:
            with PulumiModelEncoder._lock:
                callback = self._deserializers.get(klass)  # Recheck under lock
                if callback is None:
                    callback = self.__generate_deserializer(klass)
                    self._deserializers[klass] = callback

        return callback(data)

    def __generate_deserializer(
        self,
        klass: Any,
        /,
    ) -> typing.Callable[[Any], Any]:
        if klass_type := self.NATIVE_TYPES_MAPPING.get(klass):
            klass = klass_type

        elif type(klass) is str:
            if klass.startswith("list[") and (match := re.match(r"list\[(.*)]", klass)):
                return self.__generate_deserializer_for_list(match.group(1))

            if klass.startswith("set[") and (match := re.match(r"set\[(.*)]", klass)):
                return self.__generate_deserializer_for_set(match.group(1))

            if klass.startswith("dict[") and (match := re.match(r"dict\[([^,]*), (.*)]", klass)):
                return self.__generate_deserializer_for_dict(match.group(1), match.group(2))

            klass_resolved = _resolve_model_class(klass)
            if klass_resolved is None:
                klass_pos = klass.rfind(".")
                if klass_pos > 0:
                    try:
                        klass_module = klass[0:klass_pos]
                        klass_name = klass[klass_pos + 1:]
                        klass_resolved = getattr(sys.modules.get(klass_module), klass_name)
                        if klass_resolved:
                            allModels[klass] = klass_resolved
                    except Exception:
                        pass

            klass = klass_resolved

        if klass == dict:
            def _deserialize_raw_dict(data: Any, /) -> Any:
                if not isinstance(data, dict):
                    return None

                return data

            return _deserialize_raw_dict

        if klass == typing.Any:
            def _deserialize_any(data: Any, /) -> Any:
                return deepcopy(data)

            return _deserialize_any

        if klass in self.PRIMITIVE_TYPES:
            def _deserialize_primitive(data: Any, /) -> Any:
                try:
                    return klass(data)
                except TypeError:
                    return data

            return _deserialize_primitive

        if klass and issubclass(klass, Enum):
            lookup = {}
            for e in klass.__members__.values():
                lookup[e.value] = e

            def _deserialize_enum(data: Any, /) -> Any:
                result = lookup.get(data)
                if result is not None:
                    return result

                raise TypeError(f"Invalid value for {klass.__name__}: {data} is not one of {lookup.keys()}")

            return _deserialize_enum

        if klass == object:
            def _deserialize_object(data: Any, /) -> Any:
                return data

            return _deserialize_object

        if klass == date:
            def _deserialize_date(data: Any, /) -> Any:
                if data == "":
                    return None

                if isinstance(data, date):
                    return data

                # date.fromisoformat did not accept a trailing 'Z' until Python
                # 3.11; strip any time/zone suffix so an RFC 3339 date parses on
                # 3.10 with the standard library alone (no dateutil dependency).
                try:
                    return date.fromisoformat(str(data)[:10])
                except ValueError:
                    raise ValueError(f"Failed to parse `{data}` into a date object")

            return _deserialize_date

        if klass == datetime:
            def _deserialize_datetime(data: Any, /) -> Any:
                if data == "":
                    return None

                if isinstance(data, datetime):
                    if not data.tzinfo:
                        data = data.replace(tzinfo=utcTimezone)
                    return data

                # datetime.fromisoformat did not accept a trailing 'Z' until
                # Python 3.11; normalize it so RFC 3339 timestamps parse on 3.10
                # with the standard library alone (no dateutil dependency).
                normalized = data
                if isinstance(normalized, str) and normalized.endswith("Z"):
                    normalized = normalized[:-1] + "+00:00"

                try:
                    return datetime.fromisoformat(normalized)
                except ValueError:
                    raise ValueError(f"Failed to parse `{data}` into a datetime object")

            return _deserialize_datetime

        # Handle generic collections, list[T], set[T], dict[str, T]
        klass_origin: Any = typing.get_origin(klass)
        if klass_origin:
            if issubclass(klass_origin, list):
                return self.__generate_deserializer_for_list(typing.get_args(klass)[0])

            if issubclass(klass_origin, set):
                return self.__generate_deserializer_for_set(typing.get_args(klass)[0])

            if issubclass(klass_origin, dict):
                sub_kls_key = typing.get_args(klass)[0]
                sub_kls_value = typing.get_args(klass)[1]
                return self.__generate_deserializer_for_dict(sub_kls_key, sub_kls_value)

        def _deserialize_model(data: Any, /) -> Any:
            return self.__deserialize_model(data, typing.cast(type, klass))

        return _deserialize_model

    def __generate_deserializer_for_list(
        self,
        klass: Any,
        /,
    ) -> typing.Callable[[Any], Any]:
        if klass_type := self.NATIVE_TYPES_MAPPING.get(klass):
            klass = klass_type

        if klass in self.PRIMITIVE_TYPES:
            def _deserialize_list_primitive(data: Any, /) -> Any:
                if not isinstance(data, list):
                    return None

                return [klass(sub_data) for sub_data in data]

            return _deserialize_list_primitive

        def _deserialize_list(data: Any, /) -> Any:
            if not isinstance(data, list):
                return None

            return [self.__deserialize(sub_data, klass) for sub_data in data]

        return _deserialize_list

    def __generate_deserializer_for_set(
        self,
        klass: Any,
        /,
    ) -> typing.Callable[[Any], Any]:
        if klass_type := self.NATIVE_TYPES_MAPPING.get(klass):
            klass = klass_type

        if klass in self.PRIMITIVE_TYPES:
            def _deserialize_set_primitive(data: Any, /) -> Any:
                if isinstance(data, dict):
                    return {klass(sub_data) for sub_data in data.keys()}

                if isinstance(data, set):
                    return {klass(sub_data) for sub_data in data}

                return None

            return _deserialize_set_primitive

        def _deserialize_set(data: Any, /) -> Any:
            if isinstance(data, dict):
                return set(self.__deserialize(sub_data, klass) for sub_data in data.keys())

            if isinstance(data, set):
                return set(self.__deserialize(sub_data, klass) for sub_data in data)

            return None

        return _deserialize_set

    def __generate_deserializer_for_dict(
        self,
        klass_key: Any,
        klass_value: Any,
        /,
    ) -> typing.Callable[[Any], Any]:
        if klass_key_type := self.NATIVE_TYPES_MAPPING.get(klass_key):
            klass_key = klass_key_type

        if klass_value_type := self.NATIVE_TYPES_MAPPING.get(klass_value):
            klass_value = klass_value_type

        if klass_key == str:
            if klass_value in self.PRIMITIVE_TYPES:
                def _deserialize_dict_str_primitive(data: Any, /) -> Any:
                    if not isinstance(data, dict):
                        return None

                    return {k: klass_value(v) for k, v in data.items()}

                return _deserialize_dict_str_primitive

            def _deserialize_dict_str(data: Any, /) -> Any:
                if not isinstance(data, dict):
                    return None

                return {k: self.__deserialize(v, klass_value) for k, v in data.items()}

            return _deserialize_dict_str

        if klass_value in self.PRIMITIVE_TYPES:
            def _deserialize_dict_primitive(data: Any, /) -> Any:
                if not isinstance(data, dict):
                    return None

                return {self.__deserialize(k, klass_key): klass_value(v) for k, v in data.items()}

            return _deserialize_dict_primitive

        def _deserialize_dict(data: Any, /) -> Any:
            if not isinstance(data, dict):
                return None

            return {self.__deserialize(k, klass_key): self.__deserialize(v, klass_value) for k, v in data.items()}

        return _deserialize_dict

    def __deserialize_model(self, data: Any, klass: type, /) -> Any:
        """Deserialize a dict into a model instance, honoring discriminators."""
        fixup = getattr(klass, "fixup_prototype", None)
        if fixup:
            discriminator_field = getattr(klass, "DISCRIMINATOR", None)
            if discriminator_field and discriminator_field not in data:
                default_value = getattr(klass, "__DISCRIMINATOR_VALUE__")
                klass = fixup(data, default_value)
            else:
                klass = fixup(data)

        if not klass:
            return data

        if not isinstance(data, dict):
            raise TypeError(f"Cannot deserialize values of class {klass.__name__}")

        swagger_types, attribute_map, default_values = PulumiModelEncoder.infer_types_from_annotations(klass)

        args = {}
        extra_args = {}

        constructor_signature = PulumiModelEncoder.SIGNATURE_LOOKUP.get(klass)
        if constructor_signature is None:
            constructor_signature = inspect.signature(klass.__init__)
            PulumiModelEncoder.SIGNATURE_LOOKUP[klass] = constructor_signature

        constructor_parameters = constructor_signature.parameters

        # Precompute keyword arguments, so we can skip them if the input doesn't
        # have that key.
        skip_if_missing = getattr(klass, "__skip_if_missing__", None)
        if skip_if_missing is None:
            skip_if_missing = set()

            for attr in swagger_types.keys():
                sig_param = constructor_parameters.get(attr)
                if sig_param and sig_param.default != inspect.Parameter.empty:
                    skip_if_missing.add(attr)

            setattr(klass, "__skip_if_missing__", skip_if_missing)

        for attr, attr_type in swagger_types.items():
            if attr == "__DISCRIMINATOR_VALUE__":
                continue  # The entry for the discriminator, skip.

            attr_mapped = attribute_map[attr]
            if attr_mapped in data:
                value = data[attr_mapped]
                try:
                    if attr_type == "str":
                        value = str(value) if value is not None else None
                    elif attr_type == "int":
                        value = int(value) if value is not None else 0
                    elif attr_type == "float":
                        value = float(value) if value is not None else 0.0
                    elif attr_type == "bool":
                        value = bool(value) if value is not None else False
                    else:
                        value = self.__deserialize(value, attr_type)
                except Exception as e:
                    raise e.__class__(f"{klass.__name__}:{attr_mapped} -> {str(e)}")
            else:
                if attr in skip_if_missing:
                    continue  # Optional parameter, don't set it.

                value = default_values.get(attr)

            if attr in constructor_parameters:
                args[attr] = value
            else:
                extra_args[attr] = value

        try:
            instance = klass(**args)

            for k, v in extra_args.items():
                setattr(instance, k, v)

            return instance
        except Exception as e:
            raise e.__class__(f"{klass.__name__} -> {str(e)}")

    @staticmethod
    def register_attributes_to_skip(klass: type, *attrs: str) -> None:
        setattr(klass, PulumiModelEncoder.SWAGGER_TYPES, None)
        setattr(klass, PulumiModelEncoder.ATTRIBUTE_MAP, None)
        setattr(klass, PulumiModelEncoder.DEFAULT_VALUES, None)
        setattr(klass, PulumiModelEncoder.DEFAULT_STATE, None)
        setattr(klass, PulumiModelEncoder.SKIP_ATTRIBUTES, set(attrs))

    @staticmethod
    def infer_types_from_annotations(
        klass: type,
        /,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, Any]]:
        klass_dict = klass.__dict__
        swagger_types = klass_dict.get(PulumiModelEncoder.SWAGGER_TYPES)
        attribute_map = klass_dict.get(PulumiModelEncoder.ATTRIBUTE_MAP)
        default_values = klass_dict.get(PulumiModelEncoder.DEFAULT_VALUES)
        if not swagger_types or not attribute_map:
            swagger_types = {}
            attribute_map = {}
            default_values = {}
            seen_annotations = set()

            PulumiModelEncoder._accumulate_types_from_annotations(klass, swagger_types, attribute_map, default_values, seen_annotations)

            setattr(klass, PulumiModelEncoder.SWAGGER_TYPES, swagger_types)
            setattr(klass, PulumiModelEncoder.ATTRIBUTE_MAP, attribute_map)
            setattr(klass, PulumiModelEncoder.DEFAULT_VALUES, default_values)
        elif default_values is None:
            default_values = {}
            setattr(klass, PulumiModelEncoder.DEFAULT_VALUES, default_values)

        return swagger_types, attribute_map, default_values

    @staticmethod
    def _accumulate_types_from_annotations(
        klass: type,
        swagger_types: dict[str, str],
        attribute_map: dict[str, str],
        default_values: dict[str, Any],
        seen_annotations: set,
        /,
    ) -> None:
        for super_klass in klass.__bases__:
            PulumiModelEncoder._accumulate_types_from_annotations(super_klass, swagger_types, attribute_map, default_values, seen_annotations)

        klass_dict = klass.__dict__
        existing_swagger_types = klass_dict.get(PulumiModelEncoder.SWAGGER_TYPES)
        existing_attribute_map = klass_dict.get(PulumiModelEncoder.ATTRIBUTE_MAP)
        existing_default_values = klass_dict.get(PulumiModelEncoder.DEFAULT_VALUES) or {}
        skip_attributes: set = klass_dict.get(PulumiModelEncoder.SKIP_ATTRIBUTES)

        annotations = inspect.get_annotations(klass)

        if existing_swagger_types and existing_attribute_map:
            swagger_types.update(existing_swagger_types)
            attribute_map.update(existing_attribute_map)
            default_values.update(existing_default_values)

            # Annotations are for the whole type hierarchy; track parents' keys.
            seen_annotations.update(annotations.keys())
            return

        for key, val in annotations.items():
            if key in seen_annotations:
                continue

            seen_annotations.add(key)

            if hasattr(klass, key):
                continue  # Class field, skip.

            if skip_attributes and key in skip_attributes:
                continue

            attribute_map[key] = key

            val_effective = val
            if inspect.ismodule(val_effective):
                raise TypeError(f"Cannot use a module for field {key} of {klass.__name__}")

            if typing.get_origin(val_effective) is typing.Union:
                val_args = set(typing.get_args(val_effective))
                val_args.remove(type(None))
                if len(val_args) != 1:
                    raise TypeError(f"Unexpected union typing for field {key} of {klass.__name__}: {val}")

                for val_arg in val_args:
                    val_effective = val_arg
                    break

            if isinstance(val_effective, typing.ForwardRef):
                val_text = val_effective.__forward_arg__
            elif isinstance(val_effective, type) or isinstance(val_effective, GenericAlias):
                val_repr = repr(val_effective)
                val_name = val_effective.__name__
                val_text = val_repr if val_repr.startswith(val_name) else val_name
            elif isinstance(val_effective, str):
                val_text = val_effective
            elif val_effective == typing.Any:
                val_text = "Any"
            else:
                raise TypeError(f"Unexpected typing for field {key} of {klass.__name__}: {val}")

            if val_effective == bool:
                value = False
            elif val_effective == int:
                value = int(0)
            elif val_effective == float:
                value = float(0)
            else:
                value = None

            swagger_types[key] = val_text
            default_values[key] = value


default_encoder = PulumiModelEncoder()
