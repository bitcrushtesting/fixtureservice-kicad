# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from conftest import FakeBoard
from fixtureservice_kicad import board_source
from fixtureservice_kicad.api import Client
from fixtureservice_kicad.session import Session


def test_check_then_hand_the_board_to_the_browser(service):
    board = FakeBoard()
    s = Session(Client(service.url), lambda: board_source.read_board(board))
    with pytest.raises(RuntimeError):
        s.browser_url()
    r = s.check()
    assert r.board_name == "demo.kicad_pcb"
    url = s.browser_url()
    assert url.startswith(service.url + "/?lang=") and url.endswith("#board=c0de_-x")
    assert "checkout" not in url, "the customer sees the fixture before anything else"
    assert [p for p, _h, _b in service.requests] == ["/api/analyze", "/api/handoff"]

    s.check()  # the board changed in KiCad
    s.browser_url()
    sent = [b for p, _h, b in service.requests if p == "/api/handoff"]
    assert len(sent) == 2, "every click hands off afresh"
