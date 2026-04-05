"""
S3 Storage Module for Voice Profiles
=====================================
Постоянное хранилище голосовых профилей в S3 (Yandex Object Storage)

Решает проблему: HF Space temp URL истекает через ~1 час
"""

import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import uuid


class VoiceProfileStorage:
    """
    S3 хранилище для голосовых профилей
    """
    
    def __init__(self, 
                 bucket_name: str = None,
                 endpoint_url: str = "https://storage.yandexcloud.net",
                 region: str = "ru-central1"):
        """
        Инициализировать S3 хранилище
        
        Args:
            bucket_name: Имя бакета (default: из env S3_BUCKET)
            endpoint_url: URL S3 endpoint
            region: Регион
        """
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET', 'voicecraft-profiles')
        self.endpoint_url = endpoint_url
        self.region = region
        
        # Initialize S3 client
        self.s3 = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
            config=Config(signature_version='s3v4')
        )
        
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Создать бакет если не существует"""
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                self.s3.create_bucket(
                    Bucket=self.bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': self.region
                    }
                )
                print(f"[S3] Created bucket: {self.bucket_name}")
    
    def upload_voice_sample(self, 
                           user_id: str, 
                           audio_path: str,
                           content_type: str = "audio/wav") -> Tuple[bool, str]:
        """
        Загрузить образец голоса в S3
        
        Args:
            user_id: ID пользователя
            audio_path: Путь к аудио файлу
            content_type: MIME тип
            
        Returns:
            (success: bool, url_or_error: str)
        """
        try:
            # Generate unique key
            file_ext = Path(audio_path).suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            key = f"voices/{user_id}/{timestamp}_{uuid.uuid4().hex[:8]}{file_ext}"
            
            # Upload file
            with open(audio_path, 'rb') as f:
                self.s3.upload_fileobj(
                    f,
                    self.bucket_name,
                    key,
                    ExtraArgs={
                        'ContentType': content_type,
                        'Metadata': {
                            'user_id': user_id,
                            'uploaded_at': datetime.now().isoformat()
                        }
                    }
                )
            
            # Generate presigned URL (valid for 7 days)
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=604800  # 7 days
            )
            
            return True, url
            
        except Exception as e:
            return False, f"S3 upload error: {str(e)}"
    
    def refresh_presigned_url(self, 
                             key: str, 
                             expires_in: int = 604800) -> Tuple[bool, str]:
        """
        Обновить presigned URL для существующего файла
        
        Args:
            key: S3 ключ файла
            expires_in: Время жизни URL в секундах (default: 7 дней)
            
        Returns:
            (success: bool, url_or_error: str)
        """
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': key
                },
                ExpiresIn=expires_in
            )
            return True, url
        except Exception as e:
            return False, f"Failed to refresh URL: {str(e)}"
    
    def delete_voice_sample(self, key: str) -> bool:
        """
        Удалить образец голоса из S3
        
        Args:
            key: S3 ключ файла
            
        Returns:
            bool: Успешно ли удаление
        """
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            print(f"[S3] Delete error: {e}")
            return False
    
    def get_voice_sample_key_from_url(self, url: str) -> Optional[str]:
        """
        Извлечь S3 ключ из presigned URL
        
        Args:
            url: Presigned URL
            
        Returns:
            S3 ключ или None
        """
        try:
            # Parse URL to extract key
            # Format: https://storage.yandexcloud.net/bucket-name/key?...
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            path = parsed.path
            
            # Remove leading slash and bucket name
            parts = path.strip('/').split('/', 1)
            if len(parts) >= 2 and parts[0] == self.bucket_name:
                return parts[1]
            
            return path.strip('/')
        except:
            return None
    
    def list_user_voices(self, user_id: str) -> list:
        """
        Получить список всех голосовых образцов пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Список словарей с информацией о файлах
        """
        try:
            prefix = f"voices/{user_id}/"
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat()
                })
            
            return files
        except Exception as e:
            print(f"[S3] List error: {e}")
            return []


# Global storage instance
voice_storage = None

def init_storage() -> VoiceProfileStorage:
    """Инициализировать глобальное хранилище"""
    global voice_storage
    if voice_storage is None:
        voice_storage = VoiceProfileStorage()
    return voice_storage
