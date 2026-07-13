# Third-Party Licenses

Rosu itself is licensed under the **GNU General Public License v3.0 or later** (see [`LICENSE`](LICENSE)).
It bundles or depends on the third-party components below, each under its own license. These notices
are provided to satisfy the "appropriate legal notices" obligations of the respective licenses.

| Component | Role in Rosu | License |
|---|---|---|
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | GUI toolkit — the bundled Qt 6 libraries | LGPL-3.0 |
| [py7zr](https://github.com/miurahr/py7zr) | `.7z` archive extraction | LGPL-2.1-or-later |
| [openpyxl](https://openpyxl.readthedocs.io/) | Excel report generation | MIT |
| [Send2Trash](https://github.com/arsenetar/send2trash) | moving files to the Recycle Bin | BSD-3-Clause |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | fuzzy search ranking | MIT |
| [Realm .NET](https://github.com/realm/realm-dotnet) | used by the bundled `RosuLazerExport` helper to read osu!lazer's `client.realm` | Apache-2.0 |

**License compatibility:** GPL-3.0 is compatible with all of the above — LGPL-3.0 and LGPL-2.1
combine into GPLv3 by design, Apache-2.0 is GPLv3-compatible, and MIT/BSD are compatible with any
license. (This is precisely why GPL-2.0 was *not* viable: Apache-2.0 and LGPLv3 are both incompatible
with GPLv2-only.)

Full license texts are available at each linked project page. When a bundled native binary is added
in the future (e.g. `UnRAR.exe` for RAR support — freeware, redistributable unmodified but not
open-source), its license text will be added here and shown in the app's **About → Licenses** screen.
