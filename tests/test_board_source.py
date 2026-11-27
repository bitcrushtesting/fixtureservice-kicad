# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from conftest import FakeBoard
from fixtureservice_kicad import board_source, config
from fixtureservice_kicad.board_source import BoardUnavailable


def test_the_open_board_as_text():
    name, data = board_source.read_board(FakeBoard(name="/home/a/proj/main.kicad_pcb"))
    assert name == "main.kicad_pcb"
    assert data.startswith(b"(kicad_pcb")


@pytest.mark.parametrize(
    "raw,expect",
    [("", "board.kicad_pcb"), ("proj", "proj.kicad_pcb"), ("C:\\x\\b.kicad_pcb", "b.kicad_pcb")],
)
def test_file_names(raw, expect):
    assert board_source.file_name_of(FakeBoard(name=raw)) == expect


def test_no_board():
    with pytest.raises(BoardUnavailable, match="No board"):
        board_source.read_board(None)


def test_an_api_failure_is_explained():
    with pytest.raises(BoardUnavailable, match="did not hand over"):
        board_source.read_board(FakeBoard(text=RuntimeError("timeout")))


def test_something_that_is_not_a_board():
    with pytest.raises(BoardUnavailable, match="not a .kicad_pcb"):
        board_source.read_board(FakeBoard(text="(kicad_sch)"))


def test_too_large(monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 5)
    with pytest.raises(BoardUnavailable, match="accepts up to"):
        board_source.read_board(FakeBoard())
