# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""KiCad plugin for the Bitcrush fixture service.

Everything that can be tested without KiCad or a window lives in plain
modules (`config`, `api`, `model`, `locator`, `board_source`, `session`);
`app` and `ui` are the thin layer that needs both.
"""

__version__ = "0.1.0"
