"""
Quota Manager Agent
===================
Агент для управления лимитами генераций пользователей
"""

from datetime import timedelta
from typing import Optional, Any

from .base_agent import BaseAgent, AgentResult, AgentStatus
from ..storage.state_manager import state_manager
from ..config.settings import config, get_message


class QuotaManager(BaseAgent):
    """
    Менеджер квот пользователей
    Проверяет и отслеживает лимиты 3 генераций в день
    """
    
    def __init__(self):
        super().__init__("QuotaManager")
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Обработать запрос, связанный с квотами
        
        Args:
            user_input: Не используется (может быть None)
            user_id: ID пользователя
            **kwargs: 
                - action: 'check' | 'increment' | 'status'
        
        Returns:
            AgentResult с информацией о квоте
        """
        action = kwargs.get('action', 'check')
        
        if action == 'check':
            return self._check_quota(user_id)
        elif action == 'increment':
            return self._increment_quota(user_id)
        elif action == 'status':
            return self._get_status(user_id)
        else:
            return AgentResult(
                status=AgentStatus.ERROR,
                message=f"Unknown action: {action}",
                response_to_user="Ошибка: неизвестное действие"
            )
    
    def _check_quota(self, user_id: str) -> AgentResult:
        """Проверить, может ли пользователь сделать генерацию"""
        can_generate, remaining, used = state_manager.check_quota(
            user_id, 
            max_daily=config.MAX_GENERATIONS_PER_DAY
        )
        
        if can_generate:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message=f"Quota OK: {used}/{config.MAX_GENERATIONS_PER_DAY} used",
                data={
                    'can_generate': True,
                    'remaining': remaining,
                    'used': used,
                    'max': config.MAX_GENERATIONS_PER_DAY
                }
            )
        else:
            # Calculate time until reset
            time_until_reset = state_manager.get_time_until_reset()
            hours = int(time_until_reset.total_seconds() // 3600)
            minutes = int((time_until_reset.total_seconds() % 3600) // 60)
            
            time_str = f"{hours}ч {minutes}м"
            
            return AgentResult(
                status=AgentStatus.REJECTED,
                message=f"Quota exceeded: {used}/{config.MAX_GENERATIONS_PER_DAY}",
                data={
                    'can_generate': False,
                    'remaining': 0,
                    'used': used,
                    'max': config.MAX_GENERATIONS_PER_DAY,
                    'time_until_reset': time_str
                },
                response_to_user=get_message('quota_exceeded', time_until_reset=time_str)
            )
    
    def _increment_quota(self, user_id: str) -> AgentResult:
        """Увеличить счетчик генераций"""
        success = state_manager.increment_generation_count(user_id)
        
        if success:
            # Get updated stats
            can_generate, remaining, used = state_manager.check_quota(
                user_id, 
                max_daily=config.MAX_GENERATIONS_PER_DAY
            )
            
            user_state = state_manager.get_user_state(user_id)
            
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message=f"Quota incremented: {used}/{config.MAX_GENERATIONS_PER_DAY}",
                data={
                    'remaining': remaining,
                    'used': used,
                    'total_all_time': user_state.total_generations_all_time
                }
            )
        else:
            return AgentResult(
                status=AgentStatus.ERROR,
                message="Failed to increment quota",
                response_to_user="Ошибка при обновлении счетчика. Попробуйте снова."
            )
    
    def _get_status(self, user_id: str) -> AgentResult:
        """Получить полный статус квоты пользователя"""
        can_generate, remaining, used = state_manager.check_quota(
            user_id, 
            max_daily=config.MAX_GENERATIONS_PER_DAY
        )
        
        user_state = state_manager.get_user_state(user_id)
        
        # Format response message
        response = get_message(
            'quota_status',
            used=used,
            total_all_time=user_state.total_generations_all_time
        )
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message=f"Status: {used}/{config.MAX_GENERATIONS_PER_DAY}",
            data={
                'can_generate': can_generate,
                'remaining': remaining,
                'used': used,
                'max': config.MAX_GENERATIONS_PER_DAY,
                'total_all_time': user_state.total_generations_all_time,
                'has_voice_profile': user_state.voice_profile is not None
            },
            response_to_user=response
        )
    
    def can_generate(self, user_id: str) -> bool:
        """Быстрая проверка возможности генерации"""
        can_generate, _, _ = state_manager.check_quota(
            user_id, 
            max_daily=config.MAX_GENERATIONS_PER_DAY
        )
        return can_generate
    
    def get_remaining(self, user_id: str) -> int:
        """Получить оставшееся количество генераций"""
        _, remaining, _ = state_manager.check_quota(
            user_id, 
            max_daily=config.MAX_GENERATIONS_PER_DAY
        )
        return remaining


# Global quota manager instance
quota_manager = QuotaManager()
