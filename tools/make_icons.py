# SPDX-FileCopyrightText: 2026 Bitcrush Testing
# SPDX-License-Identifier: GPL-3.0-or-later
"""Draw the toolbar and package icons: a probe plate with its pins.

Pure Python (zlib only), supersampled for antialiasing, so the icons are
reproducible from this file and need no image library.

    python tools/make_icons.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SS = 8  # supersampling


def png(path: Path, size: int, rgba_rows) -> None:
    raw = b"".join(b"\x00" + bytes(row) for row in rgba_rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(raw, 9))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)


def inside(x: float, y: float, inset: float, r: float) -> bool:
    """Within a rounded square `inset` in from the 24-unit frame, corner radius `r`."""
    lo, hi = inset, 24 - inset
    cx = min(max(x, lo + r), hi - r)
    cy = min(max(y, lo + r), hi - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r and lo <= x <= hi and lo <= y <= hi


def coverage(size: int):
    """Per pixel, (plate cover, pin cover) in 0..1, in a 24-unit design grid."""
    n = size * SS
    unit = n / 24.0
    plate = [[0] * size for _ in range(size)]
    pins = [[0] * size for _ in range(size)]
    pin_xy = [(x, y) for y in (8.5, 15.5) for x in (6.5, 12.0, 17.5)]
    for py in range(n):
        y = (py + 0.5) / unit
        for px in range(n):
            x = (px + 0.5) / unit
            # the plate: a rounded square ring
            if inside(x, y, 2.0, 3.5) and not inside(x, y, 3.7, 1.8):
                plate[py // SS][px // SS] += 1
            if any((x - cx) ** 2 + (y - cy) ** 2 <= 2.05 ** 2 for cx, cy in pin_xy):
                pins[py // SS][px // SS] += 1
    full = SS * SS
    return [[(plate[j][i] / full, pins[j][i] / full) for i in range(size)] for j in range(size)]


def render(path: Path, size: int, plate_rgb, pin_rgb) -> None:
    rows = []
    for row in coverage(size):
        out = []
        for a_plate, a_pin in row:
            a = max(a_plate, a_pin)
            rgb = pin_rgb if a_pin >= a_plate else plate_rgb
            out += [*rgb, round(255 * a)]
        rows.append(out)
    png(path, size, rows)


def main() -> None:
    ink, light_ink = (40, 44, 52), (222, 226, 232)
    accent = (214, 64, 46)  # the pins, as the brand's red
    plugin = ROOT / "plugin"
    for s in (24, 48):
        render(plugin / f"icon-{s}.png", s, ink, accent)
        render(plugin / f"icon-dark-{s}.png", s, light_ink, accent)
    (ROOT / "resources").mkdir(exist_ok=True)
    render(ROOT / "resources" / "icon.png", 64, ink, accent)


if __name__ == "__main__":
    main()
