# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""Against the real things: the fixture service, and a running KiCad.

Not run by default (see pyproject's addopts). Run them with

    FIXTURESERVICE_URL=http://127.0.0.1:5173 \\
    FIXTURE_TEST_BOARD=/path/to/board.kicad_pcb \\
        pytest -m service

    pytest -m kicad      # KiCad open, IPC API server on, a board in the PCB editor

`-m service` uploads a real board and saves a real quote, so point it at a
development or staging service, never at production.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fixtureservice_kicad import board_source, config, locator
from fixtureservice_kicad.api import Client
from fixtureservice_kicad.model import parse_result
from fixtureservice_kicad.session import Session


def _service_url() -> str:
    url = os.environ.get(config.ENV_BASE_URL)
    if not url:
        pytest.skip(f"{config.ENV_BASE_URL} is not set")
    if url.rstrip("/") == config.PRODUCTION_URL:
        pytest.skip("not against production")
    return config.base_url()


def _board_file() -> Path:
    path = os.environ.get("FIXTURE_TEST_BOARD")
    if not path or not Path(path).is_file():
        pytest.skip("FIXTURE_TEST_BOARD is not set to a .kicad_pcb")
    return Path(path)


@pytest.mark.service
def test_a_real_board_gets_a_quote_and_a_checkout():
    board = _board_file()
    client = Client(_service_url(), "en")
    session = Session(client, lambda: (board.name, board.read_bytes()))
    result = session.check()
    assert result.total_net_eur and result.total_net_eur > 0
    assert result.test_points is not None and result.plate_mm is not None
    url = session.checkout_url()
    assert url.startswith(client.base_url + "/checkout?quote=")


@pytest.mark.service
def test_a_tampered_analysis_is_refused_by_the_real_service():
    board = _board_file()
    client = Client(_service_url(), "en")
    reply = client.analyze(board.name, board.read_bytes())
    reply["seal"] = "0" * len(reply["seal"])
    from fixtureservice_kicad.api import ServiceError

    with pytest.raises(ServiceError) as caught:
        client.store_quote(reply)
    assert caught.value.status in (400, 403, 422)


def _kicad():
    kipy = pytest.importorskip("kipy")
    try:
        kicad = kipy.KiCad(client_name="fixtureservice-kicad-tests", timeout_ms=20000)
        board = kicad.get_board()
    except Exception as err:  # noqa: BLE001
        pytest.skip(f"no KiCad with an open board: {err}")
    return kicad, board


@pytest.mark.kicad
def test_the_open_board_reads_as_a_whole_kicad_pcb():
    _kicad_, board = _kicad()
    name, data = board_source.read_board(board)
    assert name.endswith(".kicad_pcb")
    text = data.decode("utf-8")
    assert text.startswith("(kicad_pcb") and text.rstrip().endswith(")")
    assert text.count("(") == text.count(")"), "a complete s-expression"
    assert "(footprint " in text and "Edge.Cuts" in text


@pytest.mark.kicad
def test_a_footprint_on_the_open_board_is_selected():
    kicad, board = _kicad()
    footprints = list(board.get_footprints())
    if not footprints:
        pytest.skip("the open board has no footprints")
    ref = footprints[0].reference_field.text.value
    try:
        shown = locator.select(board, [ref, "NOT-ON-BOARD"], kicad.run_action)
        assert shown == [ref]
        selected = list(board.get_selection())
        assert len(selected) == 1
    finally:
        board.clear_selection()


@pytest.mark.kicad
@pytest.mark.service
def test_end_to_end_from_the_open_board():
    kicad, _board = _kicad()
    session = Session(Client(_service_url(), "en"), lambda: board_source.read_board(kicad.get_board()))
    result = session.check()
    assert parse_result(result.board_name, session._reply or {}).total_net_eur == result.total_net_eur
