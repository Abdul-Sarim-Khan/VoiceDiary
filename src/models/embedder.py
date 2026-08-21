"""Speaker embedding extraction using SpeechBrain ECAPA-TDNN."""
import logging
import threading
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class SpeakerEmbedder:
    """Extracts speaker embeddings using the ECAPA-TDNN model.
    
    Uses SpeechBrain's pre-trained ECAPA-TDNN model trained on VoxCeleb1+2.
    Produces 192-dimensional L2-normalized embedding vectors that represent
    unique vocal characteristics (pitch, timbre, formant frequencies).
    """

    def __init__(self, model_dir: Optional[str] = None):
        """Initialize the speaker embedder.
        
        Args:
            model_dir: Directory to cache the model. If None, uses config default.
        """
        self._model_dir = model_dir
        self._model = None
        self._lock = threading.Lock()
        self._loaded = False

    def _load_model(self):
        """Lazy-load the ECAPA-TDNN model."""
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                logger.info("Loading ECAPA-TDNN speaker embedding model...")
                from speechbrain.inference.speaker import EncoderClassifier
                from speechbrain.utils.fetching import LocalStrategy
                from config import get_models_dir

                from pathlib import Path
                save_dir = self._model_dir or str(get_models_dir() / "ecapa-tdnn")
                source_path = save_dir if (Path(save_dir) / "hyperparams.yaml").exists() else "speechbrain/spkrec-ecapa-voxceleb"

                from models.hardware import HardwareManager
                device = HardwareManager.get_embedder_device()

                try:
                    self._model = EncoderClassifier.from_hparams(
                        source=source_path,
                        savedir=save_dir,
                        run_opts={"device": device},
                        local_strategy=LocalStrategy.COPY,
                    )
                except Exception as dev_err:
                    if device != "cpu":
                        logger.warning("ECAPA-TDNN failed on %s (%s), falling back to CPU...", device, dev_err)
                        device = "cpu"
                        self._model = EncoderClassifier.from_hparams(
                            source=source_path,
                            savedir=save_dir,
                            run_opts={"device": "cpu"},
                            local_strategy=LocalStrategy.COPY,
                        )
                    else:
                        raise dev_err

                self._loaded = True
                logger.info("ECAPA-TDNN model loaded from %s (device=%s)", save_dir, device)
            except Exception as e:
                logger.error("Failed to load ECAPA-TDNN: %s", e)
                raise

    def prewarm(self):
        """Pre-load model and run a dummy forward pass to eliminate cold-start lag."""
        try:
            self._load_model()
            dummy_audio = np.zeros(8000, dtype=np.float32)
            _ = self.get_embedding(dummy_audio)
            logger.info("SpeakerEmbedder pre-warmed successfully (zero cold-start delay)")
        except Exception as e:
            logger.warning("SpeakerEmbedder pre-warm warning: %s", e)

    def get_embedding(self, audio: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
        """Extract a speaker embedding from an audio segment.
        
        Args:
            audio: Float32 mono audio array (at least 0.5 seconds).
            sample_rate: Sample rate of the audio.
            
        Returns:
            L2-normalized 192-dimensional embedding vector as np.ndarray.
            
        Raises:
            ValueError: If audio is too short.
        """
        self._load_model()
        import torch

        min_samples = int(sample_rate * 0.5)
        if len(audio) < min_samples:
            raise ValueError(
                f"Audio too short for embedding: {len(audio)} samples "
                f"(need at least {min_samples})"
            )

        try:
            target_device = getattr(self._model, 'device', 'cpu')
            # Convert to torch tensor on target device
            waveform = torch.from_numpy(audio).float().unsqueeze(0).to(target_device)  # [1, T]

            # Extract embedding with zero tracking overhead
            with torch.inference_mode():
                embedding = self._model.encode_batch(waveform)  # [1, 1, 192]

            # Convert to numpy and L2-normalize
            emb = embedding.squeeze().detach().cpu().numpy()  # [192]
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm

            return emb.astype(np.float32)
        except Exception as e:
            logger.error("Embedding extraction error: %s", e)
            raise

    def get_embeddings_batch(
        self, audio_segments: list, sample_rate: int = 16000
    ) -> list:
        """Extract embeddings from multiple audio segments.
        
        Args:
            audio_segments: List of float32 mono audio arrays.
            sample_rate: Sample rate of the audio.
            
        Returns:
            List of 192-dim embedding vectors.
        """
        return [self.get_embedding(seg, sample_rate) for seg in audio_segments]

    def is_loaded(self) -> bool:
        """Whether the model is loaded in memory."""
        return self._loaded

    def unload(self):
        """Release the model from memory."""
        with self._lock:
            self._model = None
            self._loaded = False
            logger.info("ECAPA-TDNN model unloaded")
