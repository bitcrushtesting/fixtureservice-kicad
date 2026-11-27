# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wires KiCad, the service and the window together for one run."""

from __future__ import annotations

import webbrowser
from typing import Optional

from . import board_source, config, consent, locator
from .api import Client
from .session import Session


def _settings_dir(kicad) -> Optional[str]:
    try:
        return str(kicad.get_plugin_settings_path(config.PLUGIN_ID))
    except Exception:  # noqa: BLE001 -- older KiCad: the notice just shows each time
        return None


def main() -> int:
    import wx

    from . import ui

    app = wx.App(False)

    try:
        site = config.base_url()
    except config.ConfigError as err:
        wx.MessageBox(str(err), "Bitcrush Fixture Service", wx.OK | wx.ICON_ERROR)
        return 2

    try:
        from kipy import KiCad

        kicad = KiCad(client_name="fixtureservice-kicad", timeout_ms=20000)
        kicad.get_board()
    except Exception as err:  # noqa: BLE001 -- every cause gets the same advice
        wx.MessageBox(
            "Could not reach the open board in KiCad.\n\n"
            "Open a board in the PCB editor, and check that the IPC API server is enabled "
            f"(Preferences → Plugins).\n\n({err})",
            "Bitcrush Fixture Service",
            wx.OK | wx.ICON_ERROR,
        )
        return 1

    settings = _settings_dir(kicad)
    if not consent.given(settings):
        host = config.origin_of(site).split("://", 1)[1]
        if not ui.ask_consent(None, consent.NOTICE.format(host=host)):
            return 0
        consent.remember(settings)

    language = config.ui_language()
    session = Session(Client(site, language), lambda: board_source.read_board(kicad.get_board()))
    frame = ui.ResultsFrame(
        session,
        locate=lambda refs: locator.select(kicad.get_board(), refs, kicad.run_action),
        open_url=webbrowser.open,
        site_url=site,
        language=language,
    )
    frame.Show()
    frame.start_check()
    app.MainLoop()
    return 0
