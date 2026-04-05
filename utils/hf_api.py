"""
Hugging Face Space API Integration
====================================
Интеграция с HF Space для генерации речи через OmniVoice
"""

import requests
import uuid
import time
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import json


class HFSpaceAPI:
    """Клиент для работы с HF Space API"""
    
    def __init__(self, space_url: str = "https://k2-fsa-omnivoice.hf.space"):
        self.space_url = space_url.rstrip('/')
        self.predict_endpoint = f"{self.space_url}/run/predict"
        self.upload_endpoint = f"{self.space_url}/upload"
        self.file_endpoint = f"{self.space_url}/file"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VoiceCraftBot/1.0'
        })
    
    def upload_audio(self, file_path: str) -> Tuple[bool, str]:
        """
        Загрузить аудио файл на HF Space
        
        Returns:
            (success: bool, url_or_error: str)
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'files': (Path(file_path).name, f)}
                
                response = self.session.post(
                    self.upload_endpoint,
                    files=files,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # HF returns list of uploaded files
                    if isinstance(data, list) and len(data) > 0:
                        file_name = data[0]
                        file_url = f"{self.file_endpoint}={file_name}"
                        return True, file_url
                    return False, "Invalid upload response format"
                
                return False, f"Upload failed: HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Upload timeout"
        except Exception as e:
            return False, f"Upload error: {str(e)}"
    
    def generate_speech(self,
                       text: str,
                       ref_audio_url: str,
                       ref_text: str,
                       speed: float = 1.0,
                       language: str = "auto",
                       timeout: int = 55) -> Tuple[bool, Any, str]:
        """
        Сгенерировать речь через HF Space API
        
        Args:
            text: Текст для озвучки
            ref_audio_url: URL эталонного аудио
            ref_text: Текст эталонного аудио
            speed: Скорость речи (0.5-2.0)
            language: Язык (auto для автоопределения)
            timeout: Таймаут в секундах
        
        Returns:
            (success: bool, result: Any, message: str)
            result может быть: bytes (audio data), dict (error info), или str
        """
        session_hash = str(uuid.uuid4())
        
        # Prepare payload for Gradio API
        payload = {
            "fn_index": 0,  # Main predict function
            "data": [
                text,           # user text
                ref_audio_url,  # reference audio URL
                ref_text,       # reference text
                speed,          # speed
                language        # language
            ],
            "session_hash": session_hash
        }
        
        try:
            response = self.session.post(
                self.predict_endpoint,
                json=payload,
                timeout=timeout
            )
            
            # Handle different status codes
            if response.status_code == 200:
                data = response.json()
                
                # Check for error in response
                if 'error' in data:
                    return False, data, f"API Error: {data['error']}"
                
                # Extract audio data from response
                # Gradio returns data in 'data' field
                if 'data' in data and len(data['data']) > 0:
                    result_data = data['data'][0]
                    
                    # Check if it's a file path/URL
                    if isinstance(result_data, str):
                        if result_data.startswith('http'):
                            # It's a URL, download it
                            audio_response = self.session.get(result_data, timeout=30)
                            if audio_response.status_code == 200:
                                return True, audio_response.content, "Success"
                            return False, None, f"Failed to download audio: HTTP {audio_response.status_code}"
                        else:
                            # It might be a local path on HF server
                            file_url = f"{self.file_endpoint}={result_data}"
                            audio_response = self.session.get(file_url, timeout=30)
                            if audio_response.status_code == 200:
                                return True, audio_response.content, "Success"
                    
                    # Check if it's bytes directly
                    elif isinstance(result_data, bytes):
                        return True, result_data, "Success"
                    
                    # Check if it's base64 encoded
                    elif isinstance(result_data, dict) and 'data' in result_data:
                        import base64
                        try:
                            audio_bytes = base64.b64decode(result_data['data'])
                            return True, audio_bytes, "Success"
                        except:
                            pass
                
                return False, data, "Unexpected response format"
            
            elif response.status_code == 429:
                return False, None, "RATE_LIMIT"
            
            elif response.status_code == 503:
                return False, None, "SERVICE_UNAVAILABLE"
            
            else:
                return False, None, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, None, "TIMEOUT"
        except requests.exceptions.ConnectionError:
            return False, None, "CONNECTION_ERROR"
        except Exception as e:
            return False, None, f"Error: {str(e)}"
    
    def warmup(self) -> bool:
        """
        Warm-up запрос для предотвращения cold start
        """
        try:
            # Simple GET request to check if space is alive
            response = self.session.get(self.space_url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def check_health(self) -> Tuple[bool, str]:
        """
        Проверить доступность HF Space
        
        Returns:
            (is_healthy: bool, message: str)
        """
        try:
            response = self.session.get(self.space_url, timeout=10)
            
            if response.status_code == 200:
                return True, "Space is healthy"
            elif response.status_code == 503:
                return False, "Space is loading (cold start)"
            else:
                return False, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)


# Global API instance
hf_api = HFSpaceAPI()
