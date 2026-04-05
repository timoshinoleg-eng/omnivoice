"""
Audio Watermarking Module
=========================
Добавление водяного знака в сгенерированное аудио
"""

import wave
import struct
from typing import Optional
from pathlib import Path


class AudioWatermarker:
    """
    Добавляет водяной знак в аудио файл
    
    Метод: LSB (Least Significant Bit) стеганография
    - Встраивает текстовый водяной знак в младшие биты аудио-данных
    - Не слышно на слух, но можно извлечь
    """
    
    WATERMARK_TEXT = "VoiceCraft-AI"
    WATERMARK_HEADER = b"VCFT"  # 4-byte header
    
    def __init__(self, watermark_text: str = None):
        self.watermark_text = watermark_text or self.WATERMARK_TEXT
    
    def add_watermark(self, audio_bytes: bytes) -> bytes:
        """
        Добавить водяной знак в аудио (WAV формат)
        
        Args:
            audio_bytes: Сырые байты WAV файла
            
        Returns:
            bytes: WAV с водяным знаком
        """
        try:
            # Parse WAV header
            with wave.open(BytesIO(audio_bytes), 'rb') as wav_in:
                n_channels = wav_in.getnchannels()
                sampwidth = wav_in.getsampwidth()
                framerate = wav_in.getframerate()
                n_frames = wav_in.getnframes()
                
                # Read all frames
                frames = wav_in.readframes(n_frames)
            
            # Prepare watermark data
            watermark_data = self.WATERMARK_HEADER + self.watermark_text.encode('utf-8')
            watermark_bits = ''.join(format(byte, '08b') for byte in watermark_data)
            
            # Convert frames to bytearray for modification
            frames_array = bytearray(frames)
            
            # Embed watermark in LSB of each sample
            # For 16-bit audio, each sample is 2 bytes
            if sampwidth == 2:
                for i, bit in enumerate(watermark_bits):
                    if i * 2 >= len(frames_array):
                        break
                    
                    # Get current sample (16-bit signed)
                    sample = struct.unpack('<h', frames_array[i*2:i*2+2])[0]
                    
                    # Modify LSB
                    if bit == '1':
                        sample |= 1
                    else:
                        sample &= ~1
                    
                    # Pack back
                    frames_array[i*2:i*2+2] = struct.pack('<h', sample)
            
            # Write output WAV
            from io import BytesIO
            output = BytesIO()
            with wave.open(output, 'wb') as wav_out:
                wav_out.setnchannels(n_channels)
                wav_out.setsampwidth(sampwidth)
                wav_out.setframerate(framerate)
                wav_out.writeframes(bytes(frames_array))
            
            return output.getvalue()
            
        except Exception as e:
            print(f"[AudioWatermarker] Error: {e}")
            # Return original if watermarking fails
            return audio_bytes
    
    def extract_watermark(self, audio_bytes: bytes) -> Optional[str]:
        """
        Извлечь водяной знак из аудио (для проверки)
        
        Args:
            audio_bytes: Сырые байты WAV файла
            
        Returns:
            str: Текст водяного знака или None
        """
        try:
            from io import BytesIO
            
            with wave.open(BytesIO(audio_bytes), 'rb') as wav_in:
                sampwidth = wav_in.getsampwidth()
                n_frames = wav_in.getnframes()
                frames = wav_in.readframes(n_frames)
            
            if sampwidth != 2:
                return None
            
            # Extract LSB from each sample
            bits = []
            for i in range(0, len(frames), 2):
                if i + 2 > len(frames):
                    break
                sample = struct.unpack('<h', frames[i:i+2])[0]
                bits.append(str(sample & 1))
            
            # Convert bits to bytes
            watermark_bytes = bytearray()
            for i in range(0, len(bits), 8):
                byte_bits = ''.join(bits[i:i+8])
                watermark_bytes.append(int(byte_bits, 2))
            
            # Check header
            if watermark_bytes[:4] == self.WATERMARK_HEADER:
                return watermark_bytes[4:].decode('utf-8', errors='ignore')
            
            return None
            
        except Exception as e:
            print(f"[AudioWatermarker] Extract error: {e}")
            return None


class SimpleWatermarker:
    """
    Простой водяной знак: добавляет тихий тон в начало аудио
    Более совместим с разными форматами
    """
    
    def __init__(self, watermark_text: str = "VoiceCraft-AI"):
        self.watermark_text = watermark_text
    
    def add_watermark(self, audio_bytes: bytes) -> bytes:
        """
        Добавить слышимый водяной знак (тихий тон в начале)
        """
        try:
            from io import BytesIO
            import math
            
            with wave.open(BytesIO(audio_bytes), 'rb') as wav_in:
                n_channels = wav_in.getnchannels()
                sampwidth = wav_in.getsampwidth()
                framerate = wav_in.getframerate()
                frames = wav_in.readframes(wav_in.getnframes())
            
            # Generate 0.1s silent/subliminal tone at 18kHz (near-ultrasonic)
            duration = 0.1  # seconds
            frequency = 18000  # Hz
            samples = int(framerate * duration)
            
            tone_frames = bytearray()
            for i in range(samples):
                # Very low amplitude (1% of max)
                amplitude = 32767 // 100  # 1% of 16-bit max
                t = float(i) / framerate
                
                # Generate sine wave
                value = int(amplitude * math.sin(2 * math.pi * frequency * t))
                
                # Pack for stereo/mono
                for _ in range(n_channels):
                    tone_frames.extend(struct.pack('<h', value))
            
            # Combine: tone + original
            combined = bytes(tone_frames) + frames
            
            # Write output
            output = BytesIO()
            with wave.open(output, 'wb') as wav_out:
                wav_out.setnchannels(n_channels)
                wav_out.setsampwidth(sampwidth)
                wav_out.setframerate(framerate)
                wav_out.writeframes(combined)
            
            return output.getvalue()
            
        except Exception as e:
            print(f"[SimpleWatermarker] Error: {e}")
            return audio_bytes


# Global instance
_watermarker = None

def get_watermarker() -> AudioWatermarker:
    """Получить глобальный экземпляр AudioWatermarker"""
    global _watermarker
    if _watermarker is None:
        _watermarker = AudioWatermarker()
    return _watermarker
