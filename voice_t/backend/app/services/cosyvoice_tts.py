"""CosyVoice TTS 服务模块

这个模块封装了CosyVoice TTS模型的功能，提供了语音合成服务。
"""
import os
import sys
import json
import time
import asyncio
import tempfile
import numpy as np
import torch
import torchaudio
import librosa
import soundfile as sf
import time
import torchaudio
import torch
import librosa
import numpy as np
import soundfile as sf
import os
import traceback
from pathlib import Path
import subprocess
import urllib.parse
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple, BinaryIO
from datetime import datetime
from pathlib import Path
from fastapi import BackgroundTasks, WebSocket
from app.services.shared_storage import TASK_ID_MAPPING, IN_MEMORY_AUDIO
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)
# from app.services.voice_clone import voice_cloner
from app.models.tts import TTSTaskDB, TTSTaskStatus, TTSParams
from app.core.config import settings

# 添加这个函数来安全加载参考音频文件，支持多种备用方法
def safe_load_audio(audio_path, target_sr=16000):
    """
    安全加载音频，使用多种备用方法。

    参数:
        audio_path: 音频文件路径
        target_sr: 目标采样率

    返回:
        包含 (音频张量, 采样率) 的元组，如果所有方法都失败则返回 None
    """
    print(f"尝试加载音频文件: {audio_path}")

    if not os.path.exists(audio_path):
        print(f"错误: 音频文件不存在: {audio_path}")
        return None

    # 检查文件大小，确保文件不为空
    file_size = os.path.getsize(audio_path)
    if file_size == 0:
        print(f"错误: 音频文件大小为0字节: {audio_path}")
        return None

    # 方法1: 尝试使用librosa（最稳定的方法）
    try:
        print("尝试使用librosa加载...")
        waveform, sr = librosa.load(audio_path, sr=target_sr, mono=True)
        audio_tensor = torch.FloatTensor(waveform).unsqueeze(0)
        print(f"成功使用librosa加载音频: 形状={audio_tensor.shape}, 采样率={sr}")
        return audio_tensor, sr
    except Exception as e:
        print(f"librosa加载失败: {e}")

    # 方法2: 尝试使用torchaudio的soundfile后端
    try:
        print("尝试使用torchaudio的soundfile后端...")
        audio_tensor, sr = torchaudio.load(audio_path, backend='soundfile')
        print(f"成功使用torchaudio(soundfile)加载音频: 形状={audio_tensor.shape}, 采样率={sr}")

        # 如果需要重采样
        if sr != target_sr:
            resampler = torchaudio.transforms.Resample(sr, target_sr)
            audio_tensor = resampler(audio_tensor)
            sr = target_sr

        # 如果是立体声，转换为单声道
        if audio_tensor.shape[0] > 1:
            audio_tensor = torch.mean(audio_tensor, dim=0, keepdim=True)

        return audio_tensor, sr
    except Exception as e:
        print(f"torchaudio(soundfile)加载失败: {e}")

    # 方法3: 尝试使用torchaudio的sox_io后端
    try:
        print("尝试使用torchaudio的sox_io后端...")
        audio_tensor, sr = torchaudio.load(audio_path, backend='sox_io')
        print(f"成功使用torchaudio(sox_io)加载音频: 形状={audio_tensor.shape}, 采样率={sr}")

        # 如果需要重采样
        if sr != target_sr:
            resampler = torchaudio.transforms.Resample(sr, target_sr)
            audio_tensor = resampler(audio_tensor)
            sr = target_sr

        # 如果是立体声，转换为单声道
        if audio_tensor.shape[0] > 1:
            audio_tensor = torch.mean(audio_tensor, dim=0, keepdim=True)

        return audio_tensor, sr
    except Exception as e:
        print(f"torchaudio(sox_io)加载失败: {e}")

    # 方法4: 尝试转换格式（需要安装ffmpeg）
    try:
        print("尝试使用ffmpeg转换格式...")
        # 创建临时文件
        temp_file = f"{audio_path}.converted.wav"

        # 使用ffmpeg转换为标准WAV格式
        convert_command = f'ffmpeg -y -i "{audio_path}" -ar {target_sr} -ac 1 "{temp_file}"'
        subprocess.run(convert_command, shell=True, check=True)

        if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
            print(f"成功转换格式，尝试加载转换后的文件: {temp_file}")
            waveform, sr = librosa.load(temp_file, sr=target_sr, mono=True)
            audio_tensor = torch.FloatTensor(waveform).unsqueeze(0)
            os.remove(temp_file)  # 删除临时文件
            return audio_tensor, sr
        else:
            print("转换后的文件不存在或大小为0")
    except Exception as e:
        print(f"ffmpeg转换失败: {e}")
        # 尝试清理临时文件
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

    # 所有方法都失败，创建一个简单的静音音频
    print("所有加载方法都失败，生成一个短的静音音频作为替代")
    silence_length = 3 * target_sr  # 3秒
    silence = torch.zeros(1, silence_length)
    return silence, target_sr

max_val = 0.8
def postprocess(speech, top_db=60, hop_length=220, win_length=440):
    speech, _ = librosa.effects.trim(
        speech, top_db=top_db,
        frame_length=win_length,
        hop_length=hop_length
    )
    if speech.abs().max() > max_val:
        speech = speech / speech.abs().max() * max_val
    speech = torch.concat([speech, torch.zeros(1, int(22050 * 0.2))], dim=1)
    return speech
# 获取当前目录并添加CosyVoice路径
sys.path.append('{}/third_party/Matcha-TTS'.format(ROOT_DIR))
COSYVOICE_PATH = os.path.join(ROOT_DIR, "cosyvoice")

# 检查CosyVoice路径是否存在
if os.path.exists(COSYVOICE_PATH):
    sys.path.append(ROOT_DIR)
    # 尝试导入CosyVoice
    try:
        from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
        from cosyvoice.utils.file_utils import load_wav, logging
        from cosyvoice.utils.common import set_all_random_seed
        COSYVOICE_AVAILABLE = True
        print("CosyVoice 模块加载成功")
    except ImportError as e:
        print(f"导入 CosyVoice 失败: {e}")
        print("创建模拟的CosyVoice模型用于测试")

        # 创建模拟的CosyVoice模型
        class MockCosyVoice:
            """模拟的CosyVoice模型，用于测试"""

            def __init__(self, model_dir):
                self.model_dir = model_dir
                self.sample_rate = 16000
                self.instruct = False
                print(f"模拟CosyVoice模型已加载: {model_dir}")

            def list_available_spks(self):
                """返回可用的预训练音色列表"""
                return ["chinese_female", "chinese_male", "english_female", "english_male",
                        "japanese_male", "korean_female", "cantonese_female"]

            def inference_sft(self, text, spk_id, **kwargs):
                """模拟语音合成"""
                print(f"模拟语音合成: 文本='{text}', 音色='{spk_id}'")
                # 生成一个简单的正弦波作为模拟音频
                import numpy as np
                duration = len(text) * 0.1  # 假设每个字符需要0.1秒
                t = np.linspace(0, duration, int(duration * self.sample_rate), endpoint=False)
                # 生成一个简单的音频信号
                audio = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440Hz的正弦波
                return audio

        # 使用模拟的CosyVoice模型
        CosyVoice = MockCosyVoice
        CosyVoice2 = MockCosyVoice
        COSYVOICE_AVAILABLE = True
else:
    print(f"CosyVoice 路径不存在: {COSYVOICE_PATH}")
    print("创建模拟的CosyVoice模型用于测试")

    # 创建模拟的CosyVoice模型
    class MockCosyVoice:
        """模拟的CosyVoice模型，用于测试"""

        def __init__(self, model_dir):
            self.model_dir = model_dir
            self.sample_rate = 16000
            self.instruct = False
            print(f"模拟CosyVoice模型已加载: {model_dir}")

        def list_available_spks(self):
            """返回可用的预训练音色列表"""
            return ["chinese_female", "chinese_male", "english_female", "english_male",
                    "japanese_male", "korean_female", "cantonese_female"]

        def inference_sft(self, text, spk_id, **kwargs):
            """模拟语音合成"""
            print(f"模拟语音合成: 文本='{text}', 音色='{spk_id}'")
            # 生成一个简单的正弦波作为模拟音频
            import numpy as np
            duration = len(text) * 0.1  # 假设每个字符需要0.1秒
            t = np.linspace(0, duration, int(duration * self.sample_rate), endpoint=False)
            # 生成一个简单的音频信号
            audio = 0.5 * np.sin(2 * np.pi * 440 * t)  # 440Hz的正弦波
            return audio

    # 使用模拟的CosyVoice模型
    CosyVoice = MockCosyVoice
    CosyVoice2 = MockCosyVoice
    COSYVOICE_AVAILABLE = True

# 全局变量
TTS_TASKS_DB = []
TTS_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "cosyvoice_tts_tasks.json")
cosyvoice_model = None
max_val = 0.8  # 音频归一化最大值

# 任务ID生成和规范化
# datetime序列化处理函数
def json_serial(obj):
    """JSON序列化器，特殊处理datetime对象"""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError(f"无法序列化类型 {type(obj)}")
def create_normalized_task_id(voice_id, text=None):
    """创建规范化的任务ID并记录映射关系"""

    # 使用时间戳确保唯一性
    timestamp = int(time.time())

    # 为保持简单，给每个语音ID指定一个固定的英文ID
    # 这样可以避免中文字符带来的一系列问题
    voice_mapping = {
        "中文女": "chinese_female",
        "中文男": "chinese_male",
        "英文女": "english_female",
        "英文男": "english_male",
        "日语男": "japanese_male",
        "韩语女": "korean_female",
        "粤语女": "cantonese_female"
    }

    # 如果是已知的预设中文ID，使用映射的英文ID
    safe_voice_id = voice_mapping.get(voice_id, voice_id)

    # 如果不在预设映射中，检查是否含有中文字符，如果有则创建一个安全的ID
    if safe_voice_id == voice_id and any('\u4e00' <= c <= '\u9fff' for c in voice_id):
        # 简单替换中文ID为拼音缩写+序号
        safe_voice_id = f"voice_{len(TASK_ID_MAPPING)}"

    # 创建最终的任务ID
    task_id = f"cosyvoice_tts_{timestamp}_{safe_voice_id}"

    # 记录映射关系
    TASK_ID_MAPPING[task_id] = voice_id
    print(f"创建任务ID映射: {task_id} -> {voice_id}")

    return task_id

def create_wav_header(sample_rate, num_samples):
    """创建WAV文件头"""
    # WAV文件规范 (16位PCM)
    bytes_per_sample = 2
    data_size = num_samples * bytes_per_sample

    header = bytearray(44)
    # RIFF chunk descriptor
    header[0:4] = b'RIFF'
    header[4:8] = (data_size + 36).to_bytes(4, byteorder='little')
    header[8:12] = b'WAVE'
    # "fmt " sub-chunk
    header[12:16] = b'fmt '
    header[16:20] = (16).to_bytes(4, byteorder='little')  # fmt chunk size
    header[20:22] = (1).to_bytes(2, byteorder='little')  # format = 1 (PCM)
    header[22:24] = (1).to_bytes(2, byteorder='little')  # channels = 1 (mono)
    header[24:28] = sample_rate.to_bytes(4, byteorder='little')
    header[28:32] = (sample_rate * bytes_per_sample).to_bytes(4, byteorder='little')  # byte rate
    header[32:34] = (bytes_per_sample).to_bytes(2, byteorder='little')  # block align
    header[34:36] = (16).to_bytes(2, byteorder='little')  # bits per sample
    # "data" sub-chunk
    header[36:40] = b'data'
    header[40:44] = data_size.to_bytes(4, byteorder='little')

    return header

class CosyVoiceTTS:
    """CosyVoice TTS 模型封装类"""

    def __init__(self, model_dir=None):
        """初始化 CosyVoice TTS 模型

        Args:
            model_dir: 模型目录路径，默认使用配置中的路径
        """
        if not COSYVOICE_AVAILABLE:
            print("CosyVoice 不可用，将使用替代实现")
            self.model = None
            self.sample_rate = 16000
            self.available_spks = []
            self.instruct = False
            return

        # 如果未指定模型目录，使用配置中的路径
        if model_dir is None:
            model_dir = settings.TTS_MODELS_DIR

        if not os.path.exists(model_dir):
            print(f"模型目录不存在: {model_dir}")
            try:
                # 尝试从ModelScope下载
                from modelscope import snapshot_download

                #分支下载可以另加
                print(f"尝试从ModelScope下载模型: {model_dir}")
                # snapshot_download('iic/CosyVoice2-0.5B', local_dir='d:/voice/voice_t/backend/pretrained_models/CosyVoice2-0.5B')
                # snapshot_download('iic/CosyVoice-300M', local_dir='d:/voice/voice_t/backend/pretrained_models/CosyVoice-300M')
                # snapshot_download('iic/CosyVoice-300M-25Hz', local_dir='d:/voice/voice_t/backend/pretrained_models/CosyVoice-300M-25Hz')
                snapshot_download('iic/CosyVoice-300M-SFT', local_dir='d:/voice/voice_t/backend/pretrained_models/CosyVoice-300M-SFT')
                # snapshot_download('iic/CosyVoice-300M-Instruct', local_dir='d:/voice/voice_t/backend/pretrained_models/CosyVoice-300M-Instruct')
                # snapshot_download('iic/CosyVoice-ttsfrd', local_dir='d:/voice/voice_t/backend/pretrained_models/CosyVoice-ttsfrd')
                print(f"尝试从ModelScope下载模型: {model_dir}")

            except Exception as e:
                print(f"模型下载失败: {e}")
                self.model = None
                self.sample_rate = 16000
                self.available_spks = []
                self.instruct = False
                return

        try:
            # 尝试加载CosyVoice模型
            self.model = CosyVoice(model_dir)
            print(f"CosyVoice 模型加载成功: {model_dir}")
        except Exception:
            try:
                # 尝试加载CosyVoice2模型
                self.model = CosyVoice2(model_dir)
                print(f"CosyVoice2 模型加载成功: {model_dir}")
            except Exception as e:
                print(f"加载模型失败: {e}")
                self.model = None
                self.sample_rate = 16000
                self.available_spks = []
                self.instruct = False
                return

        # 获取模型属性
        self.sample_rate = self.model.sample_rate
        self.available_spks = self.model.list_available_spks()
        print(self.available_spks)
        if len(self.available_spks) == 0:
            self.available_spks = ['']

        # 判断是否支持指令控制
        try:
            self.instruct = self.model.instruct
        except AttributeError:
            # 如果模型没有instruct属性，默认为False
            self.instruct = False

    def postprocess(self, speech, top_db=60, hop_length=220, win_length=440):
        """后处理音频信号

        Args:
            speech: 音频信号
            top_db: 静音检测分贝阈值
            hop_length: 帧移
            win_length: 窗长

        Returns:
            处理后的音频信号
        """
        # 裁剪静音部分
        speech, _ = librosa.effects.trim(
            speech, top_db=top_db,
            frame_length=win_length,
            hop_length=hop_length
        )

        # 归一化音量
        if speech.abs().max() > max_val:
            speech = speech / speech.abs().max() * max_val

        # 添加尾部空白
        speech = torch.concat([speech, torch.zeros(1, int(self.sample_rate * 0.2))], dim=1)

        return speech

    def synthesize(self, text: str, params: Dict[str, Any],
                  voice_id: Optional[str] = None,
                  prompt_audio: Optional[str] = None,
                  prompt_text: Optional[str] = None,
                  instruct_text: Optional[str] = None,
                  output_path: Optional[str] = None) -> Tuple[np.ndarray, float]:
        """
        使用 CosyVoice 合成语音

        Args:
            text: 要合成的文本
            params: 合成参数
            voice_id: 预训练音色ID
            prompt_audio: 参考音频文件路径（用于声音克隆）
            prompt_text: 参考音频对应的文本（用于3s极速复刻）
            instruct_text: 指令文本（用于自然语言控制）
            output_path: 输出文件路径（可选）

        Returns:
            audio: 音频波形
            duration: 音频时长（秒）
        """
        if not COSYVOICE_AVAILABLE or self.model is None:
            print("CosyVoice 不可用，使用替代实现")
            return self._placeholder_synthesis(text, params)

        try:
            # 设置随机种子
            seed = params.get('seed', 0)
            set_all_random_seed(seed)

            # 设置推理速度
            speed = params.get('speed', 1.0)

            # 确定推理模式
            mode = params.get('mode', 'sft')
            stream = params.get('stream', False)

            # 根据模式选择推理方法
            if mode == 'sft':
                # 预训练音色模式
                if voice_id is None or voice_id not in self.available_spks:
                    print(f"无效的预训练音色ID: {voice_id}")
                    voice_id = self.available_spks[0] if self.available_spks else ""

                result = next(self.model.inference_sft(
                    text, voice_id, stream=stream, speed=speed
                ))

            elif mode == 'zero_shot':
                # 3s极速复刻模式
                if prompt_audio is None:
                    raise ValueError("3s极速复刻模式需要提供参考音频")

                if prompt_text is None or prompt_text == "":
                    raise ValueError("3s极速复刻模式需要提供参考文本")

                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))

                result = next(self.model.inference_zero_shot(
                    text, prompt_text, prompt_speech, stream=stream, speed=speed
                ))

            elif mode == 'cross_lingual':
                # 跨语种复刻模式
                if prompt_audio is None:
                    raise ValueError("跨语种复刻模式需要提供参考音频")

                if self.instruct:
                    print("警告: 跨语种复刻模式不支持指令控制模型")

                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))

                result = next(self.model.inference_cross_lingual(
                    text, prompt_speech, stream=stream, speed=speed
                ))

            elif mode == 'instruct':
                # 自然语言控制模式
                if not self.instruct:
                    print("警告: 当前模型不支持指令控制模式")
                    # 退回到预训练音色模式
                    return self.synthesize(text, params, voice_id, prompt_audio, prompt_text, None, output_path)

                if instruct_text is None or instruct_text == "":
                    raise ValueError("指令控制模式需要提供指令文本")

                if voice_id is None or voice_id not in self.available_spks:
                    print(f"无效的预训练音色ID: {voice_id}")
                    voice_id = self.available_spks[0] if self.available_spks else ""

                result = next(self.model.inference_instruct(
                    text, voice_id, instruct_text, stream=stream, speed=speed
                ))

            else:
                raise ValueError(f"未知的推理模式: {mode}")

            # 获取合成的音频
            speech = result['tts_speech'].numpy().flatten()


            # 计算音频时长
            duration = len(speech) / self.sample_rate

            # 如果指定了输出路径，保存音频
            if output_path:
                sf.write(output_path, speech, self.sample_rate)

            return speech, duration

        except Exception as e:
            print(f"CosyVoice 合成失败: {e}")
            # 使用替代实现
            return self._placeholder_synthesis(text, params)

    async def synthesize_streaming(self, text: str, params: Dict[str, Any], websocket: WebSocket,
                           voice_id: Optional[str] = None,
                           prompt_audio: Optional[str] = None,
                           prompt_text: Optional[str] = None,
                           instruct_text: Optional[str] = None) -> float:
        """
        流式语音合成并通过 WebSocket 发送

        Args:
            text: 输入文本
            params: 合成参数
            websocket: WebSocket 连接
            voice_id: 预训练音色ID
            prompt_audio: 参考音频文件路径
            prompt_text: 参考音频对应的文本
            instruct_text: 指令文本

        Returns:
            duration: 音频总时长（秒）
        """
        if not COSYVOICE_AVAILABLE or self.model is None:
            # 使用非流式合成并分块发送
            audio, duration = self._placeholder_synthesis(text, params)

            # 发送总块数信息
            chunk_size = 4096
            total_chunks = (len(audio) + chunk_size - 1) // chunk_size
            await websocket.send_json({"type": "info", "total_chunks": total_chunks})

            # 逐块发送音频
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size].tobytes()
                await websocket.send_bytes(chunk)
                await asyncio.sleep(0.05)

            # 发送完成标记
            await websocket.send_json({"type": "complete", "duration": float(duration)})

            return duration

        try:
            # 设置随机种子和速度
            seed = params.get('seed', 0)
            speed = params.get('speed', 1.0)
            set_all_random_seed(seed)

            # 确定推理模式
            mode = params.get('mode', 'sft')
            stream = True  # 强制流式推理

            # 获取迭代器
            if mode == 'sft':
                if voice_id is None or voice_id not in self.available_spks:
                    await websocket.send_json({"type": "error", "message": f"无效的预训练音色ID: {voice_id}"})
                    return 0

                iterator = self.model.inference_sft(text, voice_id, stream=stream, speed=speed)

            elif mode == 'zero_shot':
                if prompt_audio is None:
                    await websocket.send_json({"type": "error", "message": "3s极速复刻模式需要提供参考音频"})
                    return 0

                if prompt_text is None or prompt_text == "":
                    await websocket.send_json({"type": "error", "message": "3s极速复刻模式需要提供参考文本"})
                    return 0

                try:
                    # 加载并处理参考音频
                    await websocket.send_json({"type": "info", "message": "正在加载参考音频..."})
                    audio_tensor, sr = safe_load_audio(prompt_audio, 16000)
                    if audio_tensor is None:
                        await websocket.send_json({"type": "error", "message": f"无法加载参考音频文件: {prompt_audio}"})
                        return 0

                    # 进行后处理
                    prompt_speech = self.postprocess(audio_tensor)

                    await websocket.send_json({"type": "info", "message": "正在使用您的声音进行合成..."})
                    iterator = self.model.inference_zero_shot(
                        text, prompt_text, prompt_speech, stream=stream, speed=speed
                    )
                except Exception as e:
                    print(f"加载参考音频失败: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({"type": "error", "message": f"处理参考音频失败: {str(e)}"})
                    return 0
            elif mode == 'cross_lingual':
                if prompt_audio is None:
                    await websocket.send_json({"type": "error", "message": "跨语种复刻模式需要提供参考音频"})
                    return 0

                if self.instruct:
                    await websocket.send_json({"type": "warning", "message": "跨语种复刻模式不支持指令控制模型"})

                # 加载并处理参考音频
                prompt_speech = self.postprocess(load_wav(prompt_audio, 16000))

                iterator = self.model.inference_cross_lingual(text, prompt_speech, stream=stream, speed=speed)

            elif mode == 'instruct':
                if not self.instruct:
                    await websocket.send_json({"type": "warning", "message": "当前模型不支持指令控制模式"})
                    # 退回到预训练音色模式
                    return await self.synthesize_streaming(text, {**params, "mode": "sft"}, websocket, voice_id)

                if instruct_text is None or instruct_text == "":
                    await websocket.send_json({"type": "error", "message": "指令控制模式需要提供指令文本"})
                    return 0

                if voice_id is None or voice_id not in self.available_spks:
                    await websocket.send_json({"type": "warning", "message": f"无效的预训练音色ID: {voice_id}"})
                    voice_id = self.available_spks[0] if self.available_spks else ""

                iterator = self.model.inference_instruct(text, voice_id, instruct_text, stream=stream, speed=speed)

            else:
                await websocket.send_json({"type": "error", "message": f"未知的推理模式: {mode}"})
                return 0

            # 发送开始信息
            await websocket.send_json({"type": "info", "message": "开始合成"})

            # 逐个发送音频块
            total_duration = 0
            chunk_index = 0

            for result in iterator:
                # 获取音频数据
                speech = result['tts_speech'].numpy().flatten()
                pcm_data = (speech * 32767).astype(np.int16)
                # 创建完整的WAV数据
                wav_header = create_wav_header(self.sample_rate, len(pcm_data))
                wav_data = bytearray(wav_header) + pcm_data.tobytes()

                # 发送完整的WAV数据
                await websocket.send_bytes(wav_data)

                # 计算时长
                chunk_duration = len(speech) / self.sample_rate
                total_duration += chunk_duration

                # 发送进度信息
                await websocket.send_json({
                    "type": "progress",
                    "chunk_index": chunk_index,
                    "duration": chunk_duration
                })

                chunk_index += 1

                # 短暂延迟
                await asyncio.sleep(0.01)

            # 发送完成信息
# 确保所有数值字段都是正确的数值类型
            try:
                # 确保duration是浮点数
                final_duration = float(total_duration) if total_duration is not None else 0.0
                # 确保其他数值也是正确的类型
                final_chunks = int(chunk_index) if chunk_index is not None else 0
                final_sample_rate = int(self.sample_rate)

                # 发送完成信息
                await websocket.send_json({
                    "type": "complete",
                    "duration": final_duration,
                    "chunks": final_chunks,
                    "sample_rate": final_sample_rate,
                    "format": "wav",  # 或 "pcm" 取决于你发送的格式
                    "channels": 1,
                    "bit_depth": 16
                })
            except Exception as e:
                print(f"发送完成消息时出错: {e}")
                import traceback
                traceback.print_exc()
                # 发送一个简化的完成消息
                await websocket.send_json({
                    "type": "complete",
                    "duration": 0.0,  # 使用安全的默认值
                    "error": str(e)
                })

            return total_duration

        except Exception as e:
            print(f"流式合成失败: {e}")
            # 发送错误信息
            await websocket.send_json({"type": "error", "message": str(e)})

            # 退回到非流式方式
            audio, duration = self._placeholder_synthesis(text, params)

            # 分块发送音频
            chunk_size = 4096
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size].tobytes()
                await websocket.send_bytes(chunk)
                await asyncio.sleep(0.05)

            # 发送完成信息
            await websocket.send_json({"type": "complete", "duration": float(duration)})

            return duration

    def _placeholder_synthesis(self, text: str, params: Dict[str, Any]) -> Tuple[np.ndarray, float]:
        """CosyVoice 不可用时的替代合成实现"""
        # 基于文本长度和语速估计时长
        chars = len(text)
        speed = params.get("speed", 1.0)
        chars_per_second = 5 * speed  # 假设每秒约5个汉字
        duration = max(1.0, chars / chars_per_second)

        # 创建时间数组
        sample_rate = self.sample_rate
        t = np.linspace(0, duration, int(duration * sample_rate))

        # 创建基于音高参数的载波
        pitch_param = params.get("pitch", 0)
        base_freq = 170 * (2 ** (pitch_param * 0.5))
        carrier = np.sin(2 * np.pi * base_freq * t)

        # 添加谐波增加丰富度
        harmonics = 0
        for i in range(2, 6):
            harmonics += (1/i) * np.sin(2 * np.pi * (base_freq * i) * t)

        carrier = 0.7 * carrier + 0.3 * harmonics

        # 基于音节创建包络
        syllables = max(1, chars)
        envelope = np.ones_like(t) * 0.1

        pause_factor = params.get("pause_factor", 1.0)
        syllable_positions = np.linspace(0, duration * 0.8, syllables)
        syllable_width = 0.15

        for pos in syllable_positions:
            idx = (t >= pos) & (t <= pos + syllable_width)
            if np.any(idx):
                envelope[idx] = 0.5 + 0.5 * np.sin(np.pi * (t[idx] - pos) / syllable_width)

        try:
            from scipy.ndimage import gaussian_filter1d
            envelope = gaussian_filter1d(envelope, sigma=0.01 * sample_rate)
        except ImportError:
            # 如果没有scipy，使用简单平滑
            smooth_window = int(0.01 * sample_rate)
            if smooth_window > 1:
                envelope_smooth = np.zeros_like(envelope)
                for i in range(len(envelope)):
                    start = max(0, i - smooth_window // 2)
                    end = min(len(envelope), i + smooth_window // 2)
                    envelope_smooth[i] = np.mean(envelope[start:end])
                envelope = envelope_smooth

        # 应用情感风格
        emotion = params.get("emotion", "neutral")
        if emotion == "happy":
            modulation = 0.1 * np.sin(2 * np.pi * 3 * t / duration)
            carrier = carrier + modulation
            envelope = np.power(envelope, 0.9)
        elif emotion == "sad":
            modulation = 0.05 * np.sin(2 * np.pi * 1 * t / duration)
            carrier = carrier - modulation
            envelope = np.power(envelope, 1.2)
        elif emotion == "serious":
            envelope = np.power(envelope, 1.1)
            envelope = np.clip(envelope, 0, 0.9)

        # 应用包络
        audio = carrier * envelope

        # 应用音量
        energy = params.get("energy", 1.0)
        audio = audio * energy

        # 添加噪声以模拟辅音
        noise = np.random.uniform(-0.05, 0.05, len(audio))
        audio = audio + noise * envelope * 0.3

        # 添加音高微小变化
        tremolo = 1.0 + 0.03 * np.sin(2 * np.pi * 5 * t)
        audio = audio * tremolo

        # 添加淡入淡出
        fade_len = int(0.05 * sample_rate)
        if len(audio) > 2 * fade_len:
            fade_in = np.linspace(0, 1, fade_len)
            fade_out = np.linspace(1, 0, fade_len)
            audio[:fade_len] = audio[:fade_len] * fade_in
            audio[-fade_len:] = audio[-fade_len:] * fade_out

        # 归一化
        max_amp = np.max(np.abs(audio))
        if max_amp > 0:
            audio = audio / max_amp * 0.95

        # 将浮点数组转换为16位整数格式（符合大多数音频处理的要求）
        audio = np.asarray(audio * 32767, dtype=np.int16)

        return audio, duration

    def get_available_voices(self) -> List[str]:
        """获取可用的预训练音色列表"""
        return self.available_spks

# 改进的初始化函数，加载任务和映射关系
async def init_cosyvoice_tts_service():
    global TTS_TASKS_DB, cosyvoice_model, TASK_ID_MAPPING

    # 确保目录存在
    output_dir = os.path.join(settings.UPLOAD_DIR, "cosyvoice_results")
    os.makedirs(output_dir, exist_ok=True)

    # 加载任务映射关系
    mapping_file = os.path.join(os.path.dirname(TTS_TASKS_FILE), "task_id_mapping.json")
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                TASK_ID_MAPPING = json.load(f)
                print(f"已加载 {len(TASK_ID_MAPPING)} 个任务ID映射")
        except Exception as e:
            print(f"加载任务ID映射时出错: {e}")
            TASK_ID_MAPPING = {}

    # 加载现有任务
    if os.path.exists(TTS_TASKS_FILE):
        try:
            with open(TTS_TASKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"从文件加载 {len(data)} 个任务")

                TTS_TASKS_DB = [TTSTaskDB(**item) for item in data]
                print(f"成功加载 {len(TTS_TASKS_DB)} 个任务")

                # 打印所有任务ID，用于调试
                print(f"已加载的任务ID: {[t.task_id for t in TTS_TASKS_DB]}")
        except Exception as e:
            print(f"加载任务失败: {e}")
            TTS_TASKS_DB = []
    else:
        print(f"任务文件不存在，创建空列表")
        TTS_TASKS_DB = []

    # 初始化 CosyVoice TTS 模型
    cosyvoice_model = CosyVoiceTTS()

    print("CosyVoice TTS 服务初始化完成")

# 改进的任务保存函数，确保同步保存
# 保存任务到文件
async def save_tts_tasks():
    """
    保存任务到文件，处理datetime序列化
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(TTS_TASKS_FILE), exist_ok=True)

        # 定义datetime序列化处理器
        def json_serial(obj):
            """JSON序列化器，处理datetime对象"""
            if isinstance(obj, (datetime, datetime.date)):
                return obj.isoformat()
            return str(obj)  # 为其他类型提供一个默认字符串表示

        with open(TTS_TASKS_FILE, 'w', encoding='utf-8') as f:
            # 转换为字典列表并保存
            data = [task.dict() for task in TTS_TASKS_DB]
            # 使用default参数处理datetime
            json.dump(data, f, default=json_serial, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存任务文件时出错: {e}")
        import traceback
        traceback.print_exc()
# 创建语音合成任务
async def synthesize_speech(
    background_tasks,
    text,
    voice_id,
    params,
    prompt_audio=None,
    prompt_text=None,
    instruct_text=None
):
    """创建语音合成任务，使用更可靠的任务ID机制"""
    # 验证参数
    if not text:
        raise ValueError("合成文本不能为空")

    # 创建任务ID
    task_id = create_normalized_task_id(voice_id, text)

    # 创建任务对象
    task = TTSTaskDB(
        task_id=task_id,
        text=text,
        voice_id=voice_id,  # 保留原始语音ID
        params={
            **params,
            "prompt_audio": prompt_audio,
            "prompt_text": prompt_text,
            "instruct_text": instruct_text
        },
        status="pending",
        progress=0.0,
        created_at=datetime.now()
    )

    # 添加到内存数据库
    TTS_TASKS_DB.append(task)

    # 同步保存
    await save_tts_tasks()
    print(f"任务已创建并保存: {task_id}")

    # 异步执行合成
    background_tasks.add_task(process_tts_task, task_id)

    return task_id

# 流式语音合成
async def synthesize_speech_streaming(
    websocket: WebSocket,
    text: str,
    voice_id: str,
    params: Dict[str, Any],
    prompt_audio: Optional[str] = None,
    prompt_text: Optional[str] = None,
    instruct_text: Optional[str] = None
) -> float:
    """
    流式语音合成并通过 WebSocket 发送

    Args:
        websocket: WebSocket 连接
        text: 输入文本
        voice_id: 预训练音色ID
        params: 合成参数
        prompt_audio: 参考音频文件路径
        prompt_text: 参考音频对应的文本
        instruct_text: 指令文本

    Returns:
        duration: 音频总时长（秒）
    """
    # 导入存储函数
    from app.services.shared_storage import AUDIO_STORAGE, LATEST_AUDIO
    import io
    import soundfile as sf

    # 创建任务ID
    task_id = f"stream_{int(time.time())}_{voice_id}"

    # 初始化音频存储
    if task_id not in AUDIO_STORAGE:
        AUDIO_STORAGE[task_id] = {
            "chunks": [],
            "complete_audio": None,
            "duration": 0.0,
            "timestamp": int(time.time()),
            "sample_rate": 0
        }

    # 获取合成模型
    cosyvoice_model = get_cosyvoice_model()

    if not COSYVOICE_AVAILABLE or cosyvoice_model.model is None:
        # 使用非流式合成并分块发送
        audio, duration = cosyvoice_model._placeholder_synthesis(text, params)

        # 发送总块数信息
        chunk_size = 4096
        total_chunks = (len(audio) + chunk_size - 1) // chunk_size
        await websocket.send_json({"type": "info", "total_chunks": total_chunks})

        # 将完整音频转换为WAV格式
        buffer = io.BytesIO()
        sf.write(buffer, audio, cosyvoice_model.sample_rate, format='WAV')
        buffer.seek(0)
        complete_audio = buffer.read()

        # 保存完整音频
        AUDIO_STORAGE[task_id]["complete_audio"] = complete_audio
        AUDIO_STORAGE[task_id]["duration"] = duration
        AUDIO_STORAGE[task_id]["sample_rate"] = cosyvoice_model.sample_rate

        # 逐块发送音频
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size].tobytes()
            await websocket.send_bytes(chunk)
            await asyncio.sleep(0.05)

        # 发送完成标记，包含任务ID
        await websocket.send_json({
            "type": "complete",
            "duration": float(duration),
            "task_id": task_id
        })

        return duration

    try:
        # 设置随机种子和速度
        seed = params.get('seed', 0)
        speed = params.get('speed', 1.0)
        set_all_random_seed(seed)

        # 确定推理模式
        mode = params.get('mode', 'sft')
        stream = True  # 强制流式推理

        # 获取迭代器
        if mode == 'sft':
            if voice_id is None or voice_id not in cosyvoice_model.available_spks:
                await websocket.send_json({"type": "error", "message": f"无效的预训练音色ID: {voice_id}"})
                return 0

            iterator = cosyvoice_model.model.inference_sft(text, voice_id, stream=stream, speed=speed)

        elif mode == 'zero_shot':
            if prompt_audio is None:
                await websocket.send_json({"type": "error", "message": "3s极速复刻模式需要提供参考音频"})
                return 0

            if prompt_text is None or prompt_text == "":
                await websocket.send_json({"type": "error", "message": "3s极速复刻模式需要提供参考文本"})
                return 0

            try:
                # 加载并处理参考音频
                await websocket.send_json({"type": "info", "message": "正在加载参考音频..."})
                audio_tensor, sr = safe_load_audio(prompt_audio, 16000)
                if audio_tensor is None:
                    await websocket.send_json({"type": "error", "message": f"无法加载参考音频文件: {prompt_audio}"})
                    return 0

                # 进行后处理
                prompt_speech = postprocess(audio_tensor)

                await websocket.send_json({"type": "info", "message": "正在使用您的声音进行合成..."})
                iterator = cosyvoice_model.model.inference_zero_shot(
                    text, prompt_text, prompt_speech, stream=stream, speed=speed
                )
            except Exception as e:
                print(f"加载参考音频失败: {e}")
                import traceback
                traceback.print_exc()
                await websocket.send_json({"type": "error", "message": f"处理参考音频失败: {str(e)}"})
                return 0
        elif mode == 'cross_lingual':
            if prompt_audio is None:
                await websocket.send_json({"type": "error", "message": "跨语种复刻模式需要提供参考音频"})
                return 0

            if hasattr(cosyvoice_model, 'instruct') and cosyvoice_model.instruct:
                await websocket.send_json({"type": "warning", "message": "跨语种复刻模式不支持指令控制模型"})

            # 加载并处理参考音频
            prompt_speech = postprocess(load_wav(prompt_audio, 16000))

            iterator = cosyvoice_model.model.inference_cross_lingual(text, prompt_speech, stream=stream, speed=speed)

        elif mode == 'instruct':
            if not hasattr(cosyvoice_model, 'instruct') or not cosyvoice_model.instruct:
                await websocket.send_json({"type": "warning", "message": "当前模型不支持指令控制模式"})
                # 退回到预训练音色模式
                return await synthesize_speech_streaming(websocket, text, voice_id, {**params, "mode": "sft"}, None, None, None)

            if instruct_text is None or instruct_text == "":
                await websocket.send_json({"type": "error", "message": "指令控制模式需要提供指令文本"})
                return 0

            if voice_id is None or voice_id not in cosyvoice_model.available_spks:
                await websocket.send_json({"type": "warning", "message": f"无效的预训练音色ID: {voice_id}"})
                voice_id = cosyvoice_model.available_spks[0] if cosyvoice_model.available_spks else ""

            iterator = cosyvoice_model.model.inference_instruct(text, voice_id, instruct_text, stream=stream, speed=speed)

        else:
            await websocket.send_json({"type": "error", "message": f"未知的推理模式: {mode}"})
            return 0

        # 发送开始信息
        await websocket.send_json({"type": "info", "message": "开始合成"})

        # 存储所有块的数据
        all_chunks_data = []
        all_raw_audio = []

        # 设置采样率
        AUDIO_STORAGE[task_id]["sample_rate"] = cosyvoice_model.sample_rate

        # 逐个发送音频块
        total_duration = 0
        chunk_index = 0

        for result in iterator:
            # 获取音频数据
            speech = result['tts_speech'].numpy().flatten()
            pcm_data = (speech * 32767).astype(np.int16)

            # 保存原始音频数据（用于后续合并）
            all_raw_audio.append(speech)

            # 创建完整的WAV数据
            wav_header = create_wav_header(cosyvoice_model.sample_rate, len(pcm_data))
            wav_data = bytearray(wav_header) + pcm_data.tobytes()

            # 储存块数据
            all_chunks_data.append(wav_data)
            AUDIO_STORAGE[task_id]["chunks"].append(wav_data)

            # 计算当前块的时长
            chunk_duration = len(speech) / cosyvoice_model.sample_rate

            # 更新总时长
            total_duration += chunk_duration
            AUDIO_STORAGE[task_id]["duration"] += chunk_duration

            # 发送音频数据
            await websocket.send_bytes(wav_data)

            # 更新最新音频（向后兼容）
            LATEST_AUDIO["data"] = wav_data
            LATEST_AUDIO["timestamp"] = int(time.time())
            LATEST_AUDIO["task_id"] = task_id
            LATEST_AUDIO["duration"] = chunk_duration
            LATEST_AUDIO["sample_rate"] = cosyvoice_model.sample_rate

            # 发送进度信息
            await websocket.send_json({
                "type": "progress",
                "chunk_index": chunk_index,
                "duration": chunk_duration,
                "total_duration_so_far": total_duration
            })

            chunk_index += 1

            # 短暂延迟
            await asyncio.sleep(0.01)

        # 合并所有原始音频数据，创建完整音频
        if all_raw_audio:
            try:
                # 合并所有原始音频
                merged_audio = np.concatenate(all_raw_audio)

                # 创建完整的WAV文件
                buffer = io.BytesIO()
                sf.write(buffer, merged_audio, cosyvoice_model.sample_rate, format='WAV')
                buffer.seek(0)
                complete_audio = buffer.read()

                # 保存完整音频
                AUDIO_STORAGE[task_id]["complete_audio"] = complete_audio

                print(f"已生成完整音频，时长: {total_duration:.2f}秒, 大小: {len(complete_audio)} 字节")
            except Exception as e:
                print(f"合并音频失败: {e}")
                import traceback
                traceback.print_exc()

        # 发送完成信息，包括更详细的元数据
        print(f"流式合成完成，共 {chunk_index} 个音频块，总时长: {total_duration:.2f}秒")

        try:
            # 确保所有值都是正确的数值类型
            final_duration = float(total_duration) if total_duration is not None else 0.0
            final_chunks = int(chunk_index) if chunk_index is not None else 0
            final_sample_rate = int(cosyvoice_model.sample_rate)

            # 发送更详细的完成信息，包含任务ID
            await websocket.send_json({
                "type": "complete",
                "duration": final_duration,
                "chunks": final_chunks,
                "sample_rate": final_sample_rate,
                "format": "wav",
                "channels": 1,
                "bit_depth": 16,
                "task_id": task_id  # 添加任务ID供前端使用
            })
        except Exception as e:
            print(f"发送完成消息时出错: {e}")
            import traceback
            traceback.print_exc()
            # 发送简化的完成消息
            await websocket.send_json({
                "type": "complete",
                "duration": float(total_duration),
                "error": str(e),
                "task_id": task_id  # 即使出错也包含任务ID
            })

        return total_duration

    except Exception as e:
        print(f"流式合成失败: {e}")
        # 发送错误信息
        await websocket.send_json({"type": "error", "message": str(e)})

        # 退回到简单的错误处理
        try:
            # 发送失败完成信息
            await websocket.send_json({
                "type": "complete",
                "duration": 0.0,
                "error": str(e),
                "task_id": task_id  # 包含任务ID
            })
        except:
            pass

        return 0.0
# 修改任务处理函数支持内存存储
# 修改任务处理函数支持内存存储
async def process_tts_task(task_id):
    """处理语音合成任务，支持内存存储选项"""
    # 从共享存储中导入
    from app.services.shared_storage import IN_MEMORY_AUDIO

    # 查找任务
    task = next((t for t in TTS_TASKS_DB if t.task_id == task_id), None)
    if not task:
        print(f"找不到要处理的任务: {task_id}")
        return

    try:
        # 更新状态为处理中
        task.status = "processing"
        task.progress = 0.1
        task.updated_at = datetime.now()
        await save_tts_tasks()

        # 提取参数
        voice_id = task.voice_id
        mode = task.params.get("mode")
        prompt_audio = task.params.get("prompt_audio")
        prompt_text = task.params.get("prompt_text")
        instruct_text = task.params.get("instruct_text")

        print(f"处理任务: {task_id}")
        print(f"声音ID: {voice_id}")
        print(f"合成模式: {mode}")
        print(f"参考音频: {prompt_audio}")
        print(f"参考文本: {prompt_text}")

        # 检查是否使用内存存储
        save_to_memory = task.params.get("save_to_memory", False)

        # 设置输出文件路径（即使使用内存存储，也需要临时文件路径）
        output_dir = os.path.join(settings.UPLOAD_DIR, "cosyvoice_results")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{task_id}.wav")

        # 更新进度
        task.progress = 0.3
        task.updated_at = datetime.now()
        await save_tts_tasks()

        # 短暂延迟以便状态查询可以看到进度
        await asyncio.sleep(0.2)

        # 执行语音合成
        print(f"开始语音合成: {task_id}, 语音ID: {voice_id}, 模式: {mode}")

        if mode == "zero_shot" and prompt_audio and prompt_text:
            # 使用零样本克隆模式
            print(f"使用零样本模式合成，参考音频: {prompt_audio}")
            print(f"参考文本: {prompt_text}")

            # 加载参考音频
            try:
                if os.path.exists(prompt_audio):
                    prompt_speech = load_wav(prompt_audio, 16000)
                    prompt_speech = postprocess(prompt_speech)

                    # 执行零样本合成
                    result = next(cosyvoice_model.model.inference_zero_shot(
                        task.text, prompt_text, prompt_speech,
                        stream=False, speed=task.params.get("speed", 1.0)
                    ))

                    # 获取合成的音频
                    speech = result['tts_speech'].numpy().flatten()
                else:
                    print(f"参考音频文件不存在: {prompt_audio}")
                    raise FileNotFoundError(f"参考音频文件不存在: {prompt_audio}")
            except Exception as e:
                print(f"零样本合成失败: {e}")
                # 退回到标准合成
                print("退回到标准SFT模式合成")
                result = next(cosyvoice_model.model.inference_sft(
                    task.text, voice_id,
                    stream=False, speed=task.params.get("speed", 1.0)
                ))
                speech = result['tts_speech'].numpy().flatten()
        else:
            # 使用标准SFT模式
            print(f"使用SFT模式合成，声音ID: {voice_id}")
            result = next(cosyvoice_model.model.inference_sft(
                task.text, voice_id,
                stream=False, speed=task.params.get("speed", 1.0)
            ))
            speech = result['tts_speech'].numpy().flatten()

        # 计算音频时长
        duration = len(speech) / cosyvoice_model.sample_rate

        # 如果使用内存存储
        if save_to_memory:
            # 将语音数据保存到内存
            print(f"将语音数据保存到内存: {task_id}")
            import soundfile as sf
            import io

            # 创建内存IO对象
            buffer = io.BytesIO()

            # 写入WAV格式
            sf.write(buffer, speech, cosyvoice_model.sample_rate, format='WAV')

            # 获取二进制数据
            buffer.seek(0)
            audio_data = buffer.read()

            # 保存到全局内存存储
            IN_MEMORY_AUDIO[task_id] = audio_data

            # 文件路径设为None
            output_file = None
        else:
            # 保存到文件
            import soundfile as sf
            sf.write(output_file, speech, cosyvoice_model.sample_rate)

            # 验证文件生成
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"语音文件已生成: {output_file}, 大小: {file_size}字节")
            else:
                print(f"警告: 语音文件未生成")

        # 更新进度
        task.progress = 0.7
        task.updated_at = datetime.now()
        await save_tts_tasks()

        await asyncio.sleep(0.2)

        # 完成任务
        task.status = "completed"
        task.progress = 1.0
        task.updated_at = datetime.now()
        task.file_path = output_file  # 可能为None，表示保存在内存中
        task.duration = duration
        await save_tts_tasks()

        print(f"任务完成: {task_id}, {'保存到内存' if save_to_memory else '保存到文件'}")

    except Exception as e:
        # 更新任务状态为失败
        print(f"任务处理失败: {e}")
        import traceback
        traceback.print_exc()

        task.status = "failed"
        task.error = str(e)
        task.updated_at = datetime.now()
        await save_tts_tasks()

# 直接在内存中查找任务，避免文件读取的复杂性
async def get_tts_task_status(task_id: str):
    """查找任务状态，支持多种匹配方式"""
    print(f"查找任务状态: {task_id}")

    # 1. 尝试直接精确匹配
    for task in TTS_TASKS_DB:
        if task.task_id == task_id:
            print(f"直接匹配到任务: {task.task_id}")
            return TTSTaskStatus(
                task_id=task.task_id,
                text=task.text[:100] + "..." if len(task.text) > 100 else task.text,
                status=task.status,
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                duration=task.duration,
                error=task.error
            )

    # 2. 提取时间戳部分进行匹配
    parts = task_id.split('_')
    if len(parts) >= 3:
        timestamp = parts[2]
        print(f"尝试匹配时间戳: {timestamp}")

        for task in TTS_TASKS_DB:
            task_parts = task.task_id.split('_')
            if len(task_parts) >= 3 and task_parts[2] == timestamp:
                print(f"通过时间戳匹配到任务: {task.task_id}")
                return TTSTaskStatus(
                    task_id=task.task_id,
                    text=task.text[:100] + "..." if len(task.text) > 100 else task.text,
                    status=task.status,
                    progress=task.progress,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    duration=task.duration,
                    error=task.error
                )

    # 3. 检查映射表中是否有对应关系
    original_voice_id = None
    for saved_task_id, voice_id in TASK_ID_MAPPING.items():
        if saved_task_id in task_id or task_id in saved_task_id:
            print(f"在映射表中找到相关任务ID: {saved_task_id}")
            # 查找这个已保存的任务ID
            for task in TTS_TASKS_DB:
                if task.task_id == saved_task_id:
                    print(f"通过映射关系找到任务: {task.task_id}")
                    return TTSTaskStatus(
                        task_id=task.task_id,
                        text=task.text[:100] + "..." if len(task.text) > 100 else task.text,
                        status=task.status,
                        progress=task.progress,
                        created_at=task.created_at,
                        updated_at=task.updated_at,
                        duration=task.duration,
                        error=task.error
                    )

    # 如果到这里还没找到，作为最后手段，尝试返回最近的任务
    if TTS_TASKS_DB:
        # 按创建时间排序，获取最新的任务
        latest_task = max(TTS_TASKS_DB, key=lambda t: t.created_at if t.created_at else datetime.min)
        created_time = latest_task.created_at if latest_task.created_at else datetime.now()
        time_diff = (datetime.now() - created_time).total_seconds()

        # 如果是最近30秒内创建的任务，就返回它
        if time_diff < 30:
            print(f"未找到精确匹配，返回最新任务: {latest_task.task_id}（{time_diff}秒前创建）")
            return TTSTaskStatus(
                task_id=latest_task.task_id,
                text=latest_task.text[:100] + "..." if len(latest_task.text) > 100 else latest_task.text,
                status=latest_task.status,
                progress=latest_task.progress,
                created_at=latest_task.created_at,
                updated_at=latest_task.updated_at,
                duration=latest_task.duration,
                error=latest_task.error
            )

    # 真的找不到了
    print(f"任务未找到: {task_id}")
    print(f"当前所有任务: {[t.task_id for t in TTS_TASKS_DB]}")
    print(f"当前映射关系: {TASK_ID_MAPPING}")
    return None
# 获取任务结果
async def get_tts_task_result(task_id):
    """获取已完成任务的结果"""
    # 获取任务状态
    status = await get_tts_task_status(task_id)
    if not status or status.status != "completed":
        return None

    # 找到对应任务
    task = next((t for t in TTS_TASKS_DB if t.task_id == status.task_id), None)
    if not task:
        return None

    # 添加文件路径
    if task.file_path and os.path.exists(task.file_path):
        status.file_path = task.file_path
        return status

    # 如果找不到预期文件，尝试查找相关文件
    output_dir = os.path.join(settings.UPLOAD_DIR, "cosyvoice_results")
    try:
        for filename in os.listdir(output_dir):
            if task_id in filename:
                full_path = os.path.join(output_dir, filename)
                if os.path.exists(full_path):
                    status.file_path = full_path
                    return status
    except Exception as e:
        print(f"查找结果文件时出错: {e}")

    return None

def get_cosyvoice_model():
    global cosyvoice_model
    return cosyvoice_model

# 添加 synthesize_speech 函数
async def synthesize_speech(text: str, voice_id: str, speed: float = 1.0, emotion: str = "neutral", pitch: float = 0.0, energy: float = 1.0, pause_factor: float = 1.0) -> tuple:
    """
    合成语音

    Args:
        text: 要合成的文本
        voice_id: 声音ID
        speed: 语速，默认为1.0
        emotion: 情感，默认为neutral
        pitch: 音高，默认为0.0
        energy: 能量，默认为1.0
        pause_factor: 停顿因子，默认为1.0

    Returns:
        tuple: (音频数据, 持续时间)
    """
    print(f"合成语音: {text[:30]}...")
    print(f"参数: voice_id={voice_id}, speed={speed}, emotion={emotion}, pitch={pitch}, energy={energy}, pause_factor={pause_factor}")

    # 获取合成模型
    model = get_cosyvoice_model()
    if not model:
        print("无法获取语音合成模型")
        return np.zeros(16000), 1.0  # 返回1秒的静音

    # 设置参数
    params = {
        "speed": speed,
        "emotion": emotion,
        "pitch": pitch,
        "energy": energy,
        "pause_factor": pause_factor,
        "mode": "sft"  # 使用SFT模式
    }

    try:
        # 使用模型的synthesize方法合成语音
        speech, duration = model.synthesize(text, params, voice_id)
        print(f"语音合成成功，持续时间: {duration:.2f}秒")
        return speech, duration
    except Exception as e:
        print(f"语音合成失败: {e}")
        import traceback
        traceback.print_exc()
        # 返回1秒的静音
        return np.zeros(16000), 1.0

