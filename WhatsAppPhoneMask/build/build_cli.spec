# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
# SPECPATH is a PyInstaller global containing the absolute path to the spec file's directory
spec_dir = SPECPATH

a = Analysis(
    [os.path.join(spec_dir, '..', 'src', 'cli.py')],
    pathex=[os.path.join(spec_dir, '..', 'src')],
    binaries=[],
    datas=[],
    hiddenimports=['mask_core'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='phone_mask',
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
    version=os.path.join(spec_dir, 'version_info.txt'),
)
