import re

class TextNormalizer:
    ABBREVIATIONS = {
        r'\bDr\.\s*': 'Doktor ',
        r'\bProf\.\s*': 'Profesör ',
        r'\bDoç\.\s*': 'Doçent ',
        r'\bYrd\.\s*Doç\.\s*': 'Yardımcı Doçent ',
        r'\bAv\.\s*': 'Avukat ',
        r'\bMüh\.\s*': 'Mühendis ',
        r'\bNo\.\s*': 'Numara ',
        r'\bvs\.\s*': 've sair, ',
        r'\bv\.b\.\s*': 've benzeri, ',
        r'\bvd\.\s*': 've diğerleri, ',
        r'\bbkz\.\s*': 'bakınız: ',
        r'\bap\.\s*': 'apartmanı, ',
    }

    @classmethod
    def normalize(cls, text: str) -> str:
        text = re.sub(r'\[\s*\d+\s*\]', '', text)
        text = re.sub(r'\([A-Za-zÇĞİÖŞÜçğıöşü\s\-]+,\s*\d{4}(?:\s*:\s*\d+)?\)', '', text)
        text = re.sub(r'\n\s*\d+\s*\n', '\n', text)
        for pattern, replacement in cls.ABBREVIATIONS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
