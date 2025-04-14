from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Query, Path
from fastapi.responses import FileResponse
from typing import List, Optional
import os
import uuid
from datetime import datetime


import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from app.core.config import settings
from app.services.voice_service import process_voice_sample, get_voice_samples, delete_voice_sample
from app.models.voice import VoiceSampleResponse, VoiceSampleCreate, VoiceSampleList

router = APIRouter()

@router.post("/upload", response_model=VoiceSampleResponse)
async def upload_voice_sample(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None)
):
    """
    上传声音样本文件
    """
    # 检查文件类型
    allowed_types = ["audio/wav", "audio/x-wav", "audio/mp3", "audio/mpeg", "audio/m4a"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="文件类型不支持，请上传WAV, MP3或M4A格式")
    
    # 检查文件大小
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB
    while chunk := await file.read(chunk_size):
        file_size += len(chunk)
        if file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail=f"文件过大，最大支持{settings.MAX_UPLOAD_SIZE/(1024*1024)}MB")
    
    # 重置文件指针
    await file.seek(0)
    
    # 生成唯一文件名
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(chunk_size):
            buffer.write(chunk)
    
    # 解析标签
    tag_list = tags.split(",") if tags else []
    
    # 创建样本记录
    sample_id = str(uuid.uuid4())
    sample = VoiceSampleCreate(
        id=sample_id,
        name=name,
        description=description or "",
        file_path=file_path,
        original_filename=file.filename,
        file_size=file_size,
        content_type=file.content_type,
        tags=tag_list,
        created_at=datetime.now()
    )
    
    # 异步处理声音样本
    background_tasks.add_task(process_voice_sample, sample)
    
    return VoiceSampleResponse(
        id=sample_id,
        name=name,
        description=sample.description,
        tags=tag_list,
        created_at=sample.created_at,
        status="processing",
        message="声音样本上传成功，正在处理"
    )

@router.get("/list", response_model=VoiceSampleList)
async def list_voice_samples(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    tags: Optional[str] = None
):
    """
    获取声音样本列表
    """
    tag_list = tags.split(",") if tags else None
    samples = await get_voice_samples(skip, limit, tag_list)
    return VoiceSampleList(
        total=len(samples),
        items=samples
    )

@router.get("/{sample_id}", response_model=VoiceSampleResponse)
async def get_voice_sample(
    sample_id: str = Path(..., title="声音样本ID")
):
    """
    获取声音样本详情
    """
    samples = await get_voice_samples(0, 1, None, sample_id)
    if not samples:
        raise HTTPException(status_code=404, detail="声音样本未找到")
    return samples[0]

@router.get("/{sample_id}/audio")
async def get_voice_audio(
    sample_id: str = Path(..., title="声音样本ID")
):
    """
    获取声音样本音频文件
    """
    samples = await get_voice_samples(0, 1, None, sample_id)
    if not samples:
        raise HTTPException(status_code=404, detail="声音样本未找到")
    
    return FileResponse(
        samples[0].file_path,
        media_type="audio/wav",
        filename=samples[0].original_filename
    )

@router.delete("/{sample_id}", response_model=VoiceSampleResponse)
async def remove_voice_sample(
    sample_id: str = Path(..., title="声音样本ID")
):
    """
    删除声音样本
    """
    result = await delete_voice_sample(sample_id)
    if not result:
        raise HTTPException(status_code=404, detail="声音样本未找到")
    return result