# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
from fixtureservice_kicad import consent


def test_asked_once_then_remembered(tmp_path):
    folder = str(tmp_path / "settings")
    assert not consent.given(folder)
    consent.remember(folder)
    assert consent.given(folder)


def test_a_changed_notice_is_asked_again(tmp_path):
    (tmp_path / "consent.json").write_text('{"notice": 0}')
    assert not consent.given(str(tmp_path))


def test_no_settings_folder_means_ask_every_time():
    consent.remember(None)
    assert not consent.given(None)
