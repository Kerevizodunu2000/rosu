Rosu — bundled third-party license texts
=========================================

Full license texts for Rosu's bundled third-party components. Rosu itself is
GPL-3.0-or-later (see ../LICENSE). MIT/BSD/PSF one-liners are inline in
../THIRD-PARTY-LICENSES.md.

This folder contains the CANONICAL, verbatim full texts fetched from each
license's official source, plus a component-attribution notice. Nothing here
has been hand-edited or paraphrased.

Files in this folder
---------------------

LGPL-3.0.txt
    GNU Lesser General Public License, version 3.0.
    Source: https://www.gnu.org/licenses/lgpl-3.0.txt
    Covers: PySide6 / Qt6 (GUI toolkit), shiboken6 (PySide6's binding helper —
    ships under a choice of LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only;
    Rosu relies on the LGPL-3.0-only / GPL-3.0-only option).

LGPL-2.1.txt
    GNU Lesser General Public License, version 2.1.
    Source: https://www.gnu.org/licenses/lgpl-2.1.txt
    Covers: py7zr, pyppmd, pybcj, inflate64, multivolumefile
    (`.7z` extraction + its PPMd/BCJ/deflate64 codecs and multi-volume
    archive support).

Apache-2.0.txt
    Apache License, Version 2.0.
    Source: https://www.apache.org/licenses/LICENSE-2.0.txt
    Covers: Realm .NET (embedded in the bundled RosuLazerExport.exe helper,
    used to read osu!lazer's client.realm database).

Realm-dotnet-NOTICE.txt
    Attribution notice for Realm .NET (see Apache-2.0.txt §4(d)).
    The upstream realm-dotnet repository does not publish a separate NOTICE
    file, so this is a minimal good-faith attribution naming the copyright
    holder and license — see the file for details and source links checked.

Component → file map
---------------------

| Component                                             | License file      |
|--------------------------------------------------------|--------------------|
| PySide6 / Qt6                                           | LGPL-3.0.txt       |
| shiboken6                                               | LGPL-3.0.txt       |
| py7zr                                                   | LGPL-2.1.txt       |
| pyppmd                                                  | LGPL-2.1.txt       |
| pybcj                                                   | LGPL-2.1.txt       |
| inflate64                                               | LGPL-2.1.txt       |
| multivolumefile                                         | LGPL-2.1.txt       |
| Realm .NET (in RosuLazerExport.exe)                     | Apache-2.0.txt + Realm-dotnet-NOTICE.txt |

All other bundled/depended-on components (openpyxl, Send2Trash, RapidFuzz,
keyring, pywin32-ctypes, jaraco.*, more-itertools, Brotli, texttable,
PyCryptodomex, psutil, backports.zstd, .NET Runtime, etc.) are under MIT,
BSD, PSF-2.0, or public-domain terms — those are short enough to be quoted
inline in ../THIRD-PARTY-LICENSES.md rather than duplicated here.
