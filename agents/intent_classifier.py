"""
Intent Classifier Agent
=======================
Агент для распознавания намерений пользователя
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .base_agent import BaseAgent, AgentResult, AgentStatus


class UserIntent(Enum):
    """Возможные намерения пользователя"""
    CLONE = "clone"           # Хочет клонировать голос
    GENERATE = "generate"     # Хочет сгенерировать речь
    STATUS = "status"         # Хочет проверить лимиты
    HELP = "help"             # Нужна помощь
    START = "start"           # Начало работы
    RESET_VOICE = "reset_voice"  # Сбросить голос
    DEMO = "demo"             # Демо-режим
    UNKNOWN = "unknown"       # Неизвестное намерение
    CONSENT_YES = "consent_yes"  # Подтверждение согласия
    CONSENT_NO = "consent_no"    # Отказ от согласия
    CONFIRM_SPLIT = "confirm_split"  # Подтверждение разбиения текста
    CANCEL_SPLIT = "cancel_split"    # Отмена разбиения текста
    TEXT_INPUT = "text_input"    # Просто текст (возможно транскрипция или текст для генерации)


@dataclass
class IntentResult:
    """Результат классификации намерения"""
    intent: UserIntent
    confidence: float
    data: Dict[str, Any]


class IntentClassifier(BaseAgent):
    """
    Классификатор намерений пользователя
    Анализирует сообщение и определяет, что хочет пользователь
    """
    
    # Ключевые слова для определения намерений
    KEYWORDS = {
        UserIntent.CLONE: [
            'клон', 'клонировать', 'мой голос', 'записать голос',
            'голосовой профиль', 'настроить голос', 'voice clone',
            'clone my voice', 'upload voice', 'загрузить голос'
        ],
        UserIntent.STATUS: [
            'лимит', 'limits', 'сколько осталось', 'квота', 'quota',
            'сколько генераций', 'мои лимиты', '/limits', 'статус'
        ],
        UserIntent.HELP: [
            'помощь', 'help', 'как использовать', 'инструкция',
            'что делать', 'как работает', '/help', '?'
        ],
        UserIntent.START: [
            '/start', 'начать', 'start', 'привет', 'hello', 'hi'
        ],
        UserIntent.RESET_VOICE: [
            '/voice', 'сбросить голос', 'удалить профиль', 'reset voice',
            'новый голос', 'другой голос', 'очистить профиль'
        ],
        UserIntent.DEMO: [
            '/demo', 'демо', 'demo', 'тест', 'test', 'пример'
        ],
        UserIntent.CONSENT_YES: [
            'да', 'yes', 'конечно', 'sure', 'подтверждаю', 'confirm'
        ],
        UserIntent.CONSENT_NO: [
            'нет', 'no', 'отмена', 'cancel', 'не подтверждаю'
        ],
        UserIntent.CONFIRM_SPLIT: [
            'да', 'yes', 'генерировать', 'go', 'подтверждаю', 
            'ок', 'ok', 'сгенерируй', 'давай'
        ],
        UserIntent.CANCEL_SPLIT: [
            'отмена', 'cancel', 'нет', 'no', 'отменить', 
            'не надо', 'stop', 'хватит'
        ],
    }
    
    def __init__(self):
        super().__init__("IntentClassifier")
        self.compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> Dict[UserIntent, list]:
        """Скомпилировать регулярные выражения для ключевых слов"""
        patterns = {}
        for intent, keywords in self.KEYWORDS.items():
            patterns[intent] = [re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE) for kw in keywords]
        return patterns
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Классифицировать намерение пользователя
        
        Args:
            user_input: Может быть строкой (текст) или словарем с metadata
            user_id: ID пользователя
            **kwargs: Дополнительная информация (has_voice_profile, waiting_for_consent и т.д.)
        
        Returns:
            AgentResult с определенным намерением
        """
        # Extract text from input
        if isinstance(user_input, dict):
            text = user_input.get('text', '')
            has_audio = user_input.get('has_audio', False)
            is_command = user_input.get('is_command', text.startswith('/'))
        else:
            text = str(user_input)
            has_audio = kwargs.get('has_audio', False)
            is_command = text.startswith('/')
        
        # Get context from kwargs
        has_voice_profile = kwargs.get('has_voice_profile', False)
        waiting_for_consent = kwargs.get('waiting_for_consent', False)
        waiting_for_transcript = kwargs.get('waiting_for_transcript', False)
        
        # Classify intent
        intent_result = self._classify(
            text=text,
            has_audio=has_audio,
            has_voice_profile=has_voice_profile,
            waiting_for_consent=waiting_for_consent,
            waiting_for_transcript=waiting_for_transcript,
            is_command=is_command
        )
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message=f"Intent classified: {intent_result.intent.value}",
            data={
                'intent': intent_result.intent,
                'confidence': intent_result.confidence,
                'extracted_data': intent_result.data
            }
        )
    
    def _classify(self, 
                  text: str, 
                  has_audio: bool,
                  has_voice_profile: bool,
                  waiting_for_consent: bool,
                  waiting_for_transcript: bool,
                  is_command: bool) -> IntentResult:
        """
        Внутренний метод классификации
        """
        text_lower = text.lower().strip()
        
        # Special handling for waiting states
        if waiting_for_consent:
            if self._matches_keywords(text_lower, UserIntent.CONSENT_YES):
                return IntentResult(UserIntent.CONSENT_YES, 1.0, {})
            elif self._matches_keywords(text_lower, UserIntent.CONSENT_NO):
                return IntentResult(UserIntent.CONSENT_NO, 1.0, {})
            # If waiting for consent but got other input, treat as yes/no attempt
            if text_lower in ['да', 'yes', 'д', 'y']:
                return IntentResult(UserIntent.CONSENT_YES, 0.9, {})
            if text_lower in ['нет', 'no', 'н', 'n']:
                return IntentResult(UserIntent.CONSENT_NO, 0.9, {})
        
        if waiting_for_transcript:
            # Any text input while waiting for transcript is likely the transcript
            return IntentResult(UserIntent.TEXT_INPUT, 0.9, {'is_transcript': True})
        
        # Check for commands first
        if is_command:
            if text_lower == '/start':
                return IntentResult(UserIntent.START, 1.0, {})
            elif text_lower == '/limits':
                return IntentResult(UserIntent.STATUS, 1.0, {})
            elif text_lower == '/voice':
                return IntentResult(UserIntent.RESET_VOICE, 1.0, {})
            elif text_lower == '/help':
                return IntentResult(UserIntent.HELP, 1.0, {})
            elif text_lower == '/demo':
                return IntentResult(UserIntent.DEMO, 1.0, {})
        
        # Check for specific intents
        for intent in [UserIntent.CLONE, UserIntent.STATUS, UserIntent.HELP, 
                       UserIntent.RESET_VOICE, UserIntent.DEMO]:
            if self._matches_keywords(text_lower, intent):
                return IntentResult(intent, 0.8, {})
        
        # Check for greetings (treat as start)
        if self._is_greeting(text_lower):
            return IntentResult(UserIntent.START, 0.7, {})
        
        # If user sent audio without specific intent -> CLONE
        if has_audio:
            return IntentResult(UserIntent.CLONE, 0.8, {'has_audio': True})
        
        # If user has voice profile and sends text -> GENERATE
        if has_voice_profile and len(text) > 0:
            return IntentResult(UserIntent.GENERATE, 0.7, {'text': text})
        
        # Default: treat as text input (could be transcript or generate request)
        return IntentResult(UserIntent.TEXT_INPUT, 0.5, {'text': text})
    
    def _matches_keywords(self, text: str, intent: UserIntent) -> bool:
        """Проверить соответствие ключевым словам"""
        if intent not in self.compiled_patterns:
            return False
        
        for pattern in self.compiled_patterns[intent]:
            if pattern.search(text):
                return True
        return False
    
    def _is_greeting(self, text: str) -> bool:
        """Проверить, является ли текст приветствием"""
        greetings = ['привет', 'hello', 'hi', 'здравствуй', 'добрый день', 
                     'доброе утро', 'добрый вечер', 'hey', 'хай']
        return any(g in text for g in greetings)


# Global classifier instance
intent_classifier = IntentClassifier()
