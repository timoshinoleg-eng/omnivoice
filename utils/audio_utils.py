"""
Audio Utilities Module
======================
Утилиты для работы с аудио файлами
"""

import os
import io
import wave
import tempfile
from pathlib import Path
from typing import Tuple, Optional
import subprocess


def get_audio_duration(file_path: str) -> float:
    """
    Получить длительность аудио файла в секундах
    Поддерживает WAV, MP3, OGG, M4A
    """
    try:
        ext = Path(file_path).suffix.lower()
        
        if ext == '.wav':
            with wave.open(file_path, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return frames / float(rate)
        
        # For other formats, use ffprobe if available
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        
        # Fallback: try to estimate from file size (rough approximation)
        file_size = os.path.getsize(file_path)
        # Rough estimate: ~16KB per second for 128kbps
        return file_size / (16 * 1024)
        
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return 0.0


def validate_audio_file(file_path: str, 
                        min_duration: float = 3.0,
                        max_duration: float = 15.0) -> Tuple[bool, str, float]:
    """
    Валидировать аудио файл
    
    Returns:
        (is_valid: bool, message: str, duration: float)
    """
    # Check file exists
    if not os.path.exists(file_path):
        return False, "Файл не найден", 0.0
    
    # Check file size (max 10MB)
    file_size = os.path.getsize(file_path)
    if file_size > 10 * 1024 * 1024:
        return False, "Файл слишком большой (макс. 10MB)", 0.0
    
    # Check extension
    ext = Path(file_path).suffix.lower()
    supported = ('.wav', '.mp3', '.ogg', '.m4a', '.webm')
    if ext not in supported:
        return False, f"Неподдерживаемый формат. Используйте: {', '.join(supported)}", 0.0
    
    # Get duration
    duration = get_audio_duration(file_path)
    
    if duration < min_duration:
        return False, f"Аудио слишком короткое ({duration:.1f}s). Минимум: {min_duration}s", duration
    
    if duration > max_duration:
        return False, f"Аудио слишком длинное ({duration:.1f}s). Максимум: {max_duration}s", duration
    
    return True, "OK", duration


def convert_to_wav(input_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Конвертировать аудио в WAV формат (mono, 16kHz)
    Использует ffmpeg если доступен
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix='.wav')
    
    try:
        # Try ffmpeg first
        result = subprocess.run(
            ['ffmpeg', '-i', input_path, '-ar', '16000', '-ac', '1', 
             '-acodec', 'pcm_s16le', '-y', output_path],
            capture_output=True, timeout=30
        )
        
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        
        # If ffmpeg fails, try to copy if already WAV
        ext = Path(input_path).suffix.lower()
        if ext == '.wav':
            import shutil
            shutil.copy(input_path, output_path)
            return output_path
            
    except Exception as e:
        print(f"Error converting audio: {e}")
    
    return None


def split_text_for_chunks(text: str, max_chars: int = 1000) -> list:
    """
    Разбить длинный текст на части по предложениям
    """
    if len(text) <= max_chars:
        return [text]
    
    # Split by sentence endings
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_chars:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def estimate_audio_duration(text: str, chars_per_second: float = 15.0) -> float:
    """
    Оценить длительность аудио по количеству символов
    """
    return len(text) / chars_per_second
