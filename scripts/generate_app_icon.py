#!/usr/bin/env python3
"""Draw the iOS app icon: a yellow star on a red field.

Written from scratch because the project has no imaging dependency. Emits a
1024x1024 truecolour PNG with no alpha channel, which is what App Icon slots
require. iOS applies its own rounded-corner mask, so the artwork is full bleed.

    poetry run python scripts/generate_app_icon.py
"""

import math
import struct
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = (
    PROJECT_ROOT / "ios" / "MyConLearn" / "Assets.xcassets" / "AppIcon.appiconset" / "icon-1024.png"
)

SIZE = 1024
BACKGROUND_TOP = (226, 62, 48)
BACKGROUND_BOTTOM = (196, 26, 18)
STAR_COLOUR = (255, 206, 0)

POINTS = 5
OUTER_RADIUS = SIZE * 0.30
# Ratio that gives the classic five-pointed star its proportions.
INNER_RADIUS = OUTER_RADIUS * math.sin(math.pi / 10) / math.sin(math.pi - 3 * math.pi / 10)
# Width in pixels of the antialiased band along the star's edge.
EDGE_SOFTNESS = 1.2

SECTOR = 2 * math.pi / POINTS
HALF_SECTOR = SECTOR / 2
SIN_HALF_SECTOR = math.sin(HALF_SECTOR)


def star_boundary_radius(angle: float) -> float:
    """Distance from the centre to the star's edge at `angle`.

    `angle` is measured from a point of the star. Folding it into one half
    sector leaves a straight edge running from the outer vertex (at 0) to the
    inner vertex (at HALF_SECTOR); the radius along that segment has a closed
    form, so each pixel costs a constant amount of work.
    """
    folded = angle % SECTOR
    if folded > HALF_SECTOR:
        folded = SECTOR - folded

    denominator = OUTER_RADIUS * math.sin(folded) + INNER_RADIUS * math.sin(HALF_SECTOR - folded)
    return OUTER_RADIUS * INNER_RADIUS * SIN_HALF_SECTOR / denominator


def render() -> list[bytearray]:
    centre = SIZE / 2
    rows: list[bytearray] = []

    for y in range(SIZE):
        # Vertical gradient across the background.
        blend = y / (SIZE - 1)
        background = tuple(
            round(top + (bottom - top) * blend)
            for top, bottom in zip(BACKGROUND_TOP, BACKGROUND_BOTTOM)
        )

        row = bytearray()
        dy = y + 0.5 - centre

        for x in range(SIZE):
            dx = x + 0.5 - centre
            radius = math.hypot(dx, dy)

            if radius > OUTER_RADIUS + EDGE_SOFTNESS:
                row.extend(background)
                continue

            # Rotate so that a point of the star faces up.
            angle = math.atan2(dy, dx) + math.pi / 2
            edge = star_boundary_radius(angle)

            # Linear coverage ramp across the edge for antialiasing.
            coverage = 0.5 + (edge - radius) / (2 * EDGE_SOFTNESS)
            coverage = min(1.0, max(0.0, coverage))

            if coverage <= 0.0:
                row.extend(background)
            elif coverage >= 1.0:
                row.extend(STAR_COLOUR)
            else:
                row.extend(
                    round(base + (star - base) * coverage)
                    for base, star in zip(background, STAR_COLOUR)
                )

        rows.append(row)

    return rows


def write_png(path: Path, rows: list[bytearray]) -> None:
    # Each scanline is prefixed with filter type 0 (None).
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)  # 8-bit RGB
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_png(ICON_PATH, render())
    print(f"wrote {ICON_PATH.relative_to(PROJECT_ROOT)} ({ICON_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
