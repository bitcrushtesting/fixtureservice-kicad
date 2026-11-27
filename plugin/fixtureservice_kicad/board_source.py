# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""The open board, as the `.kicad_pcb` text the service reads.

Taken from the editor through the IPC API rather than from disk, so what is
checked is what is on screen, unsaved edits included, and the user's file is
neither saved nor touched.
"""

from __future__ import annotations

from typing import Any, Tuple

from . import config


class BoardUnavailable(Exception):
    pass


def file_name_of(board: Any) -> str:
    name = ""
    try:
        name = str(board.name or "")
    except Exception:  # noqa: BLE001 -- a name is a nicety
        name = ""
    name = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        return "board.kicad_pcb"
    return name if name.endswith(".kicad_pcb") else name + ".kicad_pcb"


def read_board(board: Any) -> Tuple[str, bytes]:
    """`(file name, contents)` of the open board."""
    if board is None:
        raise BoardUnavailable("No board is open in the PCB editor.")
    try:
        text = board.get_as_string()
    except Exception as err:  # noqa: BLE001 -- any API failure means the same to the user
        raise BoardUnavailable(f"KiCad did not hand over the board ({err}).") from None
    if not isinstance(text, str) or not text.lstrip().startswith("(kicad_pcb"):
        raise BoardUnavailable("KiCad handed over something that is not a .kicad_pcb board.")
    data = text.encode("utf-8")
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise BoardUnavailable(
            f"The board is {len(data) / 2**20:.1f} MB; the service accepts up to "
            f"{config.MAX_UPLOAD_BYTES // 2**20} MB. Upload a smaller export on the website instead."
        )
    return file_name_of(board), data
