"""Speech-to-text transcription using faster-whisper.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import logging
import threading
import os
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)
PAKISTANI_LECTURE_PROMPT = (
    "Bilingual Pakistani university classroom lecture in mixed English and Urdu. "
    "Discussion on computer science, concepts, code, formulas, assignments, presentations, questions and answers."
)


class Transcriber:
    """Speech-to-text transcription using faster-whisper (CTranslate2).
    
    Optimized for live classroom lectures and Pakistani bilingual conversations (Urdu + English).
    """

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        """Initialize the transcriber.
        
        Args:
            model_size: Whisper model size ('tiny', 'base', 'small', 'medium', 'large-v3-turbo', 'distil-large-v3').
            device: Compute device ('cpu' or 'cuda').
            compute_type: Quantization type ('int8', 'float16', 'float32').
        """
        self._model_size = model_size
        self._model = None
        self._loaded = False
        self._lock = threading.Lock()

        # Dynamic Hardware Configuration (NVIDIA GPU Tensor Cores or Vectorized Multi-Core CPU)
        from models.hardware import HardwareManager
        hw = HardwareManager.get_whisper_config()
        self._device = hw["device"]
        self._compute_type = hw["compute_type"]
        self._threads = hw["cpu_threads"]

    def _load_model(self):
        """Lazy-load the Whisper model with automatic fallback."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                from faster_whisper import WhisperModel
                from config import get_models_dir, PROJECT_ROOT
                from models.model_manager import ModelManager
                from pathlib import Path

                models_to_try = [self._model_size]
                for fallback in ['base', 'small', 'tiny']:
                    if fallback not in models_to_try:
                        models_to_try.append(fallback)

                loaded_model = None
                loaded_size = None

                for m_size in models_to_try:
                    try:
                        # 1. Direct local Models folder check (Zero network, instantaneous loading)
                        direct_path = get_models_dir() / m_size
                        if (direct_path / "model.bin").exists():
                            logger.info(
                                "Loading Whisper model '%s' directly from local disk %s (device=%s, compute=%s, threads=%d)...",
                                m_size, direct_path, self._device, self._compute_type, self._threads
                            )
                            try:
                                loaded_model = WhisperModel(
                                    str(direct_path),
                                    device=self._device,
                                    compute_type=self._compute_type,
                                    cpu_threads=self._threads,
                                    local_files_only=True,
                                )
                            except Exception as dev_err:
                                if self._device != "cpu":
                                    logger.warning("CUDA load failed, falling back to CPU INT8: %s", dev_err)
                                    self._device = "cpu"
                                    self._compute_type = "int8"
                                    loaded_model = WhisperModel(
                                        str(direct_path),
                                        device="cpu",
                                        compute_type="int8",
                                        cpu_threads=self._threads,
                                        local_files_only=True,
                                    )
                                else:
                                    raise dev_err
                            loaded_size = m_size
                            break

                        # 2. Fallback to download root / HF cache
                        download_dir = str(get_models_dir() / "whisper")
                        repo_id = ModelManager.MODEL_REPOS.get(m_size, m_size)
                        logger.info(
                            "Loading Whisper model '%s' (repo=%s, device=%s, compute=%s, threads=%d)...",
                            m_size, repo_id, self._device, self._compute_type, self._threads
                        )
                        loaded_model = WhisperModel(
                            repo_id,
                            device=self._device,
                            compute_type=self._compute_type,
                            cpu_threads=self._threads,
                            download_root=download_dir,
                            local_files_only=False,
                        )
                        loaded_size = m_size
                        break
                    except Exception as e:
                        logger.warning("Could not load Whisper model '%s': %s", m_size, e)

                if loaded_model is None:
                    raise RuntimeError("Failed to load any Whisper model")

                self._model = loaded_model
                self._model_size = loaded_size
                self._loaded = True
                logger.info("Whisper model '%s' loaded successfully", self._model_size)
            except Exception as e:
                logger.error("Failed to load Whisper model: %s", e)
                raise

    def prewarm(self):
        """Pre-load model and run a dummy inference to eliminate cold-start lag."""
        try:
            self._load_model()
            dummy_audio = np.zeros(16000, dtype=np.float32)
            _ = self.transcribe(dummy_audio, language="auto")
            logger.info("Transcriber pre-warmed successfully (zero cold-start delay)")
        except Exception as e:
            logger.warning("Transcriber pre-warm warning: %s", e)

    def transcribe(self, audio: np.ndarray, language: Optional[str] = None) -> dict:
        """Transcribe audio to text with Pakistani bilingual speech optimization.
        
        Args:
            audio: Float32 mono audio array at 16kHz.
            language: 'auto' / 'roman' (Roman Urdu + English), 'ur' (Urdu Script), or 'en'.
            
        Returns:
            Dict with keys: text, language, segments.
        """
        # Noise floor check: If audio has virtually no energy (silence/whisper), return empty
        if len(audio) == 0:
            return {"text": "", "language": language or "unknown", "segments": []}
        
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.003:
            return {"text": "", "language": language or "unknown", "segments": []}

        self._load_model()

        try:
            import re
            from models.romanizer import to_roman_urdu
            from models.urdu_normalizer import UrduNormalizer
            from models.post_processor import post_process_english

            is_urdu_script = (language in ('ur', 'urdu'))
            is_english_only = (language in ('en', 'english'))
            is_roman_translit = (language == 'roman')
            # Default / Bilingual: Urdu script + English Latin code-switching ('auto' / 'bilingual')

            # Language tokenization selection
            if is_urdu_script or is_roman_translit or (not is_english_only):
                transcribe_lang = 'ur'
            else:
                transcribe_lang = 'en'

            segments_gen, info = self._model.transcribe(
                audio,
                language=transcribe_lang,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                initial_prompt=None,
                condition_on_previous_text=False,
                without_timestamps=True,
                no_speech_threshold=0.6,
                compression_ratio_threshold=2.4,
                vad_filter=False,
            )

            segments = []
            full_text_parts = []

            for seg in segments_gen:
                raw_text = seg.text.strip()
                if not raw_text:
                    continue

                # Anti-hallucination confidence checks
                conf = float(getattr(seg, "avg_logprob", getattr(seg, "avg_log_prob", 0.0)))
                no_speech_prob = float(getattr(seg, "no_speech_prob", 0.0))
                if no_speech_prob > 0.65 or conf < -1.2:
                    continue

                # Deduplicate repeating phrase loops (e.g. 'Can you can you can you' -> 'Can you')
                raw_text = re.sub(r'\b(\w+(?:\s+\w+){0,3})(?:\s+\1\b)+', r'\1', raw_text, flags=re.IGNORECASE).strip()

                if is_urdu_script:
                    # Pure Urdu Mode: Keep strictly in native Urdu script
                    text_clean = UrduNormalizer.normalize(raw_text)
                    lang_label = "ur"
                elif is_english_only:
                    # English Only Mode: Keep strictly in English
                    text_clean = post_process_english(raw_text)
                    lang_label = "en"
                elif is_roman_translit:
                    # Explicit Roman Transliteration Mode
                    normalized_urdu = UrduNormalizer.normalize(raw_text)
                    romanized = to_roman_urdu(normalized_urdu)
                    text_clean = post_process_english(romanized)
                    lang_label = "en-roman"
                else:
                    # Default: Natural Bilingual Code-Switching (Urdu Script + English Latin)
                    # Instant zero-transliteration delay!
                    words = raw_text.split()
                    processed_words = []
                    for w in words:
                        if any('\u0600' <= ch <= '\u06ff' for ch in w):
                            processed_words.append(UrduNormalizer.normalize(w))
                        else:
                            processed_words.append(w)
                    text_clean = post_process_english(" ".join(processed_words))
                    lang_label = "bilingual"

                if text_clean and len(text_clean) >= 2:
                    segments.append({
                        "text": text_clean,
                        "start": seg.start,
                        "end": seg.end,
                        "confidence": float(conf),
                    })
                    full_text_parts.append(text_clean)

            full_text = " ".join(full_text_parts).strip()
            detected_lang = lang_label if 'lang_label' in locals() else ("ur" if is_urdu_script else ("en" if is_english_only else "bilingual"))

            if full_text:
                logger.info(
                    "Transcribed: '%s' (lang=%s, model=%s)",
                    full_text, detected_lang, self._model_size
                )

            return {
                "text": full_text,
                "language": detected_lang,
                "segments": segments,
            }
        except Exception as e:
            logger.error("Transcription error: %s", e, exc_info=True)
            return {"text": "", "language": language or "unknown", "segments": []}

    def change_model(self, model_size: str):
        """Switch to a different model size dynamically.
        
        Args:
            model_size: New model size to load.
        """
        if model_size == self._model_size and self._loaded:
            return
        logger.info("Switching Whisper model from '%s' to '%s'", self._model_size, model_size)
        self.unload()
        self._model_size = model_size
        self._load_model()

    def is_loaded(self) -> bool:
        """Whether the model is loaded."""
        return self._loaded

    def unload(self):
        """Release the model from memory and trigger garbage collection."""
        with self._lock:
            self._model = None
            self._loaded = False
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            logger.info("Whisper model unloaded and memory reclaimed")
