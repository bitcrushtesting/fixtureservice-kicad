# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""From a finding's references to the footprints they name, in the editor.

A finding names what it is about by reference designator (`TP12`), now and
then with a note after it (`GND (TP-MINI)`) or a pad (`U3:4`, `U3.4`). Some
references are the fixture's own (`H1` for a hole the reader numbered, `P2`
for a clamp pin) and name nothing on the board; those simply do not match.

Selecting is all this does. It never moves, adds or changes an item.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, List, Optional, Sequence

ZOOM_TO_SELECTION = "common.Control.zoomFitSelection"


def candidates(ref: str) -> List[str]:
    """The designators a reference might mean, most specific first."""
    out: List[str] = []

    def add(text: str) -> None:
        text = text.strip()
        if text and text not in out:
            out.append(text)

    add(ref)
    bare = re.sub(r"\s*\(.*\)\s*$", "", ref)
    add(bare)
    for sep in (":", ".", "/"):
        if sep in bare:
            add(bare.split(sep, 1)[0])
    return out


def match(refs: Iterable[str], designators: Iterable[str]) -> List[str]:
    """The board's designators that `refs` name, in the order first named."""
    known = set(designators)
    found: List[str] = []
    for ref in refs:
        for c in candidates(ref):
            if c in known:
                if c not in found:
                    found.append(c)
                break
    return found


def _designator(footprint: Any) -> str:
    try:
        return str(footprint.reference_field.text.value)
    except AttributeError:
        return ""


def select(
    board: Any,
    refs: Sequence[str],
    run_action: Optional[Callable[[str], Any]] = None,
) -> List[str]:
    """Select the footprints `refs` name and zoom to them; return their designators.

    The zoom is a courtesy: a KiCad without that action still gets the
    selection, which is what matters.
    """
    footprints = list(board.get_footprints())
    by_ref = {}
    for fp in footprints:
        d = _designator(fp)
        if d and d not in by_ref:
            by_ref[d] = fp
    wanted = match(refs, by_ref.keys())
    board.clear_selection()
    if not wanted:
        return []
    board.add_to_selection([by_ref[d] for d in wanted])
    if run_action is not None:
        try:
            run_action(ZOOM_TO_SELECTION)
        except Exception:  # noqa: BLE001 -- see the docstring
            pass
    return wanted
