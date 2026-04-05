"""
VoiceCraft Bot - Main Coordinator
=================================
Главный координирующий агент бота
"""

import time
import threading
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

from .base_agent import BaseAgent, AgentResult, AgentStatus
from .intent_classifier import UserIntent, intent_classifier
from .quota_manager import quota_manager
from .voice_profile_setup import voice_profile_setup
from .content_moderator import content_moderator_agent
from .hf_generator import hf_generator
from .error_handler import error_handler, ErrorType
from ..storage.state_manager import state_manager
from ..config.settings import config, get_message


class VoiceCraftBot(BaseAgent):
    """
    Главный координирующий агент VoiceCraft Bot
    
    Управляет workflow:
    1. Классификация намерений
    2. Проверка квот
    3. Настройка голосового профиля
    4. Модерация контента
    5. Генерация речи
    6. Обработка ошибок
    """
    
    def __init__(self):
        super().__init__("VoiceCraftBot")
        
        # User session states
        self._user_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Warmup thread
        self._warmup_thread: Optional[threading.Thread] = None
        self._stop_warmup = threading.Event()
        
        # Start warmup routine
        self._start_warmup()
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Главный метод обработки запроса
        
        Args:
            user_input: Сообщение от пользователя (строка или dict)
            user_id: ID пользователя
            **kwargs: Дополнительные данные (has_audio, audio_path и т.д.)
        
        Returns:
            AgentResult с ответом для пользователя
        """
        # Get or create user session
        session = self._get_session(user_id)
        
        # Extract input data
        if isinstance(user_input, dict):
            text = user_input.get('text', '')
            has_audio = user_input.get('has_audio', False)
            audio_path = user_input.get('audio_path')
        else:
            text = str(user_input)
            has_audio = kwargs.get('has_audio', False)
            audio_path = kwargs.get('audio_path')
        
        # Step 1: Classify intent
        user_state = state_manager.get_user_state(user_id)
        
        intent_result = intent_classifier.process(
            {'text': text, 'has_audio': has_audio, 'is_command': text.startswith('/')},
            user_id,
            has_voice_profile=user_state.voice_profile is not None,
            waiting_for_consent=voice_profile_setup.is_waiting_for(user_id, 'waiting_consent'),
            waiting_for_transcript=voice_profile_setup.is_waiting_for(user_id, 'waiting_transcript')
        )
        
        intent = intent_result.data.get('intent', UserIntent.UNKNOWN)
        
        # Handle different intents
        if intent == UserIntent.START:
            return self._handle_start(user_id)
        
        elif intent == UserIntent.HELP:
            return self._handle_help(user_id)
        
        elif intent == UserIntent.STATUS:
            return self._handle_status(user_id)
        
        elif intent == UserIntent.RESET_VOICE:
            return self._handle_reset_voice(user_id)
        
        elif intent == UserIntent.DEMO:
            return self._handle_demo(user_id)
        
        elif intent == UserIntent.CLONE:
            return self._handle_clone(user_id, audio_path)
        
        elif intent == UserIntent.CONSENT_YES:
            return self._handle_consent(user_id, True)
        
        elif intent == UserIntent.CONSENT_NO:
            return self._handle_consent(user_id, False)
        
        elif intent == UserIntent.TEXT_INPUT:
            # Could be transcript or generate request
            if voice_profile_setup.is_waiting_for(user_id, 'waiting_transcript'):
                return self._handle_transcript(user_id, text)
            elif user_state.voice_profile:
                return self._handle_generate(user_id, text)
            else:
                return AgentResult(
                    status=AgentStatus.NEED_MORE_INFO,
                    message="No voice profile, need setup",
                    response_to_user=get_message('no_voice_profile')
                )
        
        elif intent == UserIntent.GENERATE:
            return self._handle_generate(user_id, text)
        
        else:
            return AgentResult(
                status=AgentStatus.NEED_MORE_INFO,
                message="Unknown intent",
                response_to_user="Не понял команду. Используйте /help для справки."
            )
    
    def _get_session(self, user_id: str) -> Dict[str, Any]:
        """Получить или создать сессию пользователя"""
        if user_id not in self._user_sessions:
            self._user_sessions[user_id] = {
                'created_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat(),
            }
        else:
            self._user_sessions[user_id]['last_activity'] = datetime.now().isoformat()
        
        return self._user_sessions[user_id]
    
    def _handle_start(self, user_id: str) -> AgentResult:
        """Обработать команду /start"""
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Welcome message sent",
            response_to_user=get_message('welcome')
        )
    
    def _handle_help(self, user_id: str) -> AgentResult:
        """Обработать команду /help"""
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Help message sent",
            response_to_user=get_message('help')
        )
    
    def _handle_status(self, user_id: str) -> AgentResult:
        """Обработать команду /limits"""
        return quota_manager.process(None, user_id, action='status')
    
    def _handle_reset_voice(self, user_id: str) -> AgentResult:
        """Обработать команду /voice (сброс профиля)"""
        return voice_profile_setup.process(None, user_id, step='reset')
    
    def _handle_demo(self, user_id: str) -> AgentResult:
        """Обработать команду /demo"""
        # Set demo mode in session
        session = self._get_session(user_id)
        session['demo_mode'] = True
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Demo mode activated",
            response_to_user=get_message('demo_mode')
        )
    
    def _handle_clone(self, user_id: str, audio_path: Optional[str]) -> AgentResult:
        """Обработать запрос на клонирование голоса"""
        if audio_path:
            # Audio uploaded, process it
            return voice_profile_setup.process(None, user_id, step='audio_uploaded', audio_path=audio_path)
        else:
            # Start setup process
            return voice_profile_setup.process(None, user_id, step='start')
    
    def _handle_consent(self, user_id: str, consent: bool) -> AgentResult:
        """Обработать ответ о согласии"""
        return voice_profile_setup.process(None, user_id, step='consent', consent=consent)
    
    def _handle_transcript(self, user_id: str, transcript: str) -> AgentResult:
        """Обработать транскрипцию"""
        return voice_profile_setup.process(None, user_id, step='transcript', transcript=transcript)
    
    def _handle_generate(self, user_id: str, text: str) -> AgentResult:
        """Обработать генерацию речи"""
        # Step 1: Check quota
        quota_result = quota_manager.process(None, user_id, action='check')
        
        if quota_result.status == AgentStatus.REJECTED:
            return quota_result
        
        # Step 2: Moderate content
        moderation_result = content_moderator_agent.process(text, user_id)
        
        if moderation_result.status == AgentStatus.REJECTED:
            return moderation_result
        
        sanitized_text = moderation_result.data.get('sanitized_text', text)
        
        # Step 3: Get voice profile
        session = self._get_session(user_id)
        use_demo = session.get('demo_mode', False)
        
        user_state = state_manager.get_user_state(user_id)
        voice_profile = user_state.voice_profile
        
        # Step 4: Generate speech
        gen_result = hf_generator.process(
            {'text': sanitized_text},
            user_id,
            voice_profile=voice_profile,
            use_demo=use_demo
        )
        
        if gen_result.status == AgentStatus.SUCCESS:
            # Increment quota
            quota_manager.process(None, user_id, action='increment')
            
            # Get updated remaining count
            remaining = quota_manager.get_remaining(user_id)
            duration = gen_result.data.get('duration', 0)
            
            # Format success message
            success_msg = get_message(
                'generation_success',
                duration=f"{duration:.1f}",
                remaining=remaining
            )
            
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message="Generation successful",
                data={
                    'audio_data': gen_result.data.get('audio_data'),
                    'duration': duration,
                    'remaining': remaining
                },
                response_to_user=success_msg
            )
        else:
            # Handle error
            error_type = error_handler.classify_error(gen_result.message)
            return error_handler.process(
                gen_result.message,
                user_id,
                error_type=error_type,
                original_error=gen_result.message
            )
    
    def _start_warmup(self):
        """Запустить фоновый warm-up поток"""
        def warmup_routine():
            while not self._stop_warmup.is_set():
                try:
                    hf_generator.warmup()
                except:
                    pass
                
                # Wait for next warmup interval
                self._stop_warmup.wait(config.WARMUP_INTERVAL_MINUTES * 60)
        
        self._warmup_thread = threading.Thread(target=warmup_routine, daemon=True)
        self._warmup_thread.start()
    
    def stop(self):
        """Остановить бота"""
        self._stop_warmup.set()
        if self._warmup_thread:
            self._warmup_thread.join(timeout=5)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику бота"""
        return {
            'active_sessions': len(self._user_sessions),
            'storage_stats': state_manager.get_all_stats()
        }


# Global bot instance
voicecraft_bot = VoiceCraftBot()
