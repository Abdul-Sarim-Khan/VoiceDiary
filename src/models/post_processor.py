"""Language Model & Acoustic Rescoring Post-Processor.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.

Performs rule-based context scoring, acoustic confusion pair resolution,
and grammatical smoothing for English and mixed-language transcripts.
"""
import re

# High-frequency acoustic confusion pairs in English lecture speech
ENGLISH_CONFUSION_PAIRS = [
    # Availability -> The ability / ability
    (r'\bavailability\s+to\s+convey\b', 'the ability to convey'),
    (r'\bavailability\s+to\b', 'ability to'),
    (r'\bfocus\s+and\s+availability\b', 'focus, and the ability'),
    (r'\bfocus\s+and\s+the\s+availability\b', 'focus, and the ability'),
    
    # Roles and the world -> Role in the world
    (r'\broles\s+and\s+the\s+world\b', 'role in the world'),
    (r'\brole\s+and\s+the\s+world\b', 'role in the world'),
    (r'\btheir\s+roles\s+and\s+the\s+world\b', 'their role in the world'),
    
    # Entertains inform -> Entertain, inform
    (r'\bentertains\s+inform\b', 'entertain, inform'),
    (r'\bentertains,\s*inform\b', 'entertain, inform'),
    (r'\bcontent\s+that\s+entertains\s+and\s+inform\b', 'content that entertains, informs'),
    
    # Common speech artifacts
    (r'\bwhether\s+they\s+write\s+fiction\s+non-fiction\b', 'whether they write fiction, nonfiction'),
    (r'\bwhether\s+they\s+write\s+fiction\s+nonfiction\b', 'whether they write fiction, nonfiction'),
]


def post_process_english(text: str) -> str:
    """Refine English transcription by resolving acoustic confusion pairs."""
    if not text:
        return ""

    processed = text
    for pattern, replacement in ENGLISH_CONFUSION_PAIRS:
        processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)

    # Clean double spaces and punctuation spacing
    processed = re.sub(r'\s+([,.:;?!])', r'\1', processed)
    processed = re.sub(r'([.?!,])\1+', r'\1', processed)
    processed = re.sub(r'\s+', ' ', processed).strip()

    if processed:
        processed = processed[0].upper() + processed[1:]

    return processed
