# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: builds a single, self-contained rosu.exe.
# Build with:  pyinstaller rosu.spec

import os

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# keyring finds its OS backend via importlib.metadata entry points, which
# PyInstaller's static analysis misses -> collect them (plus win32ctypes, the
# Windows Credential Manager backend's dependency) and the rosu.drive submodules
# (only lazily imported from services, so name them explicitly to be safe).
_drive_hidden = (
    collect_submodules('keyring')
    + collect_submodules('win32ctypes')
    + ['rosu.drive', 'rosu.drive.auth', 'rosu.drive.client',
       'rosu.drive.bundle', 'rosu.drive.manifest']
)

# Embed the OAuth client only if present. CI writes rosu/drive/oauth_client.json
# from a secret before building; it is gitignored, so an open-source build
# without the secret simply omits it (Drive login is then unavailable) rather
# than failing the build.
_oauth_client = os.path.join('rosu', 'drive', 'oauth_client.json')
_datas = [
    ('rosu/assets/icon.png', 'rosu/assets'),
    ('rosu/assets/icon.ico', 'rosu/assets'),
    ('rosu/assets/splash.png', 'rosu/assets'),
    # self-contained .NET helper that re-exports osu!lazer beatmapsets (item 15)
    ('rosu/assets/lazer_export/RosuLazerExport.exe', 'rosu/assets/lazer_export'),
    # legal notices shown in the in-app About / Licenses screen
    ('LICENSE', '.'),
    ('THIRD-PARTY-LICENSES.md', '.'),
]
if os.path.exists(_oauth_client):
    _datas.append((_oauth_client, 'rosu/drive'))

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    # send2trash: collect ALL submodules — recent versions moved the Windows
    # backend to send2trash.win.modern / .win.legacy (the old flat plat_win is
    # gone), and __init__ picks one at runtime, so a hardcoded name is fragile.
    hiddenimports=['rapidfuzz', 'py7zr', 'pyppmd', 'pybcj', 'brotli',
                   'inflate64', 'multivolumefile', 'texttable', 'Cryptodome']
                  + collect_submodules('send2trash') + _drive_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='rosu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # GUI app: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='rosu/assets/icon.ico',
)
