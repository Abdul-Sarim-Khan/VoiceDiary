import logging
import threading
import numpy as np
from typing import Optional, Tuple, Dict
from speakers.database import SpeakerDatabase
from config import DEFAULT_SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

def l2_normalize(x: np.ndarray) -> np.ndarray:
    """L2 normalizes a numpy array."""
    norm = np.linalg.norm(x)
    if norm == 0:
        return x
    return x / norm

class SpeakerMatcher:
    """High-speed vectorized speaker identification via cosine similarity matrix operations."""

    def __init__(self, database: SpeakerDatabase, threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.database = database
        self.threshold = threshold
        self.lock = threading.RLock()
        self.centroids: Dict[int, np.ndarray] = {}
        self.speaker_matrices: Dict[int, np.ndarray] = {}
        self.last_speaker_id: Optional[int] = None
        self.last_speaker_time: float = 0.0
        self._cache_valid = False
        
        self.invalidate_cache()

    def _compute_centroids(self) -> None:
        """Recomputes normalized centroid and exemplar matrix for each speaker."""
        with self.lock:
            all_embeddings = self.database.get_all_embeddings()
            self.centroids.clear()
            self.speaker_matrices.clear()
            
            for speaker_id, embeddings in all_embeddings.items():
                if not embeddings:
                    continue
                    
                # Stack and L2 normalize matrix in one C-call
                raw_mat = np.array(embeddings, dtype=np.float32)
                norms = np.linalg.norm(raw_mat, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                norm_mat = raw_mat / norms
                
                self.speaker_matrices[speaker_id] = norm_mat
                
                # Compute and normalize centroid
                mean_emb = np.mean(norm_mat, axis=0)
                c_norm = np.linalg.norm(mean_emb)
                self.centroids[speaker_id] = mean_emb / (c_norm if c_norm > 0 else 1.0)
                
            self._cache_valid = True
            logger.debug("Vectorized matrices built for %d speakers", len(self.centroids))

    def invalidate_cache(self) -> None:
        """Forces centroid and matrix recomputation."""
        with self.lock:
            self._cache_valid = False

    def update_threshold(self, threshold: float) -> None:
        """Updates the similarity threshold."""
        with self.lock:
            self.threshold = threshold
            logger.info("SpeakerMatcher threshold updated to %.2f", threshold)

    def identify(self, embedding: np.ndarray) -> Tuple[Optional[int], Optional[str], float]:
        """Identifies the speaker from the embedding using vectorized matrix dot products.
        
        Returns (speaker_id, speaker_name, confidence).
        """
        import time
        with self.lock:
            if not self._cache_valid:
                self._compute_centroids()
                
            if not self.centroids:
                return None, None, 0.0
                
            target = l2_normalize(embedding.astype(np.float32))
            
            best_id = None
            best_score = -1.0
            now = time.time()
            
            for speaker_id, centroid in self.centroids.items():
                # 1. Centroid dot product
                centroid_score = float(np.dot(centroid, target))
                
                # 2. Vectorized exemplar matrix dot product
                mat = self.speaker_matrices.get(speaker_id)
                if mat is not None and len(mat) > 0:
                    scores = np.dot(mat, target)  # Matrix-vector multiplication (BLAS C-level)
                    k = min(3, len(scores))
                    top_k_scores = np.partition(scores, -k)[-k:]
                    top_avg = float(np.mean(top_k_scores))
                    max_single = float(np.max(scores))
                    score = max(centroid_score, top_avg * 0.85 + max_single * 0.15)
                else:
                    score = centroid_score

                # Conversational continuity boost (+0.04) if recently active within 10s
                if self.last_speaker_id == speaker_id and (now - self.last_speaker_time) < 10.0:
                    score += 0.04

                if score > best_score:
                    best_score = score
                    best_id = speaker_id
            
            if best_id is not None and best_score >= self.threshold:
                self.last_speaker_id = best_id
                self.last_speaker_time = now
                speaker_info = self.database.get_speaker(best_id)
                name = speaker_info['name'] if speaker_info else f"Speaker {best_id}"
                return best_id, name, best_score
            else:
                return None, None, max(0.0, best_score)
