/* VoiceDiary Frontend
   VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
*/
'use strict';

const state = {
    mode: 'live',
    recordingState: 'stopped',
    speakers: [],
    transcript: [],
    settings: {},
    activeModel: 'base',
    activeLanguage: 'auto',
    sessionStart: null,
    timerInterval: null,
    scrollLocked: false,
    renamingSpeakerId: null,
    searchQuery: '',
};

const MODEL_NAMES = {
    'tiny': 'Whisper Tiny (39M)',
    'base': 'Whisper Base (74M)',
    'small': 'Whisper Small (244M)',
    'medium': 'Whisper Medium (769M)',
    'large-v3-turbo': 'Whisper Turbo (809M)',
    'distil-large-v3': 'Distil-Whisper (756M)',
};

const LANG_NAMES = {
    'auto': 'Bilingual (Urdu + EN)',
    'bilingual': 'Bilingual (Urdu + EN)',
    'ur': 'Pure Urdu (اردو)',
    'en': 'English Only',
    'roman': 'Roman Urdu',
};

window.onTranscriptUpdate = function(entry) {
    state.transcript.push(entry);
    const target = state.mode === 'live' ? 'transcriptList' : 'fileTranscriptList';
    addTranscriptEntry(entry, target);
};

window.onTranscriptUpdated = function(data) {
    const idx = data.index;
    const entry = data.entry;
    if (idx >= 0 && idx < state.transcript.length) {
        state.transcript[idx] = entry;
    }
    const targetId = state.mode === 'live' ? 'transcriptList' : 'fileTranscriptList';
    const list = document.getElementById(targetId);
    if (!list) return;

    const items = list.querySelectorAll('.transcript-item');
    if (items.length > 0) {
        const lastItem = items[items.length - 1];
        lastItem.dataset.text = (entry.text || '').toLowerCase();
        const textEl = lastItem.querySelector('.transcript-text');
        if (textEl) {
            const isUrduScript = /[\u0600-\u06FF]/.test(entry.text || '');
            textEl.className = 'transcript-text' + (isUrduScript ? ' rtl' : '');
            textEl.textContent = entry.text;
        }
        const timeEl = lastItem.querySelector('.transcript-time');
        if (timeEl) {
            timeEl.textContent = `[${formatTimestamp(entry.start_time || 0)}]`;
        }
        const scrollContainer = list.parentElement;
        if (scrollContainer && !state.scrollLocked) {
            scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }
    }
};

window.onSpeakerDetected = function(speaker) {
    const idx = state.speakers.findIndex(s => s.id === speaker.id);
    if (idx >= 0) {
        state.speakers[idx] = { ...state.speakers[idx], ...speaker };
    } else {
        state.speakers.push(speaker);
    }
    renderSpeakers();
};

window.onSpeakerUpdated = function(speaker) {
    const idx = state.speakers.findIndex(s => s.id === speaker.id);
    if (idx >= 0) {
        state.speakers[idx] = { ...state.speakers[idx], ...speaker };
        renderSpeakers();
    }
};

window.onRecordingStateChanged = function(newState) {
    state.recordingState = newState;
    updateRecordingUI(newState);
};

window.onModelSwitching = function(info) {
    const activeLabel = document.getElementById('activeModelName');
    if (activeLabel) {
        activeLabel.textContent = `Loading ${info.model}...`;
    }
};

window.onModelChanged = function(info) {
    if (info.status === 'ready') {
        state.activeModel = info.model;
        updateActiveModelUI(info.model);
        showToast(`AI Model switched to ${MODEL_NAMES[info.model] || info.model}`, 'success');
    } else if (info.status === 'error') {
        showToast(`Model load error: ${info.error || 'Failed'}`, 'error');
        updateActiveModelUI(state.activeModel);
    }
};

window.onLanguageChanged = function(info) {
    state.activeLanguage = info.language;
    updateActiveLanguageUI(info.language);
    showToast(`Language Mode: ${LANG_NAMES[info.language] || info.language}`, 'success');
};

window.onModelDownloadProgress = function(progress) {
    const modal = document.getElementById('downloadModal');
    const nameEl = document.getElementById('downloadModelName');
    const barEl = document.getElementById('downloadProgress');
    const msgEl = document.getElementById('downloadMessage');

    if (progress.percent >= 100) {
        modal.style.display = 'none';
        showToast(progress.model_name ? `${progress.model_name} is ready!` : 'Model ready!', 'success');
        return;
    }
    if (progress.percent < 0) {
        modal.style.display = 'none';
        showToast(progress.message || 'Model download failed', 'error');
        return;
    }

    modal.style.display = 'flex';
    nameEl.textContent = progress.model_name || 'Downloading Model...';
    barEl.style.width = Math.max(5, progress.percent) + '%';
    msgEl.textContent = progress.message || 'Downloading weights to local cache...';
};

window.onError = function(error) {
    showToast(error.message || error.details || 'An error occurred', 'error');
};

window.onFileProcessingProgress = function(progress) {
    const progDiv = document.getElementById('fileProgress');
    const textEl = document.getElementById('fileProgressText');
    const barEl = document.getElementById('fileProgressBar');
    const detailEl = document.getElementById('fileProgressDetail');

    progDiv.classList.remove('hidden');

    if (progress.percent >= 100) {
        textEl.textContent = 'Lecture processing complete!';
        barEl.style.width = '100%';
        detailEl.textContent = '';
        state.recordingState = 'stopped';
        updateRecordingUI('stopped');
        setTimeout(() => progDiv.classList.add('hidden'), 2500);
        return;
    }

    textEl.textContent = `Transcribing lecture... ${progress.percent}%`;
    barEl.style.width = progress.percent + '%';
    const proc = progress.processed_seconds ? progress.processed_seconds.toFixed(1) : '0';
    const total = progress.total_seconds ? progress.total_seconds.toFixed(1) : '?';
    detailEl.textContent = `${proc}s / ${total}s processed`;
};

/* ===== Initialization ===== */

window.addEventListener('pywebviewready', async () => {
    console.log('pywebview ready');
    try {
        const result = await pywebview.api.initialize_app();
        if (result && result.success) {
            if (result.hardware) {
                updateHardwareBadgeUI(result.hardware);
            }
            if (result.speakers && result.speakers.length > 0) {
                state.speakers = result.speakers;
                renderSpeakers();
            }
            if (result.active_model) {
                state.activeModel = result.active_model;
                updateActiveModelUI(result.active_model);
            }
            if (result.active_language) {
                state.activeLanguage = result.active_language;
                updateActiveLanguageUI(result.active_language);
            }
        }
        const settings = await pywebview.api.get_settings();
        if (settings) {
            state.settings = settings;
            if (settings.whisper_model) {
                state.activeModel = settings.whisper_model;
                updateActiveModelUI(settings.whisper_model);
            }
            if (settings.language) {
                state.activeLanguage = settings.language;
                updateActiveLanguageUI(settings.language);
            }
            applySettings(settings);
        }
        await populateDevices();
    } catch (e) {
        console.error('Init error:', e);
    }
});

async function populateDevices() {
    try {
        const devices = await pywebview.api.get_audio_devices();
        const select = document.getElementById('deviceSelect');
        if (select && devices && devices.length > 0) {
            select.innerHTML = '<option value="">Default Microphone</option>';
            devices.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.id;
                opt.textContent = d.name;
                select.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn('Device list error:', e);
    }
}

function updateHardwareBadgeUI(hw) {
    const badge = document.getElementById('hwBadgePill');
    const textEl = document.getElementById('hwBadgeText');
    if (!badge || !textEl || !hw) return;

    if (hw.cuda_available) {
        badge.classList.add('gpu');
        textEl.textContent = `⚡ GPU: ${hw.gpu_name}`;
        badge.title = `NVIDIA GPU Acceleration Active (${hw.gpu_vram_gb} GB VRAM, Compute ${hw.compute_capability}) | Whisper: ${hw.whisper_compute_type.toUpperCase()} | SpeechBrain: CUDA`;
    } else {
        badge.classList.remove('gpu');
        textEl.textContent = hw.status_label || `🚀 CPU: ${hw.cpu_threads} Threads`;
        badge.title = `Multi-Core INT8 Vectorized Engine (${hw.cpu_threads} Worker Threads, AVX2/AVX-512) | System GPU: ${hw.gpu_name}`;
    }
}

/* ===== Model Switcher Controls ===== */

function toggleModelDropdown() {
    const dd = document.getElementById('modelDropdown');
    dd?.classList.toggle('hidden');
}

async function selectModel(modelKey) {
    document.getElementById('modelDropdown')?.classList.add('hidden');
    if (modelKey === state.activeModel) return;

    try {
        showToast(`Switching to ${MODEL_NAMES[modelKey] || modelKey}...`, 'info');
        const res = await pywebview.api.set_active_model(modelKey);
        if (res && res.success) {
            state.activeModel = modelKey;
            updateActiveModelUI(modelKey);
        } else {
            showToast(res?.message || 'Could not switch model', 'error');
        }
    } catch (e) {
        showToast('Error switching model: ' + e, 'error');
    }
}

function selectRadioModel(modelKey) {
    const cards = document.querySelectorAll('.radio-card');
    cards.forEach(c => {
        const input = c.querySelector('input');
        if (input) {
            if (input.value === modelKey) {
                c.classList.add('active');
                input.checked = true;
            } else {
                c.classList.remove('active');
                input.checked = false;
            }
        }
    });
}

function updateActiveModelUI(modelKey) {
    const activeLabel = document.getElementById('activeModelName');
    if (activeLabel) {
        activeLabel.textContent = MODEL_NAMES[modelKey] || modelKey.toUpperCase();
    }

    // Update Dropdown items
    const dropdownItems = document.querySelectorAll('.model-dropdown-item');
    dropdownItems.forEach(item => {
        const onclickAttr = item.getAttribute('onclick') || '';
        if (onclickAttr.includes(`'${modelKey}'`)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update radio cards in Settings
    selectRadioModel(modelKey);
}

/* ===== Language Switcher Controls ===== */

function toggleLangDropdown() {
    const dd = document.getElementById('langDropdown');
    dd?.classList.toggle('hidden');
}

async function selectLanguage(langKey) {
    document.getElementById('langDropdown')?.classList.add('hidden');
    if (langKey === state.activeLanguage) return;

    try {
        const res = await pywebview.api.set_language_mode(langKey);
        if (res && res.success) {
            state.activeLanguage = langKey;
            updateActiveLanguageUI(langKey);
            showToast(`Output set to ${LANG_NAMES[langKey] || langKey}`, 'success');
        } else {
            showToast(res?.message || 'Could not switch language', 'error');
        }
    } catch (e) {
        showToast('Error switching language: ' + e, 'error');
    }
}

function updateActiveLanguageUI(langKey) {
    const activeLabel = document.getElementById('activeLangName');
    if (activeLabel) {
        activeLabel.textContent = LANG_NAMES[langKey] || 'Roman Urdu';
    }

    // Update Dropdown items
    const dropdownItems = document.querySelectorAll('.lang-dropdown-item');
    dropdownItems.forEach(item => {
        const onclickAttr = item.getAttribute('onclick') || '';
        if (onclickAttr.includes(`'${langKey}'`)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update settings select
    const langSelect = document.getElementById('languageSelect');
    if (langSelect) {
        langSelect.value = langKey;
    }
}

// Close dropdowns when clicking outside
document.addEventListener('click', (e) => {
    const modelWrapper = document.querySelector('.model-pill-wrapper');
    const modelDropdown = document.getElementById('modelDropdown');
    if (modelWrapper && !modelWrapper.contains(e.target) && modelDropdown && !modelDropdown.classList.contains('hidden')) {
        modelDropdown.classList.add('hidden');
    }

    const langWrapper = document.querySelector('.lang-pill-wrapper');
    const langDropdown = document.getElementById('langDropdown');
    if (langWrapper && !langWrapper.contains(e.target) && langDropdown && !langDropdown.classList.contains('hidden')) {
        langDropdown.classList.add('hidden');
    }
});

/* ===== Recording Controls ===== */

async function toggleRecording() {
    if (state.recordingState === 'stopped') {
        await startRecording();
    } else if (state.recordingState === 'recording' || state.recordingState === 'paused') {
        await stopRecording();
    }
}

async function startRecording() {
    if (state.mode !== 'live') switchMode('live');
    try {
        const emptyEl = document.getElementById('emptyTranscript');
        if (emptyEl) emptyEl.classList.add('hidden');

        const selectedDevice = state.settings?.audio_device ?? null;
        const result = await pywebview.api.start_recording(selectedDevice);
        if (result && result.success) {
            state.recordingState = 'recording';
            updateRecordingUI('recording');
            startTimer();
            startMeter();
            showToast('Lecture recording active', 'info');
        } else {
            showToast(result?.message || 'Could not start recording', 'error');
        }
    } catch (e) {
        showToast('Error starting recording: ' + e, 'error');
    }
}

async function stopRecording() {
    try {
        const result = await pywebview.api.stop_recording();
        state.recordingState = 'stopped';
        updateRecordingUI('stopped');
        stopTimer();
        stopMeter();
        if (result && result.success) {
            showToast('Lecture notes captured & saved', 'success');
        }
    } catch (e) {
        showToast('Error stopping recording: ' + e, 'error');
    }
}

async function togglePause() {
    try {
        if (state.recordingState === 'recording') {
            const res = await pywebview.api.pause_recording();
            if (res && res.success) {
                state.recordingState = 'paused';
                updateRecordingUI('paused');
                showToast('Recording paused', 'info');
            }
        } else if (state.recordingState === 'paused') {
            const res = await pywebview.api.resume_recording();
            if (res && res.success) {
                state.recordingState = 'recording';
                updateRecordingUI('recording');
                showToast('Recording resumed', 'info');
            }
        }
    } catch (e) {
        showToast('Pause/Resume error: ' + e, 'error');
    }
}

function updateRecordingUI(recordingState) {
    const recordBtn = document.getElementById('recordBtn');
    const stopBtn = document.getElementById('stopBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const statusText = document.getElementById('statusText');

    if (!recordBtn) return;

    if (recordingState === 'recording') {
        recordBtn.classList.add('recording');
        recordBtn.title = 'Stop Recording';
        if (stopBtn) stopBtn.classList.remove('hidden');
        if (pauseBtn) {
            pauseBtn.classList.remove('hidden');
            pauseBtn.title = 'Pause Recording';
        }
        if (statusText) {
            statusText.textContent = 'Live Recording';
            statusText.style.color = '#EF4444';
        }
    } else if (recordingState === 'paused') {
        recordBtn.classList.remove('recording');
        if (stopBtn) stopBtn.classList.remove('hidden');
        if (pauseBtn) {
            pauseBtn.classList.remove('hidden');
            pauseBtn.title = 'Resume Recording';
        }
        if (statusText) {
            statusText.textContent = 'Paused';
            statusText.style.color = '#F59E0B';
        }
    } else if (recordingState === 'processing') {
        recordBtn.classList.remove('recording');
        if (stopBtn) stopBtn.classList.add('hidden');
        if (pauseBtn) pauseBtn.classList.add('hidden');
        if (statusText) {
            statusText.textContent = 'Processing File';
            statusText.style.color = '#6366F1';
        }
    } else {
        recordBtn.classList.remove('recording');
        recordBtn.title = 'Start Recording';
        if (stopBtn) stopBtn.classList.add('hidden');
        if (pauseBtn) pauseBtn.classList.add('hidden');
        if (statusText) {
            statusText.textContent = 'Ready';
            statusText.style.color = '#94A3B8';
        }
    }
}

/* ===== Transcript Rendering & Live Search ===== */

function addTranscriptEntry(entry, targetId) {
    const list = document.getElementById(targetId);
    if (!list) return;

    const emptyEl = list.querySelector('.empty-state');
    if (emptyEl) emptyEl.classList.add('hidden');

    const item = document.createElement('div');
    item.className = 'transcript-item';
    item.dataset.text = (entry.text || '').toLowerCase();
    item.dataset.speaker = (entry.speaker_name || '').toLowerCase();

    const color = entry.speaker_color || '#6366F1';
    item.style.setProperty('--speaker-accent', color);
    const timeStr = formatTimestamp(entry.start_time || 0);

    const isUrduScript = /[\u0600-\u06FF]/.test(entry.text || '');
    const rtlClass = isUrduScript ? ' rtl' : '';

    item.innerHTML = `
        <div style="flex: 1;">
            <div class="speaker-tag" style="color: ${color};">
                <div class="speaker-dot" style="background: ${color};"></div>
                <span>${escapeHtml(entry.speaker_name || 'Speaker')}</span>
                <span class="transcript-time">[${timeStr}]</span>
            </div>
            <div class="transcript-text${rtlClass}">${escapeHtml(entry.text)}</div>
        </div>
    `;

    // Filter check if searching
    if (state.searchQuery) {
        const matches = item.dataset.text.includes(state.searchQuery) || item.dataset.speaker.includes(state.searchQuery);
        item.style.display = matches ? 'flex' : 'none';
    }

    list.appendChild(item);

    // Auto-scroll
    const scrollContainer = list.parentElement;
    if (scrollContainer && !state.scrollLocked) {
        scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
}

function filterTranscript() {
    const query = (document.getElementById('searchInput')?.value || '').trim().toLowerCase();
    state.searchQuery = query;

    const list = document.getElementById('transcriptList');
    if (!list) return;

    const items = list.querySelectorAll('.transcript-item');
    items.forEach(item => {
        const text = item.dataset.text || '';
        const speaker = item.dataset.speaker || '';
        if (!query || text.includes(query) || speaker.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function copyAllNotes() {
    if (state.transcript.length === 0) {
        showToast('No lecture notes to copy', 'info');
        return;
    }

    const lines = state.transcript.map(e => {
        const time = formatTimestamp(e.start_time || 0);
        return `[${time}] ${e.speaker_name}: ${e.text}`;
    });

    const fullText = lines.join('\n');
    navigator.clipboard.writeText(fullText).then(() => {
        showToast('All lecture notes copied to clipboard!', 'success');
    }).catch(err => {
        showToast('Failed to copy: ' + err, 'error');
    });
}

function clearTranscript() {
    if (state.recordingState === 'recording') {
        showToast('Please stop recording before clearing', 'info');
        return;
    }
    state.transcript = [];
    const liveList = document.getElementById('transcriptList');
    if (liveList) {
        liveList.innerHTML = `
            <div class="empty-state" id="emptyTranscript">
                <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                <p>Lecture transcript will stream here</p>
                <p class="text-secondary">Click the record button below to capture live classroom speech</p>
            </div>
        `;
    }
    showToast('Lecture session cleared', 'info');
}

/* ===== Speaker List Rendering ===== */

function renderSpeakers() {
    const list = document.getElementById('speakerList');
    const countBadge = document.getElementById('speakerCount');
    if (!list) return;

    if (countBadge) countBadge.textContent = state.speakers.length;

    if (state.speakers.length === 0) {
        list.innerHTML = `
            <div class="empty-state" id="emptySpeakers">
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>
                <p>No speakers detected</p>
                <p class="text-secondary">Start recording to identify professor & students</p>
            </div>
        `;
        return;
    }

    list.innerHTML = '';
    state.speakers.forEach(s => {
        const card = document.createElement('div');
        card.className = 'speaker-card';
        const color = s.color || '#6366F1';
        const initial = (s.name || 'S').charAt(0).toUpperCase();

        card.innerHTML = `
            <div class="speaker-avatar" style="background: ${color};">${initial}</div>
            <div class="speaker-info">
                <div class="speaker-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
                <div class="speaker-meta">${s.embedding_count || 1} voice prints</div>
            </div>
            <div class="speaker-actions">
                <button class="btn-mini" onclick="openRename(${s.id}, '${escapeHtml(s.name)}')" title="Rename speaker">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
            </div>
        `;
        list.appendChild(card);
    });
}

function openRename(speakerId, currentName) {
    state.renamingSpeakerId = speakerId;
    const input = document.getElementById('renameInput');
    if (input) input.value = currentName;
    const modal = document.getElementById('renameModal');
    if (modal) modal.classList.remove('hidden');
    input?.focus();
}

function closeRename() {
    state.renamingSpeakerId = null;
    const modal = document.getElementById('renameModal');
    if (modal) modal.classList.add('hidden');
}

async function confirmRename() {
    const input = document.getElementById('renameInput');
    const newName = input?.value.trim();
    if (!newName || !state.renamingSpeakerId) return;

    try {
        const result = await pywebview.api.rename_speaker(state.renamingSpeakerId, newName);
        if (result && result.success) {
            const idx = state.speakers.findIndex(s => s.id === state.renamingSpeakerId);
            if (idx >= 0) state.speakers[idx].name = newName;
            renderSpeakers();
            showToast(`Renamed to "${newName}"`, 'success');
        } else {
            showToast('Failed to rename', 'error');
        }
    } catch (e) {
        showToast('Rename error: ' + e, 'error');
    }
    closeRename();
}

/* ===== Mode Switcher ===== */

function switchMode(mode) {
    state.mode = mode;
    const tabLive = document.getElementById('tabLive');
    const tabFile = document.getElementById('tabFile');
    const liveArea = document.getElementById('liveArea');
    const fileArea = document.getElementById('fileArea');

    if (mode === 'live') {
        tabLive?.classList.add('active');
        tabFile?.classList.remove('active');
        liveArea?.classList.remove('hidden');
        fileArea?.classList.add('hidden');
    } else {
        tabFile?.classList.add('active');
        tabLive?.classList.remove('active');
        fileArea?.classList.remove('hidden');
        liveArea?.classList.add('hidden');
    }
}

/* ===== File Upload Mode ===== */

async function browseFile() {
    try {
        const res = await pywebview.api.select_file();
        if (res && res.success && res.path) {
            processSelectedFile(res.path);
        }
    } catch (e) {
        showToast('File select error: ' + e, 'error');
    }
}

async function processSelectedFile(filePath) {
    try {
        const list = document.getElementById('fileTranscriptList');
        if (list) list.innerHTML = '';
        state.transcript = [];

        const res = await pywebview.api.process_file(filePath);
        if (res && res.success) {
            showToast(`Processing lecture file...`, 'info');
        } else {
            showToast(res?.message || 'Processing failed', 'error');
        }
    } catch (e) {
        showToast('File process error: ' + e, 'error');
    }
}

/* ===== Settings Modal & Model Selection ===== */

function openSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal) modal.classList.remove('hidden');
}

function closeSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal) modal.classList.add('hidden');
}

async function saveSettings() {
    const dev = document.getElementById('deviceSelect')?.value;
    const model = document.querySelector('input[name="model"]:checked')?.value || state.activeModel || 'base';
    const threshold = parseFloat(document.getElementById('thresholdSlider')?.value || 32) / 100;
    const language = document.getElementById('languageSelect')?.value || 'auto';
    const vadThreshold = parseFloat(document.getElementById('vadSlider')?.value || 50) / 100;

    const geminiKey = document.getElementById('geminiApiKeyInput')?.value?.trim() || '';

    const settings = {
        audio_device: dev !== '' ? dev : null,
        whisper_model: model,
        similarity_threshold: threshold,
        language: language,
        vad_threshold: vadThreshold,
        gemini_api_key: geminiKey,
        max_embeddings: 20,
    };

    try {
        const result = await pywebview.api.update_settings(settings);
        if (result && result.success) {
            state.settings = settings;
            state.activeModel = model;
            updateActiveModelUI(model);
            showToast('Settings saved successfully', 'success');
        } else {
            showToast('Failed to save settings', 'error');
        }
    } catch (e) {
        showToast('Settings error: ' + e, 'error');
    }
    closeSettings();
}

function applySettings(s) {
    if (!s) return;
    const modelKey = s.whisper_model || 'base';
    selectRadioModel(modelKey);

    const thSlider = document.getElementById('thresholdSlider');
    if (thSlider && s.similarity_threshold) {
        thSlider.value = Math.round(s.similarity_threshold * 100);
        document.getElementById('thresholdValue').textContent = s.similarity_threshold.toFixed(2);
    }

    const langSel = document.getElementById('languageSelect');
    if (langSel && s.language) langSel.value = s.language;

    const vadSlider = document.getElementById('vadSlider');
    if (vadSlider && s.vad_threshold) {
        vadSlider.value = Math.round(s.vad_threshold * 100);
        document.getElementById('vadValue').textContent = s.vad_threshold.toFixed(2);
    }

    const geminiInput = document.getElementById('geminiApiKeyInput');
    if (geminiInput && s.gemini_api_key) {
        geminiInput.value = s.gemini_api_key;
    }
}

/* ===== Audio Meter ===== */

window.onAudioLevel = function(level) {
    const meter = document.getElementById('audioMeter');
    if (!meter) return;
    const bars = meter.querySelectorAll('.meter-bar');
    if (!bars || bars.length === 0) return;

    const scaled = Math.min(1.0, level * 16);
    const activeCount = Math.min(bars.length, Math.ceil(scaled * bars.length));

    bars.forEach((bar, i) => {
        if (i < activeCount) {
            bar.style.opacity = '1';
            bar.style.background = '#6366F1';
            bar.style.transform = `scaleY(${Math.max(0.4, (i + 1) / activeCount)})`;
        } else {
            bar.style.opacity = '0.2';
            bar.style.background = 'rgba(99, 102, 241, 0.4)';
            bar.style.transform = 'scaleY(0.2)';
        }
    });
};

function startMeter() {
    document.getElementById('audioMeter')?.classList.add('active');
}

function stopMeter() {
    document.getElementById('audioMeter')?.classList.remove('active');
    const bars = document.querySelectorAll('.meter-bar');
    bars.forEach(b => {
        b.style.transform = 'scaleY(0.2)';
        b.style.opacity = '0.2';
    });
}

/* ===== Export with Native Windows Save Dialog ===== */

function toggleExportDropdown() {
    const dd = document.getElementById('exportDropdown');
    dd?.classList.toggle('hidden');
}

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const wrapper = document.querySelector('.export-wrapper');
    const dd = document.getElementById('exportDropdown');
    if (wrapper && !wrapper.contains(e.target) && dd && !dd.classList.contains('hidden')) {
        dd.classList.add('hidden');
    }
});

async function triggerExport(format) {
    document.getElementById('exportDropdown')?.classList.add('hidden');
    if (!state.transcript || state.transcript.length === 0) {
        showToast('No lecture transcript to export', 'info');
        return;
    }
    try {
        const result = await pywebview.api.export_transcript_dialog(format, state.transcript);
        if (result && result.success) {
            showToast(result.message || 'Exported successfully!', 'success');
        } else if (result && result.message && result.message !== 'Export cancelled') {
            showToast(result.message, 'error');
        }
    } catch (e) {
        showToast('Export error: ' + e, 'error');
    }
}

/* ===== Gemini AI Lecture Summarizer & Flashcards ===== */

async function triggerGeminiSummary() {
    document.getElementById('exportDropdown')?.classList.add('hidden');
    if (!state.transcript || state.transcript.length === 0) {
        showToast('Please record or load a lecture before generating a summary.', 'info');
        return;
    }

    const modal = document.getElementById('summaryModal');
    const loading = document.getElementById('summaryLoading');
    const content = document.getElementById('summaryContent');

    modal?.classList.remove('hidden');
    loading?.classList.remove('hidden');
    content?.classList.add('hidden');

    try {
        showToast('Generating AI Summary with Gemini 2.5 Flash...', 'info');
        const res = await pywebview.api.generate_ai_summary(state.transcript, "University Classroom Lecture");
        loading?.classList.add('hidden');

        if (res && res.success) {
            content.innerHTML = renderMarkdownToHtml(res.summary_markdown);
            content.classList.remove('hidden');
            showToast('AI Summary generated successfully!', 'success');
        } else {
            content.innerHTML = `<div style="color:#EF4444; padding:16px; background:rgba(239,68,68,0.1); border-radius:8px;">❌ ${res?.message || 'Failed to generate summary'}</div>`;
            content.classList.remove('hidden');
            showToast(res?.message || 'Failed to generate summary', 'error');
        }
    } catch (e) {
        loading?.classList.add('hidden');
        content.innerHTML = `<div style="color:#EF4444; padding:16px; background:rgba(239,68,68,0.1); border-radius:8px;">❌ Error: ${e}</div>`;
        content.classList.remove('hidden');
        showToast('AI Summary error: ' + e, 'error');
    }
}

function renderMarkdownToHtml(md) {
    if (!md) return '';
    state._lastSummaryRaw = md;

    // 1. Clean up conversational filler & empty disclaimers
    let text = md.trim()
        .replace(/^(?:Here are (?:the|your)|Sure,|Below is|Here is|Note:).*?$\n?/gim, '')
        .replace(/\(No (?:mathematical|formulas|code).*?\)/gim, '')
        .replace(/(#[^\n]+\n+)\s*---\s*\n+/g, '$1')
        .replace(/\n{3,}/g, '\n\n')
        .trim();

    let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

    // 2. Horizontal Rules
    html = html.replace(/^\s*---\s*$/gim, '<hr style="border:none; border-top:1px solid rgba(255,255,255,0.08); margin:18px 0;">');

    // 3. Headings
    html = html.replace(/^### (.*$)/gim, '<h4 style="color:#FBBF24; font-size:14.5px; font-weight:700; margin:16px 0 8px 0; border-bottom:1px solid rgba(245,158,11,0.2); padding-bottom:4px;">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="color:#FFFFFF; font-size:16.5px; font-weight:700; margin:22px 0 10px 0; padding-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.1); display:flex; align-items:center; gap:8px;">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 style="color:#F59E0B; font-size:19px; font-weight:800; margin:0 0 14px 0; border-bottom:2px solid rgba(245,158,11,0.3); padding-bottom:8px;">$1</h2>');

    // 4. Bold + Italic
    html = html.replace(/\*\*\*(.*?)\*\*\*/gim, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong style="color:#F8FAFC; font-weight:700;">$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em style="color:#CBD5E1;">$1</em>');

    // 5. Code blocks & inline code
    html = html.replace(/`([^`]+)`/gim, '<code style="background:rgba(255,255,255,0.08); color:#A5B4FC; padding:2px 6px; border-radius:4px; font-family:\'Fira Code\',monospace; font-size:12px;">$1</code>');

    // 6. Sleek Card Layout for Flashcards (Q & A)
    const flashcardRegex = /^\s*[\*\-•]?\s*(?:<strong[^>]*>)?Q:?(?:<\/strong>)?\s*(.*?)(?:\n\s*|<br>|—)\s*(?:<strong[^>]*>)?A:?(?:<\/strong>)?\s*(.*?)$/gim;
    html = html.replace(
        flashcardRegex,
        '<div class="vd-flashcard">' +
        '<div class="vd-flashcard-q">💡 Q: $1</div>' +
        '<div class="vd-flashcard-a"><strong>A:</strong> $2</div>' +
        '</div>'
    );

    // 7. Lists
    html = html.replace(/^\s*[\*\-•]\s+(.*$)/gim, '<li>$1</li>');
    html = html.replace(/^\s*\d+\.\s+(.*$)/gim, '<li>$1</li>');

    // Wrap list items into <ul>
    html = html.replace(/(<li>[\s\S]*?<\/li>(?:\s*<li>[\s\S]*?<\/li>)*)/gim, '<ul>$1</ul>');

    // 8. Paragraphs
    html = html.split('\n\n').map(p => {
        p = p.trim();
        if (!p) return '';
        if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<div') || p.startsWith('<hr')) return p;
        return `<p>${p}</p>`;
    }).join('');

    return html;
}

function closeSummaryModal() {
    document.getElementById('summaryModal')?.classList.add('hidden');
}

function copySummaryText() {
    const text = state._lastSummaryRaw || document.getElementById('summaryContent')?.innerText;
    if (text) {
        navigator.clipboard.writeText(text);
        showToast('Summary copied to clipboard!', 'success');
    }
}

/* ===== Session Timer ===== */

function startTimer() {
    state.sessionStart = Date.now();
    stopTimer();
    state.timerInterval = setInterval(updateTimer, 1000);
}

function stopTimer() {
    if (state.timerInterval) {
        clearInterval(state.timerInterval);
        state.timerInterval = null;
    }
}

function updateTimer() {
    if (!state.sessionStart) return;
    const elapsed = Math.floor((Date.now() - state.sessionStart) / 1000);
    const timerEl = document.getElementById('sessionTimer');
    if (timerEl) timerEl.textContent = formatTimestamp(elapsed);
}

function formatTimestamp(seconds) {
    const s = Math.floor(seconds % 60);
    const m = Math.floor((seconds / 60) % 60);
    const h = Math.floor(seconds / 3600);
    if (h > 0) {
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/* ===== Toast Notifications ===== */

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✓', error: '✕', info: '⚡' };
    toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${escapeHtml(message)}</span>`;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

/* ===== Helpers ===== */

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
