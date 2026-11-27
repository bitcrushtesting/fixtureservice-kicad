# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""A stand-in for the fixture service, on a real local socket.

Real HTTP rather than a mocked opener, so the multipart body, the headers and
the error handling are what urllib actually sends and reads.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Tuple

import pytest

ANALYZE_REPLY: Dict[str, Any] = {
    "analysis": {
        "findings": [
            {"code": "PS010", "severity": "info", "summary": "Board read", "refs": []},
            {
                "code": "PS025",
                "severity": "error",
                "summary": "Pads too small to probe",
                "detail": "TP3 is 0.6 mm",
                "refs": ["TP3", "GND (TP-MINI)"],
            },
            {"code": "PS046", "severity": "warning", "summary": "Label clash", "refs": ["H1"]},
            {"code": "XX", "severity": "fatal", "summary": "unknown severity is dropped"},
        ],
        "meta": {"file_name": "demo.kicad_pcb"},
    },
    "options": {"face": "bottom"},
    "plan": {"probeCount": {"total": 42}, "plate": {"width": 120.4, "height": 90.2}},
    "quote": {
        "totalNetEur": 1234.5,
        "leadTimeWorkingDays": 10,
        "validUntil": "2026-12-27T00:00:00.000Z",
        "autoQuotable": True,
        "manualReview": [],
    },
    "boardDocument": {"doc": 1},
    "seal": "s3al",
}


class FakeService:
    def __init__(self) -> None:
        self.requests: List[Tuple[str, Dict[str, str], bytes]] = []
        # path -> (status, headers, body) or a callable building one
        self.routes: Dict[str, Callable[[bytes], Tuple[int, Dict[str, str], bytes]]] = {
            "/api/analyze": lambda _b: (200, {}, json.dumps(ANALYZE_REPLY).encode()),
            "/api/quote": lambda _b: (200, {}, json.dumps({"id": "q1", "token": "t/1"}).encode()),
        }
        self.url = ""

    def reply(self, path: str, status: int, body: Any, headers: Dict[str, str] = None) -> None:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.routes[path] = lambda _b: (status, headers or {}, raw)


@pytest.fixture
def service():
    fake = FakeService()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):  # keep pytest output clean
            pass

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            path = self.path.split("?", 1)[0]
            prefix = "/fixture"
            if path.startswith(prefix):
                path = path[len(prefix):]
            fake.requests.append((path, {k.lower(): v for k, v in self.headers.items()}, body))
            route = fake.routes.get(path)
            status, headers, raw = route(body) if route else (404, {}, b'{"message":"Not found"}')
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}/fixture"
    yield fake
    server.shutdown()
    server.server_close()


class FakeText:
    def __init__(self, value: str):
        self.value = value


class FakeField:
    def __init__(self, value: str):
        self.text = FakeText(value)


class FakeFootprint:
    def __init__(self, ref: str):
        self.reference_field = FakeField(ref)

    def __repr__(self) -> str:
        return f"FP({self.reference_field.text.value})"


class FakeBoard:
    def __init__(self, refs=("TP1", "TP3", "U1"), text="(kicad_pcb (version 20240108))", name="demo.kicad_pcb"):
        self.footprints = [FakeFootprint(r) for r in refs]
        self.text = text
        self.name = name
        self.selection: List[Any] = []
        self.cleared = 0

    def get_footprints(self):
        return self.footprints

    def clear_selection(self):
        self.cleared += 1
        self.selection = []

    def add_to_selection(self, items):
        self.selection.extend(items)
        return items

    def get_as_string(self):
        if isinstance(self.text, Exception):
            raise self.text
        return self.text
