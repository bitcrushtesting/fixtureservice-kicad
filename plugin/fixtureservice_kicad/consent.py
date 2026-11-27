# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""The one-time notice before the first upload, and its remembered answer."""

from __future__ import annotations

import json
import os
from typing import Optional

NOTICE_VERSION = 2  # 2: the hand-off to the browser

NOTICE = (
    "This sends the open board to the Bitcrush fixture service ({host}) over HTTPS "
    "for a DFT check and a fixture quote.\n\n"
    "The service reads the board, answers, and deletes the file before the answer "
    "is sent. Open in browser hands what was read from it (not the file) to the "
    "quote page, held in the service's memory for 15 minutes and on no disk. "
    "Nothing is stored unless you go on to save a quote in the browser.\n\n"
    "Need an NDA first? Ask for one on the website before you upload."
)


def _file(settings_dir: Optional[str]) -> Optional[str]:
    return os.path.join(settings_dir, "consent.json") if settings_dir else None


def given(settings_dir: Optional[str]) -> bool:
    path = _file(settings_dir)
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("notice") == NOTICE_VERSION
    except (OSError, ValueError, AttributeError):
        return False


def remember(settings_dir: Optional[str]) -> None:
    """Best effort: without a settings folder the notice simply shows again."""
    path = _file(settings_dir)
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"notice": NOTICE_VERSION}, f)
    except OSError:
        pass
