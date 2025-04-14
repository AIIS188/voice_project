import os
import json
import asyncio
import librosa
import numpy as np
import soundfile as sf
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.services.voice_clone import voice_cloner
from app.models.voice import VoiceSampleCreate, VoiceSampleDB, VoiceSampleResponse
from app.core.config import settings
from app.utils.audio import get_audio_duration, normalize_audio, trim_audio

# 模拟数据库存储
VOICE_SAMPLES_DB = []
VOICE_SAMPLES_FILE = os.path.join(settings.UPLOAD_DIR, "voice_samples.json")

# 初始化函数，读取已有的样本记录
async def init_voice_service():
    global VOICE_SAMPLES_DB
    # 确保目录存在
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "voice_embeddings"), exist_ok=True)
    
    if os.path.exists(VOICE_SAMPLES_FILE):
        try:
            with open(VOICE_SAMPLES_FILE, 'r') as f:
                data = json.load(f)
                VOICE_SAMPLES_DB = [VoiceSampleDB(**item) for item in data]
        except Exception as e:
            print(f"初始化声音样本服务失败: {e}")

# 保存样本记录到文件
async def save_voice_samples():
    with open(VOICE_SAMPLES_FILE, 'w') as f:
        # 转换为字典列表并保存
        data = [sample.dict() for sample in VOICE_SAMPLES_DB]
        json.dump(data, f, default=str)

# 高级声音分析
def analyze_voice_sample(y, sr):
    """
    分析声音样本并提取有意义的特征
    """
    # 基本特征
    duration = librosa.get_duration(y=y, sr=sr)
    
    # 能量和音量
    rms = librosa.feature.rms(y=y)[0]
    energy_mean = np.mean(rms)
    energy_std = np.std(rms)
    
    # 音高分析
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    pitch_values = pitches[magnitudes > 0.1]
    if len(pitch_values) > 0:
        pitch_mean = np.mean(pitch_values)
        pitch_std = np.std(pitch_values)
    else:
        pitch_mean = 0
        pitch_std = 0
    
    # 频谱特征
    spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)[0])
    spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)[0])
    
    # 声音质量指标
    # 1. 信噪比（简化版）
    noise_floor = np.percentile(rms, 10)
    if noise_floor > 0:
        snr = 10 * np.log10(energy_mean / noise_floor)
    else:
        snr = 20  # 默认值
    
    # 2. 清晰度得分基于频谱对比度
    spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)[0])
    clarity = min(1.0, max(0, spectral_contrast / 30))
    
    # 3. 稳定性得分基于音高变化
    if pitch_mean > 0 and pitch_std > 0:
        stability = max(0, min(1.0, 1.0 - (pitch_std / pitch_mean / 0.5)))
    else:
        stability = 0.5
    
    # 4. 发音清晰度
    zero_crossings = np.mean(librosa.feature.zero_crossing_rate(y=y)[0])
    articulation = min(1.0, zero_crossings * 10)
    
    # 计算总体质量得分
    # 权重各个分数
    quality_score = (
        0.25 * min(1.0, snr / 25) +   # SNR部分（最高25dB）
        0.25 * clarity +               # 清晰度部分
        0.20 * stability +             # 稳定性部分
        0.15 * articulation +          # 发音清晰度
        0.15 * min(1.0, max(0, (duration - 5) / 25) if duration >= 5 else 0)  # 时长部分
    )
    
    # 限制分数在0.95以内，留出改进空间
    quality_score = min(0.95, quality_score)
    
    # 创建声音特征指纹（简化版）
    # 使用MFCC特征作为声音的指纹
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = np.mean(mfccs, axis=1)
    
    return {
        "duration": float(duration),
        "energy_mean": float(energy_mean),
        "energy_std": float(energy_std),
        "pitch_mean": float(pitch_mean),
        "pitch_std": float(pitch_std),
        "spectral_centroid": float(spectral_centroid),
        "spectral_bandwidth": float(spectral_bandwidth),
        "snr": float(snr),
        "clarity": float(clarity),
        "stability": float(stability),
        "articulation": float(articulation),
        "quality_score": float(quality_score),
        "mfcc_fingerprint": mfcc_mean.tolist()
    }

# 保存声音分析结果和特征
def save_voice_features(features, sample_id):
    """保存声音特征和指纹"""
    features_dir = os.path.join(settings.UPLOAD_DIR, "voice_embeddings")
    os.makedirs(features_dir, exist_ok=True)
    
    # 保存特征和指纹到文件
    features_path = os.path.join(features_dir, f"{sample_id}_features.json")
    with open(features_path, 'w') as f:
        json.dump(features, f)
    
    return features_path

# 处理声音样本
async def process_voice_sample(sample: VoiceSampleCreate):
    # 创建数据库记录
    db_sample = VoiceSampleDB(**sample.dict(), status="processing")
    
    # 添加到"数据库"
    for i, s in enumerate(VOICE_SAMPLES_DB):
        if s.id == sample.id:
            VOICE_SAMPLES_DB[i] = db_sample
            break
    else:
        VOICE_SAMPLES_DB.append(db_sample)
    
    # 更新状态
    await save_voice_samples()
    
    try:
        # 模拟处理音频文件
        print(f"处理音频文件: {sample.file_path}")
        # 在现有特征提取后，添加声音克隆特征提取
        voice_cloner.process_voice_sample(sample.file_path, sample.id)
        # 1. 加载音频
        try:
            y, sr = librosa.load(sample.file_path, sr=22050)
        except Exception as e:
            raise ValueError(f"无法加载音频文件: {str(e)}")
        
        # 2. 检查音频长度是否在5-30秒之间
        duration = librosa.get_duration(y=y, sr=sr)
        if duration < 5:
            raise ValueError(f"音频长度为 {duration:.2f} 秒，太短了。需要至少5秒。")
        elif duration > 30:
            raise ValueError(f"音频长度为 {duration:.2f} 秒，太长了。需要不超过30秒。")
        
        # 3. 预处理音频
        # 归一化
        y = normalize_audio(y)
        # 去除静音
        y = trim_audio(y)[0]
        
        # 4. 分析音频特征
        features = analyze_voice_sample(y, sr)
        
        # 5. 保存特征和指纹
        embedding_path = save_voice_features(features, sample.id)
        
        # 6. 创建优化后的音频示例（用于快速预览）
        model_dir = os.path.join(settings.UPLOAD_DIR, "voice_models")
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, f"{sample.id}.wav")
        
        # 保存处理后的音频
        sf.write(model_path, y, sr)
        
        # 更新样本记录
        for i, s in enumerate(VOICE_SAMPLES_DB):
            if s.id == sample.id:
                VOICE_SAMPLES_DB[i].status = "ready"
                VOICE_SAMPLES_DB[i].quality_score = features["quality_score"]
                VOICE_SAMPLES_DB[i].embedding_path = embedding_path
                VOICE_SAMPLES_DB[i].model_path = model_path
                VOICE_SAMPLES_DB[i].updated_at = datetime.now()
                break
                
        # 保存更新
        await save_voice_samples()
        print(f"声音样本 {sample.id} 处理完成，质量评分: {features['quality_score']:.2f}")
        
    except Exception as e:
        # 处理失败，更新状态
        for i, s in enumerate(VOICE_SAMPLES_DB):
            if s.id == sample.id:
                VOICE_SAMPLES_DB[i].status = "failed"
                VOICE_SAMPLES_DB[i].error = str(e)
                VOICE_SAMPLES_DB[i].updated_at = datetime.now()
                break
        
        await save_voice_samples()
        print(f"处理声音样本 {sample.id} 失败: {e}")

# 获取声音样本列表
async def get_voice_samples(
    skip: int = 0,
    limit: int = 10,
    tags: Optional[List[str]] = None,
    sample_id: Optional[str] = None
) -> List[VoiceSampleResponse]:
    # 过滤样本
    filtered_samples = VOICE_SAMPLES_DB
    
    # 按ID过滤
    if sample_id:
        filtered_samples = [s for s in filtered_samples if s.id == sample_id]
    
    # 按标签过滤
    if tags:
        filtered_samples = [
            s for s in filtered_samples 
            if any(tag in s.tags for tag in tags)
        ]
    
    # 分页
    paginated = filtered_samples[skip:skip+limit]
    
    # 转换为响应模型
    result = []
    for sample in paginated:
        message = None
        if sample.status == "ready":
            message = "声音样本处理完成"
        elif sample.status == "processing":
            message = "声音样本正在处理中"
        elif sample.status == "failed":
            message = "声音样本处理失败"
        
        result.append(VoiceSampleResponse(
            id=sample.id,
            name=sample.name,
            description=sample.description,
            tags=sample.tags,
            created_at=sample.created_at,
            status=sample.status,
            quality_score=sample.quality_score,
            message=message,
            error=sample.error
        ))
    
    return result

# 删除声音样本
async def delete_voice_sample(sample_id: str) -> Optional[VoiceSampleResponse]:
    global VOICE_SAMPLES_DB
    
    # 查找样本
    for i, sample in enumerate(VOICE_SAMPLES_DB):
        if sample.id == sample_id:
            # 删除物理文件
            try:
                if os.path.exists(sample.file_path):
                    os.remove(sample.file_path)
                
                # 删除相关文件
                if sample.embedding_path and os.path.exists(sample.embedding_path):
                    os.remove(sample.embedding_path)
                
                if sample.model_path and os.path.exists(sample.model_path):
                    os.remove(sample.model_path)
                
                # 从"数据库"中删除
                deleted = VOICE_SAMPLES_DB.pop(i)
                await save_voice_samples()
                
                # 返回删除的样本信息
                return VoiceSampleResponse(
                    id=deleted.id,
                    name=deleted.name,
                    description=deleted.description,
                    tags=deleted.tags,
                    created_at=deleted.created_at,
                    status="deleted",
                    quality_score=deleted.quality_score,
                    message="声音样本已删除"
                )
            except Exception as e:
                print(f"删除声音样本 {sample_id} 失败: {e}")
                return None
    
    return None

# 声音相似度比较（简化版）
async def compare_voice_samples(sample_id1: str, sample_id2: str) -> float:
    """比较两个声音样本的相似度"""
    # 获取两个样本
    sample1 = None
    sample2 = None
    
    for s in VOICE_SAMPLES_DB:
        if s.id == sample_id1:
            sample1 = s
        elif s.id == sample_id2:
            sample2 = s
    
    if not sample1 or not sample2:
        raise ValueError("声音样本不存在")
    
    # 检查是否有嵌入向量
    if not sample1.embedding_path or not sample2.embedding_path:
        raise ValueError("声音样本尚未处理完成")
    
    # 加载嵌入向量
    with open(sample1.embedding_path, 'r') as f:
        features1 = json.load(f)
    
    with open(sample2.embedding_path, 'r') as f:
        features2 = json.load(f)
    
    # 获取MFCC指纹
    mfcc1 = np.array(features1.get("mfcc_fingerprint", []))
    mfcc2 = np.array(features2.get("mfcc_fingerprint", []))
    
    if len(mfcc1) == 0 or len(mfcc2) == 0:
        raise ValueError("声音样本没有有效的特征")
    
    # 计算余弦相似度
    dot_product = np.dot(mfcc1, mfcc2)
    norm1 = np.linalg.norm(mfcc1)
    norm2 = np.linalg.norm(mfcc2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    # 转换到0-1范围
    similarity = (similarity + 1) / 2
    
    return similarity

# 初始化服务
asyncio.create_task(init_voice_service())