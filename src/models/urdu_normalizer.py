"""Urdu Text Normalizer & Orthographic Standardizer.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.

Standardizes Urdu Unicode characters, terminal ه/ا variants, Hamza markers,
and common acoustic/spelling confusion pairs in speech-to-text transcripts.
"""
import re

# Character-level standardizations (Arabic -> Urdu Unicode)
CHAR_MAPPINGS = {
    '\u0643': '\u06a9',  # Arabic Kaf ك -> Urdu Kaf ک
    '\u064a': '\u06cc',  # Arabic Yeh ي -> Urdu Yeh ی
    '\u0649': '\u06cc',  # Alef Maksura ى -> Urdu Yeh ی
    '\u06c2': '\u06c1',  # Heh with goal ۂ -> Goal Heh ہ
    '\u0647': '\u06c1',  # Arabic Heh ه -> Goal Heh ہ
    '\u06c3': '\u06c1',  # Teh Marbuta Goal ۃ -> Goal Heh ہ
    '\u0629': '\u06c1',  # Arabic Teh Marbuta ة -> Goal Heh ہ
    '\u0624': '\u0648',  # Waw with Hamza ؤ -> Waw و (contextual)
}

# Hamza and Bare Yeh standardizations (e.g. آۓ -> آئے, آو -> آؤ)
HAMZA_CORRECTIONS = {
    'آو': 'آؤ',
    'جاو': 'جاؤ',
    'کھاو': 'کھاؤ',
    'پیو': 'پیئو',
    'سناو': 'سناؤ',
    'بتاو': 'بتاؤ',
    'دکھاو': 'دکھاؤ',
    'گاو': 'گاؤ',
    'لاو': 'لاؤ',
    'آۓ': 'آئے',
    'گۓ': 'گئے',
    'ہوۓ': 'ہوئے',
    'گاۓ': 'گائے',
    'بجاۓ': 'بجائے',
    'جاۓ': 'جائے',
    'پاۓ': 'پائے',
    'کھاۓ': 'کھائے',
    'سناۓ': 'سنائے',
    'بتاۓ': 'بتائے',
    'دکھاۓ': 'دکھائے',
    'چاہیۓ': 'چاہئے',
    'کیجئے': 'کیجیئے',
    'دیجئے': 'دیجیئے',
    'لیجئے': 'لیجیئے',
}

# Terminal orthography & common speech confusion pairs
ORTHOGRAPHIC_CORRECTIONS = {
    'توتہ': 'توتا',
    'گانہ': 'گانا',
    'گانَہ': 'گانا',
    'رہنی': 'رانی',
    'بچو': 'بچّو',
    'طوطا': 'توتا',
    'طوطے': 'توتے',
    'پروگرامز': 'پروگرامز',
    'کیوریکلم': 'کریکلم',
    'صحیح': 'صحیح',
    'بلکل': 'بالکل',
    'انشااللہ': 'ان شاء اللہ',
    'ماشااللہ': 'ما شاء اللہ',
}


class UrduNormalizer:
    """Standardizes Urdu text for consistent orthography and accurate transliteration."""

    @staticmethod
    def normalize(text: str) -> str:
        """Apply full normalization pipeline on Urdu text string."""
        if not text:
            return ""

        # 1. Clean zero-width non-joiners & hidden control chars
        text = re.sub(r'[\u200b-\u200f\ufeff]', '', text)

        # 2. Normalize characters to standard Urdu Unicode
        chars = [CHAR_MAPPINGS.get(c, c) for c in text]
        text = "".join(chars)

        # 3. Fix Hamza marker variants
        for wrong, right in HAMZA_CORRECTIONS.items():
            text = re.sub(r'\b' + re.escape(wrong) + r'\b', right, text)

        # 4. Fix terminal orthography and confusion pairs
        for wrong, right in ORTHOGRAPHIC_CORRECTIONS.items():
            text = re.sub(r'\b' + re.escape(wrong) + r'\b', right, text)

        # 5. Clean punctuation spacing
        text = re.sub(r'\s+([۔،؟!])', r'\1', text)
        text = re.sub(r'([.?!,])\1+', r'\1', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text
