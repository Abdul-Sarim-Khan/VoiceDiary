# VoiceDiary System Architecture & Ecosystem Flowchart
**VoiceDiary © 2026 Abdul Sarim Khan. All Rights Reserved.**

This document details the multi-tiered ecosystem connecting **Developer Deployment, GitHub CI/CD, Hugging Face Static Spaces, Google Colab NVIDIA T4 GPU Cloud Demo, Gemini 2.5 Flash API, and the Local Windows Desktop Engine**.

---

## 📊 Complete Ecosystem Flowchart

```mermaid
flowchart TD
    %% Styling Classes
    classDef dev fill:#1E293B,stroke:#64748B,stroke-width:2px,color:#F8FAFC;
    classDef hub fill:#0F172A,stroke:#F59E0B,stroke-width:2px,color:#FDE68A;
    classDef cloud fill:#022C22,stroke:#10B981,stroke-width:2px,color:#A7F3D0;
    classDef desktop fill:#1E1B4B,stroke:#6366F1,stroke-width:2px,color:#C7D2FE;
    classDef ai fill:#3B0764,stroke:#A855F7,stroke-width:2px,color:#E9D5FF;

    %% 1. DEVELOPER DEPLOYMENT FLOW
    subgraph S1[" 💻 1. DEVELOPER SOURCE & DEPLOYMENT "]
        LocalCode["📁 Local Working Directory<br/>(VoiceDiary)"]:::dev
        GitPush["🚀 git push origin main"]:::dev
        GitHub["🐙 GitHub Repository<br/>(Abdul-Sarim-Khan/VoiceDiary)"]:::dev
        GHActions["⚙️ GitHub Actions CI<br/>(Lint, Syntax & Protobuf Tests)"]:::dev
    end

    LocalCode --> GitPush --> GitHub --> GHActions

    %% 2. PUBLIC DISTRIBUTION & HOSTING
    subgraph S2[" 🌐 2. CLOUD PLATFORMS & PORTFOLIO "]
        HFSpace["🤗 Hugging Face Static Space<br/>(huggingface.co/spaces/KnuckleHead1/VoiceDiary)<br/>• 24/7 Global CDN Web Showcase<br/>• Interactive Lecture Simulation<br/>• Cost: 100% Free Forever"]:::hub
        ColabDemo["⚡ Google Colab Runner<br/>(VoiceDiary_Live_GPU_Demo.ipynb)<br/>• Allocates Free NVIDIA Tesla T4 GPU<br/>• Zero Config 1-Click Run"]:::cloud
        GHReleases["💾 GitHub Releases<br/>(VoiceDiary_Setup_v1.2.0.exe)"]:::hub
    end

    GitHub -.->|"Auto-Syncs / Deploys"| HFSpace
    GitHub -->|"Hosts Notebook"| ColabDemo
    GitHub -->|"Hosts .EXE Installer"| GHReleases

    %% 3. VISITOR INTERACTION PATHS
    subgraph S3[" 👥 3. END USER ENTRY POINTS "]
        Recruiter["👨‍💼 Recruiter / Professor / User"]:::dev
    end

    Recruiter -->|"Visits Website"| HFSpace
    HFSpace -->|"Clicks 'Open Live GPU Demo'"| ColabDemo
    HFSpace -->|"Clicks 'Download Installer'"| GHReleases

    %% 4. CLOUD GPU INFERENCE (COLAB)
    subgraph S4[" ☁️ 4. GOOGLE COLAB FREE CLOUD EXECUTION "]
        ColabVM["Google Cloud T4 VM<br/>(User's Free Google Quota)"]:::cloud
        WhisperLarge["Faster-Whisper Large-v3-Turbo<br/>+ ECAPA-TDNN"]:::cloud
        GradioLive["🌐 Live Gradio Public Web URL<br/>(https://xxxx.gradio.live)"]:::cloud
    end

    ColabDemo --> ColabVM --> WhisperLarge --> GradioLive
    Recruiter -.->|"Tests Live in Browser (<50ms)"| GradioLive

    %% 5. WINDOWS DESKTOP APP (LOCAL PRODUCTION)
    subgraph S5[" 🖥️ 5. LOCAL WINDOWS DESKTOP APPLICATION "]
        UserPC["💻 Student / User Laptop (Offline)"]:::desktop
        HWDetect["⚡ HardwareManager<br/>(Auto-detects NVIDIA CUDA FP16 vs AVX2 CPU INT8)"]:::desktop
        AudioIn["🎙️ Microphone / 📁 Audio File<br/>(80Hz Filter + Silero VAD)"]:::desktop
        LocalInference["🧠 Local Deep Learning Engine<br/>• Whisper Bilingual Transcription<br/>• ECAPA-TDNN 192-dim Voiceprint Diarization<br/>• Binary Protobuf Storage (.pb)"]:::desktop
        DesktopUI["🎨 Obsidian & Gold Dark GUI (pywebview)"]:::desktop
    end

    GHReleases -->|"Installs .exe"| UserPC
    UserPC --> HWDetect --> AudioIn --> LocalInference --> DesktopUI

    %% 6. GEMINI AI SUMMARIZER (OPTIONAL POST-CLASS)
    subgraph S6[" ✨ 6. POST-LECTURE AI STUDY ENGINE "]
        GeminiAPI["Google Gemini 2.5 Flash API<br/>(Google AI Studio)"]:::ai
        StudyNotes["📝 Generated Study Notes<br/>• 📌 Executive Lecture Summary<br/>• 🎯 Key Concepts & Formulas<br/>• 💡 Exam Study Flashcards (Q&A)<br/>• 📋 Homework & Deadlines"]:::ai
    end

    DesktopUI -->|"User clicks 'AI Summary'"| GeminiAPI --> StudyNotes --> DesktopUI
```
