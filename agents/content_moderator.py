"""
Content Moderator Agent
=======================
Агент для проверки контента перед генерацией
"""

from typing import Optional, List, Any

from .base_agent import BaseAgent, AgentResult, AgentStatus
from ..utils.content_moderator import content_moderator
from ..config.settings import config, get_message


class ContentModeratorAgent(BaseAgent):
    """
    Агент модерации контента
    Проверяет текст на запрещенные слова, длину и другие ограничения
    """
    
    def __init__(self):
        super().__init__("ContentModerator")
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Проверить контент
        
        Args:
            user_input: Текст для проверки
            user_id: ID пользователя
            **kwargs:
                - check_type: 'full' | 'length_only' | 'safety_only'
                - max_length: максимальная длина (default: 1000)
        
        Returns:
            AgentResult с результатом проверки
        """
        # Extract text
        if isinstance(user_input, dict):
            text = user_input.get('text', '')
        else:
            text = str(user_input)
        
        check_type = kwargs.get('check_type', 'full')
        max_length = kwargs.get('max_length', config.MAX_CHARACTERS_PER_REQUEST)
        
        if check_type == 'length_only':
            return self._check_length_only(text, max_length)
        elif check_type == 'safety_only':
            return self._check_safety_only(text)
        else:
            return self._full_check(text, max_length)
    
    def _full_check(self, text: str, max_length: int) -> AgentResult:
        """Полная проверка контента"""
        # First check length
        is_valid_length, length = content_moderator.validate_length(text, max_length)
        
        if not is_valid_length:
            # Calculate how many chunks needed
            from ..utils.audio_utils import split_text_for_chunks
            chunks = split_text_for_chunks(text, max_length)
            
            return AgentResult(
                status=AgentStatus.REJECTED,
                message=f"Text too long: {length} chars",
                data={
                    'length': length,
                    'max_length': max_length,
                    'suggested_chunks': len(chunks)
                },
                response_to_user=get_message(
                    'text_too_long',
                    chars=length,
                    parts=len(chunks)
                ),
                next_action='split_text'
            )
        
        # Check for blocked content
        is_safe, violations = content_moderator.check_text(text)
        
        if not is_safe:
            return AgentResult(
                status=AgentStatus.REJECTED,
                message=f"Content blocked: {', '.join(violations)}",
                data={
                    'violations': violations,
                    'length': length
                },
                response_to_user=get_message('content_blocked')
            )
        
        # All checks passed
        # Sanitize text
        sanitized_text = content_moderator.sanitize_text(text)
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Content passed all checks",
            data={
                'original_text': text,
                'sanitized_text': sanitized_text,
                'length': length,
                'is_safe': True
            }
        )
    
    def _check_length_only(self, text: str, max_length: int) -> AgentResult:
        """Проверить только длину"""
        is_valid, length = content_moderator.validate_length(text, max_length)
        
        if is_valid:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message=f"Length OK: {length} chars",
                data={'length': length, 'valid': True}
            )
        else:
            return AgentResult(
                status=AgentStatus.REJECTED,
                message=f"Too long: {length} chars",
                data={'length': length, 'valid': False}
            )
    
    def _check_safety_only(self, text: str) -> AgentResult:
        """Проверить только безопасность контента"""
        is_safe, violations = content_moderator.check_text(text)
        
        if is_safe:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message="Content is safe",
                data={'is_safe': True}
            )
        else:
            return AgentResult(
                status=AgentStatus.REJECTED,
                message=f"Unsafe content: {', '.join(violations)}",
                data={'is_safe': False, 'violations': violations}
            )
    
    def quick_check(self, text: str) -> bool:
        """Быстрая проверка (длина + безопасность)"""
        is_valid_length, _ = content_moderator.validate_length(
            text, config.MAX_CHARACTERS_PER_REQUEST
        )
        if not is_valid_length:
            return False
        
        is_safe, _ = content_moderator.check_text(text)
        return is_safe
    
    def split_long_text(self, text: str, max_length: int = None) -> List[str]:
        """Разбить длинный текст на части"""
        if max_length is None:
            max_length = config.MAX_CHARACTERS_PER_REQUEST
        
        from ..utils.audio_utils import split_text_for_chunks
        return split_text_for_chunks(text, max_length)


# Global content moderator agent instance
content_moderator_agent = ContentModeratorAgent()
