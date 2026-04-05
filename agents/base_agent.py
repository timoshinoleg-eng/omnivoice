"""
Base Agent Class
================
Базовый класс для всех агентов бота
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum


class AgentStatus(Enum):
    """Статусы выполнения агента"""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    REJECTED = "rejected"
    NEED_MORE_INFO = "need_more_info"


@dataclass
class AgentResult:
    """Результат выполнения агента"""
    status: AgentStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    next_action: Optional[str] = None
    response_to_user: Optional[str] = None


class BaseAgent(ABC):
    """Базовый класс агента"""
    
    def __init__(self, name: str):
        self.name = name
        self.context: Dict[str, Any] = {}
    
    @abstractmethod
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Основной метод обработки
        
        Args:
            user_input: Входные данные от пользователя
            user_id: ID пользователя
            **kwargs: Дополнительные параметры
        
        Returns:
            AgentResult с результатом выполнения
        """
        pass
    
    def set_context(self, key: str, value: Any):
        """Установить контекст для агента"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Получить значение из контекста"""
        return self.context.get(key, default)
    
    def clear_context(self):
        """Очистить контекст"""
        self.context.clear()


class AgentRouter:
    """Роутер для переключения между агентами"""
    
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.current_agent: Optional[str] = None
    
    def register_agent(self, name: str, agent: BaseAgent):
        """Зарегистрировать агента"""
        self.agents[name] = agent
    
    def route(self, agent_name: str, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """Направить запрос к указанному агенту"""
        if agent_name not in self.agents:
            return AgentResult(
                status=AgentStatus.ERROR,
                message=f"Agent '{agent_name}' not found",
                response_to_user="Ошибка: неизвестная команда"
            )
        
        self.current_agent = agent_name
        agent = self.agents[agent_name]
        return agent.process(user_input, user_id, **kwargs)
