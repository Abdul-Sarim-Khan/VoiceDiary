"""Hardware Detection and Dynamic Optimization Engine for VoiceDiary.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class HardwareManager:
    """Detects system hardware (NVIDIA GPU / Multi-core CPU) and configures
    optimal execution parameters for Whisper (CTranslate2), SpeechBrain, and PyTorch.
    
    Ensures 100% hardware adaptation on any PC without bottlenecks.
    """

    _initialized = False
    _cuda_available = False
    _gpu_name = ""
    _gpu_vram_gb = 0.0
    _compute_capability = (0, 0)
    _whisper_device = "cpu"
    _whisper_compute_type = "int8"
    _embedder_device = "cpu"
    _cpu_threads = 4

    @classmethod
    def initialize(cls):
        """Initializes hardware detection and sets Windows DLL search paths."""
        if cls._initialized:
            return

        # 1. Setup Windows DLL search paths for NVIDIA CUDA / cuDNN libraries
        if sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
            dll_dirs = []
            
            # Check Python site-packages for torch and nvidia wheels
            for p in sys.path:
                try:
                    p_path = Path(p)
                    torch_lib = p_path / 'torch' / 'lib'
                    if torch_lib.exists():
                        dll_dirs.append(torch_lib)
                    
                    nvidia_dir = p_path / 'nvidia'
                    if nvidia_dir.exists():
                        for sub in nvidia_dir.glob('*/bin'):
                            if sub.is_dir():
                                dll_dirs.append(sub)
                except Exception:
                    pass

            # Check system CUDA_PATH
            cuda_path = os.environ.get('CUDA_PATH')
            if cuda_path:
                cuda_bin = Path(cuda_path) / 'bin'
                if cuda_bin.exists():
                    dll_dirs.append(cuda_bin)

            # Check local app folder if frozen
            if getattr(sys, 'frozen', False):
                app_dir = Path(sys.executable).resolve().parent
                for sub in [app_dir, app_dir / '_internal', app_dir / '_internal' / 'torch' / 'lib']:
                    if sub.exists():
                        dll_dirs.append(sub)

            for d in dll_dirs:
                try:
                    os.add_dll_directory(str(d))
                except Exception:
                    pass

        # 2. CPU Thread Allocation & Thread Thrashing Protection
        cpu_count = os.cpu_count() or 4
        # Allocate optimal compute threads while leaving headroom for UI & I/O
        if cpu_count > 8:
            cls._cpu_threads = 6
        elif cpu_count > 4:
            cls._cpu_threads = max(2, cpu_count - 2)
        else:
            cls._cpu_threads = max(1, cpu_count)

        # Set OpenMP and MKL thread limits to prevent thread thrashing
        os.environ['OMP_NUM_THREADS'] = str(cls._cpu_threads)
        os.environ['MKL_NUM_THREADS'] = str(cls._cpu_threads)
        os.environ['OPENBLAS_NUM_THREADS'] = str(cls._cpu_threads)
        os.environ['VECLIB_MAXIMUM_THREADS'] = str(cls._cpu_threads)
        os.environ['NUMEXPR_NUM_THREADS'] = str(cls._cpu_threads)

        # 3. Probe CUDA capabilities
        cuda_found = False

        # Probe PyTorch CUDA
        try:
            import torch
            if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                cuda_found = True
                cls._gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                cls._gpu_vram_gb = round(props.total_memory / (1024 ** 3), 2)
                cls._compute_capability = (props.major, props.minor)
                cls._embedder_device = "cuda"
        except Exception as ex:
            logger.debug("PyTorch CUDA check: %s", ex)

        # Probe CTranslate2 CUDA
        ct2_cuda = False
        try:
            import ctranslate2
            if hasattr(ctranslate2, 'get_cuda_device_count') and ctranslate2.get_cuda_device_count() > 0:
                ct2_cuda = True
        except Exception as ex:
            logger.debug("CTranslate2 CUDA check: %s", ex)

        # Probe physical GPU cards on Windows if not already identified
        if not cls._gpu_name and sys.platform == 'win32':
            try:
                import subprocess
                res = subprocess.run(
                    ['powershell', '-Command', 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'],
                    capture_output=True, text=True, timeout=2
                )
                for line in res.stdout.strip().splitlines():
                    line = line.strip()
                    if line and 'virtual' not in line.lower() and 'citrix' not in line.lower():
                        cls._gpu_name = line
                        break
            except Exception:
                pass

        if cuda_found or ct2_cuda:
            cls._cuda_available = True
            cls._whisper_device = "cuda"
            # Tensor Core architectures (Turing / Ampere / Ada Lovelace / Hopper / Blackwell >= 7.0)
            if cls._compute_capability[0] >= 7 or (cls._compute_capability == (0, 0) and ct2_cuda):
                cls._whisper_compute_type = "float16"
            else:
                # Older Pascal / Maxwell GPUs perform faster on int8 or float32
                cls._whisper_compute_type = "int8"

            logger.info(
                "NVIDIA GPU Acceleration ACTIVATED: %s (%.1f GB VRAM, Compute %d.%d) | Whisper: device=cuda, compute=%s | SpeechBrain: device=%s",
                cls._gpu_name or "NVIDIA GPU",
                cls._gpu_vram_gb,
                cls._compute_capability[0],
                cls._compute_capability[1],
                cls._whisper_compute_type,
                cls._embedder_device
            )
        else:
            cls._cuda_available = False
            cls._whisper_device = "cpu"
            cls._whisper_compute_type = "int8"
            cls._embedder_device = "cpu"
            logger.info(
                "Multi-Core CPU Vectorization ACTIVATED (%d logical cores, %d worker threads) | Whisper: device=cpu, compute=int8 (AVX2/AVX-512) | Installed GPU: %s",
                cpu_count,
                cls._cpu_threads,
                cls._gpu_name or "Integrated"
            )

        cls._initialized = True

    @classmethod
    def get_whisper_config(cls) -> Dict[str, Any]:
        """Returns optimal configuration dict for faster_whisper.WhisperModel."""
        cls.initialize()
        return {
            "device": cls._whisper_device,
            "compute_type": cls._whisper_compute_type,
            "cpu_threads": cls._cpu_threads,
        }

    @classmethod
    def get_embedder_device(cls) -> str:
        """Returns optimal device ('cuda' or 'cpu') for SpeechBrain ECAPA-TDNN."""
        cls.initialize()
        return cls._embedder_device

    @classmethod
    def get_hardware_info(cls) -> Dict[str, Any]:
        """Returns hardware telemetry for UI presentation."""
        cls.initialize()
        if cls._cuda_available:
            label = f"⚡ GPU: {cls._gpu_name}"
        elif cls._gpu_name:
            label = f"🚀 CPU: {cls._cpu_threads} Threads (AVX2) | GPU: {cls._gpu_name}"
        else:
            label = f"🚀 CPU: {cls._cpu_threads} Threads (INT8 AVX2)"

        return {
            "cuda_available": cls._cuda_available,
            "gpu_name": cls._gpu_name or "Integrated Graphics",
            "gpu_vram_gb": cls._gpu_vram_gb,
            "compute_capability": f"{cls._compute_capability[0]}.{cls._compute_capability[1]}",
            "cpu_threads": cls._cpu_threads,
            "whisper_device": cls._whisper_device,
            "whisper_compute_type": cls._whisper_compute_type,
            "embedder_device": cls._embedder_device,
            "status_label": label,
        }
