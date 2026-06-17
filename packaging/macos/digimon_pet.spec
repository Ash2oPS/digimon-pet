# Build on macOS with the target Python architecture.
# arm64: run this spec from an arm64 Python on Apple Silicon.
# x86_64: run this spec from an x86_64 Python or Intel runner.

from pathlib import Path


block_cipher = None
project_root = Path(SPECPATH).parents[2]


a = Analysis(
    [str(project_root / "src" / "digimon_pet" / "__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=[
        (str(project_root / "data"), "data"),
        (str(project_root / "assets"), "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Digimon Pet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name="Digimon Pet",
)
app = BUNDLE(
    coll,
    name="Digimon Pet.app",
    icon=None,
    bundle_identifier="local.digimon-pet",
    info_plist={
        "CFBundleName": "Digimon Pet",
        "CFBundleDisplayName": "Digimon Pet",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
)
