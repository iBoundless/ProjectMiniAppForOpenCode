#!/usr/bin/env python3
"""Сгенерировать PNG-иконки PWA без внешних зависимостей.

Рисунок: приглашение терминала «>_» на темном фоне, с запасом под
maskable-область (80% от центра). Запуск: python3 scripts/make_icons.py
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
BG = (23, 33, 43)
FG = (98, 188, 249)
SIZES = {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 180}


def seg_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def coverage(x: float, y: float) -> float:
    """Доля переднего плана в точке (координаты 0..1), со сглаживанием."""
    width = 0.055
    edge = 0.006
    d = min(
        seg_distance(x, y, 0.30, 0.34, 0.47, 0.50),
        seg_distance(x, y, 0.47, 0.50, 0.30, 0.66),
    )
    chevron = max(0.0, min(1.0, (width - d) / edge + 0.5))
    under = 1.0 if 0.52 <= x <= 0.72 and 0.62 <= y <= 0.62 + 2 * width else 0.0
    return max(chevron, under)


def render(size: int) -> bytes:
    rows = bytearray()
    for j in range(size):
        rows.append(0)
        for i in range(size):
            a = coverage((i + 0.5) / size, (j + 0.5) / size)
            rows.extend(round(BG[k] + (FG[k] - BG[k]) * a) for k in range(3))
    return bytes(rows)


def png(size: int) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(render(size), 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size in SIZES.items():
        (OUT / name).write_bytes(png(size))
        print(OUT / name)


if __name__ == "__main__":
    main()
