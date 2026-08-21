"""VoiceDiary — Global configuration and path resolution.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import os
import sys
from pathlib import Path


def _detect_app_dir() -> Path:
    """Detects the application installation/executable directory."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller frozen exe (e.g. C:\Program Files\VoiceDiary)
        return Path(sys.executable).resolve().parent
    
    # Running in development mode (from run.py or src/main.py)
    file_dir = Path(__file__).resolve().parent
    return file_dir.parent  # src/ -> Voice-Diary-Gemini root


APP_DIR = _detect_app_dir()
PROJECT_ROOT = APP_DIR

APP_NAME = 'VoiceDiary'
APP_VERSION = '1.2.0'
APP_COPYRIGHT = 'VoiceDiary © Abdul Sarim Khan. All Rights Reserved.'

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 500  # 500ms sliding window
CHUNK_OVERLAP_MS = 200   # 200ms overlap
MIN_SEGMENT_DURATION_MS = 1200   # 1.2s min for coherent sentences & stable speaker embeddings
DEFAULT_SIMILARITY_THRESHOLD = 0.32  # 0.32 optimal for classroom acoustics
DEFAULT_VAD_THRESHOLD = 0.50
DEFAULT_WHISPER_MODEL = 'base'  # default fast balanced model
MAX_EMBEDDINGS_PER_SPEAKER = 50  # store up to 50 unique voice prints per speaker (high speed + high accuracy)
EMBEDDING_DIM = 192

# Acoustic filtering & lecture optimizations
HIGH_PASS_CUTOFF_HZ = 80         # 80 Hz low-cut filter to remove table bumps and room rumble
NOISE_GATE_RATIO = 1.4           # Skip VAD compute if below ambient noise gate
PARAGRAPH_MERGE_MAX_GAP_S = 3.5  # Merge consecutive sentences from same speaker into smooth paragraphs

# Modern refined palette colors for speakers
SPEAKER_COLORS = [
    '#6366F1', '#10B981', '#F59E0B', '#EC4899', '#06B6D4',
    '#8B5CF6', '#F97316', '#14B8A6', '#3B82F6', '#E11D48'
]


def get_app_data_dir() -> Path:
    """Returns writable user data directory.
    
    In frozen/installed mode: Uses %APPDATA%/VoiceDiary (always writable on all user accounts).
    In local dev mode: Uses PROJECT_ROOT/data.
    """
    if getattr(sys, 'frozen', False):
        appdata = os.environ.get('APPDATA')
        if appdata:
            return Path(appdata) / 'VoiceDiary'
        return Path.home() / '.voicediary'
    return PROJECT_ROOT / 'data'


def get_models_dir() -> Path:
    """Returns the offline Models directory across all deployment environments."""
    candidates = [
        APP_DIR / 'Models',
        APP_DIR / '_internal' / 'Models',
        PROJECT_ROOT / 'Models',
        get_app_data_dir() / 'models',
    ]
    for c in candidates:
        if c.exists() and (c / 'ecapa-tdnn').exists():
            return c
    for c in candidates:
        if c.exists():
            return c
    return APP_DIR / 'Models'


def get_database_path() -> Path:
    """Returns path to speakers.pb in writable data directory."""
    return get_app_data_dir() / 'speakers.pb'


def get_settings_path() -> Path:
    """Returns path to settings.pb in writable data directory."""
    return get_app_data_dir() / 'settings.pb'


def get_sessions_dir() -> Path:
    """Returns path to sessions directory in writable data directory."""
    return get_app_data_dir() / 'sessions'


def get_exports_dir() -> Path:
    """Returns path to exports directory in writable data directory."""
    return get_app_data_dir() / 'exports'


def get_cache_dir() -> Path:
    """Returns path to cache directory in writable data directory."""
    return get_app_data_dir() / 'cache'


_cache_dir = get_cache_dir()
os.environ['HF_HOME'] = str(_cache_dir / 'huggingface')
os.environ['TORCH_HOME'] = str(_cache_dir / 'torch')
os.environ['XDG_CACHE_HOME'] = str(_cache_dir)
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'


def ensure_dirs():
    """Creates all required writable directories if they don't exist."""
    dirs = [
        get_app_data_dir(),
        get_sessions_dir(),
        get_exports_dir(),
        get_cache_dir(),
        get_cache_dir() / 'torch_hub',
        get_app_data_dir() / 'logs',
    ]
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
