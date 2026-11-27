# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
from conftest import FakeBoard
from fixtureservice_kicad import locator


def test_a_reference_may_carry_a_note_or_a_pad():
    assert locator.candidates("GND (TP-MINI)") == ["GND (TP-MINI)", "GND"]
    assert locator.candidates("U3:4") == ["U3:4", "U3"]
    assert locator.candidates("U3.4") == ["U3.4", "U3"]
    assert locator.candidates("TP1") == ["TP1"]


def test_only_what_is_on_the_board_matches_once_each():
    assert locator.match(["TP3", "U1:2", "H1", "TP3", "U1"], ["TP1", "TP3", "U1"]) == ["TP3", "U1"]


def test_select_selects_and_zooms():
    board = FakeBoard()
    actions = []
    shown = locator.select(board, ["U1.1", "P2"], actions.append)
    assert shown == ["U1"]
    assert [fp.reference_field.text.value for fp in board.selection] == ["U1"]
    assert actions == [locator.ZOOM_TO_SELECTION]


def test_nothing_to_select_clears_and_does_not_zoom():
    board = FakeBoard()
    board.selection = ["old"]
    actions = []
    assert locator.select(board, ["H1"], actions.append) == []
    assert board.selection == [] and actions == []


def test_a_kicad_without_the_zoom_action_still_selects():
    def broken(_name):
        raise RuntimeError("no such action")

    board = FakeBoard()
    assert locator.select(board, ["TP1"], broken) == ["TP1"]
