"""Silero Voice Activity Detection (VAD) wrapper."""
import logging
import threading
import numpy as np
import torch

logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    """Voice Activity Detection using Silero VAD.
    
    Detects speech/non-speech regions in audio. Uses the Silero VAD model
    which is lightweight and fast (< 1ms per 30ms chunk on CPU).
    """

    def __init__(self, threshold: float = 0.5):
        """Initialize VAD.
        
        Args:
            threshold: Speech probability threshold (0.0-1.0). Higher = stricter.
        """
        self._threshold = threshold
        self._model = None
        self._utils = None
        self._lock = threading.Lock()
        self._loaded = False

    def _load_model(self):
        """Lazy-load the Silero VAD model."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                from config import get_cache_dir, get_models_dir
                logger.info("Loading Silero VAD model...")
                models_dir = get_models_dir() / "silero-vad"
                hub_dir = get_cache_dir() / "torch_hub"
                hub_dir.mkdir(parents=True, exist_ok=True)
                torch.hub.set_dir(str(hub_dir))

                local_dir = models_dir if models_dir.exists() else (hub_dir / "snakers4_silero-vad_master")
                if local_dir.exists():
                    model, utils = torch.hub.load(
                        repo_or_dir=str(local_dir),
                        model="silero_vad",
                        source="local",
                        trust_repo=True,
                    )
                else:
                    model, utils = torch.hub.load(
                        repo_or_dir="snakers4/silero-vad",
                        model="silero_vad",
                        force_reload=False,
                        trust_repo=True,
                    )
                self._model = model
                self._utils = utils
                self._loaded = True
                logger.info("Silero VAD loaded successfully")
            except Exception as e:
                logger.error("Failed to load Silero VAD: %s", e)
                raise

    def is_speech(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> tuple:
        """Check if an audio chunk contains speech.
        
        Args:
            audio_chunk: Float32 mono audio array.
            sample_rate: Sample rate of the audio (default 16000).
            
        Returns:
            Tuple of (is_speech: bool, confidence: float).
        """
        self._load_model()

        try:
            tensor = torch.from_numpy(audio_chunk).float()
            if tensor.dim() > 1:
                tensor = tensor.squeeze()

            # Silero VAD expects 16000 Hz
            if sample_rate != 16000:
                target_len = int(len(tensor) * 16000 / sample_rate)
                tensor = torch.nn.functional.interpolate(
                    tensor.unsqueeze(0).unsqueeze(0), size=target_len, mode="linear"
                ).squeeze()

            # Silero VAD requires 512-sample blocks at 16kHz
            window_size = 512
            if len(tensor) < window_size:
                # Pad to 512 if chunk is too short
                pad_len = window_size - len(tensor)
                tensor = torch.nn.functional.pad(tensor, (0, pad_len))

            probs = []
            for i in range(0, len(tensor) - window_size + 1, window_size):
                frame = tensor[i : i + window_size]
                prob = self._model(frame, 16000).item()
                probs.append(prob)

            confidence = max(probs) if probs else 0.0
            return (confidence >= self._threshold, confidence)
        except Exception as e:
            logger.error("VAD inference error: %s", e)
            return (False, 0.0)

    def get_speech_timestamps(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> list:
        """Get timestamps of speech segments in audio.
        
        Args:
            audio: Full audio array (float32, mono).
            sample_rate: Sample rate of the audio.
            
        Returns:
            List of dicts with 'start' and 'end' keys (sample indices).
        """
        self._load_model()

        try:
            tensor = torch.from_numpy(audio).float()
            if tensor.dim() > 1:
                tensor = tensor.squeeze()

            # Use Silero's utility function
            get_speech_ts = self._utils[0]  # get_speech_timestamps is first util
            timestamps = get_speech_ts(
                tensor,
                self._model,
                sampling_rate=sample_rate,
                threshold=self._threshold,
                min_speech_duration_ms=250,
                min_silence_duration_ms=100,
            )
            result = [{"start": ts["start"], "end": ts["end"]} for ts in timestamps]
            logger.debug("Found %d speech segments", len(result))
            return result
        except Exception as e:
            logger.error("Speech timestamp error: %s", e)
            return []

    def reset_states(self):
        """Reset the model's hidden states (for streaming)."""
        if self._model is not None:
            try:
                self._model.reset_states()
            except Exception as e:
                logger.error("Reset states error: %s", e)

    def set_threshold(self, threshold: float):
        """Update the VAD threshold."""
        self._threshold = max(0.0, min(1.0, threshold))
        logger.info("VAD threshold set to %.2f", self._threshold)
