# SPDX-License-Identifier: GPL-3.0-or-later
"""osu! Archive Manager.

A desktop tool that extracts osu! beatmap pack archives (.zip) into a flat
Output folder, tracks them in a SQLite memory, detects gaps in the numbered
pack series (marked red in an Excel report), deduplicates the .osz beatmaps
into a permanent Library, and can bulk-import them straight into osu!lazer.

All background/log/code text is English by design; only the user-facing UI is
translated (see i18n.py).
"""

__version__ = "1.0.1"
__app_name__ = "Rosu"
