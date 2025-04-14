import librosa
import soundfile as sf
import numpy as np
from typing import Tuple, Optional

def get_audio_duration(file_path: str) -> int:
    """获取音频文件的时长（秒）"""
    try:
        duration = librosa.get_duration(path=file_path)
        return int(duration)
    except Exception:
        return 0

def load_audio(file_path: str) -> Tuple[np.ndarray, int]:
    """加载音频文件"""
    try:
        audio, sr = librosa.load(file_path, sr=None)
        return audio, sr
    except Exception as e:
        raise ValueError(f"无法加载音频文件: {str(e)}")

def save_audio(
    audio: np.ndarray,
    sr: int,
    file_path: str,
    format: str = "wav"
) -> None:
    """保存音频文件"""
    try:
        sf.write(file_path, audio, sr, format=format)
    except Exception as e:
        raise ValueError(f"无法保存音频文件: {str(e)}")

def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """音频归一化"""
    return librosa.util.normalize(audio)

def resample_audio(
    audio: np.ndarray,
    orig_sr: int,
    target_sr: int
) -> np.ndarray:
    """重采样音频"""
    return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)

def trim_audio(
    audio: np.ndarray,
    top_db: float = 20,
    frame_length: int = 2048,
    hop_length: int = 512
) -> np.ndarray:
    """裁剪音频静音部分"""
    return librosa.effects.trim(
        audio,
        top_db=top_db,
        frame_length=frame_length,
        hop_length=hop_length
    )[0] 