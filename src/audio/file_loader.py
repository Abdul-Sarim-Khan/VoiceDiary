"""Load audio files in various formats and convert to a standard format."""
import logging
import os
import numpy as np

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".wma", ".opus"}


def load_audio_file(file_path: str, target_sr: int = 16000) -> tuple:
    """Load an audio file and return as mono float32 numpy array.
    
    Supports WAV, FLAC, OGG, MP3, M4A, AAC, WMA, OPUS.
    Uses soundfile for lossless formats, pydub as fallback for compressed formats.
    
    Args:
        file_path: Path to the audio file.
        target_sr: Target sample rate for resampling (default 16000).
        
    Returns:
        Tuple of (audio_array, sample_rate) where audio_array is float32 mono
        normalized to [-1, 1].
        
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format: {ext}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    audio = None
    sr = None

    # Try soundfile first (best for WAV, FLAC, OGG)
    if ext in {".wav", ".flac", ".ogg"}:
        try:
            import soundfile as sf

            audio, sr = sf.read(file_path, dtype="float32")
            logger.info("Loaded %s via soundfile (sr=%d, samples=%d)", ext, sr, len(audio))
        except Exception as e:
            logger.warning("soundfile failed for %s: %s, trying pydub", file_path, e)
            audio = None

    # Fallback to pydub for MP3, M4A, or if soundfile failed
    if audio is None:
        try:
            from pydub import AudioSegment

            seg = AudioSegment.from_file(file_path)
            sr = seg.frame_rate
            samples = np.array(seg.get_array_of_samples(), dtype=np.float32)

            # Handle stereo
            if seg.channels > 1:
                samples = samples.reshape(-1, seg.channels)
                samples = samples.mean(axis=1)

            # Normalize to [-1, 1]
            max_val = float(2 ** (seg.sample_width * 8 - 1))
            audio = samples / max_val
            logger.info("Loaded %s via pydub (sr=%d, samples=%d)", ext, sr, len(audio))
        except Exception as e:
            raise RuntimeError(f"Failed to load audio file {file_path}: {e}") from e

    # Convert stereo to mono if needed
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    # Ensure float32
    audio = audio.astype(np.float32)

    # Resample if needed
    if sr != target_sr:
        audio = _resample(audio, sr, target_sr)
        logger.info("Resampled from %d to %d Hz", sr, target_sr)
        sr = target_sr

    # Normalize
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    return audio, sr


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio array using scipy or linear interpolation."""
    if orig_sr == target_sr:
        return audio

    try:
        from scipy.signal import resample

        num_samples = int(len(audio) * target_sr / orig_sr)
        return resample(audio, num_samples).astype(np.float32)
    except ImportError:
        logger.warning("scipy not available, using linear interpolation for resampling")
        num_samples = int(len(audio) * target_sr / orig_sr)
        indices = np.linspace(0, len(audio) - 1, num_samples)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
