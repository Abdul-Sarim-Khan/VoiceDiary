"""Audio file processing pipeline with speaker identification."""
import logging
import threading
import time
import numpy as np

logger = logging.getLogger(__name__)


class FilePipeline:
    """Processes audio files for speaker-attributed transcription."""
    
    def __init__(self, on_result, on_speaker, on_progress, db=None, matcher=None, whisper_model='base', language=None):
        """
        Args:
            on_result: callback(dict) same as LivePipeline
            on_speaker: callback(dict) same as LivePipeline
            on_progress: callback(dict) with {percent, processed_seconds, total_seconds}
            db: Shared SpeakerDatabase instance (optional)
            matcher: Shared SpeakerMatcher instance (optional)
            whisper_model: Whisper model size
            language: Target language
        """
        from audio.file_loader import load_audio_file
        from audio.vad import VoiceActivityDetector
        from models.embedder import SpeakerEmbedder
        from models.transcriber import Transcriber
        from speakers.database import SpeakerDatabase
        from speakers.matcher import SpeakerMatcher
        from config import SAMPLE_RATE, DEFAULT_SIMILARITY_THRESHOLD, get_database_path
        
        self._on_result = on_result
        self._on_speaker = on_speaker
        self._on_progress = on_progress
        self._load_audio = load_audio_file
        self._whisper_model = whisper_model
        self._language = language
        
        self._vad = VoiceActivityDetector()
        self._embedder = SpeakerEmbedder()
        self._transcriber = Transcriber(model_size=whisper_model)

        if db is not None:
            self._db = db
        else:
            self._db = SpeakerDatabase(str(get_database_path()))
            self._db.load()

        if matcher is not None:
            self._matcher = matcher
        else:
            self._matcher = SpeakerMatcher(self._db)
        
        self._processing = False
        self._cancelled = False
        self._thread = None
        self._transcript = []
        self._next_speaker_num = self._db.speaker_count() + 1
    
    def process(self, file_path):
        """Process an audio file in a background thread."""
        if self._processing:
            return []
        
        self._processing = True
        self._cancelled = False
        self._transcript = []
        
        self._thread = threading.Thread(target=self._process_file, args=(file_path,), daemon=True)
        self._thread.start()
        return self._transcript
    
    def cancel(self):
        self._cancelled = True
    
    def is_processing(self):
        return self._processing
    
    def _process_file(self, file_path):
        try:
            logger.info(f'Processing file: {file_path}')
            audio, sr = self._load_audio(file_path, target_sr=16000)
            total_duration = len(audio) / sr
            
            # Get speech timestamps via VAD
            timestamps = self._vad.get_speech_timestamps(audio, sample_rate=sr)
            
            if not timestamps:
                logger.warning('No speech detected in file')
                self._on_progress({'percent': 100, 'processed_seconds': total_duration, 'total_seconds': total_duration})
                self._processing = False
                return
            
            # Merge close timestamps (gap < 0.5s)
            merged = []
            for ts in timestamps:
                if merged and (ts['start'] - merged[-1]['end']) < int(0.5 * sr):
                    merged[-1]['end'] = ts['end']
                else:
                    merged.append({'start': ts['start'], 'end': ts['end']})
            
            # Process each speech segment
            for i, ts in enumerate(merged):
                if self._cancelled:
                    break
                
                segment = audio[ts['start']:ts['end']]
                seg_start = ts['start'] / sr
                seg_end = ts['end'] / sr
                seg_duration = seg_end - seg_start
                
                # Skip very short segments
                if seg_duration < 1.0:
                    continue
                
                # Split long segments into manageable chunks
                max_chunk = 10 * sr  # 10 seconds
                chunks = []
                if len(segment) > max_chunk:
                    for j in range(0, len(segment), max_chunk):
                        chunks.append((segment[j:j+max_chunk], seg_start + j/sr))
                else:
                    chunks = [(segment, seg_start)]
                
                for chunk, chunk_start in chunks:
                    if self._cancelled:
                        break
                    if len(chunk) < sr:  # skip < 1s
                        continue
                    
                    chunk_duration = len(chunk) / sr
                    
                    # Transcribe first
                    result = self._transcriber.transcribe(chunk, language=self._language)
                    text = result.get('text', '').strip()
                    lang = result.get('language', '')
                    
                    if not text:
                        continue

                    # Embed
                    embedding = self._embedder.get_embedding(chunk)
                    
                    # Identify
                    spk_id, spk_name, confidence = self._matcher.identify(embedding)
                    
                    if spk_id is None:
                        name = f'Speaker {self._next_speaker_num}'
                        self._next_speaker_num += 1
                        spk_id = self._db.add_speaker(name)
                        self._db.add_embedding(spk_id, embedding, duration=chunk_duration, confidence=confidence)
                        info = self._db.get_speaker(spk_id)
                        spk_name = name
                        spk_color = info['color'] if info else '#EF4E6A'
                        self._matcher.invalidate_cache()
                        self._on_speaker({'id': spk_id, 'name': spk_name, 'color': spk_color, 'embedding_count': 1, 'is_active': True})
                    else:
                        self._db.add_embedding(spk_id, embedding, duration=chunk_duration, confidence=confidence)
                        info = self._db.get_speaker(spk_id)
                        spk_color = info['color'] if info else '#EF4E6A'
                        self._matcher.invalidate_cache()
                        self._on_speaker({'id': spk_id, 'name': spk_name, 'color': spk_color,
                                         'embedding_count': info['embedding_count'] if info else 0, 'is_active': True})
                    
                    entry = {
                        'speaker_id': spk_id, 'speaker_name': spk_name, 'speaker_color': spk_color,
                        'text': text, 'language': lang,
                        'start_time': chunk_start, 'end_time': chunk_start + chunk_duration,
                    }
                    self._transcript.append(entry)
                    self._on_result(entry)
                
                # Progress
                progress = min(100, int((i + 1) / len(merged) * 100))
                self._on_progress({'percent': progress, 'processed_seconds': seg_end, 'total_seconds': total_duration})
            
            self._db.save()
            self._on_progress({'percent': 100, 'processed_seconds': total_duration, 'total_seconds': total_duration})
            
        except Exception as e:
            logger.error(f'File processing error: {e}', exc_info=True)
        finally:
            self._processing = False
