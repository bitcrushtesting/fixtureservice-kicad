# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
from conftest import ANALYZE_REPLY
from fixtureservice_kicad.model import format_eur, parse_result


def test_the_reply_becomes_what_the_window_shows():
    r = parse_result("demo.kicad_pcb", ANALYZE_REPLY)
    assert r.total_net_eur == 1234.5
    assert r.lead_time_days == 10
    assert r.valid_until == "2026-12-27"
    assert r.test_points == 42
    assert r.plate_mm == (120.4, 90.2)
    assert [f.severity for f in r.findings] == ["error", "warning", "info"], "errors first, unknown dropped"
    assert r.findings[0].refs == ("TP3", "GND (TP-MINI)")
    assert (r.count("error"), r.count("warning"), r.count("info")) == (1, 1, 1)


def test_a_thin_reply_shows_unknowns_rather_than_failing():
    r = parse_result("x.kicad_pcb", {"quote": None, "plan": [], "analysis": {"findings": "no"}})
    assert r.total_net_eur is None and r.test_points is None and r.plate_mm is None
    assert r.findings == [] and r.valid_until == ""


def test_money_in_both_languages():
    assert format_eur(1234.5) == "€1,234.50"
    assert format_eur(1234.5, "de") == "1.234,50 €"
    assert format_eur(None) == "–"
