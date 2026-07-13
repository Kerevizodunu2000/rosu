# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate Rosu's app icon + splash from the chosen geometric-rose design.

Run:  python -m rosu.assets.make_icon
Outputs icon.png (256), icon.ico (multi-size), splash.png next to this file.

The design itself lives in :mod:`rosu.assets.icon_lab` (round-2 #02:
white facets on osu! pink). This module is kept as the documented entry point.
"""
from __future__ import annotations

from . import icon_lab


def main() -> None:
    icon_lab.finalize()


if __name__ == "__main__":
    main()
