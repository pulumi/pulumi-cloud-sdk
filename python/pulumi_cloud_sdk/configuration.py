# coding: utf-8

# Copyright 2026, Pulumi Corporation.  All rights reserved.

"""Client configuration for the generated Pulumi Cloud Python SDK."""

from typing import Optional


class Configuration(object):
    """
    Holds the connection settings shared by the generated API classes.

    ``host`` is the API base URL and ``access_token`` is the Pulumi access token
    sent as ``Authorization: token <token>``. A single ``ApiClient`` is cached on
    ``api_client`` so the generated ``*Api`` classes can share one HTTP client.
    """

    def __init__(self) -> None:
        self.host: str = "https://api.pulumi.com"
        self.access_token: Optional[str] = None
        self.api_client = None
