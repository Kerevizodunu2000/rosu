# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: builds a single, self-contained rosu.exe.
# Build with:  pyinstaller rosu.spec

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('rosu/assets/icon.png', 'rosu/assets'),
        ('rosu/assets/icon.ico', 'rosu/assets'),
        ('rosu/assets/splash.png', 'rosu/assets'),
        # self-contained .NET helper that re-exports osu!lazer beatmapsets (item 15)
        ('rosu/assets/lazer_export/RosuLazerExport.exe',
         'rosu/assets/lazer_export'),
    ],
    hiddenimports=['send2trash', 'send2trash.plat_win', 'rapidfuzz',
                   'py7zr', 'pyppmd', 'pybcj', 'brotli', 'inflate64',
                   'multivolumefile', 'texttable', 'Cryptodome'],
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
