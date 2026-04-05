"""
Content Moderation Module
=========================
Проверка текста на запрещенный контент
"""

import re
from typing import Tuple, List


class ContentModerator:
    """Модератор контента для проверки текста"""
    
    # Запрещенные ключевые слова (нижний регистр)
    BLOCKED_KEYWORDS = {
        # Russian - насилие
        'насилие', 'насилием', 'насильно', 'насильник',
        # Russian - убийство
        'убийство', 'убийства', 'убийству', 'убийством',
        'убивать', 'убью', 'убей', 'убийца', 'убийце', 'убийцей',
        # Russian - терроризм
        'терроризм', 'террорист', 'террористы', 'террористический',
        # Russian - экстремизм
        'экстремизм', 'экстремист', 'экстремисты', 'экстремистский',
        # Russian - расизм
        'расизм', 'расист', 'расисты', 'расистский',
        # Russian - дискриминация
        'дискриминация', 'дискриминации', 'дискриминировать',
        # Russian - ненависть
        'ненависть', 'ненавижу', 'ненавидеть',
        # Russian - порно/NSFW
        'порно', 'порнография', 'порнографический', 'nsfw',
        'секс', 'сексуальный', 'изнасилование', 'изнасиловать',
        'педофил', 'педофилия', 'детское порно',
        # Russian - нацизм
        'нацизм', 'нацист', 'нацисты', 'нацистский',
        'фашизм', 'фашист', 'фашисты', 'фашистский',
        'гитлер', 'свастика', 'ку клукс клан', 'ккк',
        # Russian - наркотики
        'наркотики', 'наркота', 'наркотический',
        'героин', 'кокаин', 'метамфетамин', 'амфетамин',
        # Russian - оружие/взрывы
        'оружие', 'оружием', 'взрывчатка', 'бомба', 'бомбы',
        'взрыв', 'взрывы', 'стрельба', 'расстрел',
        
        # English - violence
        'violence', 'violent', 'kill', 'killing', 'killed', 'killer',
        'murder', 'murdering', 'murdered', 'murderer',
        # English - terrorism
        'terrorism', 'terrorist', 'terrorists',
        'extremism', 'extremist', 'extremists',
        # English - racism
        'racism', 'racist', 'racists',
        'discrimination', 'discriminate', 'hate speech',
        # English - NSFW
        'porn', 'pornography', 'pornographic', 'sexual content',
        'rape', 'raping', 'pedophile', 'pedophilia',
        'child abuse', 'child pornography', 'child porn',
        # English - nazism
        'nazi', 'nazism', 'nazis', 'fascism', 'fascist', 'fascists',
        'hitler', 'swastika', 'kkk', 'ku klux klan',
        # English - drugs
        'drugs', 'drug', 'heroin', 'cocaine', 'methamphetamine', 'meth',
        # English - weapons
        'weapon', 'weapons', 'explosive', 'explosives',
        'bomb', 'bombs', 'shooting', 'massacre',
        
        # Other harmful content
        'suicide', 'suicidal',
        'суицид', 'суицидальный', 'самоубийство', 'самоубийству',
        'self-harm', 'self harm', 'самоповреждение',
        'doxxing', 'doxing', 'доксинг', 'доксить',
    }
    
    # Подозрительные паттерны
    SUSPICIOUS_PATTERNS = [
        r'\b(?:kill|убей|убить)\s+(?:yourself|себя|all|всех|them|их)\b',
        r'\b(?:bomb|бомба|взрыв)\s+(?:building|здание|school|школа)\b',
        r'\b(?:shoot|стрелять|расстрел)\s+(?:people|люди|everyone|всех)\b',
        r'\b(?:how\s+to|как)\s+(?:make|сделать)\s+(?:bomb|бомбу|drugs|наркотики)\b',
    ]
    
    def __init__(self):
        self.compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.SUSPICIOUS_PATTERNS]
    
    def check_text(self, text: str) -> Tuple[bool, List[str]]:
        """
        Проверить текст на запрещенный контент
        
        Args:
            text: Текст для проверки
        
        Returns:
            (is_safe: bool, violations: list of strings)
            is_safe = True если текст прошел проверку
        """
        if not text:
            return True, []
        
        violations = []
        text_lower = text.lower()
        
        # Check for blocked keywords
        words = re.findall(r'\b\w+\b', text_lower)
        for word in words:
            if word in self.BLOCKED_KEYWORDS:
                violations.append(f"Запрещенное слово: '{word}'")
        
        # Check for suspicious patterns
        for pattern in self.compiled_patterns:
            matches = pattern.findall(text)
            if matches:
                violations.append(f"Подозрительный паттерн обнаружен")
        
        # Check character limit
        if len(text) > 1000:
            violations.append(f"Превышен лимит символов: {len(text)} > 1000")
        
        is_safe = len(violations) == 0
        return is_safe, violations
    
    def validate_length(self, text: str, max_length: int = 1000) -> Tuple[bool, int]:
        """
        Проверить длину текста
        
        Returns:
            (is_valid: bool, length: int)
        """
        length = len(text)
        return length <= max_length, length
    
    def sanitize_text(self, text: str) -> str:
        """
        Очистить текст от потенциально опасных символов
        """
        # Remove control characters except newlines
        sanitized = ''.join(char for char in text if char == '\n' or ord(char) >= 32)
        
        # Limit length
        sanitized = sanitized[:1000]
        
        return sanitized.strip()


# Global moderator instance
content_moderator = ContentModerator()
