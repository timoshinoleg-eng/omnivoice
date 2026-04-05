"""
Audio Watermarking Module
=========================
Добавление водяного знака в сгенерированное аудио
"""

import io
import wave
import struct
from typing import Optional, Tuple
import numpy as np


class AudioWatermarker:
    """
    Добавление цифрового водяного знака в аудио
    """
    
    def __init__(self, watermark_text: str = "AI_GENERATED"):
        self.watermark_text = watermark_text
        self.sample_rate = 16000
    
    def add_watermark(self, audio_bytes: bytes, method: str = "lsb") -> bytes:
        """
        Добавить водяной знак в аудио
        
        Args:
            audio_bytes: WAV аудио данные
            method: Метод watermarking ('lsb' или 'metadata')
            
        Returns:
            bytes: Аудио с водяным знаком
        """
        if method == "lsb":
            return self._add_lsb_watermark(audio_bytes)
        elif method == "metadata":
            return self._add_metadata_watermark(audio_bytes)
        else:
            return audio_bytes
    
    def _add_lsb_watermark(self, audio_bytes: bytes) -> bytes:
        """
        LSB (Least Significant Bit) watermarking
        Встраивает текст в младшие биты аудио-сэмплов
        """
        try:
            # Parse WAV
            wav_file = wave.open(io.BytesIO(audio_bytes), 'rb')
            
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            n_frames = wav_file.getnframes()
            
            # Read audio data
            audio_data = wav_file.readframes(n_frames)
            wav_file.close()
            
            if sample_width != 2:
                # Convert to 16-bit if needed
                return audio_bytes
            
            # Convert to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Prepare watermark data
            watermark_bytes = self.watermark_text.encode('utf-8')
            watermark_bits = []
            
            # Add length prefix (2 bytes)
            length_bytes = len(watermark_bytes).to_bytes(2, 'big')
            full_data = length_bytes + watermark_bytes
            
            for byte in full_data:
                for i in range(8):
                    watermark_bits.append((byte >> i) & 1)
            
            # Embed watermark in LSB
            modified_array = audio_array.copy()
            
            for i, bit in enumerate(watermark_bits):
                if i >= len(modified_array):
                    break
                # Clear LSB and set watermark bit
                modified_array[i] = (modified_array[i] & ~1) | bit
            
            # Create output WAV
            output = io.BytesIO()
            out_wav = wave.open(output, 'wb')
            out_wav.setnchannels(n_channels)
            out_wav.setsampwidth(sample_width)
            out_wav.setframerate(self.sample_rate)
            out_wav.writeframes(modified_array.tobytes())
            out_wav.close()
            
            return output.getvalue()
            
        except Exception as e:
            print(f"[Watermark] LSB failed: {e}")
            return audio_bytes
    
    def _add_metadata_watermark(self, audio_bytes: bytes) -> bytes:
        """
        Добавить метаданные в WAV файл (INFO chunk)
        Совместимо с большинством плееров
        """
        try:
            # Parse WAV
            wav_file = wave.open(io.BytesIO(audio_bytes), 'rb')
            
            n_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()
            
            audio_data = wav_file.readframes(n_frames)
            wav_file.close()
            
            # Create new WAV with custom chunk
            output = io.BytesIO()
            
            # Write RIFF header
            output.write(b'RIFF')
            
            # Calculate sizes
            fmt_chunk_size = 16
            data_chunk_size = len(audio_data)
            info_chunk_size = 8 + len(self.watermark_text) + 1  # +1 for null terminator
            
            # Total file size (will update later)
            total_size = 4 + 8 + fmt_chunk_size + 8 + data_chunk_size + 8 + info_chunk_size
            output.write(struct.pack('<I', total_size))
            
            # Write WAVE
            output.write(b'WAVE')
            
            # Write fmt chunk
            output.write(b'fmt ')
            output.write(struct.pack('<I', fmt_chunk_size))
            output.write(struct.pack('<H', 1))  # PCM
            output.write(struct.pack('<H', n_channels))
            output.write(struct.pack('<I', framerate))
            output.write(struct.pack('<I', framerate * n_channels * sample_width))
            output.write(struct.pack('<H', n_channels * sample_width))
            output.write(struct.pack('<H', sample_width * 8))
            
            # Write LIST/INFO chunk with watermark
            output.write(b'LIST')
            output.write(struct.pack('<I', 4 + info_chunk_size))
            output.write(b'INFO')
            output.write(b'ICMT')  # Comment chunk
            output.write(struct.pack('<I', len(self.watermark_text) + 1))
            output.write(self.watermark_text.encode('utf-8'))
            output.write(b'\x00')  # Null terminator
            
            # Write data chunk
            output.write(b'data')
            output.write(struct.pack('<I', data_chunk_size))
            output.write(audio_data)
            
            return output.getvalue()
            
        except Exception as e:
            print(f"[Watermark] Metadata failed: {e}")
            return audio_bytes
    
    def verify_watermark(self, audio_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Проверить наличие водяного знака
        
        Returns:
            (found: bool, text: str or None)
        """
        try:
            wav_file = wave.open(io.BytesIO(audio_bytes), 'rb')
            n_frames = wav_file.getnframes()
            sample_width = wav_file.getsampwidth()
            
            if sample_width != 2:
                return False, None
            
            audio_data = wav_file.readframes(n_frames)
            wav_file.close()
            
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Extract LSB bits
            bits = []
            for i in range(min(16 + len(self.watermark_text) * 8, len(audio_array))):
                bits.append(audio_array[i] & 1)
            
            # Convert bits to bytes
            if len(bits) < 16:
                return False, None
            
            # Extract length (first 16 bits)
            length = 0
            for i in range(16):
                length |= bits[i] << i
            
            if length > 1000:  # Sanity check
                return False, None
            
            # Extract text
            text_bytes = []
            for i in range(length):
                byte_bits = bits[16 + i * 8: 16 + (i + 1) * 8]
                if len(byte_bits) < 8:
                    break
                byte_val = 0
                for j, bit in enumerate(byte_bits):
                    byte_val |= bit << j
                text_bytes.append(byte_val)
            
            extracted_text = bytes(text_bytes).decode('utf-8', errors='ignore')
            
            if self.watermark_text in extracted_text:
                return True, extracted_text
            
            return False, None
            
        except Exception as e:
            print(f"[Watermark] Verification failed: {e}")
            return False, None


# Global instance
audio_watermarker = AudioWatermarker()
