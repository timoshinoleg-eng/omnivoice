"""
State Management Module
=======================
Управление состоянием пользователей: лимиты, профили голосов, статистика
"""

import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any
from pathlib import Path
import threading


@dataclass
class VoiceProfile:
    """Профиль голоса пользователя"""
    ref_audio_url: str
    ref_text: str
    created_at: str
    expires_at: Optional[str] = None  # HF temp files expire
    s3_url: Optional[str] = None      # Permanent S3 URL
    s3_key: Optional[str] = None      # S3 key for refresh
    
    def is_expired(self) -> bool:
        """Проверить, не истек ли срок действия URL"""
        # If we have S3, never expired
        if self.s3_url:
            return False
        
        if self.expires_at:
            return datetime.now() > datetime.fromisoformat(self.expires_at)
        
        # HF temp files typically expire after ~1 hour
        created = datetime.fromisoformat(self.created_at)
        return (datetime.now() - created) > timedelta(hours=1)
    
    def get_effective_url(self) -> str:
        """Получить рабочий URL (S3 приоритет)"""
        return self.s3_url or self.ref_audio_url
    
    def needs_refresh(self) -> bool:
        """Проверить нужно ли обновить URL"""
        return self.is_expired() and self.s3_key is not None


@dataclass
class UserState:
    """Состояние пользователя"""
    user_id: str
    daily_generations_used: int = 0
    last_generation_date: str = ""  # YYYY-MM-DD
    voice_profile: Optional[VoiceProfile] = None
    total_generations_all_time: int = 0
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class StateManager:
    """
    Менеджер состояний пользователей
    Потокобезопасное хранение в JSON файлах
    """
    
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = "/mnt/okcomputer/output/voicecraft_bot/storage/data"
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self._lock = threading.Lock()
        self._cache: Dict[str, UserState] = {}
        
    def _get_user_file(self, user_id: str) -> Path:
        """Получить путь к файлу пользователя"""
        return self.storage_dir / f"{user_id}.json"
    
    def _load_user(self, user_id: str) -> Optional[UserState]:
        """Загрузить состояние пользователя из файла"""
        file_path = self._get_user_file(user_id)
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert voice_profile dict to VoiceProfile object
            if data.get('voice_profile'):
                data['voice_profile'] = VoiceProfile(**data['voice_profile'])
            
            return UserState(**data)
        except Exception as e:
            print(f"Error loading user {user_id}: {e}")
            return None
    
    def _save_user(self, user_state: UserState) -> bool:
        """Сохранить состояние пользователя в файл"""
        file_path = self._get_user_file(user_state.user_id)
        
        try:
            # Convert to dict
            data = asdict(user_state)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving user {user_state.user_id}: {e}")
            return False
    
    def get_user_state(self, user_id: str) -> UserState:
        """
        Получить состояние пользователя (создает новое если не существует)
        Проверяет и сбрасывает дневные лимиты если нужно
        """
        with self._lock:
            # Check cache first
            if user_id in self._cache:
                user_state = self._cache[user_id]
            else:
                # Load from file
                user_state = self._load_user(user_id)
                if user_state is None:
                    # Create new user
                    user_state = UserState(user_id=user_id)
                self._cache[user_id] = user_state
            
            # Check if we need to reset daily counter
            current_date = datetime.now().strftime('%Y-%m-%d')
            if user_state.last_generation_date != current_date:
                user_state.daily_generations_used = 0
                user_state.last_generation_date = current_date
                self._save_user(user_state)
            
            return user_state
    
    def update_user_state(self, user_state: UserState) -> bool:
        """Обновить состояние пользователя"""
        with self._lock:
            self._cache[user_state.user_id] = user_state
            return self._save_user(user_state)
    
    def increment_generation_count(self, user_id: str) -> bool:
        """Увеличить счетчик генераций"""
        with self._lock:
            user_state = self.get_user_state(user_id)
            user_state.daily_generations_used += 1
            user_state.total_generations_all_time += 1
            user_state.last_generation_date = datetime.now().strftime('%Y-%m-%d')
            return self._save_user(user_state)
    
    def set_voice_profile(self, user_id: str, voice_profile: VoiceProfile) -> bool:
        """Установить голосовой профиль пользователя"""
        with self._lock:
            user_state = self.get_user_state(user_id)
            user_state.voice_profile = voice_profile
            return self._save_user(user_state)
    
    def clear_voice_profile(self, user_id: str) -> bool:
        """Очистить голосовой профиль пользователя"""
        with self._lock:
            user_state = self.get_user_state(user_id)
            user_state.voice_profile = None
            return self._save_user(user_state)
    
    def check_quota(self, user_id: str, max_daily: int = 3) -> tuple:
        """
        Проверить квоту пользователя
        Returns: (can_generate: bool, remaining: int, used: int)
        """
        user_state = self.get_user_state(user_id)
        used = user_state.daily_generations_used
        remaining = max(0, max_daily - used)
        can_generate = used < max_daily
        return can_generate, remaining, used
    
    def get_time_until_reset(self) -> timedelta:
        """Получить время до сброса лимитов (00:00 UTC)"""
        now = datetime.utcnow()
        tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        return tomorrow - now
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Получить общую статистику"""
        total_users = 0
        total_generations = 0
        active_today = 0
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for file_path in self.storage_dir.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                total_users += 1
                total_generations += data.get('total_generations_all_time', 0)
                
                if data.get('last_generation_date') == current_date:
                    active_today += 1
            except:
                pass
        
        return {
            'total_users': total_users,
            'total_generations': total_generations,
            'active_today': active_today
        }


# Global state manager instance
state_manager = StateManager()
