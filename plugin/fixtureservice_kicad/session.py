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
        self.result: Optional[Result] = None

    def check(self) -> Result:
        """Read the board as it is now and ask the service about it.

        A re-check is a new upload, not `/api/check`: after an edit in KiCad
        the geometry itself has changed, and only a new read knows it.
        """
        name, data = self._read_board()
        reply = self.client.analyze(name, data)
        self._reply = reply
        self.result = parse_result(name, reply)
        return self.result

    def browser_url(self) -> str:
        """Hand the checked board to the quote page and return its address.

        A new hand-off on every click: one lives only minutes on the service,
        and a click after a coffee should still open the board.
        """
        if self._reply is None:
            raise RuntimeError("check() first")
        return self.client.board_page_url(self.client.hand_off(self._reply))
