# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('c:\\ROOT\\CodeBase\\Py\\1c_launcher\\src\\resources\\app_icon.ico', '.'), ('c:\\ROOT\\CodeBase\\Py\\1c_launcher\\src\\resources\\Start-1C-Console.ps1', '.')],
    hiddenimports=[],
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
    name='app',
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
    icon=['c:\\ROOT\\CodeBase\\Py\\1c_launcher\\src\\resources\\app_icon.ico'],
)
