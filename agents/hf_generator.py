"""
HF Generator Agent
==================
Агент для генерации речи через Hugging Face Space API
"""

import os
import tempfile
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

from .base_agent import BaseAgent, AgentResult, AgentStatus
from ..utils.hf_api import hf_api
from ..utils.audio_utils import estimate_audio_duration
from ..utils.storage import init_storage
from ..utils.audio_watermarker import get_watermarker
from ..storage.state_manager import state_manager
from ..config.settings import config, get_message


class HFGenerator(BaseAgent):
    """
    Агент генерации речи через HF Space
    Управляет вызовами API и обработкой результатов
    """
    
    def __init__(self):
        super().__init__("HFGenerator")
        # Track active generations to prevent concurrent requests
        self._active_generations: Dict[str, Dict[str, Any]] = {}
    
    def process(self, user_input: Any, user_id: str, **kwargs) -> AgentResult:
        """
        Сгенерировать речь
        
        Args:
            user_input: Текст для озвучки (или dict с 'text')
            user_id: ID пользователя
            **kwargs:
                - voice_profile: VoiceProfile объект (если None, используется демо)
                - speed: скорость речи (default: 1.0)
                - language: язык (default: 'auto')
        
        Returns:
            AgentResult с аудио данными или ошибкой
        """
        # Extract text
        if isinstance(user_input, dict):
            text = user_input.get('text', '')
        else:
            text = str(user_input)
        
        # Check for concurrent generation
        if user_id in self._active_generations:
            job_id = self._active_generations[user_id].get('job_id', 'unknown')
            return AgentResult(
                status=AgentStatus.REJECTED,
                message="Concurrent request detected",
                data={'job_id': job_id},
                response_to_user=get_message('concurrent_request', job_id=job_id)
            )
        
        # Get voice profile
        voice_profile = kwargs.get('voice_profile')
        
        if voice_profile is None:
            # Try to get from user state
            user_state = state_manager.get_user_state(user_id)
            voice_profile = user_state.voice_profile
        
        # If still no voice profile, use demo or return error
        use_demo = kwargs.get('use_demo', False)
        
        if voice_profile is None:
            if use_demo and config.DEMO_VOICE_URL:
                voice_profile = type('obj', (object,), {
                    'ref_audio_url': config.DEMO_VOICE_URL,
                    'ref_text': config.DEMO_VOICE_TEXT
                })()
            else:
                return AgentResult(
                    status=AgentStatus.REJECTED,
                    message="No voice profile",
                    response_to_user=get_message('no_voice_profile')
                )
        
        # Check if voice profile expired
        if hasattr(voice_profile, 'is_expired') and voice_profile.is_expired():
            # Try to refresh from S3 if available
            if hasattr(voice_profile, 's3_key') and voice_profile.s3_key:
                storage = init_storage()
                refreshed, new_url = storage.refresh_presigned_url(voice_profile.s3_key)
                if refreshed:
                    voice_profile.s3_url = new_url
                    voice_profile.ref_audio_url = new_url
                else:
                    return AgentResult(
                        status=AgentStatus.ERROR,
                        message="Voice profile expired and refresh failed",
                        response_to_user=get_message('voice_profile_expired')
                    )
            else:
                return AgentResult(
                    status=AgentStatus.ERROR,
                    message="Voice profile expired",
                    response_to_user=get_message('voice_profile_expired')
                )
        
        # Start generation
        job_id = f"{user_id}_{int(time.time())}"
        self._active_generations[user_id] = {
            'job_id': job_id,
            'start_time': datetime.now(),
            'text': text
        }
        
        try:
            # Estimate duration
            estimated_duration = estimate_audio_duration(text)
            
            # Check if might exceed limit
            if estimated_duration > config.MAX_AUDIO_DURATION_SECONDS:
                del self._active_generations[user_id]
                return AgentResult(
                    status=AgentStatus.REJECTED,
                    message=f"Text too long, estimated {estimated_duration:.1f}s > {config.MAX_AUDIO_DURATION_SECONDS}s",
                    response_to_user=f"⚠️ Текст слишком длинный. Ожидаемая длительность: {estimated_duration:.1f}s (максимум: {config.MAX_AUDIO_DURATION_SECONDS}s)"
                )
            
            # Call HF API
            speed = kwargs.get('speed', 1.0)
            language = kwargs.get('language', 'auto')
            
            success, result, message = hf_api.generate_speech(
                text=text,
                ref_audio_url=voice_profile.ref_audio_url,
                ref_text=voice_profile.ref_text,
                speed=speed,
                language=language,
                timeout=config.HF_REQUEST_TIMEOUT
            )
            
            # Remove from active generations
            del self._active_generations[user_id]
            
            if success:
                # Calculate actual duration (estimate)
                actual_duration = estimate_audio_duration(text)
                
                # Add audio watermark
                watermarker = get_watermarker()
                watermarked_audio = watermarker.add_watermark(result)
                
                return AgentResult(
                    status=AgentStatus.SUCCESS,
                    message="Generation successful with watermark",
                    data={
                        'audio_data': watermarked_audio,
                        'duration': actual_duration,
                        'text': text,
                        'job_id': job_id,
                        'watermarked': True
                    }
                )
            else:
                # Handle specific error types
                if message == "TIMEOUT":
                    return AgentResult(
                        status=AgentStatus.ERROR,
                        message="Generation timeout",
                        response_to_user=get_message('timeout_error')
                    )
                elif message == "RATE_LIMIT":
                    return AgentResult(
                        status=AgentStatus.ERROR,
                        message="Rate limit exceeded",
                        response_to_user=get_message('rate_limit_error')
                    )
                elif message == "SERVICE_UNAVAILABLE":
                    return AgentResult(
                        status=AgentStatus.ERROR,
                        message="Service unavailable",
                        response_to_user=get_message('service_unavailable')
                    )
                else:
                    return AgentResult(
                        status=AgentStatus.ERROR,
                        message=f"Generation failed: {message}",
                        response_to_user=f"❌ Ошибка генерации: {message}"
                    )
        
        except Exception as e:
            # Cleanup on error
            if user_id in self._active_generations:
                del self._active_generations[user_id]
            
            return AgentResult(
                status=AgentStatus.ERROR,
                message=f"Exception during generation: {str(e)}",
                response_to_user=f"❌ Ошибка: {str(e)}"
            )
    
    def warmup(self) -> AgentResult:
        """Выполнить warm-up запрос к HF Space"""
        success = hf_api.warmup()
        
        if success:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                message="Warmup successful",
                response_to_user=None  # Silent warmup
            )
        else:
            return AgentResult(
                status=AgentStatus.ERROR,
                message="Warmup failed",
                response_to_user=None
            )
    
    def check_health(self) -> AgentResult:
        """Проверить состояние HF Space"""
        is_healthy, message = hf_api.check_health()
        
        return AgentResult(
            status=AgentStatus.SUCCESS if is_healthy else AgentStatus.ERROR,
            message=message,
            data={'healthy': is_healthy}
        )
    
    def is_generating(self, user_id: str) -> bool:
        """Проверить, выполняется ли генерация для пользователя"""
        return user_id in self._active_generations
    
    def get_generation_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить статус активной генерации"""
        return self._active_generations.get(user_id)
    
    def cancel_generation(self, user_id: str) -> bool:
        """Отменить активную генерацию"""
        if user_id in self._active_generations:
            del self._active_generations[user_id]
            return True
        return False


# Global HF generator instance
hf_generator = HFGenerator()
