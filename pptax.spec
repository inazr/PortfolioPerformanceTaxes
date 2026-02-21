# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for SteuerPP – folder (onedir) mode.
# Build: pyinstaller pptax.spec

a = Analysis(
    ["src/pptax/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/pptax/data/tax_parameters.json", "data"),
    ],
    hiddenimports=[
        "lxml._elementpath",
        "lxml.etree",
        "lxml.objectify",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pptax",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep True: CLI mode needs a console
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
    upx=True,
    upx_exclude=[],
    name="pptax",
)