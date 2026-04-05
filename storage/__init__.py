"""
VoiceCraft Bot Storage
======================
Модуль хранения состояний пользователей
"""

from .state_manager import StateManager, UserState, VoiceProfile, state_manager

__all__ = [
    'StateManager',
    'UserState',
    'VoiceProfile',
    'state_manager',
]
