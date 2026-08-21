"""Model download and cache management for VoiceDiary.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages downloading and caching of ML models.
    
    Checks if required models are available locally and handles
    downloading them with progress reporting.
    """

    MODEL_REPOS = {
        "tiny": "Systran/faster-whisper-tiny",
        "base": "Systran/faster-whisper-base",
        "small": "Systran/faster-whisper-small",
        "medium": "Systran/faster-whisper-medium",
        "large-v3-turbo": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
    }

    MODEL_DIR_PATTERNS = {
        "tiny": ["faster-whisper-tiny"],
        "base": ["faster-whisper-base"],
        "small": ["faster-whisper-small"],
        "medium": ["faster-whisper-medium"],
        "large-v3-turbo": ["large-v3-turbo", "large-v3-turbo-ct2"],
        "distil-large-v3": ["distil-whisper-large-v3", "distil-large-v3"],
    }

    # Approximate download sizes in MB
    MODEL_SIZES = {
        "silero-vad": 2,
        "ecapa-tdnn": 80,
        "whisper-tiny": 75,
        "whisper-base": 145,
        "whisper-small": 465,
        "whisper-medium": 1500,
        "whisper-large-v3-turbo": 1600,
        "whisper-distil-large-v3": 1500,
    }

    def __init__(self):
        """Initialize the model manager."""
        from config import get_models_dir
        self._models_dir = get_models_dir()

    def check_models_available(self, model_size: str = "base") -> dict:
        """Check which models are available locally.
        
        Returns:
            Dict with model availability status and list of downloaded models.
        """
        from config import ensure_dirs, get_models_dir
        ensure_dirs()

        models_root = get_models_dir()
        ecapa_dir = models_root / "ecapa-tdnn"
        whisper_dir = models_root / "whisper"

        ecapa_available = False
        if ecapa_dir.exists():
            files = (
                list(ecapa_dir.rglob("*.ckpt"))
                or list(ecapa_dir.rglob("*.bin"))
                or list(ecapa_dir.rglob("*.onnx"))
                or list(ecapa_dir.rglob("hyperparams.yaml"))
            )
            ecapa_available = len(files) > 0

        whisper_available = False
        available_whisper_models = []

        for m_key, patterns in self.MODEL_DIR_PATTERNS.items():
            # 1. Direct Models/folder check
            direct_folder = models_root / m_key
            if direct_folder.exists() and (direct_folder / "model.bin").exists():
                available_whisper_models.append(m_key)
                continue

            # 2. Whisper cache folder check
            if whisper_dir.exists():
                for p in whisper_dir.iterdir():
                    if p.is_dir() and any(pat in p.name.lower() for pat in patterns):
                        weights = list(p.rglob("model.bin")) + list(p.rglob("model.safetensors"))
                        if weights:
                            available_whisper_models.append(m_key)
                            break

        whisper_available = len(available_whisper_models) > 0

        return {
            "ecapa_available": ecapa_available,
            "whisper_available": whisper_available,
            "available_whisper_models": available_whisper_models,
            "ecapa_path": str(ecapa_dir),
            "whisper_path": str(whisper_dir),
        }

    def download_whisper_model(self, model_size: str = "base", progress_callback=None) -> bool:
        """Download a faster-whisper model.
        
        Args:
            model_size: Whisper model size key.
            progress_callback: Optional callback(dict) with {model_name, percent, message}.
            
        Returns:
            True if successful.
        """
        try:
            repo_id = self.MODEL_REPOS.get(model_size, f"Systran/faster-whisper-{model_size}")
            display_name = f"Whisper {model_size.capitalize()}"

            if progress_callback:
                progress_callback({
                    "model_name": display_name,
                    "percent": 0,
                    "message": f"Downloading {display_name} model...",
                })

            from huggingface_hub import snapshot_download

            download_dir = str(self._models_dir / "whisper")
            os.makedirs(download_dir, exist_ok=True)

            logger.info("Downloading Whisper model '%s' from %s to %s", model_size, repo_id, download_dir)

            snapshot_download(
                repo_id=repo_id,
                cache_dir=download_dir,
            )

            if progress_callback:
                progress_callback({
                    "model_name": display_name,
                    "percent": 100,
                    "message": f"{display_name} model ready",
                })

            logger.info("Whisper model '%s' downloaded successfully", model_size)
            return True
        except Exception as e:
            logger.error("Whisper download failed for %s: %s", model_size, e)
            if progress_callback:
                progress_callback({
                    "model_name": f"Whisper ({model_size})",
                    "percent": -1,
                    "message": f"Download failed: {e}",
                })
            return False

    def download_ecapa_model(self, progress_callback=None) -> bool:
        """Download the ECAPA-TDNN speaker embedding model.
        
        Args:
            progress_callback: Optional callback(dict).
            
        Returns:
            True if successful.
        """
        try:
            if progress_callback:
                progress_callback({
                    "model_name": "ECAPA-TDNN (Speaker Embedding)",
                    "percent": 0,
                    "message": "Downloading speaker embedding model...",
                })

            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            save_dir = str(self._models_dir / "ecapa-tdnn")
            os.makedirs(save_dir, exist_ok=True)

            logger.info("Downloading ECAPA-TDNN to %s", save_dir)

            _ = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=save_dir,
                run_opts={"device": "cpu"},
                local_strategy=LocalStrategy.COPY,
            )

            if progress_callback:
                progress_callback({
                    "model_name": "ECAPA-TDNN (Speaker Embedding)",
                    "percent": 100,
                    "message": "Speaker embedding model ready",
                })

            logger.info("ECAPA-TDNN downloaded successfully")
            return True
        except Exception as e:
            logger.error("ECAPA-TDNN download failed: %s", e)
            if progress_callback:
                progress_callback({
                    "model_name": "ECAPA-TDNN",
                    "percent": -1,
                    "message": f"Download failed: {e}",
                })
            return False

    def download_all_models(self, model_size: str = "base", progress_callback=None) -> bool:
        """Download all required baseline models.
        
        Args:
            model_size: Whisper model size to download.
            progress_callback: Optional callback(dict).
            
        Returns:
            True if all downloads succeeded.
        """
        status = self.check_models_available()
        success = True

        if not status["ecapa_available"]:
            if not self.download_ecapa_model(progress_callback):
                success = False

        if not status["whisper_available"]:
            if not self.download_whisper_model(model_size, progress_callback):
                success = False

        return success

    def get_model_sizes(self) -> dict:
        """Get approximate download sizes for models."""
        return dict(self.MODEL_SIZES)

    def get_disk_usage(self) -> dict:
        """Get actual disk usage of cached models."""
        result = {}
        for name in ["ecapa-tdnn", "whisper"]:
            path = self._models_dir / name
            if path.exists():
                total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                result[name] = round(total / (1024 * 1024), 1)
            else:
                result[name] = 0
        return result
