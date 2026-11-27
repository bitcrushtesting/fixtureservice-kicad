# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from conftest import FakeBoard
from fixtureservice_kicad import board_source
from fixtureservice_kicad.api import Client
from fixtureservice_kicad.session import Session


def test_check_then_one_stored_quote_per_board(service):
    board = FakeBoard()
    s = Session(Client(service.url), lambda: board_source.read_board(board))
    with pytest.raises(RuntimeError):
        s.checkout_url()
    r = s.check()
    assert r.board_name == "demo.kicad_pcb"
    url = s.checkout_url()
    assert s.checkout_url() == url, "a second click reuses the stored quote"
    assert [p for p, _h, _b in service.requests] == ["/api/analyze", "/api/quote"]

    s.check()  # the board changed in KiCad
    s.checkout_url()
    assert [p for p, _h, _b in service.requests][-2:] == ["/api/analyze", "/api/quote"], "a new board, a new quote"
