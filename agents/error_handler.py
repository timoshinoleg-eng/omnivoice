"""
Error Handler Agent
===================
Агент для обработки ошибок и восстановления
"""

import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

from .base_agent import BaseAgent, AgentResult, AgentStatus
from ..config.settings import get_message


class ErrorType(Enum):
    """Типы ошибок"""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    SERVICE_UNAVAILABLE = "service_unavailable"
    NETWORK_ERROR = "network_error"
    INVALID_INPUT = "invalid_input"
    VOICE_PROFILE_EXPIRED = "voice_profile_expired"
    QUOTA_EXCEEDED = "quota_exceeded"
    UNKNOWN = "unknown"


@dataclass
class ErrorContext:
    """Контекст ошибки"""
    error_type: ErrorType
    original_error: str
    user_id: str
    retry_count: int = 0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class ErrorHandler(BaseAgent):
    """
    Обработчик ошибок
    Предоставляет стратегии восстановления для различных типов ошибок
    """
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAYS = {
        ErrorType.TIMEOUT: [5, 10, 15],  # seconds
        ErrorType.RATE_LIMIT: [60, 120, 180],
        ErrorType.SERVICE_UNAVAILABLE: [30, 60, 120],
        ErrorType.NETWORK_ERROR: [3, 5, 10],
    }
    
    def __init__(self):
        super().__init__("ErrorHandler")
        self._error_history: Dict[str, list] = {}  # user_id -> list of ErrorContext
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Обработать ошибку
        
        Args:
            user_input: Ошибка или контекст ошибки
            user_id: ID пользователя
            **kwargs:
                - error_type: ErrorType
                - original_error: str
                - can_retry: bool
        
        Returns:
            AgentResult с рекомендациями
        """
        error_type = kwargs.get('error_type', ErrorType.UNKNOWN)
        original_error = kwargs.get('original_error', str(user_input))
        can_retry = kwargs.get('can_retry', True)
        
        # Log error
        error_context = ErrorContext(
            error_type=error_type,
            original_error=original_error,
            user_id=user_id
        )
        self._log_error(user_id, error_context)
        
        # Get retry count
        retry_count = self._get_retry_count(user_id, error_type)
        
        # Determine strategy
        if can_retry and retry_count < self.MAX_RETRIES:
            strategy = self._get_retry_strategy(error_type, retry_count)
            return AgentResult(
                status=AgentStatus.NEED_MORE_INFO,
                message=f"Error can be retried: {error_type.value}",
                data={
                    'error_type': error_type.value,
                    'retry_count': retry_count,
                    'max_retries': self.MAX_RETRIES,
                    'retry_delay': strategy['delay'],
                    'strategy': strategy
                },
                response_to_user=strategy['message'],
                next_action='retry'
            )
        else:
            # Cannot retry, provide fallback
            fallback = self._get_fallback(error_type)
            return AgentResult(
                status=AgentStatus.ERROR,
                message=f"Error cannot be retried: {error_type.value}",
                data={
                    'error_type': error_type.value,
                    'fallback': fallback
                },
                response_to_user=fallback['message'],
                next_action=fallback['action']
            )
    
    def _log_error(self, user_id: str, error_context: ErrorContext):
        """Залогировать ошибку"""
        if user_id not in self._error_history:
            self._error_history[user_id] = []
        
        self._error_history[user_id].append(error_context)
        
        # Keep only last 10 errors per user
        self._error_history[user_id] = self._error_history[user_id][-10:]
    
    def _get_retry_count(self, user_id: str, error_type: ErrorType) -> int:
        """Получить количество повторных попыток для данного типа ошибки"""
        if user_id not in self._error_history:
            return 0
        
        # Count recent errors of same type (within last 5 minutes)
        current_time = time.time()
        recent_errors = [
            e for e in self._error_history[user_id]
            if e.error_type == error_type and (current_time - e.timestamp) < 300
        ]
        
        return len(recent_errors)
    
    def _get_retry_strategy(self, error_type: ErrorType, retry_count: int) -> Dict[str, Any]:
        """Получить стратегию повторной попытки"""
        delays = self.RETRY_DELAYS.get(error_type, [5, 10, 15])
        delay = delays[min(retry_count, len(delays) - 1)]
        
        messages = {
            ErrorType.TIMEOUT: (
                f"⏱️ Превышено время ожидания. "
                f"Повторная попытка через {delay} секунд... ({retry_count + 1}/{self.MAX_RETRIES})"
            ),
            ErrorType.RATE_LIMIT: (
                f"🚦 Слишком много запросов. "
                f"Подождите {delay} секунд... ({retry_count + 1}/{self.MAX_RETRIES})"
            ),
            ErrorType.SERVICE_UNAVAILABLE: (
                f"🔧 Сервис временно недоступен. "
                f"Повторная попытка через {delay} секунд... ({retry_count + 1}/{self.MAX_RETRIES})"
            ),
            ErrorType.NETWORK_ERROR: (
                f"📡 Проблема с сетью. "
                f"Повторная попытка через {delay} секунд... ({retry_count + 1}/{self.MAX_RETRIES})"
            ),
        }
        
        return {
            'delay': delay,
            'message': messages.get(error_type, f"Ошибка. Повторная попытка через {delay} секунд..."),
            'can_retry': True
        }
    
    def _get_fallback(self, error_type: ErrorType) -> Dict[str, Any]:
        """Получить fallback стратегию"""
        fallbacks = {
            ErrorType.TIMEOUT: {
                'message': get_message('timeout_error'),
                'action': 'split_text'
            },
            ErrorType.RATE_LIMIT: {
                'message': get_message('rate_limit_error'),
                'action': 'wait_and_notify'
            },
            ErrorType.SERVICE_UNAVAILABLE: {
                'message': get_message('service_unavailable'),
                'action': 'notify_when_ready'
            },
            ErrorType.VOICE_PROFILE_EXPIRED: {
                'message': get_message('voice_profile_expired'),
                'action': 'reset_voice_profile'
            },
            ErrorType.QUOTA_EXCEEDED: {
                'message': get_message('quota_exceeded', time_until_reset="завтра"),
                'action': 'show_upgrade_options'
            },
            ErrorType.INVALID_INPUT: {
                'message': "❌ Некорректный ввод. Проверьте формат и попробуйте снова.",
                'action': 'request_correct_input'
            },
        }
        
        return fallbacks.get(error_type, {
            'message': "❌ Произошла ошибка. Попробуйте снова позже.",
            'action': 'retry_later'
        })
    
    def classify_error(self, error_message: str) -> ErrorType:
        """Классифицировать ошибку по сообщению"""
        error_lower = error_message.lower()
        
        if 'timeout' in error_lower or 'time' in error_lower:
            return ErrorType.TIMEOUT
        elif '429' in error_lower or 'rate limit' in error_lower or 'too many' in error_lower:
            return ErrorType.RATE_LIMIT
        elif '503' in error_lower or 'unavailable' in error_lower or 'overloaded' in error_lower:
            return ErrorType.SERVICE_UNAVAILABLE
        elif 'network' in error_lower or 'connection' in error_lower:
            return ErrorType.NETWORK_ERROR
        elif 'expired' in error_lower or 'profile' in error_lower:
            return ErrorType.VOICE_PROFILE_EXPIRED
        elif 'quota' in error_lower or 'limit' in error_lower or 'exceeded' in error_lower:
            return ErrorType.QUOTA_EXCEEDED
        elif 'invalid' in error_lower or 'format' in error_lower:
            return ErrorType.INVALID_INPUT
        else:
            return ErrorType.UNKNOWN
    
    def clear_error_history(self, user_id: str):
        """Очистить историю ошибок пользователя"""
        if user_id in self._error_history:
            del self._error_history[user_id]
    
    def get_error_stats(self, user_id: str) -> Dict[str, Any]:
        """Получить статистику ошибок пользователя"""
        if user_id not in self._error_history:
            return {'total_errors': 0, 'error_types': {}}
        
        errors = self._error_history[user_id]
        error_types = {}
        
        for e in errors:
            et = e.error_type.value
            error_types[et] = error_types.get(et, 0) + 1
        
        return {
            'total_errors': len(errors),
            'error_types': error_types
        }


# Global error handler instance
error_handler = ErrorHandler()
