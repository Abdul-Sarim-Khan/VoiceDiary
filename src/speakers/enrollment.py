import logging
import threading
import numpy as np
from typing import Optional, Dict

from speakers.database import SpeakerDatabase
from models.embedder import SpeakerEmbedder
from audio.vad import VoiceActivityDetector
from config import SAMPLE_RATE

logger = logging.getLogger(__name__)

class SpeakerEnrollment:
    """Speaker enrollment workflow."""

    def __init__(self, embedder: SpeakerEmbedder, database: SpeakerDatabase, vad: VoiceActivityDetector):
        self.embedder = embedder
        self.database = database
        self.vad = vad
        self.lock = threading.RLock()
        
        self.target_duration = 15.0  # seconds
        self.min_duration = 10.0
        
        self._active = False
        self._speaker_name = ""
        self._collected_audio = []
        self._collected_duration = 0.0

    def start(self, speaker_name: str) -> None:
        """Starts a new enrollment session."""
        with self.lock:
            self._active = True
            self._speaker_name = speaker_name
            self._collected_audio = []
            self._collected_duration = 0.0
            logger.info(f"Started enrollment for speaker: {speaker_name}")

    def add_audio(self, audio_chunk: np.ndarray) -> Dict:
        """
        Adds audio to the enrollment session.
        Returns {status, duration_collected, target_duration}
        """
        with self.lock:
            if not self._active:
                return {
                    'status': 'inactive',
                    'duration_collected': 0.0,
                    'target_duration': self.target_duration
                }
                
            is_speech, prob = self.vad.is_speech(audio_chunk, SAMPLE_RATE)
            if is_speech:
                self._collected_audio.append(audio_chunk)
                duration = len(audio_chunk) / SAMPLE_RATE
                self._collected_duration += duration
                
            status = 'ready' if self._collected_duration >= self.target_duration else 'collecting'
            
            return {
                'status': status,
                'duration_collected': self._collected_duration,
                'target_duration': self.target_duration
            }

    def finish(self) -> Optional[int]:
        """
        Finishes enrollment, extracts embeddings, stores in database.
        Returns speaker_id if successful.
        """
        with self.lock:
            if not self._active:
                return None
                
            if self._collected_duration < self.min_duration:
                logger.warning(f"Enrollment failed: not enough audio ({self._collected_duration:.2f}s < {self.min_duration}s)")
                self.cancel()
                return None
                
            # Concatenate all speech segments
            if not self._collected_audio:
                self.cancel()
                return None
                
            full_audio = np.concatenate(self._collected_audio)
            
            # Create a new speaker
            speaker_id = self.database.add_speaker(self._speaker_name)
            
            # We want to extract 3-5 embeddings. Let's do chunks of 3 seconds.
            chunk_samples = int(3.0 * SAMPLE_RATE)
            num_chunks = len(full_audio) // chunk_samples
            
            # If we don't even have 1 full chunk, just embed the whole thing
            if num_chunks == 0:
                embedding = self.embedder.get_embedding(full_audio, sample_rate=SAMPLE_RATE)
                self.database.add_embedding(speaker_id, embedding, duration=len(full_audio)/SAMPLE_RATE)
            else:
                # Limit to 5 chunks to avoid making too many embeddings at once
                num_chunks = min(num_chunks, 5)
                for i in range(num_chunks):
                    start = i * chunk_samples
                    end = start + chunk_samples
                    chunk = full_audio[start:end]
                    embedding = self.embedder.get_embedding(chunk, sample_rate=SAMPLE_RATE)
                    self.database.add_embedding(speaker_id, embedding, duration=3.0)
                    
            logger.info(f"Enrollment finished successfully for {self._speaker_name} (ID: {speaker_id})")
            self._active = False
            return speaker_id

    def cancel(self) -> None:
        """Cancels the active enrollment."""
        with self.lock:
            self._active = False
            self._collected_audio = []
            self._collected_duration = 0.0
            self._speaker_name = ""
            logger.info("Enrollment cancelled.")

    def is_active(self) -> bool:
        """Returns True if enrollment is in progress."""
        with self.lock:
            return self._active
