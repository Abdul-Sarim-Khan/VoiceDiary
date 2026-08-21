"""Real-time microphone transcription pipeline with speaker identification.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import logging
import threading
import queue
import time
import numpy as np

logger = logging.getLogger(__name__)


class LivePipeline:
    """Processes live microphone audio for speaker-attributed transcription.
    
    Architecture (Decoupled Multi-Threaded Pipeline):
        Thread 1: AudioCapture callback -> _audio_queue
        Thread 2 (VAD Worker): Consumes _audio_queue in real-time (<1ms) -> AudioProcessor -> _segment_queue
        Thread 3 (Inference Worker): Consumes _segment_queue (with dynamic catch-up batching) -> Transcriber + SpeakerMatcher -> UI
    """
    
    def __init__(self, on_result, on_speaker, on_state_change, on_audio_level=None, db=None, matcher=None, whisper_model='base', language=None, embedder=None, transcriber=None):
        from audio.capture import AudioCapture
        from audio.vad import VoiceActivityDetector
        from audio.processor import AudioProcessor
        from models.embedder import SpeakerEmbedder
        from models.transcriber import Transcriber
        from speakers.database import SpeakerDatabase
        from speakers.matcher import SpeakerMatcher
        from config import SAMPLE_RATE, CHUNK_DURATION_MS, get_database_path
        
        self._on_result = on_result
        self._on_speaker = on_speaker
        self._on_state_change = on_state_change
        self._on_audio_level = on_audio_level
        self._whisper_model = whisper_model
        self._language = language
        
        # High-capacity decoupled queues to prevent any dropped chunks
        self._audio_queue = queue.Queue(maxsize=3000)
        self._segment_queue = queue.Queue(maxsize=500)
        self._capture = AudioCapture(sample_rate=SAMPLE_RATE, chunk_duration_ms=CHUNK_DURATION_MS)
        
        # Core components
        self._vad = VoiceActivityDetector()
        self._processor = AudioProcessor(self._vad)
        self._embedder = embedder if embedder is not None else SpeakerEmbedder()
        self._transcriber = transcriber if transcriber is not None else Transcriber(model_size=whisper_model)
        
        if db is not None:
            self._db = db
        else:
            self._db = SpeakerDatabase(str(get_database_path()))
            self._db.load()

        if matcher is not None:
            self._matcher = matcher
        else:
            self._matcher = SpeakerMatcher(self._db)
        
        self._vad_thread = None
        self._inference_thread = None
        self._running = False
        self._paused = False
        self._transcript = []
        self._session_start = None
        self._state = 'stopped'
        self._next_speaker_num = self._db.speaker_count() + 1

    def start(self, device=None):
        """Start the live transcription pipeline with decoupled threads."""
        if self._running:
            return
        
        logger.info('Starting live pipeline (device=%s, model=%s)', device, self._whisper_model)
        self._running = True
        self._paused = False
        self._transcript = []
        self._session_start = time.time()
        self._processor.reset()
        
        # Clear any stale queue items
        while not self._audio_queue.empty():
            try: self._audio_queue.get_nowait()
            except Exception: break
        while not self._segment_queue.empty():
            try: self._segment_queue.get_nowait()
            except Exception: break

        # Start Thread 2: Real-time VAD Ingestion
        self._vad_thread = threading.Thread(target=self._vad_worker_loop, daemon=True)
        self._vad_thread.start()

        # Start Thread 3: Asynchronous AI Inference
        self._inference_thread = threading.Thread(target=self._inference_worker_loop, daemon=True)
        self._inference_thread.start()

        # Start Thread 1: Hardware Audio Capture
        self._capture.start(self._on_audio_chunk, device=device)
        self._set_state('recording')

    def stop(self):
        """Stop the pipeline and return transcript."""
        logger.info('Stopping live pipeline')
        self._running = False
        self._capture.stop()
        
        # Send sentinels
        try: self._audio_queue.put_nowait(None)
        except Exception: pass

        if self._vad_thread and self._vad_thread.is_alive():
            self._vad_thread.join(timeout=1.0)

        try: self._segment_queue.put_nowait(None)
        except Exception: pass

        if self._inference_thread and self._inference_thread.is_alive():
            self._inference_thread.join(timeout=2.0)
        
        self._set_state('stopped')
        try:
            self._db.save()
        except Exception as e:
            logger.error(f'DB save error on stop: {e}')

        return self._transcript

    def pause(self):
        self._paused = True
        self._capture.pause()
        self._set_state('paused')

    def resume(self):
        self._paused = False
        self._capture.resume()
        self._set_state('recording')

    def get_state(self):
        return self._state

    def _set_state(self, state):
        self._state = state
        try:
            self._on_state_change(state)
        except Exception as e:
            logger.error(f'State change callback error: {e}')

    def _on_audio_chunk(self, chunk, rms=0.0):
        """Hardware callback from AudioCapture (runs on audio driver thread)."""
        if self._running and not self._paused:
            try:
                self._audio_queue.put_nowait(chunk)
                if self._on_audio_level:
                    self._on_audio_level(rms)
            except queue.Full:
                logger.warning('Audio queue full, dropping chunk')

    def _vad_worker_loop(self):
        """Thread 2: Consumes raw audio chunks in real-time and segments speech."""
        logger.info('VAD ingestion worker started')
        
        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if chunk is None:
                rem = self._processor.flush()
                if rem is not None and len(rem) > 0:
                    self._segment_queue.put(rem)
                break

            segments = self._processor.feed(chunk)
            for seg in segments:
                try:
                    self._segment_queue.put_nowait(seg)
                except queue.Full:
                    logger.warning('Segment queue full, dropping segment')

        logger.info('VAD ingestion worker stopped')

    def _inference_worker_loop(self):
        """Thread 3: Consumes speech segments and performs Whisper + Speaker identification."""
        logger.info('Inference worker started')

        while self._running or not self._segment_queue.empty():
            try:
                first_seg = self._segment_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if first_seg is None:
                break

            # Dynamic Batching / Catch-Up: If multiple segments accumulated while model was transcribing,
            # combine them into one unified contiguous audio array!
            accumulated = [first_seg]
            while not self._segment_queue.empty():
                try:
                    next_seg = self._segment_queue.get_nowait()
                    if next_seg is None:
                        break
                    # Keep max batch length to 10 seconds for coherent transcript sentences
                    if sum(len(s) for s in accumulated) + len(next_seg) <= 16000 * 10:
                        accumulated.append(next_seg)
                    else:
                        # Re-queue for next iteration
                        self._segment_queue.put(next_seg)
                        break
                except queue.Empty:
                    break

            unified_segment = np.concatenate(accumulated) if len(accumulated) > 1 else first_seg
            self._process_segment(unified_segment)

        logger.info('Inference worker stopped')

    def _process_segment(self, audio_segment):
        """Process a single audio segment: embed + identify + transcribe."""
        try:
            current_time = time.time() - (self._session_start or time.time())
            segment_duration = len(audio_segment) / 16000
            
            # Transcribe first
            result = self._transcriber.transcribe(audio_segment, language=self._language)
            text = result.get('text', '').strip()
            language = result.get('language', 'unknown')
            
            # If no meaningful speech text was transcribed, skip noise/artifacts
            if not text:
                return
            
            # Get speaker embedding
            embedding = self._embedder.get_embedding(audio_segment)
            
            # Identify speaker
            speaker_id, speaker_name, confidence = self._matcher.identify(embedding)
            
            if speaker_id is None:
                # If segment is short (<1.4s) and we already have an active speaker, attribute to last speaker
                if segment_duration < 1.4 and self._matcher.last_speaker_id is not None:
                    speaker_id = self._matcher.last_speaker_id
                    speaker_info = self._db.get_speaker(speaker_id)
                    speaker_name = speaker_info['name'] if speaker_info else f'Speaker {speaker_id}'
                    speaker_color = speaker_info['color'] if speaker_info else '#6366F1'
                else:
                    # New speaker
                    name = f'Speaker {self._next_speaker_num}'
                    self._next_speaker_num += 1
                    speaker_id = self._db.add_speaker(name)
                    self._db.add_embedding(speaker_id, embedding, duration=segment_duration, confidence=confidence)
                    speaker_info = self._db.get_speaker(speaker_id)
                    speaker_name = name
                    speaker_color = speaker_info['color'] if speaker_info else '#6366F1'
                    self._matcher.invalidate_cache()
                    
                    self._on_speaker({
                        'id': speaker_id, 'name': speaker_name,
                        'color': speaker_color, 'embedding_count': 1, 'is_active': True
                    })
            else:
                # Known speaker - Continual Learning / Adaptive Diversity Update
                if segment_duration >= 0.8:
                    self._db.add_embedding(speaker_id, embedding, duration=segment_duration, confidence=confidence)
                    self._matcher.invalidate_cache()
                    
                speaker_info = self._db.get_speaker(speaker_id)
                if speaker_info:
                    speaker_name = speaker_info['name']
                    speaker_color = speaker_info['color']
                    emb_count = speaker_info.get('embedding_count', 1)
                    self._on_speaker({
                        'id': speaker_id,
                        'name': speaker_name,
                        'color': speaker_color,
                        'embedding_count': max(1, emb_count),
                        'is_active': True
                    })
                else:
                    speaker_color = '#6366F1'

            start_time = max(0, current_time - segment_duration)
            end_time = current_time

            # Smart Paragraph Merging for Professor Lecture Flow
            if self._transcript:
                last = self._transcript[-1]
                gap = start_time - last.get('end_time', 0.0)
                if last.get('speaker_id') == speaker_id and gap <= 3.5:
                    last['text'] = last['text'] + (" " if last['text'] else "") + text
                    last['end_time'] = end_time
                    self._on_result({'action': 'update', 'entry': dict(last), 'index': len(self._transcript) - 1})
                    return

            entry = {
                'speaker_id': speaker_id,
                'speaker_name': speaker_name,
                'speaker_color': speaker_color,
                'text': text,
                'language': language,
                'start_time': start_time,
                'end_time': end_time,
            }
            self._transcript.append(entry)
            self._on_result({'action': 'add', 'entry': dict(entry)})
                
        except Exception as e:
            logger.error(f'Error processing segment: {e}', exc_info=True)
