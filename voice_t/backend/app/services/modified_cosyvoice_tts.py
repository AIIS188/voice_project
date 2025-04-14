"""Modified CosyVoice TTS Service - Simplified for real-time use

专注于实时语音合成，不保存历史任务。
"""
import os
import time
import torch
import librosa
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import BackgroundTasks
import torch
import librosa
import os
import traceback
# 导入必要的组件
from app.services.cosyvoice_tts import (
    get_cosyvoice_model,
    synthesize_speech_streaming,
    safe_load_audio,
    postprocess

)
from app.services.unified_voice_service import get_voice_by_id
from app.core.config import settings
from cosyvoice.utils.file_utils import load_wav

# 内存中的活跃任务映射表 - 只保存当前活跃的任务
# 键: 任务ID，值: 任务状态对象
ACTIVE_TASKS = {}
prompt_sr = 16000


# 简化的任务ID生成
def create_simple_task_id(voice_id):
    """创建简单的任务ID，基于时间戳和语音ID"""
    timestamp = int(time.time())
    # 使用时间戳确保唯一性，但不再需要复杂的映射
    return f"tts_{timestamp}_{voice_id}"


# 简化的任务状态类
class SimpleTaskStatus:
    def __init__(self, task_id, voice_id, text, params, status="pending"):
        self.task_id = task_id
        self.voice_id = voice_id
        self.text = text
        self.status = status
        self.progress = 0.0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.file_path = None
        self.audio_data = None
        self.duration = None
        self.error = None
        self.params = params
    
    def to_dict(self):
        """转换为字典用于API响应"""
        return {
            "task_id": self.task_id,
            "voice_id": self.voice_id,
            "text": self.text[:100] + "..." if len(self.text) > 100 else self.text,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "duration": self.duration,
            "error": self.error,
            "ready_to_play": self.status == "completed",
            "download_url": f"/api/tts/download/{self.task_id}" if self.status == "completed" else None,
            "audio_url": f"/api/tts/preview_audio/{self.task_id}" if self.status == "completed" else None
        }

async def synthesize_speech_unified(
    background_tasks: BackgroundTasks,
    text: str,
    voice_id: str,
    params: Dict[str, Any]
) -> str:
    """简化的语音合成任务创建 - 实时系统版本"""
    # 验证参数
    if not text:
        raise ValueError("文本不能为空")
    
    # 获取声音信息
    voice = get_voice_by_id(voice_id)
    if not voice:
        print(f"找不到声音: {voice_id}")
        raise ValueError(f"找不到声音: {voice_id}")
    
    # 创建简单任务ID
    task_id = create_simple_task_id(voice_id)
    print(f"创建任务ID: {task_id}")
    
    # 根据声音类型配置合成
    enhanced_params = params.copy()
    
    if voice["type"] == "pretrained":
        # 预训练声音，使用SFT模式
        enhanced_params["mode"] = "sft"
    elif voice["type"] == "user-uploaded":
        # 用户上传的声音，使用zero-shot克隆
        enhanced_params["mode"] = "zero_shot"
        
        # 获取参考音频和文本
        prompt_audio = voice.get("reference_audio")
        prompt_text = voice.get("reference_text")
        
        # 如果缺少参考资料，尝试找到它
        if not prompt_audio or not prompt_text:
            if voice_id.startswith("user_"):
                # 尝试标准路径
                reference_path = os.path.join(settings.UPLOAD_DIR, "user_voices", voice_id, "reference.wav")
                if os.path.exists(reference_path):
                    prompt_audio = reference_path
                    
                    # 如果没有文本，使用默认文本
                    if not prompt_text:
                        prompt_text = "这是一段用于语音合成的参考音频。"
                        print("使用默认的参考文本")
        
        # 检查是否找到必要资源
        if not prompt_audio:
            raise ValueError(f"无法找到声音的参考音频: {voice_id}")
        
        if not prompt_text:
            # 使用默认文本
            prompt_text = "这是一段用于语音合成的参考音频。"
            print("使用默认的参考文本")
        
        # 使用安全的方法加载参考音频
        try:
            audio_tensor, sr = safe_load_audio(prompt_audio, prompt_sr)
            if audio_tensor is None:
                raise ValueError(f"无法加载参考音频文件: {prompt_audio}")
            
            # 进行后处理
            prompt_speech = postprocess(audio_tensor)
            
            # 添加参考数据到参数
            enhanced_params["prompt_speech"] = prompt_speech
            enhanced_params["prompt_text"] = prompt_text
        except Exception as e:
            print(f"处理参考音频时出错: {e}")
            traceback.print_exc()
            raise ValueError(f"处理参考音频时出错: {str(e)}")
    else:
        raise ValueError(f"不支持的声音类型: {voice['type']}")
    
    # 创建任务状态
    task = SimpleTaskStatus(task_id, voice_id, text, enhanced_params)
    
    # 保存到活跃任务表
    ACTIVE_TASKS[task_id] = task
    
    # 异步处理合成
    background_tasks.add_task(process_tts_task, task_id)
    
    return task_id
# 简化的任务处理函数
# 修改process_tts_task函数来处理所有音频片段

async def process_tts_task(task_id):
    """处理语音合成任务 - 专注于保存最新音频"""
    # 从共享存储中导入
    from app.services.shared_storage import LATEST_AUDIO, add_audio_chunk, merge_audio_chunks
    import soundfile as sf
    import io
    import time
    import asyncio
    # 查找任务
    if task_id not in ACTIVE_TASKS:
        print(f"找不到要处理的任务: {task_id}")
        return
    
    task = ACTIVE_TASKS[task_id]
    
    try:
        # 获取合成模型
        cosyvoice_model = get_cosyvoice_model()
        
        if not cosyvoice_model:
            raise ValueError("无法获取语音合成模型")
        # 执行语音合成
        # 更新进度 - 3 (30%)
        task.progress = 0.3
        task.updated_at = datetime.now()
        await asyncio.sleep(0.1)
        speech = None
        
        # 使用标准SFT模式
        if task.params.get("mode")=="zero_shot":
            print(f"使用zero_shot模式合成")
            result = next(cosyvoice_model.model.inference_zero_shot(
                task.text, task.params.get("prompt_text"), task.params.get("prompt_speech"),  
                stream=False, speed=task.params.get("speed", 1.0)
            ))
            speech = result['tts_speech'].numpy().flatten()
        else:
            print(f"使用SFT模式合成")
            result = next(cosyvoice_model.model.inference_sft(
                task.text, task.voice_id, 
                stream=False, speed=task.params.get("speed", 1.0)
            ))
            speech = result['tts_speech'].numpy().flatten()
        
        # 计算音频时长
        duration = len(speech) / cosyvoice_model.sample_rate
        
        # 将音频转换为WAV格式
        buffer = io.BytesIO()
        sf.write(buffer, speech, cosyvoice_model.sample_rate, format='WAV')
        buffer.seek(0)
        audio_data = buffer.read()
        
        # 添加到音频存储 - 使用新的函数
        add_audio_chunk(task_id, audio_data, duration, cosyvoice_model.sample_rate)
        
        # 确保生成完整音频
        merge_audio_chunks(task_id)
        
        print(f"音频已添加到存储，时长: {duration:.2f}秒")
        
        # 更新任务状态
        task.status = "completed"
        task.progress = 1.0
        try:
            task.duration = float(duration) if duration is not None else 0.0
        except (TypeError, ValueError) as e:
            print(f"转换音频时长时出错: {e}")
            task.duration = 0.0
        task.updated_at = datetime.now()
        
        print(f"任务完成: {task_id}, 时长: {duration:.2f}秒")
        
    except Exception as e:
        # 处理错误
        import traceback
        print(f"任务处理失败: {e}")
        traceback.print_exc()
        
        # 更新任务状态
        task.status = "failed"
        task.error = str(e)
        task.updated_at = datetime.now()
# 获取任务状态 - 修复版本
def get_task_status(task_id):
    """获取任务状态，增强版本处理中文字符和URL编码"""
    import urllib.parse
    
    # 1. 尝试URL解码
    try:
        decoded_task_id = urllib.parse.unquote(task_id)
    except:
        decoded_task_id = task_id
    
    print(f"正在查找任务状态: {decoded_task_id} (原始ID: {task_id})")
    
    # 2. 在活跃任务表中查找
    if decoded_task_id in ACTIVE_TASKS:
        print(f"在活跃任务表中找到任务: {decoded_task_id}")
        task = ACTIVE_TASKS[decoded_task_id]
        response = task.to_dict()
        
        # 如果任务已完成，增加音频URL
        if task.status == "completed":
            response["ready_to_play"] = True
            response["download_url"] = f"/api/tts/download/{urllib.parse.quote(decoded_task_id)}"
            response["audio_url"] = f"/api/tts/preview_audio/{urllib.parse.quote(decoded_task_id)}"
        
        return response
    
    # 3. 尝试按时间戳部分匹配
    timestamp_match = None
    parts = decoded_task_id.split('_')
    if len(parts) >= 3:
        timestamp = parts[2]
        
        for active_id in ACTIVE_TASKS:
            active_parts = active_id.split('_')
            if len(active_parts) >= 3 and active_parts[2] == timestamp:
                timestamp_match = active_id
                print(f"按时间戳匹配到任务: {active_id}")
                break
    
    if timestamp_match:
        task = ACTIVE_TASKS[timestamp_match]
        response = task.to_dict()
        
        # 如果任务已完成，增加音频URL
        if task.status == "completed":
            response["ready_to_play"] = True
            response["download_url"] = f"/api/tts/download/{urllib.parse.quote(timestamp_match)}"
            response["audio_url"] = f"/api/tts/preview_audio/{urllib.parse.quote(timestamp_match)}"
        
        response["task_id"] = decoded_task_id  # 保持返回的ID与请求一致
        return response
    
    # 4. 尝试部分匹配
    best_match = None
    for active_id in ACTIVE_TASKS:
        if decoded_task_id in active_id or active_id in decoded_task_id:
            best_match = active_id
            print(f"部分匹配到任务: {active_id}")
            break
    
    if best_match:
        task = ACTIVE_TASKS[best_match]
        response = task.to_dict()
        
        # 如果任务已完成，增加音频URL
        if task.status == "completed":
            response["ready_to_play"] = True
            response["download_url"] = f"/api/tts/download/{urllib.parse.quote(best_match)}"
            response["audio_url"] = f"/api/tts/preview_audio/{urllib.parse.quote(best_match)}"
        
        response["task_id"] = decoded_task_id  # 保持返回的ID与请求一致
        return response
    
    # 5. 现在查找最后一个创建的任务，如果任何任务在10秒内创建
    import time
    current_time = int(time.time())
    latest_task = None
    latest_time = 0
    
    for active_id, task in ACTIVE_TASKS.items():
        task_parts = active_id.split('_')
        if len(task_parts) >= 3:
            try:
                task_time = int(task_parts[2])
                if task_time > latest_time and current_time - task_time < 10:
                    latest_time = task_time
                    latest_task = active_id
            except:
                pass
    
    if latest_task:
        print(f"使用最新创建的任务: {latest_task}")
        task = ACTIVE_TASKS[latest_task]
        response = task.to_dict()
        
        # 如果任务已完成，增加音频URL
        if task.status == "completed":
            response["ready_to_play"] = True
            response["download_url"] = f"/api/tts/download/{urllib.parse.quote(latest_task)}"
            response["audio_url"] = f"/api/tts/preview_audio/{urllib.parse.quote(latest_task)}"
        
        response["task_id"] = decoded_task_id  # 保持返回的ID与请求一致
        return response
    
    # 找不到任务返回错误状态
    print(f"找不到任务: {decoded_task_id}")
    return {
        "task_id": decoded_task_id,
        "status": "failed",
        "error": "任务不存在或已过期"
    }

# 获取任务结果
def get_task_result(task_id):
    """获取任务结果"""
    if task_id in ACTIVE_TASKS:
        task = ACTIVE_TASKS[task_id]
        if task.status == "completed":
            return task
    
    return None

