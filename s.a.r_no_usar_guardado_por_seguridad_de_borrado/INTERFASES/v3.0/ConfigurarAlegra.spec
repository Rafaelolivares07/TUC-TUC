# -*- mode: python ; coding: utf-8 -*-
# ConfigurarAlegra.spec — v3.0 UI Tkinter, acceso directo en escritorio

import os
SRC = os.path.join(os.path.dirname(SPEC), '')

a = Analysis(
    [os.path.join(SRC, 'configurar_allegra.py')],
    pathex=[SRC],
    binaries=[],
    datas=[],
    hiddenimports=[
        'dbf', 'dbf.tables', 'dbf.fields',
        'requests',
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox',
        'tkinter.filedialog',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='ConfigurarAlegra',
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
