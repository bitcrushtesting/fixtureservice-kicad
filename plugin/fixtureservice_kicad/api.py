# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""The fixture service's public HTTP API, as the web page uses it.

Standard library only: the plugin's environment is built by KiCad on the
user's machine, and every dependency is one more thing that can fail to
install there.
"""

from __future__ import annotations

import json
import socket
import ssl
import uuid
from typing import Any, Callable, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from . import config

Opener = Callable[..., Any]

_tls: Optional[ssl.SSLContext] = None


def tls_context() -> ssl.SSLContext:
    """The system's trusted roots, plus Mozilla's from certifi.

    KiCad's bundled Python on macOS (and python.org builds generally) has no
    root certificates of its own, so the default context trusts nothing and
    every HTTPS request fails verification. certifi, installed by KiCad from
    requirements.txt, fills that in. On top of the system store rather than
    instead of it, so a company's own root (an inspecting proxy) still counts
    where the system Python knows it.
    """
    global _tls
    if _tls is None:
        ctx = ssl.create_default_context()
        try:
            import certifi

            ctx.load_verify_locations(cafile=certifi.where())
        except (ImportError, OSError):
            pass
        _tls = ctx
    return _tls


def _urlopen(req: Request, timeout: float) -> Any:
    return urlopen(req, timeout=timeout, context=tls_context())

# The keys of /api/analyze's reply that the plugin reads or hands back.
ANALYZE_KEYS = ("analysis", "options", "plan", "quote", "boardDocument", "seal")


class ServiceError(Exception):
    """A request that did not give a usable answer, worded for the user."""

    def __init__(self, message: str, status: Optional[int] = None, retry_after: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retry_after = retry_after


def _multipart(field: str, file_name: str, data: bytes) -> "tuple[bytes, str]":
    boundary = f"----fixtureservice-kicad-{uuid.uuid4().hex}"
    safe_name = file_name.replace('"', "").replace("\r", "").replace("\n", "") or "board.kicad_pcb"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{safe_name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("ascii")
    return head + data + tail, f"multipart/form-data; boundary={boundary}"


def _error_text(body: bytes) -> str:
    """SvelteKit answers errors as `{"message": …}`; anything else, briefly."""
    try:
        parsed = json.loads(body.decode("utf-8"))
        if isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
            return parsed["message"]
    except (ValueError, UnicodeDecodeError):
        pass
    return body.decode("utf-8", "replace").strip()[:300]


class Client:
    def __init__(
        self,
        base_url: str,
        language: str = "en",
        opener: Opener = _urlopen,
    ):
        self.base_url = base_url.rstrip("/")
        self.language = language
        self._open = opener

    # -- requests ---------------------------------------------------------

    def _headers(self, content_type: Optional[str]) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Accept-Language": self.language,
            "User-Agent": config.USER_AGENT,
            "X-Fixture-Client": config.USER_AGENT,
            # SvelteKit refuses a multipart POST whose Origin is not its own
            # (its CSRF check). A browser sets this; a plain client must.
            "Origin": config.origin_of(self.base_url),
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def _request(self, path: str, body: bytes, content_type: str, timeout: float) -> Dict[str, Any]:
        req = Request(self.base_url + path, data=body, method="POST", headers=self._headers(content_type))
        try:
            with self._open(req, timeout=timeout) as res:
                raw = res.read()
        except HTTPError as err:
            raise self._http_error(err) from None
        except (socket.timeout, TimeoutError):
            raise ServiceError("The fixture service took too long to answer. Please try again.") from None
        except URLError as err:
            if isinstance(err.reason, ssl.SSLCertVerificationError):
                raise ServiceError(
                    "The fixture service's certificate could not be verified, so nothing was sent. "
                    "A network that inspects HTTPS can cause this; try another network, or ask "
                    f"your IT to trust {config.origin_of(self.base_url)}. "
                    f"({getattr(err.reason, 'verify_message', None) or err.reason})"
                ) from None
            raise ServiceError(f"Could not reach the fixture service ({err.reason}).") from None
        try:
            reply = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ServiceError("The fixture service sent an answer this plugin cannot read.") from None
        if not isinstance(reply, dict):
            raise ServiceError("The fixture service sent an answer this plugin cannot read.")
        return reply

    def _http_error(self, err: HTTPError) -> ServiceError:
        try:
            said = _error_text(err.read() or b"")
        except Exception:  # noqa: BLE001 -- a broken error body is still an error
            said = ""
        status = err.code
        if status == 413:
            return ServiceError(said or "The board file is larger than the service accepts.", status)
        if status == 429:
            retry = None
            header = err.headers.get("Retry-After") if err.headers else None
            if header and header.strip().isdigit():
                retry = int(header.strip())
            return ServiceError(said or "Too many requests. Please wait a few minutes.", status, retry)
        if status == 403 and "cross-site" in said.lower():
            return ServiceError("The service refused the upload's origin. Check the service URL.", status)
        if status == 426:
            return ServiceError(said or "This plugin version is too old. Please update it.", status)
        if 400 <= status < 500:
            return ServiceError(said or f"The service refused the request ({status}).", status)
        return ServiceError(
            "The fixture service had a problem with this board. Please try again later"
            + (f" ({said})" if said else "")
            + ".",
            status,
        )

    # -- endpoints --------------------------------------------------------

    def analyze(self, file_name: str, data: bytes) -> Dict[str, Any]:
        """POST /api/analyze: the DFT check and the quote. Nothing is stored."""
        if not data:
            raise ServiceError("The board is empty.")
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise ServiceError(
                f"The board is {len(data) / 2**20:.1f} MB; the service accepts up to "
                f"{config.MAX_UPLOAD_BYTES // 2**20} MB."
            )
        body, content_type = _multipart("board", file_name, data)
        reply = self._request("/api/analyze", body, content_type, config.ANALYZE_TIMEOUT_S)
        missing = [k for k in ANALYZE_KEYS if k not in reply]
        if missing:
            raise ServiceError(
                "The fixture service's answer is missing " + ", ".join(missing) + ". Is the plugin up to date?"
            )
        return reply

    def store_quote(self, analyzed: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST /api/quote: the binding quote, stored, with its access token.

        The analysis goes back exactly as it came, with the seal the service
        put on it; a changed analysis is refused, which is the point.
        """
        payload = {
            "analysis": analyzed["analysis"],
            "options": options if options is not None else analyzed.get("options") or {},
            "boardDocument": analyzed["boardDocument"],
            "seal": analyzed["seal"],
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        reply = self._request("/api/quote", body, "application/json", config.JSON_TIMEOUT_S)
        if not isinstance(reply.get("id"), str) or not isinstance(reply.get("token"), str):
            raise ServiceError("The quote could not be saved. Please try again.")
        return reply

    def checkout_url(self, quote_id: str, token: str) -> str:
        return f"{self.base_url}/checkout?{urlencode({'quote': quote_id, 'token': token})}"
