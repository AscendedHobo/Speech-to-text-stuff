# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['Gemini_Whisper.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['whisper', 'tkinterdnd2'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Add whisper model directory to the package
import os
import whisper

# Get the whisper model directory
whisper_dir = os.path.dirname(whisper.__file__)
model_dir = os.path.join(os.path.dirname(whisper_dir), 'whisper')

# Add the model directory to the datas
a.datas += [(os.path.join('whisper', os.path.basename(f)), f, 'DATA') 
           for f in os.listdir(model_dir) if os.path.isfile(os.path.join(model_dir, f))]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Gemini_Whisper',
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
    icon='NONE',
)
