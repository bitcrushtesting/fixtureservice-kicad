# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""Where the service is, and what the plugin calls itself there."""

from __future__ import annotations

import locale
import os
from typing import Mapping, Optional
from urllib.parse import urlsplit

from . import __version__

PLUGIN_ID = "com.bitcrushtesting.fixture-service"
DEFAULT_BASE_URL = "https://bitcrushtesting.com"

# A developer setting, not a user one: there is deliberately no field in the
# UI that sends a board to another host. Staging and a local `npm run dev`
# (http://localhost:3000/fixture) are reached through this variable.
ENV_BASE_URL = "FIXTURESERVICE_URL"

# The service refuses larger uploads with 413; checking first saves sending
# 25 MB to be told so.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

ANALYZE_TIMEOUT_S = 300
JSON_TIMEOUT_S = 60

USER_AGENT = f"fixtureservice-kicad/{__version__}"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ConfigError(ValueError):
    pass


def base_url(env: Optional[Mapping[str, str]] = None) -> str:
    """The service's base URL, without a trailing slash.

    HTTPS only, except for a service on this machine: a board is a customer's
    design and does not travel in clear text.
    """
    env = os.environ if env is None else env
    raw = (env.get(ENV_BASE_URL) or DEFAULT_BASE_URL).strip().rstrip("/")
    parts = urlsplit(raw)
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ConfigError(f"{ENV_BASE_URL} is not an http(s) URL: {raw!r}")
    if parts.scheme == "http" and parts.hostname not in _LOCAL_HOSTS:
        raise ConfigError(f"{ENV_BASE_URL} must use https unless it is localhost: {raw!r}")
    if parts.query or parts.fragment:
        raise ConfigError(f"{ENV_BASE_URL} must not carry a query or fragment: {raw!r}")
    return raw


def origin_of(url: str) -> str:
    """`scheme://host[:port]`, which the service compares an upload's Origin to."""
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def ui_language(env: Optional[Mapping[str, str]] = None) -> str:
    """`de` or `en`: the two languages the service answers in."""
    env = os.environ if env is None else env
    candidates = [env.get("LC_ALL"), env.get("LC_MESSAGES"), env.get("LANG")]
    try:
        candidates.append(locale.getlocale()[0])
    except ValueError:
        pass
    for c in candidates:
        if c:
            return "de" if c.lower().startswith("de") else "en"
    return "en"
