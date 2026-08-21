import os
import time
import struct
import shutil
import logging
import threading
import numpy as np
from typing import Optional, List, Dict

from proto import voicediary_pb2
from config import get_database_path, SPEAKER_COLORS, MAX_EMBEDDINGS_PER_SPEAKER

logger = logging.getLogger(__name__)

class SpeakerDatabase:
    """Speaker profile database using Protocol Buffers."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database with the given path or default."""
        self.db_path = str(db_path) if db_path else str(get_database_path())
        dir_name = os.path.dirname(self.db_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        self.lock = threading.RLock()
        self.db = voicediary_pb2.SpeakerDatabase()
        self._color_index = 0
        self.load()

    def load(self) -> None:
        """Loads from .pb file."""
        with self.lock:
            if os.path.exists(self.db_path):
                try:
                    with open(self.db_path, 'rb') as f:
                        self.db.ParseFromString(f.read())
                    logger.info(f"Loaded speaker database from {self.db_path}")
                except Exception as e:
                    logger.error(f"Failed to load speaker database: {e}")
            else:
                self.db.next_speaker_id = 1
                logger.info(f"Created new speaker database at {self.db_path}")

    def save(self) -> None:
        """Saves to .pb file (atomic write: write to .tmp then rename)."""
        with self.lock:
            try:
                tmp_path = self.db_path + '.tmp'
                with open(tmp_path, 'wb') as f:
                    f.write(self.db.SerializeToString())
                
                if os.path.exists(self.db_path):
                    # Windows requires the target to be removed or replaced explicitly
                    # os.replace works atomically on Windows
                    os.replace(tmp_path, self.db_path)
                else:
                    os.rename(tmp_path, self.db_path)
                logger.debug(f"Saved speaker database to {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to save speaker database: {e}")

    def add_speaker(self, name: str, color: Optional[str] = None) -> int:
        """Adds a new speaker and returns speaker_id."""
        with self.lock:
            speaker = self.db.speakers.add()
            speaker.id = self.db.next_speaker_id
            self.db.next_speaker_id += 1
            speaker.name = name
            
            if not color:
                color = SPEAKER_COLORS[self._color_index % len(SPEAKER_COLORS)]
                self._color_index += 1
            speaker.color = color
            
            now = int(time.time() * 1000)
            speaker.created_at = now
            speaker.updated_at = now
            
            self.save()
            return speaker.id

    def _get_speaker_proto(self, speaker_id: int):
        for speaker in self.db.speakers:
            if speaker.id == speaker_id:
                return speaker
        return None

    def rename_speaker(self, speaker_id: int, new_name: str) -> bool:
        """Renames a speaker."""
        with self.lock:
            speaker = self._get_speaker_proto(speaker_id)
            if speaker:
                speaker.name = new_name
                speaker.updated_at = int(time.time() * 1000)
                self.save()
                return True
            return False

    def delete_speaker(self, speaker_id: int) -> bool:
        """Deletes a speaker."""
        with self.lock:
            for i, speaker in enumerate(self.db.speakers):
                if speaker.id == speaker_id:
                    del self.db.speakers[i]
                    self.save()
                    return True
            return False

    def clear_all(self) -> bool:
        """Wipes all enrolled speakers and voiceprints."""
        with self.lock:
            del self.db.speakers[:]
            self.db.next_speaker_id = 1
            self._color_index = 0
            self.save()
            logger.info("Cleared all speakers from database.")
            return True

    def merge_speakers(self, keep_id: int, merge_id: int) -> bool:
        """Merges two speaker profiles into one."""
        with self.lock:
            if keep_id == merge_id:
                return False
                
            keep_speaker = self._get_speaker_proto(keep_id)
            merge_speaker = self._get_speaker_proto(merge_id)
            
            if not keep_speaker or not merge_speaker:
                return False
                
            # Move embeddings
            for emb in merge_speaker.embeddings:
                new_emb = keep_speaker.embeddings.add()
                new_emb.CopyFrom(emb)
                
            # Limit embeddings
            if len(keep_speaker.embeddings) > MAX_EMBEDDINGS_PER_SPEAKER:
                sorted_embs = sorted(keep_speaker.embeddings, key=lambda x: x.timestamp)
                del keep_speaker.embeddings[:]
                for emb in sorted_embs[-MAX_EMBEDDINGS_PER_SPEAKER:]:
                    new_emb = keep_speaker.embeddings.add()
                    new_emb.CopyFrom(emb)
                    
            keep_speaker.updated_at = int(time.time() * 1000)
            
            # Delete merged speaker
            self.delete_speaker(merge_id)
            return True

    def add_embedding(self, speaker_id: int, embedding: np.ndarray, duration: float = 0, confidence: float = 0, max_similarity_threshold: float = 0.98) -> bool:
        """Adds a unique voice print embedding to the speaker's memory buffer.
        
        Ensures stored embeddings are diverse (uniqueness check). If the buffer reaches
        MAX_EMBEDDINGS_PER_SPEAKER (50), intelligently prunes the most redundant embedding.
        """
        with self.lock:
            speaker = self._get_speaker_proto(speaker_id)
            if not speaker:
                return False

            emb_norm = embedding / (np.linalg.norm(embedding) or 1.0)
            
            # Check uniqueness against existing voice prints
            existing_vectors = []
            for emb in speaker.embeddings:
                floats = struct.unpack(f'{len(emb.vector)//4}f', emb.vector)
                v = np.array(floats, dtype=np.float32)
                v_norm = v / (np.linalg.norm(v) or 1.0)
                existing_vectors.append(v_norm)

            if existing_vectors:
                sims = [float(np.dot(emb_norm, ex)) for ex in existing_vectors]
                max_sim = max(sims)
                max_idx = int(np.argmax(sims))
                
                # If almost identical (> 0.95 similarity), update existing entry if this one has higher confidence
                if max_sim >= max_similarity_threshold:
                    target_emb = speaker.embeddings[max_idx]
                    if confidence > target_emb.confidence or duration > target_emb.audio_duration:
                        vec_bytes = struct.pack(f'{len(embedding)}f', *embedding)
                        target_emb.vector = vec_bytes
                        target_emb.confidence = max(target_emb.confidence, confidence)
                        target_emb.audio_duration = max(target_emb.audio_duration, duration)
                        target_emb.timestamp = int(time.time() * 1000)
                        speaker.updated_at = int(time.time() * 1000)
                        self.save()
                    return True

            # It is a novel unique voice print -> Add to speaker profile
            emb_proto = speaker.embeddings.add()
            vec_bytes = struct.pack(f'{len(embedding)}f', *embedding)
            emb_proto.vector = vec_bytes
            emb_proto.audio_duration = duration
            emb_proto.confidence = confidence
            emb_proto.timestamp = int(time.time() * 1000)

            # If buffer exceeds 100, prune the most redundant exemplar (highest pairwise similarity)
            if len(speaker.embeddings) > MAX_EMBEDDINGS_PER_SPEAKER:
                all_v = []
                for emb in speaker.embeddings:
                    floats = struct.unpack(f'{len(emb.vector)//4}f', emb.vector)
                    v = np.array(floats, dtype=np.float32)
                    all_v.append(v / (np.linalg.norm(v) or 1.0))
                
                # Compute pairwise cosine similarity matrix
                M = np.array(all_v)
                sim_matrix = M @ M.T
                np.fill_diagonal(sim_matrix, -1.0)
                
                # Find pair with highest similarity
                idx1, idx2 = np.unravel_index(np.argmax(sim_matrix), sim_matrix.shape)
                
                # Drop the one with lower confidence / shorter duration
                e1 = speaker.embeddings[idx1]
                e2 = speaker.embeddings[idx2]
                drop_idx = idx1 if (e1.confidence <= e2.confidence) else idx2
                del speaker.embeddings[drop_idx]

            speaker.updated_at = int(time.time() * 1000)
            self.save()
            return True

    def get_all_speakers(self) -> List[Dict]:
        """Returns list of {id, name, color, embedding_count, created_at}."""
        with self.lock:
            return [
                {
                    'id': s.id,
                    'name': s.name,
                    'color': s.color,
                    'embedding_count': len(s.embeddings),
                    'created_at': s.created_at
                }
                for s in self.db.speakers
            ]

    def get_speaker(self, speaker_id: int) -> Optional[Dict]:
        """Returns info dict for a single speaker."""
        with self.lock:
            speaker = self._get_speaker_proto(speaker_id)
            if speaker:
                return {
                    'id': speaker.id,
                    'name': speaker.name,
                    'color': speaker.color,
                    'embedding_count': len(speaker.embeddings),
                    'created_at': speaker.created_at
                }
            return None

    def get_speaker_embeddings(self, speaker_id: int) -> List[np.ndarray]:
        """Returns list of embeddings as numpy arrays."""
        with self.lock:
            speaker = self._get_speaker_proto(speaker_id)
            result = []
            if speaker:
                for emb in speaker.embeddings:
                    vec_len = len(emb.vector) // 4
                    vec_array = np.array(struct.unpack(f'{vec_len}f', emb.vector))
                    result.append(vec_array)
            return result

    def get_all_embeddings(self) -> Dict[int, List[np.ndarray]]:
        """Returns {speaker_id: list[np.ndarray]}."""
        with self.lock:
            return {s.id: self.get_speaker_embeddings(s.id) for s in self.db.speakers}

    def speaker_count(self) -> int:
        """Returns total number of speakers."""
        with self.lock:
            return len(self.db.speakers)
