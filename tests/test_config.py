# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from fixtureservice_kicad import config


def test_production_unless_told_otherwise():
    assert config.base_url({}) == config.DEFAULT_BASE_URL == "https://staging.bitcrushtesting.com"


@pytest.mark.parametrize(
    "url",
    ["https://staging.example.com/", "http://localhost:3000/fixture", "http://127.0.0.1:5173"],
)
def test_https_or_this_machine(url):
    assert config.base_url({config.ENV_BASE_URL: url}) == url.rstrip("/")


@pytest.mark.parametrize(
    "url", ["http://example.com", "ftp://example.com", "example.com", "https://x.com/?a=1", "https://x.com/#f"]
)
def test_a_board_never_travels_in_clear_text(url):
    with pytest.raises(config.ConfigError):
        config.base_url({config.ENV_BASE_URL: url})


def test_origin_drops_the_path():
    assert config.origin_of("http://localhost:3000/fixture") == "http://localhost:3000"


def test_language_follows_the_environment():
    assert config.ui_language({"LANG": "de_AT.UTF-8"}) == "de"
    assert config.ui_language({"LANG": "en_GB.UTF-8"}) == "en"
    assert config.ui_language({"LC_ALL": "de_DE", "LANG": "en_US"}) == "de"
