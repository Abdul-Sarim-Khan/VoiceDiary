"""pywebview API bridge — connects JavaScript frontend to Python backend.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import json
import logging
import threading
import os
import sys
import time

logger = logging.getLogger(__name__)


class Api:
    """API class exposed to JavaScript via pywebview.
    
    All public methods are callable from JS as:
        await window.pywebview.api.method_name(args)
    """

    def __init__(self):
        self._window = None
        self._live_pipeline = None
        self._file_pipeline = None
        self._db = None
        self._matcher = None
        self._model_manager = None
        self._embedder = None
        self._transcriber = None
        self._transcript = []
        self._lock = threading.Lock()
        self._initialized = False
        self._model_switch_lock = threading.Lock()
        self._target_model = None

    def set_window(self, window):
        """Set the pywebview window reference."""
        self._window = window

    def _push_to_js(self, callback_name, data):
        """Push data to a JavaScript callback function safely."""
        if self._window:
            try:
                json_data = json.dumps(data, ensure_ascii=False, default=str)
                self._window.evaluate_js(
                    f'if(window.{callback_name}){{window.{callback_name}({json_data})}}'
                )
            except Exception as e:
                # Handle window close / disposal cleanly
                logger.debug('Push to JS skipped (%s): %s', callback_name, e)

    def initialize_app(self):
        """Initialize the application: load database, check models, pre-warm."""
        try:
            from config import ensure_dirs, get_database_path, DEFAULT_WHISPER_MODEL
            from speakers.database import SpeakerDatabase
            from speakers.matcher import SpeakerMatcher
            from models.model_manager import ModelManager

            ensure_dirs()

            # Load speaker database
            self._db = SpeakerDatabase(str(get_database_path()))
            self._db.load()
            self._matcher = SpeakerMatcher(self._db)

            # Check models
            self._model_manager = ModelManager()
            status = self._model_manager.check_models_available()
            models_ready = status.get('ecapa_available', False) and status.get('whisper_available', False)

            # Load settings
            self._load_settings()

            # Background Pre-Warming Thread to ensure zero cold-start delay
            def prewarm_worker():
                try:
                    logger.info("Starting background AI model pre-warming...")
                    from models.embedder import SpeakerEmbedder
                    from models.transcriber import Transcriber
                    from audio.vad import VoiceActivityDetector

                    model_size = self._settings.get('whisper_model', DEFAULT_WHISPER_MODEL) if self._settings else DEFAULT_WHISPER_MODEL

                    vad = VoiceActivityDetector()
                    vad._load_model()
                    self._embedder = SpeakerEmbedder()
                    self._embedder.prewarm()
                    self._transcriber = Transcriber(model_size=model_size)
                    self._transcriber.prewarm()
                    logger.info("Background pre-warming finished successfully (all models ready in RAM/GPU).")
                except Exception as e:
                    logger.warning("Pre-warm warning (will load on demand): %s", e)

            threading.Thread(target=prewarm_worker, daemon=True).start()

            self._initialized = True
            speakers = self._db.get_all_speakers()
            active_model = self._settings.get('whisper_model', 'base') if self._settings else 'base'
            active_lang = self._settings.get('language', 'auto') if self._settings else 'auto'

            from models.hardware import HardwareManager
            hw_info = HardwareManager.get_hardware_info()

            return {
                'success': True,
                'models_ready': models_ready,
                'speakers': speakers,
                'available_models': status.get('available_whisper_models', ['base']),
                'active_model': active_model,
                'active_language': active_lang,
                'hardware': hw_info,
            }
        except Exception as e:
            logger.error('Initialization error: %s', e, exc_info=True)
            return {'success': False, 'message': str(e), 'models_ready': False, 'speakers': [], 'active_model': 'base', 'active_language': 'auto', 'hardware': {}}

    def get_hardware_info(self):
        """Returns active hardware acceleration and device info."""
        try:
            from models.hardware import HardwareManager
            return {'success': True, 'hardware': HardwareManager.get_hardware_info()}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def set_language_mode(self, language_mode: str):
        """Switch language output mode dynamically ('auto' / 'roman', 'ur', 'en')."""
        try:
            logger.info("Requested language mode switch to: %s", language_mode)
            if not self._settings:
                self._load_settings()

            self._settings['language'] = language_mode
            self._save_settings()

            if self._live_pipeline:
                self._live_pipeline._language = language_mode

            self._push_to_js('onLanguageChanged', {'language': language_mode})
            return {'success': True, 'language': language_mode}
        except Exception as e:
            logger.error('set_language_mode error: %s', e)
            return {'success': False, 'message': str(e)}

    def set_active_model(self, model_name: str):
        """Switch active Whisper model dynamically on the fly with pre-warming."""
        try:
            logger.info("Requested model switch to: %s", model_name)
            if not self._settings:
                self._load_settings()

            self._settings['whisper_model'] = model_name
            self._save_settings()
            self._target_model = model_name

            def switch_worker():
                with self._model_switch_lock:
                    target = self._target_model
                    if not target:
                        return
                    try:
                        self._push_to_js('onModelSwitching', {'model': target, 'status': 'loading'})
                        from models.transcriber import Transcriber
                        if self._transcriber is None:
                            self._transcriber = Transcriber(model_size=target)
                        else:
                            self._transcriber.change_model(target)
                        
                        self._transcriber.prewarm()
                        logger.info("Model '%s' is now fully pre-warmed and active.", target)
                        self._push_to_js('onModelChanged', {'model': target, 'status': 'ready'})
                    except Exception as ex:
                        logger.error("Error switching model to %s: %s", target, ex)
                        self._push_to_js('onModelChanged', {'model': target, 'status': 'error', 'error': str(ex)})

            threading.Thread(target=switch_worker, daemon=True).start()
            return {'success': True, 'model': model_name, 'message': f'Switching to {model_name}...'}
        except Exception as e:
            logger.error('set_active_model error: %s', e)
            return {'success': False, 'message': str(e)}

    def start_recording(self, device=None):
        """Start live microphone recording and transcription."""
        try:
            if self._live_pipeline:
                return {'success': False, 'message': 'Already recording'}

            from pipeline.live_pipeline import LivePipeline

            self._transcript = []
            
            model_size = self._settings.get('whisper_model', 'base') if self._settings else 'base'
            lang = self._settings.get('language', 'auto') if self._settings else 'auto'
            target_lang = lang

            # If transcriber is missing or different, initialize / update
            if self._transcriber is None:
                from models.transcriber import Transcriber
                self._transcriber = Transcriber(model_size=model_size)
            elif self._transcriber._model_size != model_size:
                self._transcriber.change_model(model_size)

            def on_live_result(data):
                if isinstance(data, dict) and data.get('action') == 'update':
                    idx = data.get('index', -1)
                    entry = data.get('entry', {})
                    if 0 <= idx < len(self._transcript):
                        self._transcript[idx] = entry
                    self._push_to_js('onTranscriptUpdated', data)
                    return

                entry = data.get('entry', data) if isinstance(data, dict) and 'entry' in data else data
                self._transcript.append(entry)
                self._push_to_js('onTranscriptUpdate', entry)

            self._live_pipeline = LivePipeline(
                on_result=on_live_result,
                on_speaker=lambda s: self._push_to_js('onSpeakerDetected', s),
                on_state_change=lambda st: self._push_to_js('onRecordingStateChanged', st),
                on_audio_level=lambda lvl: self._push_to_js('onAudioLevel', lvl),
                db=self._db,
                matcher=self._matcher,
                whisper_model=model_size,
                language=target_lang,
                embedder=self._embedder,
                transcriber=self._transcriber,
            )

            dev_idx = None
            if device is not None:
                try:
                    dev_idx = int(device)
                except (ValueError, TypeError):
                    dev_idx = None

            self._live_pipeline.start(device=dev_idx)
            return {'success': True, 'message': 'Recording started'}
        except Exception as e:
            logger.error('Start recording error: %s', e, exc_info=True)
            return {'success': False, 'message': str(e)}

    def get_audio_devices(self):
        """Get available microphone input devices."""
        try:
            from audio.capture import AudioCapture
            return AudioCapture.get_devices()
        except Exception as e:
            logger.error('Get audio devices error: %s', e)
            return []

    def stop_recording(self):
        """Stop recording and return the transcript."""
        try:
            if not self._live_pipeline:
                return {'success': False, 'message': 'Not recording', 'transcript': []}

            transcript = self._live_pipeline.stop()
            self._transcript = transcript or []
            self._live_pipeline = None

            if self._db:
                self._db.load()

            # Auto-persist completed lecture session to binary Protobuf
            if self._transcript:
                self._save_session_protobuf(self._transcript, session_name="Live Classroom Lecture")

            return {'success': True, 'transcript': self._transcript}
        except Exception as e:
            logger.error('Stop recording error: %s', e, exc_info=True)
            self._live_pipeline = None
            return {'success': False, 'message': str(e), 'transcript': []}

    def _save_session_protobuf(self, transcript, session_name="Classroom Lecture"):
        """Save a completed transcript session into a binary Protobuf (.pb) file."""
        if not transcript:
            return
        try:
            from config import get_sessions_dir
            from proto import voicediary_pb2
            import time

            sessions_dir = get_sessions_dir()
            sessions_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time())
            session_id = f"session_{timestamp}"
            pb_session = voicediary_pb2.TranscriptSession(
                session_id=session_id,
                session_name=session_name,
                created_at=timestamp,
            )

            for item in transcript:
                entry = pb_session.entries.add()
                entry.speaker_id = int(item.get("speaker_id", 0))
                entry.speaker_name = str(item.get("speaker_name", "Speaker"))
                entry.speaker_color = str(item.get("speaker_color", "#6366F1"))
                entry.text = str(item.get("text", ""))
                entry.language = str(item.get("language", "auto"))
                entry.start_time = float(item.get("start_time", 0.0))
                entry.end_time = float(item.get("end_time", 0.0))
                entry.timestamp = int(item.get("timestamp", timestamp))

            pb_path = sessions_dir / f"{session_id}.pb"
            with open(pb_path, "wb") as f:
                f.write(pb_session.SerializeToString())
            logger.info("Saved lecture session to binary Protobuf file: %s", pb_path)
        except Exception as e:
            logger.warning("Failed to save session protobuf: %s", e)

    def pause_recording(self):
        """Pause live recording."""
        try:
            if self._live_pipeline:
                self._live_pipeline.pause()
                return {'success': True}
            return {'success': False, 'message': 'Not recording'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def resume_recording(self):
        """Resume live recording."""
        try:
            if self._live_pipeline:
                self._live_pipeline.resume()
                return {'success': True}
            return {'success': False, 'message': 'Not recording'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def process_file(self, file_path):
        """Process an audio file for transcription."""
        try:
            from pipeline.file_pipeline import FilePipeline

            self._transcript = []
            model_size = self._settings.get('whisper_model', 'base') if self._settings else 'base'
            lang = self._settings.get('language', 'auto') if self._settings else 'auto'
            target_lang = None if lang == 'auto' else lang

            self._file_pipeline = FilePipeline(
                on_result=lambda e: (self._transcript.append(e),
                                     self._push_to_js('onTranscriptUpdate', e)),
                on_speaker=lambda s: self._push_to_js('onSpeakerDetected', s),
                on_progress=lambda p: self._push_to_js('onFileProcessingProgress', p),
                db=self._db,
                matcher=self._matcher,
                whisper_model=model_size,
                language=target_lang,
            )
            self._file_pipeline.process(file_path)
            self._push_to_js('onRecordingStateChanged', 'processing')
            return {'success': True, 'message': f'Processing {os.path.basename(file_path)}'}
        except Exception as e:
            logger.error('File processing error: %s', e, exc_info=True)
            return {'success': False, 'message': str(e)}

    def rename_speaker(self, speaker_id, new_name):
        """Rename a speaker."""
        try:
            if self._db:
                sp_id = int(speaker_id)
                new_n = str(new_name).strip()
                success = self._db.rename_speaker(sp_id, new_n)
                if success:
                    self._db.save()
                    if self._matcher:
                        self._matcher.invalidate_cache()

                    # Update in-memory transcript items
                    for entry in self._transcript:
                        if entry.get('speaker_id') == sp_id:
                            entry['speaker_name'] = new_n

                    speaker = self._db.get_speaker(sp_id)
                    if speaker:
                        self._push_to_js('onSpeakerUpdated', speaker)
                return {'success': success}
            return {'success': False, 'message': 'Database not loaded'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def delete_speaker(self, speaker_id):
        """Delete a speaker."""
        try:
            if self._db:
                sp_id = int(speaker_id)
                success = self._db.delete_speaker(sp_id)
                if success:
                    self._db.save()
                    if self._matcher:
                        self._matcher.invalidate_cache()
                    self._push_to_js('onSpeakerDeleted', {'id': sp_id})
                return {'success': success}
            return {'success': False, 'message': 'Database not loaded'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def clear_all_speakers(self):
        """Wipes all speakers from the database."""
        try:
            if self._db:
                self._db.clear_all()
                if self._matcher:
                    self._matcher.invalidate_cache()
                self._push_to_js('onSpeakersCleared', {})
                return {'success': True}
            return {'success': False, 'message': 'Database not loaded'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_speakers(self):
        """Get all known speakers."""
        try:
            if self._db:
                return self._db.get_all_speakers()
            return []
        except Exception as e:
            logger.error('Get speakers error: %s', e)
            return []

    def get_settings(self):
        """Get current application settings."""
        try:
            self._load_settings()
            return self._settings or {
                'whisper_model': 'base',
                'similarity_threshold': 0.38,
                'language': 'auto',
                'vad_threshold': 0.50,
                'max_embeddings': 20,
            }
        except Exception as e:
            logger.error('Get settings error: %s', e)
            return {}

    def update_settings(self, settings):
        """Update application settings."""
        try:
            old_model = self._settings.get('whisper_model', 'base') if self._settings else 'base'
            new_model = settings.get('whisper_model', old_model)

            self._settings = settings
            self._save_settings()
            if self._matcher and 'similarity_threshold' in settings:
                self._matcher.update_threshold(float(settings['similarity_threshold']))

            # If model changed, trigger switch
            if new_model != old_model:
                self.set_active_model(new_model)

            return {'success': True}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def download_model(self, model_name):
        """Trigger background download of a chosen Whisper model with progress."""
        try:
            if not self._model_manager:
                from models.model_manager import ModelManager
                self._model_manager = ModelManager()

            def run_dl():
                self._model_manager.download_whisper_model(
                    model_size=model_name,
                    progress_callback=lambda p: self._push_to_js('onModelDownloadProgress', p)
                )

            threading.Thread(target=run_dl, daemon=True).start()
            return {'success': True, 'message': f'Downloading {model_name}...'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def generate_ai_summary(self, client_transcript=None, lecture_title="Classroom Lecture"):
        """Generates structured lecture summary and flashcards using Google Gemini 2.5 Flash."""
        try:
            transcript_data = client_transcript if (client_transcript and len(client_transcript) > 0) else self._transcript
            if not transcript_data or len(transcript_data) == 0:
                return {'success': False, 'message': 'No transcript content to summarize.'}

            from models.gemini_summarizer import GeminiSummarizer
            summarizer = GeminiSummarizer()
            res = summarizer.summarize_lecture(transcript_data, lecture_title=lecture_title)
            return res
        except Exception as e:
            logger.error('Gemini summarization error: %s', e, exc_info=True)
            return {'success': False, 'message': str(e)}

    def export_transcript_dialog(self, fmt='txt', client_transcript=None):
        """Open native Windows Save File Dialog to choose directory and filename."""
        try:
            transcript_data = client_transcript if (client_transcript and len(client_transcript) > 0) else self._transcript
            if not transcript_data or len(transcript_data) == 0:
                return {'success': False, 'message': 'No transcript to export'}

            import webview
            from datetime import datetime

            timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
            default_filename = f"VoiceDiary_LectureNotes_{timestamp_str}.{fmt}"

            filters = {
                'txt': 'Text Documents (*.txt)',
                'md': 'Markdown Notes (*.md)',
                'srt': 'SubRip Subtitles (*.srt)',
                'json': 'JSON Files (*.json)',
            }
            file_filter = (filters.get(fmt, 'All Files (*.*)'),)

            save_path = None
            if self._window:
                res = self._window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    save_filename=default_filename,
                    file_types=file_filter,
                )
                if res:
                    save_path = res if isinstance(res, str) else res[0]

            if not save_path:
                return {'success': False, 'message': 'Export cancelled'}

            # Generate content
            content = self._generate_export_content(fmt, transcript=transcript_data)

            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return {
                'success': True,
                'message': f'Saved to {os.path.basename(save_path)}',
                'path': save_path,
            }
        except Exception as e:
            logger.error('Export dialog error: %s', e, exc_info=True)
            return {'success': False, 'message': str(e)}

    def _generate_export_content(self, fmt, transcript=None):
        """Format transcript into chosen file format with copyright header."""
        from datetime import datetime
        import json
        header_time = datetime.now().strftime("%B %d, %Y - %I:%M %p")
        copyright_line = "VoiceDiary © Abdul Sarim Khan. All Rights Reserved."
        items = transcript if transcript is not None else self._transcript

        if fmt == 'md':
            lines = [
                f"# Classroom Lecture Notes — VoiceDiary",
                f"**Date:** {header_time}  ",
                f"**System:** {copyright_line}  ",
                "",
                "---",
                "",
                "## Transcript & Diarization",
                ""
            ]
            for e in items:
                ts = self._format_time(e.get('start_time', 0))
                speaker = e.get('speaker_name', 'Speaker')
                text = e.get('text', '')
                lines.append(f"- **`[{ts}]` {speaker}:** {text}")
            lines.append("")
            lines.append("---")
            lines.append(f"*{copyright_line}*")
            return '\n'.join(lines)

        elif fmt == 'srt':
            lines = []
            for i, e in enumerate(items, 1):
                start = self._format_time(e.get('start_time', 0))
                end = self._format_time(e.get('end_time', e.get('start_time', 0) + 2.0))
                speaker = e.get('speaker_name', 'Speaker')
                text = e.get('text', '')
                lines.append(f"{i}\n{start},000 --> {end},000\n[{speaker}] {text}\n")
            return '\n'.join(lines)

        elif fmt == 'json':
            data = {
                "app": "VoiceDiary",
                "copyright": copyright_line,
                "exported_at": header_time,
                "total_entries": len(items),
                "transcript": items,
            }
            return json.dumps(data, ensure_ascii=False, indent=2)

        else: # Default TXT
            lines = [
                "===========================================================",
                f"VoiceDiary Lecture Notes — {header_time}",
                copyright_line,
                "===========================================================",
                "",
            ]
            for e in items:
                ts = self._format_time(e.get('start_time', 0))
                speaker = e.get('speaker_name', 'Speaker')
                text = e.get('text', '')
                lines.append(f"[{ts}] {speaker}: {text}")
            lines.append("")
            lines.append("===========================================================")
            lines.append(copyright_line)
            return '\n'.join(lines)

    def select_file(self):
        """Open a file dialog to select an audio file."""
        try:
            import webview
            if self._window:
                result = self._window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    file_types=('Audio Files (*.wav;*.mp3;*.flac;*.ogg;*.m4a)',),
                )
                if result and len(result) > 0:
                    return {'success': True, 'path': result[0]}
            return {'success': False, 'message': 'No file selected'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def get_model_status(self):
        """Check model availability."""
        try:
            if self._model_manager:
                return self._model_manager.check_models_available()
            return {'ecapa_available': False, 'whisper_available': False}
        except Exception:
            return {'ecapa_available': False, 'whisper_available': False}

    def get_app_info(self):
        """Get application information and copyright."""
        from config import APP_NAME, APP_VERSION
        return {
            'name': APP_NAME,
            'version': APP_VERSION,
            'copyright': 'VoiceDiary © Abdul Sarim Khan. All Rights Reserved.',
            'speakers_count': self._db.speaker_count() if self._db else 0,
        }

    # === Private Helpers ===

    def _load_settings(self):
        """Load settings from protobuf file."""
        try:
            from config import get_settings_path, DEFAULT_SIMILARITY_THRESHOLD, DEFAULT_WHISPER_MODEL
            path = get_settings_path()
            if path.exists():
                from proto import voicediary_pb2
                settings_pb = voicediary_pb2.Settings()
                with open(str(path), 'rb') as f:
                    settings_pb.ParseFromString(f.read())
                self._settings = {
                    'whisper_model': settings_pb.whisper_model or DEFAULT_WHISPER_MODEL,
                    'similarity_threshold': settings_pb.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD,
                    'language': settings_pb.language or 'auto',
                    'vad_threshold': settings_pb.vad_threshold or 0.50,
                    'max_embeddings': settings_pb.max_embeddings or 20,
                }
            else:
                self._settings = {
                    'whisper_model': DEFAULT_WHISPER_MODEL,
                    'similarity_threshold': DEFAULT_SIMILARITY_THRESHOLD,
                    'language': 'auto',
                    'vad_threshold': 0.50,
                    'max_embeddings': 20,
                }
        except Exception as e:
            logger.error('Load settings error: %s', e)
            self._settings = {
                'whisper_model': 'base', 'similarity_threshold': 0.38,
                'language': 'auto', 'vad_threshold': 0.50, 'max_embeddings': 20,
            }

    def _save_settings(self):
        """Save settings to protobuf file."""
        try:
            from config import get_settings_path
            from proto import voicediary_pb2

            settings_pb = voicediary_pb2.Settings()
            s = self._settings or {}
            settings_pb.whisper_model = s.get('whisper_model', 'base')
            settings_pb.similarity_threshold = float(s.get('similarity_threshold', 0.38))
            settings_pb.language = s.get('language', 'auto')
            settings_pb.vad_threshold = float(s.get('vad_threshold', 0.50))
            settings_pb.max_embeddings = int(s.get('max_embeddings', 20))

            path = get_settings_path()
            with open(str(path), 'wb') as f:
                f.write(settings_pb.SerializeToString())
            logger.info('Settings saved')
        except Exception as e:
            logger.error('Save settings error: %s', e)

    @staticmethod
    def _format_time(seconds):
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f'{h:02d}:{m:02d}:{s:02d}'
        return f'{m:02d}:{s:02d}'

    @staticmethod
    def _srt_time(seconds):
        ms = int((seconds % 1) * 1000)
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
