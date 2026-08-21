"""Real-time microphone audio capture using sounddevice."""
import logging
import threading
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures audio from the microphone in real-time using sounddevice.
    
    Streams audio at a configurable sample rate and chunk size,
    delivering float32 mono audio chunks via a callback function.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, chunk_duration_ms: int = 500):
        """Initialize audio capture.
        
        Args:
            sample_rate: Audio sample rate in Hz (default 16000).
            channels: Number of audio channels (default 1, mono).
            chunk_duration_ms: Duration of each audio chunk in milliseconds.
        """
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_samples = int(sample_rate * chunk_duration_ms / 1000)
        self._callback = None
        self._stream = None
        self._recording = False
        self._paused = False
        self._lock = threading.Lock()

    def start(self, callback, device: Optional[int] = None):
        """Start recording audio from the microphone with universal driver resilience.
        
        Args:
            callback: Function that receives (audio_chunk, rms_level).
            device: Audio input device index (optional).
        """
        import sounddevice as sd

        with self._lock:
            if self._recording:
                logger.warning("Already recording")
                return
            self._callback = callback
            self._paused = False
            try:
                # 1. Try direct 16000 Hz input stream
                self._stream = sd.InputStream(
                    device=device,
                    samplerate=self._sample_rate,
                    channels=self._channels,
                    dtype="float32",
                    blocksize=self._chunk_samples,
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._recording = True
                logger.info(
                    "Recording started directly (device=%s, sr=%d, chunk=%d samples)",
                    device,
                    self._sample_rate,
                    self._chunk_samples,
                )
            except Exception as e:
                logger.warning("16kHz direct input failed (%s). Attempting native driver rate fallback...", e)
                try:
                    dev_info = sd.query_devices(device, kind='input')
                    native_sr = int(dev_info.get('default_samplerate', 44100))
                    native_block = int(native_sr * (self._chunk_samples / self._sample_rate))

                    def resampled_callback(indata, frames, time_info, status):
                        if status:
                            logger.warning("Audio status: %s", status)
                        if not self._paused and self._callback:
                            try:
                                mono = indata[:, 0].copy()
                                from scipy.signal import resample_poly
                                gcd = int(np.gcd(self._sample_rate, native_sr))
                                up = self._sample_rate // gcd
                                down = native_sr // gcd
                                resampled = resample_poly(mono, up, down).astype(np.float32)
                                rms = float(np.sqrt(np.mean(resampled ** 2)))
                                self._callback(resampled, rms)
                            except Exception as ex:
                                logger.error("Resampling audio callback error: %s", ex)

                    self._stream = sd.InputStream(
                        device=device,
                        samplerate=native_sr,
                        channels=self._channels,
                        dtype="float32",
                        blocksize=native_block,
                        callback=resampled_callback,
                    )
                    self._stream.start()
                    self._recording = True
                    logger.info("Recording started via native driver rate fallback (%d Hz -> 16000 Hz)", native_sr)
                except Exception as ex2:
                    logger.error("Failed to start audio capture even with native rate fallback: %s", ex2)
                    self._recording = False
                    raise ex2

    def _audio_callback(self, indata, frames, time_info, status):
        """sounddevice callback — runs in audio thread."""
        if status:
            logger.warning("Audio status: %s", status)
        if not self._paused and self._callback:
            try:
                mono = indata[:, 0].copy()
                rms = float(np.sqrt(np.mean(mono ** 2)))
                self._callback(mono, rms)
            except Exception as e:
                logger.error("Audio callback error: %s", e)

    def stop(self):
        """Stop recording and release the audio stream."""
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.error("Error stopping stream: %s", e)
                finally:
                    self._stream = None
            self._recording = False
            self._paused = False
            logger.info("Recording stopped")

    def pause(self):
        """Pause recording (audio is silently discarded)."""
        self._paused = True
        logger.info("Recording paused")

    def resume(self):
        """Resume recording after pause."""
        self._paused = False
        logger.info("Recording resumed")

    def is_recording(self) -> bool:
        """Whether the capture is actively recording."""
        return self._recording

    def is_paused(self) -> bool:
        """Whether the capture is paused."""
        return self._paused

    @staticmethod
    def get_devices() -> list:
        """List available audio input devices.
        
        Returns:
            List of dicts with keys: index, name, channels.
        """
        import sounddevice as sd

        devices = sd.query_devices()
        result = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                result.append(
                    {
                        "index": i,
                        "name": d["name"],
                        "channels": d["max_input_channels"],
                    }
                )
        return result
