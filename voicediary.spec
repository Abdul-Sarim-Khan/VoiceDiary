# -*- mode: python ; coding: utf-8 -*-
"""
VoiceDiary — PyInstaller Spec File
===================================

Build command:
    pyinstaller voicediary.spec

This produces a one-directory bundle under  dist/VoiceDiary/  with the
executable  VoiceDiary.exe  inside it.  One-dir mode is chosen over
one-file because ML applications load much faster when libraries are
already on disk rather than being extracted from a single archive at
every launch.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path helpers — all paths are resolved relative to the spec file location
# so that directories containing spaces are handled correctly.
# ---------------------------------------------------------------------------
SPEC_DIR = os.path.abspath(SPECPATH)          # noqa: F821  (SPECPATH injected by PyInstaller)
SRC_DIR  = os.path.join(SPEC_DIR, 'src')

# Icon path (Branding icon)
_icon_path = os.path.join(SPEC_DIR, 'Branding', 'Voice Diary Icon.ico')
if not os.path.isfile(_icon_path):
    _icon_path = os.path.join(SRC_DIR, 'ui', 'static', 'assets', 'icon.ico')
ICON = _icon_path if os.path.isfile(_icon_path) else None

# ---------------------------------------------------------------------------
# Data files to bundle
# ---------------------------------------------------------------------------
added_datas = []

# Branding assets
_branding_dir = os.path.join(SPEC_DIR, 'Branding')
if os.path.isdir(_branding_dir):
    added_datas.append((_branding_dir, 'Branding'))

# UI static assets (HTML, CSS, JS, images, fonts)
_ui_static = os.path.join(SRC_DIR, 'ui', 'static')
if os.path.isdir(_ui_static):
    added_datas.append((_ui_static, os.path.join('ui', 'static')))

# Compiled protobuf / gRPC stubs
_proto_dir = os.path.join(SRC_DIR, 'proto')
if os.path.isdir(_proto_dir):
    added_datas.append((_proto_dir, 'proto'))

# Bundle speechbrain package directory and metadata for PyInstaller
import speechbrain
_sb_dir = os.path.dirname(speechbrain.__file__)
if os.path.isdir(_sb_dir):
    added_datas.append((_sb_dir, 'speechbrain'))

from PyInstaller.utils.hooks import collect_data_files, copy_metadata
added_datas += collect_data_files('speechbrain')
added_datas += copy_metadata('speechbrain')
added_datas += copy_metadata('huggingface_hub')

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [os.path.join(SRC_DIR, 'main.py')],
    pathex=[SRC_DIR],
    binaries=[],
    datas=added_datas,
    hiddenimports=[
        # PyTorch
        'torch',
        'torch.nn',
        'torch.nn.functional',
        'torchaudio',
        'torchaudio.transforms',
        'torchaudio.functional',
        # SpeechBrain
        'speechbrain',
        'speechbrain.inference',
        'speechbrain.inference.speaker',
        # Whisper
        'faster_whisper',
        # Audio I/O & Signal Processing
        'sounddevice',
        'soundfile',
        'numpy',
        'scipy',
        'scipy.signal',
        'scipy.io',
        'scipy.io.wavfile',
        'pydub',
        # UI
        'webview',
        # Protobuf
        'google',
        'google.protobuf',
        'google.protobuf.descriptor',
        'google.protobuf.descriptor_pool',
        'google.protobuf.reflection',
        'google.protobuf.symbol_database',
        # Windows platform
        'ctypes',
        'ctypes.wintypes',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'IPython',
        'jupyter',
        'jupyter_client',
        'jupyter_core',
        'notebook',
        'pytest',
        'tkinter',
        '_tkinter',
        'sphinx',
        'docutils',
    ],
    noarchive=False,
    optimize=0,
)

# ---------------------------------------------------------------------------
# PYZ (Python archive of pure-Python modules)
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure)

# ---------------------------------------------------------------------------
# EXE
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,          # one-dir mode
    name='VoiceDiary',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                      # Disabled for instant packaging of PyTorch & MKL DLLs
    console=False,                  # windowed (no terminal)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)

# ---------------------------------------------------------------------------
# COLLECT (gather everything into dist/VoiceDiary/)
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VoiceDiary',
)
