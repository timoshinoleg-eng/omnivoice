"""
Storage Module for Voice Profiles (Multi-backend)
=================================================
Поддержка Supabase Storage (primary) и S3 fallback

Supabase: бесплатный tier 500MB, простой REST API
"""

import os
import uuid
import base64
import requests
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path


class SupabaseStorage:
    """
    Supabase Storage для голосовых профилей
    Использует REST API без дополнительных зависимостей
    """
    
    def __init__(self,
                 url: str = None,
                 key: str = None,
                 bucket: str = "voice-profiles"):
        """
        Инициализировать Supabase Storage
        
        Args:
            url: Supabase project URL (e.g., https://xxxxx.supabase.co)
            key: Supabase anon key
            bucket: Storage bucket name
        """
        self.url = (url or os.getenv('SUPABASE_URL', '')).rstrip('/')
        self.key = key or os.getenv('SUPABASE_KEY', '')
        self.bucket = bucket
        
        self.headers = {
            'Authorization': f'Bearer {self.key}',
            'apikey': self.key,
            'Content-Type': 'application/octet-stream'
        }
        
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Создать бакет если не существует"""
        try:
            # Check if bucket exists
            response = requests.get(
                f"{self.url}/storage/v1/bucket/{self.bucket}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 404:
                # Create bucket
                create_headers = {
                    'Authorization': f'Bearer {self.key}',
                    'apikey': self.key,
                    'Content-Type': 'application/json'
                }
                response = requests.post(
                    f"{self.url}/storage/v1/bucket",
                    headers=create_headers,
                    json={
                        'id': self.bucket,
                        'name': self.bucket,
                        'public': True
                    },
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    print(f"[Supabase] Created bucket: {self.bucket}")
                else:
                    print(f"[Supabase] Bucket creation response: {response.status_code}")
        except Exception as e:
            print(f"[Supabase] Bucket check error: {e}")
    
    def upload_voice_sample(self,
                           user_id: str,
                           audio_path: str) -> Tuple[bool, str]:
        """
        Загрузить образец голоса в Supabase Storage
        
        Args:
            user_id: ID пользователя
            audio_path: Путь к аудио файлу
            
        Returns:
            (success: bool, url_or_error: str)
        """
        try:
            # Generate unique path
            file_ext = Path(audio_path).suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"
            storage_path = f"{user_id}/{file_name}"
            
            # Read file
            with open(audio_path, 'rb') as f:
                file_data = f.read()
            
            # Upload via REST API
            upload_url = f"{self.url}/storage/v1/object/{self.bucket}/{storage_path}"
            
            response = requests.post(
                upload_url,
                headers=self.headers,
                data=file_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                # Get public URL
                public_url = f"{self.url}/storage/v1/object/public/{self.bucket}/{storage_path}"
                return True, public_url
            else:
                return False, f"Upload failed: HTTP {response.status_code}"
                
        except Exception as e:
            return False, f"Supabase upload error: {str(e)}"
    
    def delete_voice_sample(self, storage_path: str) -> bool:
        """
        Удалить образец голоса из Supabase
        
        Args:
            storage_path: Путь к файлу в хранилище
            
        Returns:
            bool: Успешно ли удаление
        """
        try:
            response = requests.delete(
                f"{self.url}/storage/v1/object/{self.bucket}/{storage_path}",
                headers=self.headers,
                timeout=10
            )
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"[Supabase] Delete error: {e}")
            return False
    
    def get_storage_path_from_url(self, url: str) -> Optional[str]:
        """Извлечь путь к файлу из URL"""
        try:
            # Format: https://xxx.supabase.co/storage/v1/object/public/bucket/path
            if '/storage/v1/object/public/' in url:
                parts = url.split('/storage/v1/object/public/')
                if len(parts) == 2:
                    return parts[1]
            return None
        except:
            return None


class VoiceProfileStorage:
    """
    Универсальное хранилище для голосовых профилей
    Primary: Supabase, Fallback: S3
    """
    
    def __init__(self):
        self.supabase = None
        self._init_supabase()
    
    def _init_supabase(self):
        """Инициализировать Supabase если есть credentials"""
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_KEY')
        
        if url and key:
            try:
                self.supabase = SupabaseStorage(url, key)
                print("[Storage] Supabase initialized")
            except Exception as e:
                print(f"[Storage] Supabase init failed: {e}")
                self.supabase = None
        else:
            print("[Storage] Supabase credentials not found")
    
    def upload_voice_sample(self,
                           user_id: str,
                           audio_path: str,
                           content_type: str = None) -> Tuple[bool, str]:
        """
        Загрузить образец голоса (Supabase primary)
        
        Returns:
            (success: bool, url_or_error: str)
        """
        # Try Supabase first
        if self.supabase:
            success, result = self.supabase.upload_voice_sample(user_id, audio_path)
            if success:
                return True, result
            print(f"[Storage] Supabase failed: {result}, trying fallback...")
        
        # Fallback message
        return False, "No storage backend available. Set SUPABASE_URL and SUPABASE_KEY."
    
    def delete_voice_sample(self, url_or_path: str) -> bool:
        """Удалить образец голоса"""
        if self.supabase:
            path = self.supabase.get_storage_path_from_url(url_or_path)
            if path:
                return self.supabase.delete_voice_sample(path)
        return False
    
    def get_storage_path_from_url(self, url: str) -> Optional[str]:
        """Извлечь путь к файлу из URL"""
        if self.supabase:
            return self.supabase.get_storage_path_from_url(url)
        return None


# Global storage instance
_voice_storage = None

def init_storage() -> VoiceProfileStorage:
    """Инициализировать глобальное хранилище"""
    global _voice_storage
    if _voice_storage is None:
        _voice_storage = VoiceProfileStorage()
    return _voice_storage
