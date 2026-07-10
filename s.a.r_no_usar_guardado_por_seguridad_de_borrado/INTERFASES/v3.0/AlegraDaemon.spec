# -*- mode: python ; coding: utf-8 -*-
# AlegraDaemon.spec — v3.0 EXE sin Python en cliente
# allegra_sync e interfaz_allegra se invocan via --run (bundleados como modulos)

import os
SRC = os.path.join(os.path.dirname(SPEC), '')

a = Analysis(
    [os.path.join(SRC, 'alegra_daemon.py')],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[
        'allegra_sync',
        'interfaz_allegra',
        'dbf', 'dbf.tables', 'dbf.fields',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AlegraDaemon',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
