from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Path, Query
from fastapi.responses import FileResponse
from typing import List, Optional

import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from app.models.course import CoursewareUploadResponse, CoursewareTaskStatus, CoursewareTextExtraction
from app.services.course_service import upload_courseware, extract_text, generate_voiced_courseware, get_task_status, get_task_result, get_all_courseware, get_all_tasks

router = APIRouter()

@router.get("/list")
async def list_courseware():
    """
    获取所有课件文件列表
    """
    courseware_list = await get_all_courseware()
    return courseware_list

@router.get("/tasks")
async def list_tasks():
    """
    获取所有课件处理任务列表
    """
    tasks_list = await get_all_tasks()
    return tasks_list

@router.post("/upload", response_model=CoursewareUploadResponse)
async def upload_courseware_file(
    file: UploadFile = File(...),
    name: str = Form(...)
):
    """
    上传课件文件（PPT等）
    """
    # 检查文件类型
    allowed_types = [
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/pdf"
    ]

    content_type = file.content_type
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="文件类型不支持，请上传PPT、PPTX或PDF文件")

    # 上传课件
    file_id = await upload_courseware(file, name)

    return CoursewareUploadResponse(
        file_id=file_id,
        name=name,
        status="uploaded",
        message="课件上传成功"
    )

@router.get("/extract/{file_id}", response_model=CoursewareTextExtraction)
async def extract_courseware_text(
    file_id: str = Path(..., title="课件文件ID")
):
    """
    提取课件文本内容
    """
    result = await extract_text(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="课件文件未找到")

    return result

@router.post("/synthesize/{file_id}", response_model=CoursewareUploadResponse)
async def create_voiced_courseware(
    background_tasks: BackgroundTasks,
    file_id: str = Path(..., title="课件文件ID"),
    voice_id: str = Form(..., title="声音样本ID"),
    speed: float = Form(1.0, ge=0.5, le=2.0, title="语速")
):
    """
    生成有声课件
    """
    task_id = await generate_voiced_courseware(background_tasks, file_id, voice_id, speed)

    return CoursewareUploadResponse(
        file_id=task_id,
        name="",  # 将在处理过程中更新
        status="processing",
        message="有声课件生成任务已提交"
    )

@router.get("/status/{task_id}", response_model=CoursewareTaskStatus)
async def check_courseware_task_status(
    task_id: str = Path(..., title="任务ID")
):
    """
    查询课件处理任务状态
    """
    status = await get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="任务未找到")

    return status

@router.get("/download/{task_id}")
async def download_courseware_result(
    task_id: str = Path(..., title="任务ID")
):
    """
    下载处理后的课件
    """
    result = await get_task_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务未找到或尚未完成")

    if result.status != "completed":
        raise HTTPException(status_code=400, detail=f"任务状态为 {result.status}，无法下载")

    return FileResponse(
        result.file_path,
        media_type="application/octet-stream",
        filename=result.output_filename
    )