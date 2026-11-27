# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""The results window. Every decision it shows is made elsewhere.

Network calls run on a worker thread and come back through `wx.CallAfter`,
so a 30 second upload never freezes the window.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, List, Optional, Sequence

import wx
import wx.adv

from .api import ServiceError
from .board_source import BoardUnavailable
from .model import Finding, Result, format_eur
from .session import Session

LABEL = {"error": "Error", "warning": "Warning", "info": "Note"}
# The web report's colours, light enough to read black text on.
TINT = {"error": (253, 226, 226), "warning": (254, 240, 199), "info": (224, 236, 255)}


def ask_consent(parent: Optional[wx.Window], text: str) -> bool:
    dlg = wx.MessageDialog(
        parent,
        text,
        "Bitcrush Fixture Service",
        style=wx.OK | wx.CANCEL | wx.ICON_INFORMATION,
    )
    dlg.SetOKCancelLabels("Send the board", "Cancel")
    try:
        return dlg.ShowModal() == wx.ID_OK
    finally:
        dlg.Destroy()


class ResultsFrame(wx.Frame):
    def __init__(
        self,
        session: Session,
        locate: Callable[[Sequence[str]], List[str]],
        open_url: Callable[[str], Any],
        site_url: str,
        language: str = "en",
    ):
        super().__init__(None, title="Bitcrush Fixture Service", size=(760, 620))
        self.session = session
        self.locate = locate
        self.open_url = open_url
        self.language = language
        self.findings: List[Finding] = []
        self._busy = False

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        self.title = wx.StaticText(panel, label="Reading the board…")
        font = self.title.GetFont()
        font.SetPointSize(font.GetPointSize() + 3)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title.SetFont(font)
        root.Add(self.title, 0, wx.ALL, 12)

        self.gauge = wx.Gauge(panel, range=100, size=(-1, 6))
        root.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)

        self.status = wx.StaticText(panel, label="")
        root.Add(self.status, 0, wx.ALL | wx.EXPAND, 12)

        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=24)
        self.values = {}
        for key, label in (
            ("price", "Fixture price, net"),
            ("lead", "Lead time"),
            ("valid", "Price valid until"),
            ("points", "Test points probed"),
            ("plate", "Probe plate"),
        ):
            grid.Add(wx.StaticText(panel, label=label))
            value = wx.StaticText(panel, label="–")
            value.SetFont(value.GetFont().Bold())
            grid.Add(value)
            self.values[key] = value
        root.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.review = wx.StaticText(panel, label="")
        self.review.Hide()
        root.Add(self.review, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 12)

        self.counts = wx.StaticText(panel, label="")
        root.Add(self.counts, 0, wx.ALL, 12)

        self.list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        for i, (name, width) in enumerate((("", 72), ("Code", 70), ("Finding", 420), ("On", 140))):
            self.list.InsertColumn(i, name, width=width)
        root.Add(self.list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)

        # Fixed height, scrolling: a long finding must not push the buttons away.
        self.detail = wx.TextCtrl(
            panel,
            value="Select a finding to show it on the board.",
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE,
            size=(-1, 84),
        )
        root.Add(self.detail, 0, wx.ALL | wx.EXPAND, 12)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        link = wx.adv.HyperlinkCtrl(panel, label="Privacy", url=f"{site_url}/privacy")
        buttons.Add(link, 0, wx.ALIGN_CENTER_VERTICAL)
        buttons.AddStretchSpacer()
        self.recheck = wx.Button(panel, label="Re-check")
        self.order = wx.Button(panel, label="Open in browser")
        close = wx.Button(panel, wx.ID_CLOSE, label="Close")
        for b in (self.recheck, self.order, close):
            buttons.Add(b, 0, wx.LEFT, 8)
        root.Add(buttons, 0, wx.EXPAND | wx.ALL, 12)

        panel.SetSizer(root)
        self.order.Disable()

        self.recheck.Bind(wx.EVT_BUTTON, lambda _e: self.start_check())
        self.order.Bind(wx.EVT_BUTTON, lambda _e: self.start_handoff())
        close.Bind(wx.EVT_BUTTON, lambda _e: self.Close())
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_select)

        self._pulse = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda _e: self.gauge.Pulse(), self._pulse)

    # -- work on a thread ---------------------------------------------------

    def _run(self, work: Callable[[], Any], done: Callable[[Any], None], message: str) -> None:
        if self._busy:
            return
        self._set_busy(True, message)

        def worker() -> None:
            try:
                outcome: Any = work()
            except (ServiceError, BoardUnavailable) as err:
                outcome = err
            except Exception as err:  # noqa: BLE001 -- shown, never swallowed
                outcome = ServiceError(f"Unexpected error: {err}")
            wx.CallAfter(self._finish, done, outcome)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, done: Callable[[Any], None], outcome: Any) -> None:
        if not self:  # the window was closed while the request ran
            return
        self._set_busy(False, "")
        if isinstance(outcome, (ServiceError, BoardUnavailable)):
            text = getattr(outcome, "message", None) or str(outcome)
            retry = getattr(outcome, "retry_after", None)
            if retry:
                text += f" Try again in {max(1, round(retry / 60))} min."
            self.status.SetLabel(text)
            self.status.SetForegroundColour(wx.Colour(180, 30, 30))
            self.Layout()
            return
        self.status.SetForegroundColour(wx.NullColour)
        done(outcome)

    def _set_busy(self, busy: bool, message: str) -> None:
        self._busy = busy
        self.recheck.Enable(not busy)
        self.order.Enable(not busy and self.session.result is not None)
        if busy:
            self.status.SetLabel(message)
            self._pulse.Start(80)
        else:
            self._pulse.Stop()
            self.gauge.SetValue(0)

    # -- the two actions ------------------------------------------------------

    def start_check(self) -> None:
        self._run(self.session.check, self.show, "Checking the board. A large board takes a minute…")

    def start_handoff(self) -> None:
        def opened(url: str) -> None:
            self.open_url(url)
            self.status.SetLabel("The quote is saved and open in your browser.")

        self._run(self.session.checkout_url, opened, "Saving the quote…")

    # -- showing a result ---------------------------------------------------------

    def show(self, result: Result) -> None:
        lang = self.language
        self.title.SetLabel(result.board_name)
        self.values["price"].SetLabel(format_eur(result.total_net_eur, lang))
        self.values["lead"].SetLabel(
            f"{result.lead_time_days} working days" if result.lead_time_days is not None else "–"
        )
        self.values["valid"].SetLabel(result.valid_until or "–")
        self.values["points"].SetLabel(str(result.test_points) if result.test_points is not None else "–")
        self.values["plate"].SetLabel(
            f"{result.plate_mm[0]:.0f} × {result.plate_mm[1]:.0f} mm" if result.plate_mm else "–"
        )
        self.review.SetLabel(
            ""
            if result.auto_quotable
            else "This board needs a look by the shop before the order is confirmed: "
            + "; ".join(result.manual_review)
        )
        self.review.Show(not result.auto_quotable)
        self.counts.SetLabel(
            f"{result.count('error')} errors · {result.count('warning')} warnings · {result.count('info')} notes"
        )

        self.findings = list(result.findings)
        self.list.DeleteAllItems()
        for i, f in enumerate(self.findings):
            row = self.list.InsertItem(i, LABEL[f.severity])
            self.list.SetItem(row, 1, f.code)
            self.list.SetItem(row, 2, f.summary)
            self.list.SetItem(row, 3, ", ".join(f.refs[:6]) + (" …" if len(f.refs) > 6 else ""))
            self.list.SetItemBackgroundColour(row, wx.Colour(*TINT[f.severity]))
            self.list.SetItemTextColour(row, wx.Colour(20, 20, 20))
        self.status.SetLabel(
            "Checked. Fix what you need in KiCad, then Re-check, or open the quote in your browser to order."
        )
        self.order.Enable(True)
        self.Layout()

    def _on_select(self, event: wx.ListEvent) -> None:
        f = self.findings[event.GetIndex()]
        text = f.detail or f.summary
        if not f.refs:
            self.detail.SetValue(text)
            return
        try:
            shown = self.locate(f.refs)
        except Exception as err:  # noqa: BLE001 -- the editor may have closed the board
            shown = []
            text += f"\n(Could not select it in KiCad: {err})"
        if shown:
            text += "\nSelected on the board: " + ", ".join(shown)
        else:
            text += "\nNot a footprint on the board (a fixture part or a pad the editor cannot select)."
        self.detail.SetValue(text)
