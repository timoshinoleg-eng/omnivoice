"""
VoiceCraft Bot
==============
Бот для клонирования голоса и генерации речи через Hugging Face Spaces

Основные возможности:
- Клонирование голоса (3-10 сек аудио)
- Генерация речи (до 59 сек, 1000 символов)
- Лимит 3 генерации в день на пользователя
- Интеграция с OmniVoice HF Space
"""

__version__ = "1.0.0"
__author__ = "VoiceCraft Team"

from .agents.voicecraft_bot import VoiceCraftBot, voicecraft_bot
from .agents import (
    UserIntent,
    AgentStatus,
    ErrorType,
    intent_classifier,
    quota_manager,
    voice_profile_setup,
    content_moderator_agent,
    hf_generator,
    error_handler,
)
from .storage import state_manager, VoiceProfile
from .config import config, get_message

__all__ = [
    # Main bot
    'VoiceCraftBot',
    'voicecraft_bot',
    
    # Enums
    'UserIntent',
    'AgentStatus',
    'ErrorType',
    
    # Agents
    'intent_classifier',
    'quota_manager',
    'voice_profile_setup',
    'content_moderator_agent',
    'hf_generator',
    'error_handler',
    
    # Storage
    'state_manager',
    'VoiceProfile',
    
    # Config
    'config',
    'get_message',
]
