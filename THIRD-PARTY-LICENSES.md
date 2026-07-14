# Third-Party Licenses

Rosu itself is licensed under the **GNU General Public License v3.0 or later** (see [`LICENSE`](LICENSE)).
It bundles or depends on the third-party components below, each under its own license. These notices
are provided to satisfy the "appropriate legal notices" obligations of the respective licenses, and the
same list is shown in-app under **Settings → About / Licenses**.

| Component | Role in Rosu | License |
|---|---|---|
| [PySide6 / Qt](https://www.qt.io/qt-for-python) | GUI toolkit — the bundled Qt 6 libraries | LGPL-3.0-only |
| [py7zr](https://github.com/miurahr/py7zr) | `.7z` archive extraction | LGPL-2.1-or-later |
| [openpyxl](https://openpyxl.readthedocs.io/) | Excel report generation | MIT |
| [Send2Trash](https://github.com/arsenetar/send2trash) | moving files to the Recycle Bin | BSD-3-Clause |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | fuzzy search ranking | MIT |
| [keyring](https://github.com/jaraco/keyring) | OS-native credential storage for the Google Drive OAuth refresh token | MIT |
| [pywin32-ctypes](https://github.com/enthought/pywin32-ctypes) | keyring's Windows Credential Manager backend | BSD-3-Clause |
| [jaraco.classes](https://github.com/jaraco/jaraco.classes), [jaraco.functools](https://github.com/jaraco/jaraco.functools), [jaraco.context](https://github.com/jaraco/jaraco.context), [more-itertools](https://github.com/more-itertools/more-itertools) | small utility libraries required by keyring | MIT |
| [pyppmd](https://github.com/miurahr/pyppmd), [pybcj](https://github.com/miurahr/pybcj), [inflate64](https://github.com/miurahr/inflate64), [multivolumefile](https://github.com/miurahr/multivolume) | py7zr codec dependencies — PPMd/BCJ/deflate64 decoders + multi-volume archive support | LGPL-2.1-or-later |
| [Brotli](https://github.com/google/brotli) (Python bindings), [texttable](https://github.com/foutaise/texttable/) | py7zr codec dependencies — Brotli decoder + internal table formatting | MIT |
| [PyCryptodomex](https://www.pycryptodome.org/) (`Cryptodome`) | py7zr dependency — AES/legacy decryption for encrypted 7z archives | BSD-2-Clause and Public Domain (dual, per-module) |
| [psutil](https://github.com/giampaolo/psutil) | py7zr dependency — process/system info used during extraction | BSD-3-Clause |
| [backports.zstd](https://github.com/rogdham/backports.zstd) | py7zr dependency — zstd decompression backport for Python < 3.14 | PSF-2.0 |
| [Realm .NET](https://github.com/realm/realm-dotnet) | used by the bundled `RosuLazerExport` helper to read osu!lazer's `client.realm` | Apache-2.0 |
| [.NET Runtime](https://github.com/dotnet/runtime) | self-contained .NET 8 runtime embedded in the single-file `RosuLazerExport.exe` publish | MIT |

**License compatibility:** GPL-3.0 is compatible with every component above. LGPL-3.0 and LGPL-2.1-or-later
are deliberately structured to permit use by programs under any license (including GPL) without imposing
relicensing obligations on Rosu's own code; Apache-2.0 and MIT/BSD/PSF-2.0/Public-Domain are all
GPLv3-compatible or outright permissive. (This is precisely why GPL-2.0 was *not* viable: Apache-2.0 and
LGPLv3 are both incompatible with GPLv2-only.) Note that `shiboken6` — PySide6's binding helper — ships
under a choice of `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; the LGPL-3.0-only (or GPL-3.0-only)
option is fully compatible with Rosu's GPL-3.0-or-later.

Full license texts are available at each linked project page. When a bundled native binary is added
in the future (e.g. `UnRAR.exe` for RAR support — freeware, redistributable unmodified but not
open-source), its license text will be added here and shown in the app's **About → Licenses** screen.
