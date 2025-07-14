# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all whisper submodules and data files
whisper_hidden_imports = collect_submodules('whisper')
whisper_datas = collect_data_files('whisper')

# Add torch and related packages
torch_hidden_imports = collect_submodules('torch') + collect_submodules('tqdm') + collect_submodules('numpy')

a = Analysis(
    ['Whisper.py'],
    pathex=[],
    binaries=[],
    datas=whisper_datas,
    hiddenimports=whisper_hidden_imports + torch_hidden_imports + ['tiktoken', 'tiktoken_ext', 'numba'],
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
    [],
    exclude_binaries=True,
    name='Whisper Transcription',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Set to True to see any errors during startup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Whisper Transcription',
)
