# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point KiCad runs when the toolbar button is pressed (see plugin.json)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixtureservice_kicad.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
