"""AI Lecture Summarization and Flashcard Generation using Google Gemini 2.5 Flash.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.
"""
import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_API_KEY = ""


class GeminiSummarizer:
    """Generates structured classroom lecture summaries, key takeaways,
    exam revision flashcards, and action items using Gemini 2.5 Flash.
    """

    def __init__(self, api_key: str = None):
        key = api_key
        if not key:
            try:
                from pathlib import Path
                from config import get_app_data_dir, PROJECT_ROOT
                import json
                candidates = [
                    get_app_data_dir() / "settings.json",
                    PROJECT_ROOT / "data" / "settings.json",
                ]
                appdata = os.environ.get("APPDATA")
                if appdata:
                    candidates.append(Path(appdata) / "VoiceDiary" / "settings.json")

                for p in candidates:
                    if p.exists():
                        try:
                            s = json.loads(p.read_text(encoding="utf-8"))
                            k = s.get("gemini_api_key", "").strip()
                            if k:
                                key = k
                                break
                        except Exception:
                            continue
            except Exception as e:
                logger.debug("Failed reading settings.json for Gemini: %s", e)

        if not key:
            key = os.environ.get("GEMINI_API_KEY", "") or DEFAULT_GEMINI_API_KEY

        self.api_key = key.strip() if key else ""

    def summarize_lecture(self, transcript_entries: List[Dict[str, Any]], lecture_title: str = "Classroom Lecture") -> Dict[str, Any]:
        """Summarizes a full lecture session into structured markdown."""
        if not transcript_entries:
            return {"success": False, "message": "No transcript content to summarize."}

        if not self.api_key:
            return {
                "success": False,
                "message": "Gemini API Key is not set. Please add your free key in Settings (get one free in 30s at aistudio.google.com)."
            }

        # Format transcript lines for prompt
        lines = []
        for e in transcript_entries:
            spk = e.get("speaker_name", "Speaker")
            time_str = e.get("timestamp", "")
            text = e.get("text", "").strip()
            if text:
                prefix = f"[{time_str}] {spk}: " if time_str else f"{spk}: "
                lines.append(f"{prefix}{text}")

        full_transcript = "\n".join(lines)
        if len(full_transcript) < 30:
            return {"success": False, "message": "Transcript is too short to generate a meaningful summary."}

        system_instruction = (
            "You are an expert academic AI note-taker and university study assistant for 'VoiceDiary'. "
            "Analyze classroom lecture transcripts (including mixed English and Urdu) "
            "and produce clean, beautifully structured study notes in standard GitHub-flavored Markdown.\n\n"
            "CRITICAL FORMATTING GUIDELINES:\n"
            "- Start directly with the lecture title heading: # [Lecture Title]\n"
            "- Do NOT include any conversational intro/outro filler (e.g. do NOT say 'Here are your notes', do NOT write horizontal rules '---' under the title).\n"
            "- Never write negative disclaimers like '(No mathematical formulas were mentioned)'. Focus purely on what was taught.\n"
            "- For Study Flashcards, format each card clearly as:\n"
            "  * **Q:** [Clear question text]?\n"
            "    **A:** [Concise, accurate answer text]\n\n"
            "REQUIRED SECTIONS:\n"
            "## 📌 Executive Lecture Summary\n"
            "(3-4 high-yield bullet points summarizing core themes)\n\n"
            "## 🎯 Key Concepts & Academic Definitions\n"
            "(In-depth breakdown of concepts, formulas, logic, or technical steps discussed)\n\n"
            "## 💡 Study Flashcards & Exam Revision\n"
            "(4-5 high-yield Question and Answer pairs for rapid exam revision)\n\n"
            "## 📋 Action Items & Homework Mentioned\n"
            "(Any tasks, assignments, deadlines, or follow-ups mentioned, or 'None mentioned' if none)\n\n"
            "If any technical terms were spoken in Roman Urdu, explain the concept clearly in English and Urdu."
        )

        user_prompt = f"Lecture Title: {lecture_title}\n\nTranscript Content:\n{full_transcript}"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_instruction}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.25,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            }
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=25) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                candidates = res_data.get("candidates", [])
                if not candidates:
                    return {"success": False, "message": "Gemini returned an empty response."}

                raw_summary = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                
                # Clean up any leftover conversational filler & negative disclaimers
                import re
                clean_text = re.sub(r'^(?:Here are (?:the|your)|Sure,|Below is|Here is).*?$\n?', '', raw_summary.strip(), flags=re.MULTILINE | re.IGNORECASE)
                clean_text = re.sub(r'\(No (?:mathematical|formulas|code).*?\)', '', clean_text, flags=re.IGNORECASE)
                clean_text = re.sub(r'(#[^\n]+\n+)\s*---\s*\n+', r'\1', clean_text)
                clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

                logger.info("AI Lecture Summary successfully generated and cleaned by Gemini 2.5 Flash.")
                return {
                    "success": True,
                    "summary_markdown": clean_text,
                    "model": "gemini-2.5-flash"
                }

        except urllib.error.HTTPError as he:
            err_msg = he.read().decode("utf-8", errors="ignore")
            logger.error("Gemini API HTTP Error %d: %s", he.code, err_msg)
            return {"success": False, "message": f"Gemini API Error ({he.code}): {err_msg}"}
        except Exception as ex:
            logger.error("Gemini summarization failed: %s", ex)
            return {"success": False, "message": f"Failed to generate summary: {str(ex)}"}
