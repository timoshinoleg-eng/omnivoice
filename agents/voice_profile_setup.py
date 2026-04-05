"""
Voice Profile Setup Agent
=========================
Агент для настройки голосового профиля пользователя с S3 хранением
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path

from .base_agent import BaseAgent, AgentResult, AgentStatus
from ..storage.state_manager import state_manager, VoiceProfile
from ..utils.audio_utils import validate_audio_file, convert_to_wav
from ..utils.hf_api import hf_api
from ..utils.s3_storage import init_storage, voice_storage
from ..config.settings import config, get_message


class VoiceProfileSetup(BaseAgent):
    """
    Агент настройки голосового профиля
    Управляет процессом загрузки и валидации образца голоса
    """
    
    def __init__(self):
        super().__init__("VoiceProfileSetup")
        # Track user states in setup process
        self._setup_states: Dict[str, Dict[str, Any]] = {}
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Обработать шаг настройки голосового профиля
        
        Args:
            user_input: Аудио файл или текст (транскрипция/согласие)
            user_id: ID пользователя
            **kwargs:
                - step: 'start' | 'audio_uploaded' | 'consent' | 'transcript' | 'complete'
                - audio_path: путь к загруженному аудио
        
        Returns:
            AgentResult с результатом шага
        """
        step = kwargs.get('step', 'start')
        
        if step == 'start':
            return self._start_setup(user_id)
        elif step == 'audio_uploaded':
            audio_path = kwargs.get('audio_path')
            return self._process_audio_upload(user_id, audio_path)
        elif step == 'consent':
            consent = kwargs.get('consent')
            return self._process_consent(user_id, consent)
        elif step == 'transcript':
            transcript = kwargs.get('transcript')
            return self._process_transcript(user_id, transcript)
        elif step == 'reset':
            return self._reset_profile(user_id)
        else:
            return AgentResult(
                status=AgentStatus.ERROR,
                message=f"Unknown step: {step}",
                response_to_user="Ошибка: неизвестный шаг настройки"
            )
    
    def _start_setup(self, user_id: str) -> AgentResult:
        """Начать процесс настройки"""
        # Initialize setup state
        self._setup_states[user_id] = {
            'step': 'waiting_audio',
            'audio_path': None,
            'audio_duration': None,
            'consent_given': False,
            'transcript': None
        }
        
        return AgentResult(
            status=AgentStatus.NEED_MORE_INFO,
            message="Setup started, waiting for audio",
            data={'next_step': 'audio_upload'},
            response_to_user=get_message('voice_setup_start')
        )
    
    def _process_audio_upload(self, user_id: str, audio_path: str) -> AgentResult:
        """Обработать загруженное аудио"""
        if not audio_path or not os.path.exists(audio_path):
            return AgentResult(
                status=AgentStatus.ERROR,
                message="Audio file not found",
                response_to_user="Ошибка: аудио файл не найден"
            )
        
        # Validate audio
        is_valid, message, duration = validate_audio_file(
            audio_path,
            min_duration=config.MIN_VOICE_SAMPLE_DURATION,
            max_duration=config.MAX_VOICE_SAMPLE_DURATION
        )
        
        if not is_valid:
            return AgentResult(
                status=AgentStatus.REJECTED,
                message=f"Invalid audio: {message}",
                data={'duration': duration},
                response_to_user=get_message('invalid_audio', duration=f"{duration:.1f}")
            )
        
        # Store audio info
        if user_id not in self._setup_states:
            self._setup_states[user_id] = {}
        
        self._setup_states[user_id].update({
            'step': 'waiting_consent',
            'audio_path': audio_path,
            'audio_duration': duration
        })
        
        return AgentResult(
            status=AgentStatus.NEED_MORE_INFO,
            message=f"Audio valid ({duration:.1f}s), waiting for consent",
            data={
                'duration': duration,
                'next_step': 'consent'
            },
            response_to_user=get_message('voice_consent_request')
        )
    
    def _process_consent(self, user_id: str, consent: bool) -> AgentResult:
        """Обработать подтверждение согласия"""
        setup_state = self._setup_states.get(user_id)
        
        if not setup_state:
            return AgentResult(
                status=AgentStatus.ERROR,
                message="No active setup session",
                response_to_user="Ошибка: сессия настройки истекла. Начните заново."
            )
        
        if not consent:
            # User declined consent
            del self._setup_states[user_id]
            return AgentResult(
                status=AgentStatus.REJECTED,
                message="Consent declined",
                response_to_user="❌ Настройка отменена. Для клонирования голоса требуется подтверждение прав."
            )
        
        # Consent given, move to transcript
        setup_state['consent_given'] = True
        setup_state['step'] = 'waiting_transcript'
        
        return AgentResult(
            status=AgentStatus.NEED_MORE_INFO,
            message="Consent given, waiting for transcript",
            data={'next_step': 'transcript'},
            response_to_user=get_message('voice_transcript_request')
        )
    
    def _process_transcript(self, user_id: str, transcript: str) -> AgentResult:
        """Обработать транскрипцию и создать профиль с S3 хранением"""
        setup_state = self._setup_states.get(user_id)
        
        if not setup_state:
            return AgentResult(
                status=AgentStatus.ERROR,
                message="No active setup session",
                response_to_user="Ошибка: сессия настройки истекла. Начните заново."
            )
        
        if not transcript or len(transcript.strip()) < 3:
            return AgentResult(
                status=AgentStatus.NEED_MORE_INFO,
                message="Transcript too short",
                response_to_user="Текст слишком короткий. Введите полную расшифровку аудио."
            )
        
        audio_path = setup_state.get('audio_path')
        
        if not audio_path or not os.path.exists(audio_path):
            return AgentResult(
                status=AgentStatus.ERROR,
                message="Audio file lost",
                response_to_user="Ошибка: аудио файл не найден. Начните заново."
            )
        
        # Step 1: Upload to S3 for permanent storage
        storage = init_storage()
        s3_success, s3_result = storage.upload_voice_sample(user_id, audio_path)
        
        if not s3_success:
            return AgentResult(
                status=AgentStatus.ERROR,
                message=f"S3 upload failed: {s3_result}",
                response_to_user=f"❌ Ошибка сохранения аудио: {s3_result}\n\nПопробуйте снова."
            )
        
        s3_url = s3_result
        s3_key = storage.get_voice_sample_key_from_url(s3_url)
        
        # Step 2: Also upload to HF for immediate use (with retry)
        hf_success, hf_result = hf_api.upload_audio(audio_path)
        
        if not hf_success:
            # HF upload failed, but S3 is OK - still create profile
            print(f"[VoiceProfile] HF upload failed: {hf_result}, using S3 only")
            hf_temp_url = None
        else:
            hf_temp_url = hf_result
        
        # Step 3: Create voice profile with both URLs
        voice_profile = VoiceProfile(
            ref_audio_url=hf_temp_url or s3_url,  # Use HF temp if available, else S3
            ref_text=transcript.strip(),
            created_at=datetime.now().isoformat(),
            expires_at=None,  # No expiration with S3
            s3_url=s3_url,    # Permanent S3 URL
            s3_key=s3_key     # S3 key for refresh
        )
        
        # Save to user state
        state_manager.set_voice_profile(user_id, voice_profile)
        
        # Cleanup setup state
        del self._setup_states[user_id]
        
        # Cleanup temp file
        try:
            os.remove(audio_path)
        except:
            pass
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Voice profile created successfully with S3 backup",
            data={
                's3_url': s3_url,
                's3_key': s3_key,
                'hf_url': hf_temp_url,
                'transcript': transcript.strip(),
                'duration': setup_state.get('audio_duration')
            },
            response_to_user=get_message('voice_profile_created') + "\n\n💾 Голос сохранён в облаке (7 дней доступности)."
        )
    
    def _reset_profile(self, user_id: str) -> AgentResult:
        """Сбросить голосовой профиль"""
        state_manager.clear_voice_profile(user_id)
        
        # Also clear any active setup state
        if user_id in self._setup_states:
            del self._setup_states[user_id]
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            message="Voice profile reset",
            response_to_user=get_message('voice_reset_confirm')
        )
    
    def get_setup_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить текущее состояние настройки"""
        return self._setup_states.get(user_id)
    
    def is_waiting_for(self, user_id: str, step: str) -> bool:
        """Проверить, ожидается ли определенный шаг"""
        setup_state = self._setup_states.get(user_id)
        if not setup_state:
            return False
        return setup_state.get('step') == step
    
    def has_active_setup(self, user_id: str) -> bool:
        """Проверить, есть ли активная сессия настройки"""
        return user_id in self._setup_states


# Global voice profile setup instance
voice_profile_setup = VoiceProfileSetup()
