"""Roman Urdu, Pakistani bilingual speech normalization, and Latin transliteration.
VoiceDiary © Abdul Sarim Khan. All Rights Reserved.

Converts Urdu (Nastaliq), Hindi (Devanagari), and Arabic unicode scripts
into clean, natural, phonetic Roman Urdu / Pakistani English (e.g. 'Kya kar rahe ho?').
"""
import re

# Comprehensive high-frequency Pakistani Urdu to Roman Urdu word dictionary
URDU_WORD_DICT = {
    # Pronouns & Auxiliaries
    'میں': 'mein', 'ہم': 'hum', 'تم': 'tum', 'آپ': 'aap', 'تو': 'tu',
    'یہ': 'yeh', 'وہ': 'woh', 'اس': 'is', 'ان': 'un', 'انھیں': 'unhein',
    'انہیں': 'unhein', 'انہوں': 'unhoon', 'ہمیں': 'humein', 'تمہیں': 'tumhein',
    'مجھے': 'mujhe', 'مجھ': 'mujh', 'تجھ': 'tujh', 'تجھے': 'tujhe',
    'اسے': 'use', 'اسکا': 'uska', 'اسکی': 'uski', 'اسکے': 'uske',
    'انکا': 'unka', 'انکی': 'unki', 'انکے': 'unke', 'میرا': 'mera',
    'میری': 'meri', 'میرے': 'mere', 'ہمارا': 'hamara', 'ہماری': 'hamari',
    'ہمارے': 'hamare', 'تمہارا': 'tumhara', 'تمہاری': 'tumhari', 'تمہارے': 'tumhare',
    'آپکا': 'aapka', 'آپکی': 'aapki', 'آپکے': 'aapke', 'اپنا': 'apna',
    'अपनी': 'apni', 'اپنے': 'apne', 'خود': 'khud',
    
    # Prepositions & Conjunctions
    'کا': 'ka', 'کی': 'ki', 'کے': 'ke', 'کو': 'ko', 'سے': 'se',
    'پر': 'par', 'تک': 'tak', 'نے': 'ne', 'اور': 'aur', 'یا': 'ya',
    'لیکن': 'lekin', 'مگر': 'magar', 'اگر': 'agar', 'کیونکہ': 'kyunke',
    'چونکہ': 'chunke', 'تو': 'toh', 'بھی': 'bhi', 'ہی': 'hi',
    'ساتھ': 'saath', 'پاس': 'paas', 'سامنے': 'saamne', 'پیچھے': 'peeche',
    'اوپر': 'oopar', 'نیچے': 'neeche', 'اندر': 'andar', 'باہر': 'bahar',
    'درمیان': 'darmiyan', 'بغیر': 'baghair', 'بعد': 'baad', 'پہلے': 'pehle',
    'جب': 'jab', 'تب': 'tab', 'اب': 'ab', 'کب': 'kab', 'سب': 'sab',
    'کہ': 'ke', 'جیسے': 'jaise', 'جیسا': 'jaisa', 'جیسی': 'jaisi',
    'نہیں': 'nahin', 'نھیں': 'nahin', 'نہيں': 'nahin', 'نہ': 'na',
    'صحیح': 'sahi', 'دونوں': 'dono', 'دونوں کا': 'dono ka', 'دونوں کو': 'dono ko',
    
    # Question Words
    'کیا': 'kya', 'کون': 'kaun', 'کب': 'kab', 'کہاں': 'kahan',
    'کیسے': 'kaise', 'کیسی': 'kaisi', 'کیسا': 'kaisa', 'کیوں': 'kyun',
    'کتنا': 'kitna', 'کتنے': 'kitne', 'کتنی': 'kitni', 'کس': 'kis',
    'کسے': 'kise', 'کسکا': 'kiska', 'کسکی': 'kiski', 'کسکے': 'kiske',
    'جس': 'jis', 'جسے': 'jise', 'جسکو': 'jisko', 'جسکی': 'jiski', 'جسکے': 'jiske', 'جس میں': 'jis mein',
    'باقی': 'baqi', 'باقیوں': 'baqiyon', 'باقیوں کا': 'baqiyon ka', 'باقیوں کو': 'baqiyon ko',
    
    # Verbs & Tenses
    'ہے': 'hai', 'ہیں': 'hain', 'ہو': 'ho', 'ہوں': 'hoon',
    'تھا': 'tha', 'تھی': 'thi', 'تھے': 'thay', 'تھیں': 'theen',
    'کر': 'kar', 'کرنا': 'karna', 'کرنے': 'karne', 'کرنی': 'karni',
    'کرتا': 'karta', 'کرتی': 'karti', 'کرتے': 'karte', 'کریں': 'karein',
    'بنا': 'bana', 'بنانا': 'banana', 'بنانے': 'banane', 'بنائیں': 'banayein',
    'بناؤ': 'banao', 'بنایا': 'banaya', 'بنائی': 'banayi', 'بنائے': 'banaye',
    'کرو': 'karo', 'کروں': 'karoon', 'کرے': 'kare', 'کریں گے': 'karein ge',
    'کرے گا': 'kare ga', 'کرے گی': 'kare gi', 'کریں گی': 'karein gi',
    'رہا': 'raha', 'رہی': 'rahi', 'رہے': 'rahe', 'رہیں': 'rahein',
    'ہوا': 'hua', 'ہوئی': 'hui', 'ہوئے': 'hue', 'ہونا': 'hona',
    'ہونے': 'hone', 'ہونی': 'honi', 'ہوتا': 'hota', 'ہوتی': 'hoti',
    'ہوتے': 'hote', 'ہوگا': 'hoga', 'ہوگی': 'hogi', 'ہوں گے': 'hoon ge',
    'ہو جائیں': 'ho jayein', 'ہو گیا': 'ho gaya', 'ہو گئی': 'ho gayi',
    'دیا': 'diya', 'دی': 'di', 'دے': 'de', 'دیں': 'dein', 'دو': 'do',
    'دینا': 'dena', 'دینے': 'dene', 'دیتا': 'deta', 'دیتی': 'deti', 'دیتے': 'dete',
    'لیا': 'liya', 'لی': 'li', 'لے': 'le', 'لیں': 'lein', 'لو': 'lo',
    'لینا': 'lena', 'لینے': 'lene', 'لیتا': 'leta', 'لیتی': 'leti', 'لیتے': 'lete',
    'گیا': 'gaya', 'گئی': 'gayi', 'گئے': 'gaye', 'جانا': 'jana', 'جانے': 'jane',
    'جاتا': 'jata', 'جاتی': 'jati', 'جاتے': 'jate', 'جائیں': 'jayein', 'جاؤ': 'jao',
    'آیا': 'aaya', 'آئی': 'aayi', 'آئے': 'aaye', 'آنا': 'aana', 'آنے': 'aane',
    'آتا': 'aata', 'آتی': 'aati', 'آتے': 'aate', 'آئیں': 'aayein', 'آؤ': 'aao',
    'دیکھا': 'dekha', 'دیکھی': 'dekhi', 'دیکھے': 'dekhe', 'دیکھنا': 'dekhna',
    'دیکھنے': 'dekhne', 'دیکھتا': 'dekhta', 'دیکھتی': 'dekhti', 'دیکھتے': 'dekhte',
    'دیکھو': 'dekho', 'دیکھیں': 'dekhein',
    'سنا': 'suna', 'سنی': 'suni', 'سنے': 'sune', 'سننا': 'sunna', 'سننے': 'sunne',
    'سنتا': 'sunta', 'سنتی': 'sunti', 'سنتے': 'sunte', 'سنو': 'suno', 'سنیں': 'sunein',
    'بولا': 'bola', 'بولی': 'boli', 'بولے': 'bole', 'بولنا': 'bolna', 'بولنے': 'bolne',
    'بولو': 'bolo', 'بولیں': 'bolein', 'بتایا': 'bataya', 'بتائی': 'batayi',
    'بتائے': 'bataye', 'بتانا': 'batana', 'بتانے': 'batane', 'بتاؤ': 'batao', 'بتائیں': 'batayein',
    'سمجھا': 'samjha', 'سمجھی': 'samjhi', 'سمجھے': 'samjhe', 'سمجھنا': 'samjhna',
    'سمجھنے': 'samjhne', 'سمجھ': 'samajh', 'سمجھیں': 'samjhein',
    'پڑھا': 'parha', 'پڑھی': 'parhi', 'پڑھے': 'parhe', 'پڑھنا': 'parhna',
    'پڑھو': 'parho', 'پڑھیں': 'parhein',
    'لکھا': 'likha', 'لکھی': 'likhi', 'لکھے': 'likhe', 'لکھنا': 'likhna',
    'لکھو': 'likho', 'لکھیں': 'likhein',
    'حل': 'hal', 'حال': 'haal', 'کٹ': 'cut', 'کٹا': 'kata',
    'ڈاکٹر': 'Doctor', 'ڈوم': 'Doom', 'تھور': 'Thor',
    'ایکشن': 'action', 'ایڈونچر': 'adventure', 'ایڈوانس': 'advance',
    'سوالات': 'sawalat', 'جوابات': 'jawabat', 'اردو': 'Urdu', 'انگریزی': 'English', 'آواز': 'aawaz',
    
    # Common English Loanwords in Pakistani Urdu
    'فائنل': 'final', 'ٹیسٹ': 'test', 'مکس': 'mix', 'آڈیو': 'audio', 'آڈیوز': 'audios',
    'ویڈیو': 'video', 'ویڈیوز': 'videos', 'ریکارڈ': 'record', 'ریکارڈنگ': 'recording',
    'پروگرام': 'program', 'ڈیٹیکٹ': 'detect', 'ڈیٹیکشن': 'detection', 'انگلش': 'English',
    'کمپیوٹر': 'computer', 'سائنس': 'science', 'سسٹم': 'system', 'ماڈل': 'model',
    'کوڈ': 'code', 'ڈیٹا': 'data', 'پروجیکٹ': 'project', 'اسائنمنٹ': 'assignment',
    'لیکچر': 'lecture', 'کلاس': 'class', 'یونیورسٹی': 'university', 'کالج': 'college',
    'اسکول': 'school', 'آن لائن': 'online', 'آف لائن': 'offline', 'اسکرین': 'screen',
    'ڈسپلے': 'display', 'ٹاپک': 'topic', 'کنسیپٹ': 'concept', 'پوائنٹ': 'point',
    'پوائنٹس': 'points', 'فائل': 'file', 'فائلز': 'files', 'نوٹس': 'notes',
    'پیپر': 'paper', 'ایگزام': 'exam', 'رزلٹ': 'result', 'پریزنٹیشن': 'presentation',
    'مائیک': 'mic', 'مائیکروفون': 'microphone', 'اسپیکر': 'speaker', 'اسپیکرز': 'speakers',
    'ٹیکسٹ': 'text', 'میسج': 'message', 'چیٹ': 'chat', 'گروپ': 'group', 'کال': 'call',
    'لنک': 'link', 'لاگ ان': 'login', 'پاس ورڈ': 'password', 'اکاؤنٹ': 'account',
    'چیک': 'check', 'سیو': 'save', 'ڈاؤنلوڈ': 'download', 'اپلوڈ': 'upload',
    'شیئر': 'share', 'اوپن': 'open', 'کلوز': 'close', 'سٹارٹ': 'start', 'اسٹارٹ': 'start',
    'سٹاپ': 'stop', 'اسٹاپ': 'stop', 'اپ ڈیٹ': 'update', 'انسٹال': 'install',
    'پاکستان': 'Pakistan', 'پاکستانی': 'Pakistani',
    
    # Common Adjectives & Adverbs
    'بہت': 'bohot', 'زیادہ': 'zyada', 'کم': 'kam', 'تھوڑا': 'thora',
    'تھوڑی': 'thori', 'تھوڑے': 'thore', 'سب': 'sab', 'سبھی': 'sabhi',
    'کچھ': 'kuch', 'کوئی': 'koi', 'ہر': 'har', 'سارا': 'saara',
    'ساری': 'saari', 'سارے': 'saare', 'تمام': 'tamam',
    'اچھا': 'acha', 'اچھی': 'achi', 'اچھے': 'ache', 'برا': 'bura',
    'صحیح': 'sahi', 'غلط': 'ghalat', 'ٹھیک': 'theek', 'بالکل': 'bilkul',
    'ضرور': 'zaroor', 'ضروری': 'zaroori', 'آسان': 'aasan', 'مشکل': 'mushkil',
    'اہم': 'aham', 'خاص': 'khaas', 'عام': 'aam', 'بڑا': 'bara',
    'بڑی': 'bari', 'بڑے': 'bare', 'چھوٹا': 'chota', 'چھوٹی': 'choti', 'چھوٹے': 'chote',
    'نیا': 'naya', 'نئی': 'nayi', 'نئے': 'naye', 'پرانا': 'purana',
    
    # Time & Classroom
    'آج': 'aaj', 'کل': 'kal', 'پرسوں': 'parson', 'اب': 'ab', 'ابھی': 'abhi',
    'پھر': 'phir', 'دوبارہ': 'dobara', 'ہمیشہ': 'hamesha', 'کبھی': 'kabhi',
    'وقت': 'waqt', 'بات': 'baat', 'کام': 'kaam', 'چیز': 'cheez',
    'لوگ': 'log', 'طلباء': 'students', 'طالب علم': 'student',
    'کلاس': 'class', 'لیکچر': 'lecture', 'اسائنمنٹ': 'assignment',
    'پروجیکٹ': 'project', 'یونیورسٹی': 'university', 'کالج': 'college',
    'اسکول': 'school', 'ٹیچر': 'teacher', 'سر': 'sir', 'میم': 'Ma\'am',
    'مونا': 'Mona', 'سارم': 'Sarim', 'خان': 'Khan',
    'کیوریکلم': 'curriculum', 'کوریکلم': 'curriculum', 'کورس': 'course',
    'کمپیوٹر': 'computer', 'سائنس': 'science', 'ماڈل': 'model',
    'ڈیٹا': 'data', 'کوڈ': 'code', 'ٹاپک': 'topic', 'سوال': 'sawal', 'جواب': 'jawab',
    'نوٹس': 'notes', 'پوائنٹ': 'point', 'پوائنٹس': 'points',
    'شکریہ': 'shukriya', 'پلیز': 'please', 'سلام': 'salam',
    'ایک': 'ek', 'دو': 'do', 'تین': 'teen', 'چار': 'chaar', 'پانچ': 'paanch',
    'چھ': 'chhah', 'سات': 'saat', 'آٹھ': 'aath', 'نو': 'nau', 'دس': 'das',
    'شروع': 'shuru', 'ختم': 'khatam', 'جمع': 'jama', 'کروائیں': 'karwayein', 'کروائیں گے': 'karwayein ge',
    'کروا': 'karwa', 'کروانا': 'karwana', 'کروائی': 'karwayi',
}

# Character-level phonetic transliteration for unmapped Urdu words
URDU_CHAR_MAP = {
    'ا': 'a', 'آ': 'aa', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ٹ': 't', 'ث': 's',
    'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ڈ': 'd', 'ذ': 'z',
    'ر': 'r', 'ڑ': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh', 'ص': 's',
    'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
    'ک': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ں': 'n', 'و': 'o',
    'ہ': 'h', 'ۂ': 'h', 'ۃ': 't', 'ھ': 'h', 'ء': '', 'ی': 'i', 'ے': 'e',
    'ئ': 'i', '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5',
    '۶': '6', '۷': '7', '۸': '8', '۹': '9', '،': ',', '؟': '?', '۔': '.',
    'َ': 'a', 'ِ': 'i', 'ُ': 'u', 'ً': 'an', 'ّ': '', 'إ': 'i', 'أ': 'a',
    'ؤ': 'o', 'ة': 't', 'ى': 'a', 'ي': 'y', 'ك': 'k', 'ه': 'h'
}

HINDI_CHAR_MAP = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo', 'ऋ': 'ri',
    'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'क': 'k', 'ख': 'kh', 'ग': 'g',
    'घ': 'gh', 'ङ': 'ng', 'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n', 'त': 't', 'थ': 'th',
    'द': 'd', 'ध': 'dh', 'न': 'n', 'پ': 'p', 'ف': 'ph', 'ب': 'b', 'بھ': 'bh',
    'م': 'm', 'ی': 'y', 'ر': 'r', 'ل': 'l', 'و': 'v', 'ش': 'sh', 'ष': 'sh',
    'س': 's', 'ہ': 'h', 'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
    'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', '्': '', 'ं': 'n', 'ः': 'h',
    '़': '', '।': '.', '॥': '.'
}

CLEANUP_PHRASES = {
    'thank you for watching': '',
    'thanks for watching': '',
    'subscribe to my channel': '',
    'subtitles by': '',
    'like and subscribe': '',
    'in the next video': '',
}


def transliterate_token(token: str) -> str:
    """Transliterate a single Urdu/Hindi word or punctuation token."""
    # Strip punctuation around token
    leading_punct = re.match(r'^[^\w\s]+', token)
    trailing_punct = re.search(r'[^\w\s]+$', token)
    
    lead = leading_punct.group(0) if leading_punct else ''
    trail = trailing_punct.group(0) if trailing_punct else ''
    
    clean_word = token[len(lead):len(token)-len(trail)] if (lead or trail) else token
    
    # Check word dictionary
    if clean_word in URDU_WORD_DICT:
        converted = URDU_WORD_DICT[clean_word]
    elif clean_word.lower() in URDU_WORD_DICT:
        converted = URDU_WORD_DICT[clean_word.lower()]
    else:
        # Fallback to character mapping
        chars = []
        for ch in clean_word:
            if ch in URDU_CHAR_MAP:
                chars.append(URDU_CHAR_MAP[ch])
            elif ch in HINDI_CHAR_MAP:
                chars.append(HINDI_CHAR_MAP[ch])
            else:
                chars.append(ch)
        converted = "".join(chars)
        
        # If 2 consonants without vowels (e.g., jb, hl, kt, tb, sb, kht), insert 'a'
        if len(converted) == 2 and re.match(r'^[bcdfghjklmnpqrstvwxyz]{2}$', converted, re.I):
            converted = converted[0] + 'a' + converted[1]

        # Post-process common vowel clusters in unmapped words
        converted = re.sub(r'([bcdfghjklmnpqrstvwxyz])([bcdfghjklmnpqrstvwxyz]{2,})', r'\1a\2', converted)
        converted = re.sub(r'yonyorsty', 'university', converted, flags=re.IGNORECASE)
        converted = re.sub(r'lykchr', 'lecture', converted, flags=re.IGNORECASE)
        converted = re.sub(r'kyoryklm', 'curriculum', converted, flags=re.IGNORECASE)
        converted = re.sub(r'asainmnt', 'assignment', converted, flags=re.IGNORECASE)
        converted = re.sub(r'projykt', 'project', converted, flags=re.IGNORECASE)
        converted = re.sub(r'dakatr', 'Doctor', converted, flags=re.IGNORECASE)

    # Re-attach punct (translating Urdu punct)
    lead_trans = lead.replace('،', ',').replace('؟', '?').replace('۔', '.')
    trail_trans = trail.replace('،', ',').replace('؟', '?').replace('۔', '.')
    
    return f"{lead_trans}{converted}{trail_trans}"


def to_roman_urdu(text: str) -> str:
    """Converts Urdu / Hindi / Arabic script into clean, natural Roman Urdu."""
    if not text:
        return ""
    
    # Check if text contains non-Latin scripts
    has_urdu_or_hindi = bool(re.search(r'[\u0600-\u06FF\u0900-\u097F]', text))
    if not has_urdu_or_hindi:
        # Already Latin, just clean up punctuation debris
        cleaned = re.sub(r'([.?!,])\1+', r'\1', text)
        cleaned = re.sub(r'(?:,\s*)+,', ',', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    # First replace known multi-word phrases
    for phrase, roman_rep in [
        ('پاکستانی یونیورسٹی لیکچر', 'Pakistani university lecture'),
        ('بات چیت', 'baat cheet'),
        ('طالب علم', 'student'),
        ('جمع کروا', 'jama karwa'),
        ('جمع کروائیں', 'jama karwayein'),
        ('ڈیپ لرننگ', 'deep learning'),
        ('مشین لرننگ', 'machine learning'),
        ('کمپیوٹر سائنس', 'computer science'),
        ('میم مونا', "Ma'am Mona"),
    ]:
        if phrase in text:
            text = text.replace(phrase, roman_rep)

    tokens = text.split()
    converted_tokens = [transliterate_token(t) for t in tokens]
    converted = " ".join(converted_tokens)

    # Remove repetitive video transcript hallucinations
    lower_conv = converted.lower().strip()
    for phrase, rep in CLEANUP_PHRASES.items():
        if phrase in lower_conv and len(converted.split()) <= 6:
            converted = re.sub(re.escape(phrase), rep, converted, flags=re.IGNORECASE).strip()

    # Clean redundant whitespaces, repeated commas and single-character debris
    converted = re.sub(r'([.?!,])\1+', r'\1', converted)
    converted = re.sub(r'(?:,\s*)+,', ',', converted)
    converted = re.sub(r'\s+', ' ', converted).strip()
    converted = re.sub(r'^[\s,.:;!?]+|[\s,.:;!?]+$', '', converted).strip()

    # Capitalize the first letter of sentences
    if converted:
        converted = converted[0].upper() + converted[1:]
    
    return converted

