# shared_storage.py

"""共享存储模块，用于在不同服务组件间共享数据"""
import time
from typing import Dict, List, Any, Optional
import numpy as np
import io
import soundfile as sf

# 任务ID映射表，用于处理复杂ID
TASK_ID_MAPPING = {}

# 最新音频存储 - 兼容旧版本
LATEST_AUDIO = {
    "data": None,
    "timestamp": None,
    "task_id": None,
    "duration": None,
    "sample_rate": None
}

# 按任务ID索引的音频存储
AUDIO_STORAGE = {}

# 内存音频存储（向后兼容）
IN_MEMORY_AUDIO = {}

def add_audio_chunk(task_id: str, audio_data, duration: float, sample_rate: int):
    """添加音频块到存储"""
    import soundfile as sf
    import io
    
    # 确保任务记录存在
    if task_id not in AUDIO_STORAGE:
        AUDIO_STORAGE[task_id] = {
            "chunks": [],
            "chunks_raw": [],  # 存储原始音频数据（非WAV格式）
            "complete_audio": None,
            "duration": 0.0,
            "timestamp": int(time.time()),
            "sample_rate": sample_rate
        }
    
    # 添加块
    # 确保音频数据是bytes类型
    if isinstance(audio_data, bytearray):
        audio_data = bytes(audio_data)
    
    AUDIO_STORAGE[task_id]["chunks"].append(audio_data)
    
    # 尝试解析WAV数据获取原始PCM数据
    try:
        with io.BytesIO(audio_data) as buffer:
            # 读取WAV文件内容（跳过头部）
            data, sr = sf.read(buffer)
            AUDIO_STORAGE[task_id]["chunks_raw"].append(data)
    except Exception as e:
        print(f"无法解析WAV数据：{e}")
    
    # 更新总时长
    AUDIO_STORAGE[task_id]["duration"] += duration
    
    # 更新时间戳
    AUDIO_STORAGE[task_id]["timestamp"] = int(time.time())
    
    # 同时更新最新音频（向后兼容）
    LATEST_AUDIO["data"] = audio_data
    LATEST_AUDIO["timestamp"] = int(time.time())
    LATEST_AUDIO["task_id"] = task_id
    LATEST_AUDIO["duration"] = duration
    LATEST_AUDIO["sample_rate"] = sample_rate
    
    print(f"已添加音频块到任务 {task_id}，当前块数: {len(AUDIO_STORAGE[task_id]['chunks'])}")
    
    # 如果块数超过1个，尝试合并
    if len(AUDIO_STORAGE[task_id]["chunks"]) > 1:
        merge_audio_chunks(task_id)

def merge_audio_chunks(task_id: str) -> Optional[bytes]:
    """合并指定任务的所有音频块"""
    import io
    import soundfile as sf
    import numpy as np
    
    if task_id not in AUDIO_STORAGE or not AUDIO_STORAGE[task_id]["chunks"]:
        print(f"没有可合并的音频块，任务: {task_id}")
        return None
    
    try:
        # 如果有原始数据，使用原始数据合并
        if AUDIO_STORAGE[task_id]["chunks_raw"] and len(AUDIO_STORAGE[task_id]["chunks_raw"]) > 0:
            print(f"使用原始PCM数据合并，块数: {len(AUDIO_STORAGE[task_id]['chunks_raw'])}")
            
            # 合并所有原始音频数据
            merged_data = np.concatenate(AUDIO_STORAGE[task_id]["chunks_raw"])
            
            # 获取采样率
            sample_rate = AUDIO_STORAGE[task_id]["sample_rate"]
            
            # 创建完整的WAV文件
            buffer = io.BytesIO()
            sf.write(buffer, merged_data, sample_rate, format='WAV')
            buffer.seek(0)
            complete_audio = buffer.read()
            
            # 确保结果是bytes类型
            if isinstance(complete_audio, bytearray):
                complete_audio = bytes(complete_audio)
            
            # 保存完整音频
            AUDIO_STORAGE[task_id]["complete_audio"] = complete_audio
            
            print(f"成功合并音频块，总时长: {AUDIO_STORAGE[task_id]['duration']:.2f}秒，总大小: {len(complete_audio)} 字节")
            return complete_audio
        
        # 回退选项：如果没有原始数据，尝试直接解析WAV文件
        print(f"没有原始PCM数据，尝试解析WAV文件进行合并，块数: {len(AUDIO_STORAGE[task_id]['chunks'])}")
        chunks_data = []
        sample_rate = AUDIO_STORAGE[task_id].get("sample_rate", 16000)
        
        for chunk in AUDIO_STORAGE[task_id]["chunks"]:
            # 从WAV文件内存读取数据，跳过头部
            with io.BytesIO(chunk) as buffer:
                data, sr = sf.read(buffer)
                chunks_data.append(data)
        
        # 合并所有块
        merged_data = np.concatenate(chunks_data)
        
        # 创建合并后的WAV文件
        buffer = io.BytesIO()
        sf.write(buffer, merged_data, sample_rate, format='WAV')
        buffer.seek(0)
        complete_audio = buffer.read()
        
        # 确保结果是bytes类型
        if isinstance(complete_audio, bytearray):
            complete_audio = bytes(complete_audio)
        
        # 更新完整音频
        AUDIO_STORAGE[task_id]["complete_audio"] = complete_audio
        
        print(f"成功合并音频块，总时长: {AUDIO_STORAGE[task_id]['duration']:.2f}秒，总大小: {len(complete_audio)} 字节")
        return complete_audio
    
    except Exception as e:
        print(f"合并音频块失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_audio_for_task(task_id: str) -> Dict[str, Any]:
    """获取任务的音频数据"""
    if task_id not in AUDIO_STORAGE:
        print(f"找不到任务ID: {task_id}")
        return None
    
    # 如果没有完整音频，尝试合并
    if not AUDIO_STORAGE[task_id].get("complete_audio") and AUDIO_STORAGE[task_id]["chunks"]:
        print(f"尝试合并任务 {task_id} 的音频块")
        merge_audio_chunks(task_id)
    
    return AUDIO_STORAGE[task_id]