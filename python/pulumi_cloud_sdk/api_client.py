# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""
Minimal HTTP client for the generated Pulumi Cloud Python SDK.

The generated ``*Api`` classes call :meth:`ApiClient.call_api` with the resource
path, verb, categorized parameters, and the ``response_type`` name. This client
substitutes path parameters, applies auth, serializes the request body, performs
the request with the standard library, and deserializes the response into the
generated model type.
"""

import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ._support import default_encoder
from .configuration import Configuration


def _query_param_value(value: Any) -> str:
    """
    Render a scalar query-parameter value in its wire form.

    Matches the reference clients: booleans become lowercase ``true``/``false``
    (Python's ``str(True)`` would yield ``"True"``, which stricter parsers
    reject), enums serialize to their value, and datetimes to ISO 8601.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _encode_query(query_params: dict) -> str:
    """
    Encode query parameters into a URL query string.

    ``None`` values are dropped; list/tuple/set values are emitted as repeated
    keys (``k=a&k=b``), matching the TypeScript client and gorilla/mux's
    ``Query()[key]`` decoding on the backend.
    """
    pairs: list = []
    for key, value in query_params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            pairs.extend((key, _query_param_value(item)) for item in value)
        else:
            pairs.append((key, _query_param_value(value)))
    return urlencode(pairs)


class ApiClient(object):
    def __init__(self, configuration: Optional[Configuration] = None) -> None:
        self.configuration = configuration or Configuration()
        self.default_headers: dict[str, str] = {}
        self.last_response: Any = None

    def select_header_accept(self, accepts: list[str]) -> Optional[str]:
        if not accepts:
            return None
        return ", ".join(accepts)

    def select_header_content_type(self, content_types: list[str]) -> str:
        if not content_types:
            return "application/json"
        return content_types[0]

    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params: Optional[dict] = None,
        query_params: Optional[dict] = None,
        header_params: Optional[dict] = None,
        body: Any = None,
        post_params: Any = None,
        files: Any = None,
        response_type: Optional[str] = None,
        auth_settings: Optional[list] = None,
        collection_formats: Optional[dict] = None,
        _preload_content: bool = True,
        _request_timeout: Optional[float] = None,
    ) -> Any:
        headers = dict(self.default_headers)
        headers.update(header_params or {})
        if self.configuration.access_token:
            headers["Authorization"] = "token " + self.configuration.access_token

        # Substitute path parameters, then append query parameters.
        path = resource_path
        for key, value in (path_params or {}).items():
            path = path.replace("{" + key + "}", quote(str(value), safe=""))

        url = self.configuration.host.rstrip("/") + path
        if query_params:
            encoded = _encode_query(query_params)
            if encoded:
                url = url + "?" + encoded

        data: Optional[bytes] = None
        if body is not None:
            headers.setdefault("Content-Type", "application/json")
            data = json.dumps(default_encoder.sanitize_for_serialization(body)).encode("utf-8")

        request = Request(url, data=data, headers=headers, method=method)
        with urlopen(request, timeout=_request_timeout) as response:
            raw = response.read()

        self.last_response = raw
        if not _preload_content or not response_type:
            return raw

        # response_type is the wire type-name string (e.g. 'Stack', 'list[Stack]');
        # PulumiModelEncoder resolves it against the generated models package.
        decoded = json.loads(raw) if raw else None
        return default_encoder.deserialize(decoded, response_type)
