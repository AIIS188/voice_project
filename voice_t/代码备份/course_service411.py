import os
from fastapi import FastAPI
import json
import asyncio
import time
import shutil
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import UploadFile, BackgroundTasks

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COSYVOICE_PATH = os.path.join(ROOT_DIR, "cosyvoice")
sys.path.append(ROOT_DIR)
sys.path.append('{}/third_party/Matcha-TTS'.format(ROOT_DIR))
from app.models.course import CoursewareDB, CoursewareTaskDB, CoursewareTextExtraction, CoursewareTaskStatus, \
    SlideContent
from app.services.cosyvoice_tts import synthesize_speech, get_tts_task_status, get_tts_task_result
from app.core.config import settings

# 导入PPT处理和讲案生成相关模块
from app.core.extractor_main import run_pipeline
from app.core.outppt import PPTExtractor
from app.core.ppt_lecture import LectureGenerator

# 模拟数据库存储
COURSEWARE_DB = []
COURSEWARE_TASKS_DB = []
COURSEWARE_FILE = os.path.join(settings.UPLOAD_DIR, "courseware.json")
COURSEWARE_TASKS_FILE = os.path.join(settings.UPLOAD_DIR, "courseware_tasks.json")


# 初始化函数
async def init_course_service():
    global COURSEWARE_DB, COURSEWARE_TASKS_DB
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "courseware"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "voiced_courseware"), exist_ok=True)

    if os.path.exists(COURSEWARE_FILE):
        try:
            with open(COURSEWARE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COURSEWARE_DB = [CoursewareDB(**item) for item in data]
        except Exception as e:
            print(f"初始化课件服务失败: {e}")

    if os.path.exists(COURSEWARE_TASKS_FILE):
        try:
            with open(COURSEWARE_TASKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COURSEWARE_TASKS_DB = [CoursewareTaskDB(**item) for item in data]
        except Exception as e:
            print(f"初始化课件任务服务失败: {e}")


# 保存到文件
async def save_courseware_db():
    with open(COURSEWARE_FILE, 'w', encoding='utf-8') as f:
        data = [item.dict() for item in COURSEWARE_DB]
        json.dump(data, f, default=str)


async def save_courseware_tasks_db():
    with open(COURSEWARE_TASKS_FILE, 'w', encoding='utf-8') as f:
        data = [item.dict() for item in COURSEWARE_TASKS_DB]
        json.dump(data, f, default=str)


# 上传课件
async def upload_courseware(file: UploadFile, name: str) -> str:
    # 生成唯一文件ID
    file_id = f"course_{int(time.time())}_{hash(file.filename) % 10000:04d}"

    # 创建存储目录
    courseware_dir = os.path.join(settings.UPLOAD_DIR, "courseware")
    os.makedirs(courseware_dir, exist_ok=True)

    # 保存文件
    file_path = os.path.join(courseware_dir, f"{file_id}_{file.filename}")

    # 获取文件大小
    file.file.seek(0, 2)  # 移到文件末尾
    file_size = file.file.tell()  # 获取位置（即文件大小）
    file.file.seek(0)  # 回到文件开始

    # 写入文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 创建记录
    courseware = CoursewareDB(
        file_id=file_id,
        name=name,
        original_filename=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        created_at=datetime.now()
    )

    # 添加到"数据库"
    COURSEWARE_DB.append(courseware)
    await save_courseware_db()

    return file_id


def extract_from_ppt(file_path):
    """
    从ppt提取内容、获得讲案。这个函数使用main.py中的run_pipeline来处理PPT文件。

    Args:
        file_path: PPT文件路径

    Returns:
        slides_count: 幻灯片数量
        slides: SlideContent对象列表
    """
    print(f"开始从PPT文件提取内容: {file_path}")

    # 创建临时输出目录
    temp_dir = os.path.join(os.path.dirname(file_path), "temp_extraction")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # 运行PPT处理流程，得到讲案文件路径和幻灯片数量
        lecture_path, slides_count = run_pipeline(
            pptx_file=file_path,
            output_dir=temp_dir,
            temp_format="json",
            lecture_mode="auto",
            output_format="json",
            save_intermediate=True
        )

        # 读取生成的讲案文件
        with open(lecture_path, 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)

        # 创建SlideContent对象列表
        slides = []

        # 处理讲案数据
        lecture_title = lecture_data.get("# 讲案标题", "")
        opening = lecture_data.get("## 开场白", "")

        # 获取所有幻灯片键
        slide_keys = [key for key in lecture_data.keys() if key.startswith("## 幻灯片")]
        slide_keys.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0)

        for key in slide_keys:
            try:
                # 提取幻灯片编号
                slide_id = int(re.search(r'(\d+)', key).group(1))
                slide_data = lecture_data[key]

                # 提取幻灯片内容
                if isinstance(slide_data, dict):
                    # 提取讲解内容
                    content = slide_data.get("讲解", "")

                    # 提取重点总结并格式化为笔记
                    notes = ""
                    key_points = slide_data.get("重点总结", [])
                    if key_points:
                        notes = "重点总结：\n" + "\n".join([f"- {point}" for point in key_points])

                    # 如果有互动环节，添加到笔记中
                    interactions = slide_data.get("互动环节", [])
                    if interactions:
                        if notes:
                            notes += "\n\n"
                        notes += "互动环节：\n" + "\n".join([f"- {item}" for item in interactions])

                    # 如果是最后一张幻灯片，添加结束语
                    if "结束语" in slide_data:
                        if notes:
                            notes += "\n\n"
                        notes += f"结束语：\n{slide_data['结束语']}"

                    # 尝试提取标题（使用内容的第一行或标题字段）
                    title = ""
                    if content:
                        lines = content.split('\n')
                        if lines:
                            title = lines[0].strip()
                            # 如果第一行很短，可能是标题
                            if len(title) < 50:
                                content = '\n'.join(lines[1:]).strip()

                    # 创建SlideContent对象
                    slide_content = SlideContent(
                        slide_id=slide_id,
                        title=title,
                        content=content,
                        notes=notes
                    )

                    slides.append(slide_content)
                else:
                    # 处理滑动数据是字符串的情况
                    print(f"警告: 幻灯片 {key} 数据格式不正确，跳过处理")

            except Exception as e:
                print(f"处理幻灯片 {key} 时出错: {e}")
                import traceback
                traceback.print_exc()

        # 按幻灯片编号排序
        slides.sort(key=lambda x: x.slide_id)

        # 如果是第一张幻灯片，添加开场白到内容中
        if slides and opening:
            first_slide = slides[0]
            first_slide.content = f"{opening}\n\n{first_slide.content}"

        # 如果没有幻灯片内容（可能是解析失败），创建一个默认的幻灯片
        if not slides:
            default_slide = SlideContent(
                slide_id=1,
                title=lecture_title if lecture_title else "课件内容",
                content="无法提取具体幻灯片内容，请查看原始PPT文件。",
                notes=""
            )
            slides.append(default_slide)

        return slides_count, slides

    except Exception as e:
        print(f"提取PPT内容时出错: {e}")
        import traceback
        traceback.print_exc()

        # 创建一个默认幻灯片
        default_slide = SlideContent(
            slide_id=1,
            title="处理错误",
            content=f"处理PPT文件时出错: {str(e)}",
            notes=""
        )

        return 1, [default_slide]


# 提取课件文本
async def extract_text(file_id: str) -> Optional[CoursewareTextExtraction]:
    # 查找课件
    courseware = None
    for cw in COURSEWARE_DB:
        if cw.file_id == file_id:
            courseware = cw
            break

    if not courseware:
        return None

    # 如果已经提取过文本，直接返回
    if courseware.slides_count > 0 and courseware.extracted_text:
        return CoursewareTextExtraction(
            file_id=courseware.file_id,
            name=courseware.name,
            slides_count=courseware.slides_count,
            extracted_text=courseware.extracted_text,
            total_text_length=sum(len(slide.content) for slide in courseware.extracted_text)
        )

    try:
        # 从PPT提取文本
        slides_count, extracted_text = extract_from_ppt(courseware.file_path)

        # 更新课件记录
        for i, cw in enumerate(COURSEWARE_DB):
            if cw.file_id == file_id:
                COURSEWARE_DB[i].slides_count = slides_count
                COURSEWARE_DB[i].extracted_text = extracted_text
                COURSEWARE_DB[i].updated_at = datetime.now()
                break

        await save_courseware_db()

        return CoursewareTextExtraction(
            file_id=courseware.file_id,
            name=courseware.name,
            slides_count=slides_count,
            extracted_text=extracted_text,
            total_text_length=sum(len(slide.content) for slide in extracted_text)
        )
    except Exception as e:
        print(f"提取文本失败: {e}")
        import traceback
        traceback.print_exc()
        return None


# 将文本分段，便于语音合成
def split_text_into_chunks(text, max_length=500):
    """将长文本分成适合TTS处理的小段"""
    # 按句子分割
    sentences = re.split(r'(?<=[。！？.!?])', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if not sentence.strip():
            continue

        # 如果当前块加上这个句子不超过最大长度，则添加到当前块
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += sentence
        else:
            # 如果当前块不为空，添加到结果中
            if current_chunk:
                chunks.append(current_chunk)
            # 开始新的块
            current_chunk = sentence

    # 添加最后一个块
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


# 生成有声课件
async def generate_voiced_courseware(
        background_tasks: BackgroundTasks,
        file_id: str,
        voice_id: str,
        speed: float = 1.0,
        emotion: str = "neutral",
        pitch: float = 0.0,
        energy: float = 1.0,
        pause_factor: float = 1.0
) -> str:
    # 查找课件
    courseware = None
    for cw in COURSEWARE_DB:
        if cw.file_id == file_id:
            courseware = cw
            break

    if not courseware:
        raise ValueError("课件未找到")

    # 提取文本（如果尚未提取）
    if courseware.slides_count == 0 or not courseware.extracted_text:
        extraction_result = await extract_text(file_id)
        if not extraction_result:
            raise ValueError("文本提取失败")

        # 重新获取更新后的课件
        for cw in COURSEWARE_DB:
            if cw.file_id == file_id:
                courseware = cw
                break

    # 创建任务
    task_id = f"course_task_{int(time.time())}_{file_id[-6:]}"

    # 构建TTS参数
    tts_params = {
        "speed": speed,
        "emotion": emotion,
        "pitch": pitch,
        "energy": energy,
        "pause_factor": pause_factor,
        "seed": int(time.time()) % 10000  # 随机种子
    }

    task = CoursewareTaskDB(
        task_id=task_id,
        file_id=file_id,
        name=courseware.name,
        voice_id=voice_id,
        params=tts_params,
        status="processing",
        progress=0.0,
        slides_processed=0,
        total_slides=courseware.slides_count,
        created_at=datetime.now()
    )

    # 添加到"数据库"
    COURSEWARE_TASKS_DB.append(task)
    await save_courseware_tasks_db()

    # 异步处理任务
    background_tasks.add_task(process_courseware_task, task_id)

    return task_id


# 处理课件任务
async def process_courseware_task(task_id: str):
    # 查找任务
    task = None
    for t in COURSEWARE_TASKS_DB:
        if t.task_id == task_id:
            task = t
            break

    if not task:
        print(f"任务未找到: {task_id}")
        return

    try:
        # 查找课件
        courseware = None
        for cw in COURSEWARE_DB:
            if cw.file_id == task.file_id:
                courseware = cw
                break

        if not courseware:
            raise ValueError(f"课件未找到: {task.file_id}")

        # 更新状态
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].status = "processing"
                COURSEWARE_TASKS_DB[i].progress = 0.1
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break

        await save_courseware_tasks_db()

        # 创建输出目录
        output_dir = os.path.join(settings.UPLOAD_DIR, "voiced_courseware")
        os.makedirs(output_dir, exist_ok=True)

        # 生成输出文件名
        file_ext = Path(courseware.original_filename).suffix.lower()
        output_filename = f"有声_{courseware.name}{file_ext}"
        output_path = os.path.join(output_dir, f"{task_id}_{output_filename}")

        # 更新任务输出文件名
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].output_filename = output_filename
                break

        await save_courseware_tasks_db()

        # 创建音频目录
        audio_dir = os.path.join(output_dir, f"{task_id}_audio")
        os.makedirs(audio_dir, exist_ok=True)

        # 处理每张幻灯片
        tts_tasks = []
        slides_total = len(courseware.extracted_text)

        for i, slide in enumerate(courseware.extracted_text):
            # 更新进度
            progress = 0.1 + (0.8 * ((i + 1) / slides_total))
            for j, t in enumerate(COURSEWARE_TASKS_DB):
                if t.task_id == task_id:
                    COURSEWARE_TASKS_DB[j].progress = progress
                    COURSEWARE_TASKS_DB[j].slides_processed = i + 1
                    COURSEWARE_TASKS_DB[j].updated_at = datetime.now()
                    break

            await save_courseware_tasks_db()

            # 准备幻灯片文本
            slide_text = ""
            if slide.title:
                slide_text += f"{slide.title}。\n"
            slide_text += slide.content

            if slide.notes:
                slide_text += f"\n\n讲解要点：{slide.notes}"

            # 将长文本分段
            text_chunks = split_text_into_chunks(slide_text)

            # 为每个文本块生成语音
            chunk_tasks = []
            for chunk_idx, chunk in enumerate(text_chunks):
                # 使用任务中设置的TTS参数
                tts_params = task.params

                # 提交TTS任务
                try:
                    # 使用临时的BackgroundTasks对象，因为我们需要等待TTS完成
                    temp_bg_tasks = BackgroundTasks()
                    tts_task_id = await synthesize_speech(
                        temp_bg_tasks,
                        chunk,
                        task.voice_id,
                        tts_params
                    )

                    # 手动启动TTS任务处理
                    await temp_bg_tasks()

                    # 等待TTS任务完成
                    await asyncio.sleep(1)  # 等待一会，让TTS任务启动

                    retry_count = 0
                    max_retries = 30  # 最多等待30次，每次0.5秒

                    while retry_count < max_retries:
                        tts_status = await get_tts_task_status(tts_task_id)
                        if tts_status and tts_status.status in ["completed", "failed"]:
                            break
                        await asyncio.sleep(0.5)
                        retry_count += 1

                    if retry_count >= max_retries:
                        print(f"TTS任务超时: {tts_task_id}")
                        continue

                    if tts_status and tts_status.status == "completed":
                        # 获取TTS结果
                        tts_result = await get_tts_task_result(tts_task_id)

                        if tts_result and tts_result.file_path:
                            # 复制TTS生成的音频文件到课件音频目录
                            chunk_audio_file = os.path.join(audio_dir, f"slide_{slide.slide_id}_chunk_{chunk_idx}.wav")

                            try:
                                tts_output_file = tts_result.file_path
                                if os.path.exists(tts_output_file):
                                    shutil.copy2(tts_output_file, chunk_audio_file)

                                    chunk_tasks.append({
                                        "chunk_id": chunk_idx,
                                        "audio_file": chunk_audio_file,
                                        "duration": tts_result.duration or 0  # 添加音频时长信息
                                    })
                                else:
                                    print(f"TTS输出文件不存在: {tts_output_file}")
                            except Exception as e:
                                print(f"复制音频文件失败: {e}")
                    else:
                        print(f"TTS任务失败 ({tts_status.status if tts_status else 'unknown'}): {tts_task_id}")
                except Exception as e:
                    print(f"处理文本块失败: {e}")
                    import traceback
                    traceback.print_exc()

            # 保存幻灯片任务信息
            tts_tasks.append({
                "slide_id": slide.slide_id,
                "title": slide.title,
                "chunks": chunk_tasks,
                "total_duration": sum(chunk.get("duration", 0) for chunk in chunk_tasks)  # 计算总时长
            })

        # 更新进度
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].progress = 0.9
                COURSEWARE_TASKS_DB[i].slides_processed = slides_total
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break

        await save_courseware_tasks_db()

        # 模拟创建有声课件（复制原始文件）
        # 注意：实际项目中会使用python-pptx等库修改PPT，嵌入音频
        try:
            if os.path.exists(courseware.file_path):
                shutil.copy2(courseware.file_path, output_path)
            else:
                print(f"原始课件文件不存在: {courseware.file_path}")
        except Exception as e:
            print(f"复制课件文件失败: {e}")
            import traceback
            traceback.print_exc()

        # 创建包含幻灯片和音频路径的清单文件
        manifest_path = os.path.join(output_dir, f"{task_id}_manifest.json")
        try:
            with open(manifest_path, "w", encoding='utf-8') as f:
                manifest = {
                    "task_id": task_id,
                    "courseware": {
                        "file_id": courseware.file_id,
                        "name": courseware.name,
                        "original_filename": courseware.original_filename
                    },
                    "output_file": output_path,
                    "total_duration": sum(slide.get("total_duration", 0) for slide in tts_tasks),  # 总时长
                    "slides": tts_tasks,
                    "tts_params": task.params
                }
                json.dump(manifest, f, default=str, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"创建清单文件失败: {e}")
            import traceback
            traceback.print_exc()

        # 更新任务完成状态
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].status = "completed"
                COURSEWARE_TASKS_DB[i].progress = 1.0
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                COURSEWARE_TASKS_DB[i].file_path = output_path
                COURSEWARE_TASKS_DB[i].manifest_path = manifest_path  # 添加清单文件路径
                COURSEWARE_TASKS_DB[i].total_duration = manifest["total_duration"]  # 添加总时长
                break

        await save_courseware_tasks_db()
        print(f"课件处理任务完成: {task_id}, 文件: {output_path}")

    except Exception as e:
        # 更新任务状态为失败
        for i, t in enumerate(COURSEWARE_TASKS_DB):
            if t.task_id == task_id:
                COURSEWARE_TASKS_DB[i].status = "failed"
                COURSEWARE_TASKS_DB[i].error = str(e)
                COURSEWARE_TASKS_DB[i].updated_at = datetime.now()
                break

        await save_courseware_tasks_db()
        print(f"课件处理任务失败: {task_id}, 错误: {e}")
        import traceback
        traceback.print_exc()


# 获取任务状态
async def get_task_status(task_id: str) -> Optional[CoursewareTaskStatus]:
    for task in COURSEWARE_TASKS_DB:
        if task.task_id == task_id:
            return CoursewareTaskStatus(
                task_id=task.task_id,
                name=task.name,
                status=task.status,
                progress=task.progress,
                created_at=task.created_at,
                updated_at=task.updated_at,
                slides_processed=task.slides_processed,
                total_slides=task.total_slides,
                output_filename=task.output_filename,
                total_duration=task.total_duration if hasattr(task, 'total_duration') else None,
                error=task.error
            )

    return None


# 获取任务结果
async def get_task_result(task_id: str) -> Optional[CoursewareTaskStatus]:
    status = await get_task_status(task_id)
    if status and status.status == "completed":
        # 找到对应任务获取文件路径
        for task in COURSEWARE_TASKS_DB:
            if task.task_id == task_id:
                if hasattr(task, 'file_path') and task.file_path and os.path.exists(task.file_path):
                    return status

    return None


# 列出所有课件
async def list_all_courseware() -> List[Dict[str, Any]]:
    """获取所有课件列表"""
    result = []
    for cw in COURSEWARE_DB:
        result.append({
            "file_id": cw.file_id,
            "name": cw.name,
            "original_filename": cw.original_filename,
            "content_type": cw.content_type,
            "file_size": cw.file_size,
            "slides_count": cw.slides_count,
            "created_at": cw.created_at,
            "updated_at": cw.updated_at
        })
    return result


# 列出所有生成任务
async def list_all_tasks() -> List[Dict[str, Any]]:
    """获取所有语音合成任务列表"""
    result = []
    for task in COURSEWARE_TASKS_DB:
        result.append({
            "task_id": task.task_id,
            "file_id": task.file_id,
            "name": task.name,
            "voice_id": task.voice_id,
            "status": task.status,
            "progress": task.progress,
            "slides_processed": task.slides_processed,
            "total_slides": task.total_slides,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "total_duration": task.total_duration if hasattr(task, 'total_duration') else None,
            "output_filename": task.output_filename if hasattr(task, 'output_filename') else None
        })
    return result


asyncio.create_task(init_course_service())
# 如果需要语音服务，添加这个导入
# 如果需要语音服务，添加这个导入
try:
    from app.services.cosyvoice_tts import init_cosyvoice_tts_service

    # 然后初始化语音合成服务
    TTS_INIT_TASK = asyncio.create_task(init_cosyvoice_tts_service())
except ImportError:
    print("CosyVoice TTS服务模块未找到或无法导入，跳过初始化")