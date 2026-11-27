# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""One run of the plugin: check the board, then hand it to the browser.

The service's reply lives here, in memory, for as long as the window is
open. Nothing about the board is written to disk.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from .api import Client
from .model import Result, parse_result

BoardReader = Callable[[], Tuple[str, bytes]]


class Session:
    def __init__(self, client: Client, read_board: BoardReader):
        self.client = client
        self._read_board = read_board
        self._reply: Optional[Dict[str, Any]] = None
        self._checkout: Optional[str] = None
        self.result: Optional[Result] = None

    def check(self) -> Result:
        """Read the board as it is now and ask the service about it.

        A re-check is a new upload, not `/api/check`: after an edit in KiCad
        the geometry itself has changed, and only a new read knows it.
        """
        name, data = self._read_board()
        reply = self.client.analyze(name, data)
        self._reply = reply
        self._checkout = None  # a quote stored for the old board is not this one's
        self.result = parse_result(name, reply)
        return self.result

    def checkout_url(self) -> str:
        """Store the quote once and return the browser checkout for it."""
        if self._reply is None:
            raise RuntimeError("check() first")
        if self._checkout is None:
            stored = self.client.store_quote(self._reply)
            self._checkout = self.client.checkout_url(stored["id"], stored["token"])
        return self._checkout
