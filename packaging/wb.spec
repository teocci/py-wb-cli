# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the `wb` CLI.

Build (from repo root):
    pyinstaller packaging/wb.spec --noconfirm --clean

Output: dist/wb/  (one-dir bundle, portable)
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH is injected by PyInstaller and points at this file's directory.
ROOT = Path(SPECPATH).parent
SRC = ROOT / 'src'
ENTRY = SRC / 'wb' / '__main__.py'

hidden_imports = (
    collect_submodules('keyring.backends')
    + collect_submodules('pydantic')
    + collect_submodules('pydantic_core')
    + collect_submodules('wb')
)

datas = collect_data_files('certifi')

a = Analysis(
    [str(ENTRY)],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest', 'pydoc'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='wb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='wb',
)
