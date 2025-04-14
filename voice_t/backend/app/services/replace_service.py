import os
import json
import asyncio
import time
import shutil
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import UploadFile, BackgroundTasks
from app.models.replace import MediaFileDB, TranscriptionTaskDB, ReplaceTaskDB, Transcription, Segment, VoiceReplaceStatus, SubtitleResponse
from app.services.cosyvoice_tts import synthesize_speech, get_tts_task_status, get_tts_task_result
from app.core.config import settings

# 模拟数据库存储
MEDIA_FILES_DB = []
TRANSCRIPTION_TASKS_DB = []
REPLACE_TASKS_DB = []
MEDIA_FILES_FILE = os.path.join(settings.UPLOAD_DIR, "media_files.json")
TRANSCRIPTION_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "transcription_tasks.json")
REPLACE_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "replace_tasks.json")

# 初始化函数
async def init_replace_service():
    global MEDIA_FILES_DB, TRANSCRIPTION_TASKS_DB, REPLACE_TASKS_DB
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "media"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "transcriptions"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "replaced_media"), exist_ok=True)
    
    if os.path.exists(MEDIA_FILES_FILE):
        try:
            with open(MEDIA_FILES_FILE, 'r') as f:
                data = json.load(f)
                MEDIA_FILES_DB = [MediaFileDB(**item) for item in data]
        except Exception as e:
            print(f"初始化媒体文件服务失败: {e}")
    
    if os.path.exists(TRANSCRIPTION_TASKS_FILE):
        try:
            with open(TRANSCRIPTION_TASKS_FILE, 'r') as f:
                data = json.load(f)
                TRANSCRIPTION_TASKS_DB = [TranscriptionTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化转写任务服务失败: {e}")
    
    if os.path.exists(REPLACE_TASKS_FILE):
        try:
            with open(REPLACE_TASKS_FILE, 'r') as f:
                data = json.load(f)
                REPLACE_TASKS_DB = [ReplaceTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化替换任务服务失败: {e}")

# 保存到文件
async def save_media_files_db():
    with open(MEDIA_FILES_FILE, 'w') as f:
        data = [item.dict() for item in MEDIA_FILES_DB]
        json.dump(data, f, default=str)

async def save_transcription_tasks_db():
    with open(TRANSCRIPTION_TASKS_FILE, 'w') as f:
        data = [item.dict() for item in TRANSCRIPTION_TASKS_DB]
        json.dump(data, f, default=str)

async def save_replace_tasks_db():
    with open(REPLACE_TASKS_FILE, 'w') as f:
        data = [item.dict() for item in REPLACE_TASKS_DB]
        json.dump(data, f, default=str)

# 上传媒体文件
async def upload_media(file: UploadFile, name: str) -> str:
    # 生成唯一文件ID
    file_id = f"media_{int(time.time())}_{hash(file.filename) % 10000:04d}"
    
    # 创建存储目录
    media_dir = os.path.join(settings.UPLOAD_DIR, "media")
    os.makedirs(media_dir, exist_ok=True)
    
    # 保存文件
    file_path = os.path.join(media_dir, f"{file_id}_{file.filename}")
    
    # 获取文件大小
    file.file.seek(0, 2)  # 移到文件末尾
    file_size = file.file.tell()  # 获取位置（即文件大小）
    file.file.seek(0)  # 回到文件开始
    
    # 写入文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 判断是否为视频文件
    is_video = file.content_type.startswith("video/")
    
    # 创建记录
    media_file = MediaFileDB(
        file_id=file_id,
        name=name,
        original_filename=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        is_video=is_video,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    MEDIA_FILES_DB.append(media_file)
    await save_media_files_db()
    
    return file_id

# 语音活动检测 (VAD)
def detect_speech_segments(y, sr, threshold=0.01, min_duration=0.5, max_duration=10.0):
    """
    检测音频中的语音片段
    返回语音片段的开始和结束时间列表
    """
    # 计算短时帧能量
    frame_length = int(0.025 * sr)  # 25ms帧
    hop_length = int(0.010 * sr)    # 10ms跳步
    
    # 计算RMS能量
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    
    # 计算时间点
    times = librosa.times_like(rms, sr=sr, hop_length=hop_length)
    
    # 使用自适应阈值
    adaptive_threshold = threshold * np.mean(rms)
    
    # 寻找语音片段
    segments = []
    in_speech = False
    speech_start = 0
    
    for i, energy in enumerate(rms):
        current_time = times[i]
        
        if not in_speech and energy > adaptive_threshold:
            # 开始新的语音片段
            in_speech = True
            speech_start = current_time
        elif in_speech and (energy <= adaptive_threshold or current_time - speech_start >= max_duration):
            # 结束当前语音片段
            if current_time - speech_start >= min_duration:
                segments.append((speech_start, current_time))
            in_speech = False
    
    # 处理最后一个片段
    if in_speech and times[-1] - speech_start >= min_duration:
        segments.append((speech_start, times[-1]))
    
    return segments

# 生成更现实的转写文本
def generate_realistic_transcription(name, duration, segments):
    """
    基于音频信息生成更现实的转写文本
    """
    # 一些常见的话题和句子模板
    topics = [
        "教育", "技术", "科学", "艺术", "健康", "环境", "社会", "历史"
    ]
    
    sentence_templates = [
        "在{topic}领域中，我们需要注重{aspect}和{aspect2}。",
        "{topic}的发展趋势表明，{aspect}将变得越来越重要。",
        "今天我想和大家分享关于{topic}的几点看法。",
        "通过研究{topic}，我们可以发现{aspect}与{aspect2}之间的关系。",
        "从{topic}的角度来看，{aspect}是一个关键因素。",
        "最近在{topic}领域有了新的突破，特别是在{aspect}方面。",
        "让我们来讨论一下{topic}中的{aspect}问题。",
        "关于{topic}，有三点需要强调，首先是{aspect}，其次是{aspect2}。",
        "{topic}的核心在于理解{aspect}如何影响我们的日常生活。",
        "在探讨{topic}时，我们不能忽视{aspect}的重要性。"
    ]
    
    aspects = {
        "教育": ["学习方法", "教学质量", "创新思维", "个性化教育", "学生参与", "终身学习", "批判性思考"],
        "技术": ["人工智能", "大数据", "云计算", "区块链", "物联网", "虚拟现实", "增强现实"],
        "科学": ["实验方法", "理论框架", "数据分析", "科研伦理", "跨学科合作", "科学普及"],
        "艺术": ["创作过程", "美学价值", "文化影响", "艺术教育", "传统与创新", "表达方式"],
        "健康": ["预防保健", "生活方式", "心理健康", "医疗技术", "营养饮食", "体育锻炼"],
        "环境": ["可持续发展", "气候变化", "资源保护", "生态平衡", "环境政策", "绿色技术"],
        "社会": ["文化多样性", "社会公平", "经济发展", "政策制定", "公民参与", "社区建设"],
        "历史": ["历史事件", "文化传承", "社会变迁", "历史人物", "考古发现", "历史研究方法"]
    }
    
    # 基于名称选择主题
    # 提取名称中的关键词，简单匹配主题
    selected_topic = None
    for topic in topics:
        if topic in name:
            selected_topic = topic
            break
    
    if not selected_topic:
        # 如果没有匹配到，随机选择一个主题
        import random
        selected_topic = random.choice(topics)
    
    # 为每个语音片段生成一段转写文本
    transcription_segments = []
    
    for i, (start, end) in enumerate(segments):
        # 选择句子模板
        import random
        template = random.choice(sentence_templates)
        
        # 选择方面
        topic_aspects = aspects.get(selected_topic, aspects["教育"])
        aspect1 = random.choice(topic_aspects)
        aspect2 = random.choice([a for a in topic_aspects if a != aspect1])
        
        # 生成文本
        text = template.format(
            topic=selected_topic,
            aspect=aspect1,
            aspect2=aspect2
        )
        
        # 添加到转写片段
        transcription_segments.append(Segment(
            start=start,
            end=end,
            text=text
        ))
    
    return Transcription(
        segments=transcription_segments,
        language="zh-CN",
        total_duration=duration
    )

# 转写媒体文件
async def transcribe_media(background_tasks: BackgroundTasks, file_id: str) -> str:
    # 查找媒体文件
    media_file = None
    for mf in MEDIA_FILES_DB:
        if mf.file_id == file_id:
            media_file = mf
            break
    
    if not media_file:
        raise ValueError("媒体文件未找到")
    
    # 创建转写任务
    task_id = f"transcribe_{int(time.time())}_{file_id[-6:]}"
    task = TranscriptionTaskDB(
        task_id=task_id,
        file_id=file_id,
        name=media_file.name,
        status="processing",
        progress=0.0,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    TRANSCRIPTION_TASKS_DB.append(task)
    await save_transcription_tasks_db()
    
    # 异步处理任务
    background_tasks.add_task(process_transcription_task, task_id)
    
    return task_id

# 处理转写任务
async def process_transcription_task(task_id: str):
    # 查找任务
    task = None
    for t in TRANSCRIPTION_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break
    
    if not task:
        print(f"任务未找到: {task_id}")
        return
    
    try:
        # 查找媒体文件
        media_file = None
        for mf in MEDIA_FILES_DB:
            if mf.file_id == task.file_id:
                media_file = mf
                break
        
        if not media_file:
            raise ValueError(f"媒体文件未找到: {task.file_id}")
        
        # 更新状态
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].status = "processing"
                TRANSCRIPTION_TASKS_DB[i].progress = 0.1
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "transcriptions")
        os.makedirs(output_dir, exist_ok=True)
        
        # 模拟转写过程 - 加载音频文件
        try:
            # 读取音频文件
            y, sr = librosa.load(media_file.file_path, sr=None)
            duration = librosa.get_duration(y=y, sr=sr)
        except Exception as e:
            # 如果无法读取音频，使用估计的持续时间
            print(f"无法加载音频，使用估计时长: {e}")
            duration = media_file.file_size / (500 * 1024)  # 估计时长
            
            # 生成随机片段
            import random
            num_segments = max(3, int(duration / 10))
            segments = []
            
            for i in range(num_segments):
                start = i * (duration / num_segments)
                end = (i + 1) * (duration / num_segments) - 0.2  # 留出一点间隔
                segments.append((start, end))
        else:
            # 成功加载了音频，使用VAD检测语音片段
            segments = detect_speech_segments(y, sr)
            
            if not segments:
                # 如果没有检测到片段，创建一些模拟片段
                num_segments = max(3, int(duration / 10))
                segments = []
                
                for i in range(num_segments):
                    start = i * (duration / num_segments)
                    end = (i + 1) * (duration / num_segments) - 0.2  # 留出一点间隔
                    segments.append((start, end))
        
        # 更新媒体文件的时长
        for i, mf in enumerate(MEDIA_FILES_DB):
            if mf.file_id == media_file.file_id:
                MEDIA_FILES_DB[i].duration = duration
                MEDIA_FILES_DB[i].updated_at = datetime.now()
                break
        
        await save_media_files_db()
        
        # 更新进度
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].progress = 0.3
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        
        # 模拟处理时间
        await asyncio.sleep(2.0)
        
        # 生成转写
        transcription = generate_realistic_transcription(media_file.name, duration, segments)
        
        # 更新进度
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].progress = 0.7
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        
        # 生成SRT字幕文件
        srt_path = os.path.join(output_dir, f"{task_id}.srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(transcription.segments):
                f.write(f"{i+1}\n")
                
                # 格式化时间码 (HH:MM:SS,mmm)
                start_h = int(segment.start / 3600)
                start_m = int((segment.start % 3600) / 60)
                start_s = int(segment.start % 60)
                start_ms = int((segment.start % 1) * 1000)
                
                end_h = int(segment.end / 3600)
                end_m = int((segment.end % 3600) / 60)
                end_s = int(segment.end % 60)
                end_ms = int((segment.end % 1) * 1000)
                
                time_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms:03d} --> "
                time_str += f"{end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms:03d}"
                
                f.write(f"{time_str}\n")
                f.write(f"{segment.text}\n\n")
        
        # 生成VTT字幕文件
        vtt_path = os.path.join(output_dir, f"{task_id}.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            
            for i, segment in enumerate(transcription.segments):
                # 格式化时间码 (HH:MM:SS.mmm)
                start_h = int(segment.start / 3600)
                start_m = int((segment.start % 3600) / 60)
                start_s = int(segment.start % 60)
                start_ms = int((segment.start % 1) * 1000)
                
                end_h = int(segment.end / 3600)
                end_m = int((segment.end % 3600) / 60)
                end_s = int(segment.end % 60)
                end_ms = int((segment.end % 1) * 1000)
                
                time_str = f"{start_h:02d}:{start_m:02d}:{start_s:02d}.{start_ms:03d} --> "
                time_str += f"{end_h:02d}:{end_m:02d}:{end_s:02d}.{end_ms:03d}"
                
                f.write(f"{time_str}\n")
                f.write(f"{segment.text}\n\n")
        
        # 模拟处理时间
        await asyncio.sleep(1.0)
        
        # 更新任务状态
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].status = "completed"
                TRANSCRIPTION_TASKS_DB[i].progress = 1.0
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                TRANSCRIPTION_TASKS_DB[i].transcription = transcription
                TRANSCRIPTION_TASKS_DB[i].subtitles_path = {
                    "srt": srt_path,
                    "vtt": vtt_path
                }
                break
        
        await save_transcription_tasks_db()
        print(f"转写任务完成: {task_id}")
        
    except Exception as e:
        # 更新任务状态为失败
        for i, t in enumerate(TRANSCRIPTION_TASKS_DB):
            if t.task_id == task_id:
                TRANSCRIPTION_TASKS_DB[i].status = "failed"
                TRANSCRIPTION_TASKS_DB[i].error = str(e)
                TRANSCRIPTION_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_transcription_tasks_db()
        print(f"转写任务失败: {task_id}, 错误: {e}")

# 替换声音
async def replace_voice(
    background_tasks: BackgroundTasks,
    transcription_task_id: str,
    voice_id: str,
    speed: float = 1.0
) -> str:
    # 查找转写任务
    transcription_task = None
    for tt in TRANSCRIPTION_TASKS_DB:
        if tt.task_id == transcription_task_id:
            transcription_task = tt
            break
    
    if not transcription_task:
        raise ValueError("转写任务未找到")
    
    if transcription_task.status != "completed":
        raise ValueError(f"转写任务状态 {transcription_task.status} 不是 completed")
    
    # 创建替换任务
    task_id = f"replace_{int(time.time())}_{transcription_task_id[-6:]}"
    task = ReplaceTaskDB(
        task_id=task_id,
        transcription_task_id=transcription_task_id,
        name=transcription_task.name,
        voice_id=voice_id,
        params={"speed": speed},
        status="processing",
        progress=0.0,
        created_at=datetime.now()
    )
    
    # 添加到"数据库"
    REPLACE_TASKS_DB.append(task)
    await save_replace_tasks_db()
    
    # 异步处理任务
    background_tasks.add_task(process_replace_task, task_id)
    
    return task_id

# 处理替换任务
async def process_replace_task(task_id: str):
    # 查找任务
    task = None
    for t in REPLACE_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break
    
    if not task:
        print(f"任务未找到: {task_id}")
        return
    
    try:
        # 查找转写任务
        transcription_task = None
        for tt in TRANSCRIPTION_TASKS_DB:
            if tt.task_id == task.transcription_task_id:
                transcription_task = tt
                break
        
        if not transcription_task:
            raise ValueError(f"转写任务未找到: {task.transcription_task_id}")
        
        # 查找媒体文件
        media_file = None
        for mf in MEDIA_FILES_DB:
            if mf.file_id == transcription_task.file_id:
                media_file = mf
                break
        
        if not media_file:
            raise ValueError(f"媒体文件未找到: {transcription_task.file_id}")
        
        # 更新状态
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].status = "processing"
                REPLACE_TASKS_DB[i].progress = 0.1
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        
        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "replaced_media")
        os.makedirs(output_dir, exist_ok=True)
        audio_dir = os.path.join(output_dir, f"{task_id}_audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        # 生成输出文件名
        file_ext = Path(media_file.original_filename).suffix.lower()
        output_filename = f"替换后_{media_file.name}{file_ext}"
        output_path = os.path.join(output_dir, f"{task_id}_{output_filename}")
        
        # 更新任务输出文件名
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].output_filename = output_filename
                break
        
        await save_replace_tasks_db()
        
        # 获取转写结果
        transcription = transcription_task.transcription
        if not transcription or not transcription.segments:
            raise ValueError("转写结果为空")
        
        # TTS参数
        tts_params = {
            "speed": task.params.get("speed", 1.0),
            "pitch": 0,
            "energy": 1.0,
            "emotion": "neutral",
            "pause_factor": 1.0
        }
        
        # 为每个转写片段生成语音
        tts_results = []
        total_segments = len(transcription.segments)
        
        for i, segment in enumerate(transcription.segments):
            # 更新进度
            progress = 0.1 + 0.7 * ((i + 1) / total_segments)
            for j, t in enumerate(REPLACE_TASKS_DB):
                if t.task_id == task_id:
                    REPLACE_TASKS_DB[j].progress = progress
                    REPLACE_TASKS_DB[j].updated_at = datetime.now()
                    break
            
            await save_replace_tasks_db()
            
            # 提交TTS任务
            try:
                # 使用临时的BackgroundTasks对象，因为我们需要等待TTS完成
                temp_bg_tasks = BackgroundTasks()
                tts_task_id = await synthesize_speech(
                    temp_bg_tasks, 
                    segment.text, 
                    task.voice_id, 
                    tts_params
                )
                
                # 手动启动TTS任务处理
                await temp_bg_tasks()
                
                # 等待TTS任务完成
                await asyncio.sleep(0.5)  # 等待一会，让TTS任务启动
                
                while True:
                    tts_status = await get_tts_task_status(tts_task_id)
                    if tts_status and tts_status.status in ["completed", "failed"]:
                        break
                    await asyncio.sleep(0.5)
                
                if tts_status and tts_status.status == "completed":
                    # 获取TTS结果
                    tts_result = await get_tts_task_result(tts_task_id)
                    
                    if tts_result:
                        # 复制TTS生成的音频文件到输出目录
                        segment_audio_file = os.path.join(audio_dir, f"segment_{i}.wav")
                        
                        tts_output_file = tts_result.file_path
                        shutil.copy2(tts_output_file, segment_audio_file)
                        
                        tts_results.append({
                            "segment_id": i,
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "audio_file": segment_audio_file,
                            "duration": tts_result.duration
                        })
                else:
                    print(f"TTS任务失败: {tts_task_id}")
                    raise ValueError(f"生成片段 {i} 的语音失败")
            except Exception as e:
                print(f"处理片段失败: {e}")
                raise ValueError(f"处理片段 {i} 失败: {e}")
        
        # 更新进度
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].progress = 0.8
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        
        # 生成音频替换记录
        replacement_info = {
            "task_id": task_id,
            "original_file": {
                "file_id": media_file.file_id,
                "name": media_file.name,
                "duration": transcription.total_duration
            },
            "voice_id": task.voice_id,
            "segments": tts_results,
            "output_file": output_path
        }
        
        # 保存替换信息
        replacement_info_path = os.path.join(output_dir, f"{task_id}_info.json")
        with open(replacement_info_path, "w") as f:
            json.dump(replacement_info, f, default=str)
        
        # 创建替换后的媒体文件
        if media_file.is_video:
            # 对于视频文件，我们需要替换音频轨道
            # 这里简单模拟，复制原始文件
            shutil.copy2(media_file.file_path, output_path)
        else:
            # 对于音频文件，我们可以生成一个新的音频文件，连接所有TTS生成的片段
            # 在实际项目中，我们会使用FFmpeg或类似工具
            
            # 读取所有音频片段
            try:
                # 创建一个空列表存储所有音频片段
                combined_audio = []
                sample_rate = None
                
                # 按时间顺序排序片段
                sorted_results = sorted(tts_results, key=lambda x: x["start"])
                
                # 读取并连接所有音频片段
                for result in sorted_results:
                    audio_file = result["audio_file"]
                    if os.path.exists(audio_file):
                        y, sr = librosa.load(audio_file, sr=None)
                        if sample_rate is None:
                            sample_rate = sr
                        elif sr != sample_rate:
                            # 如果采样率不一致，重新采样
                            y = librosa.resample(y, orig_sr=sr, target_sr=sample_rate)
                        
                        # 添加到合并列表
                        combined_audio.append(y)
                    else:
                        print(f"音频文件不存在: {audio_file}")
                
                if combined_audio and sample_rate:
                    # 连接所有音频片段
                    final_audio = np.concatenate(combined_audio)
                    
                    # 保存为输出文件
                    sf.write(output_path, final_audio, sample_rate)
                else:
                    # 如果没有成功生成音频，复制原始文件
                    shutil.copy2(media_file.file_path, output_path)
            except Exception as e:
                print(f"合并音频失败: {e}")
                # 出错时复制原始文件
                shutil.copy2(media_file.file_path, output_path)
        
        # 更新任务完成状态
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].status = "completed"
                REPLACE_TASKS_DB[i].progress = 1.0
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                REPLACE_TASKS_DB[i].file_path = output_path
                break
        
        await save_replace_tasks_db()
        print(f"替换任务完成: {task_id}, 文件: {output_path}")
        
    except Exception as e:
        # 更新任务状态为失败
        for i, t in enumerate(REPLACE_TASKS_DB):
            if t.task_id == task_id:
                REPLACE_TASKS_DB[i].status = "failed"
                REPLACE_TASKS_DB[i].error = str(e)
                REPLACE_TASKS_DB[i].updated_at = datetime.now()
                break
        
        await save_replace_tasks_db()
        print(f"替换任务失败: {task_id}, 错误: {e}")

# 获取任务状态
async def get_task_status(task_id: str) -> Optional[VoiceReplaceStatus]:
    # 尝试查找转写任务
    for task in TRANSCRIPTION_TASKS_DB:
        if task.task_id == task_id:
            # 查找对应的媒体文件获取时长
            original_duration = None
            for mf in MEDIA_FILES_DB:
                if mf.file_id == task.file_id:
                    original_duration = mf.duration
                    break
            
            return VoiceReplaceStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                task_type="transcribe",
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                original_duration=original_duration,
                error=task.error
            )
    
    # 尝试查找替换任务
    for task in REPLACE_TASKS_DB:
        if task.task_id == task_id:
            return VoiceReplaceStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                task_type="replace",
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                output_filename=task.output_filename,
                error=task.error
            )
    
    return None

# 获取字幕
async def get_subtitles(task_id: str, format: str = "srt") -> Optional[SubtitleResponse]:
    # 查找转写任务
    for task in TRANSCRIPTION_TASKS_DB:
        if task.task_id == task_id and task.status == "completed" and task.subtitles_path:
            if format in task.subtitles_path and os.path.exists(task.subtitles_path[format]):
                with open(task.subtitles_path[format], "r", encoding="utf-8") as f:
                    content = f.read()
                
                return SubtitleResponse(
                    task_id=task.task_id,
                    content=content,
                    format=format,
                    language=task.transcription.language if task.transcription else "zh-CN",
                    segments_count=len(task.transcription.segments) if task.transcription else 0
                )
    
    return None

# 获取任务结果
async def get_task_result(task_id: str) -> Optional[VoiceReplaceStatus]:
    status = await get_task_status(task_id)
    if status and status.status == "completed" and status.task_type == "replace":
        # 找到对应任务获取文件路径
        for task in REPLACE_TASKS_DB:
            if task.task_id == task_id:
                if os.path.exists(task.file_path):
                    return status
    
    return None

# 初始化服务
asyncio.create_task(init_replace_service())