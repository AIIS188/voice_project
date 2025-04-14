from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class SlideContent(BaseModel):
    slide_id: int
    title: Optional[str] = None
    content: str
    notes: Optional[str] = None

class CoursewareTextExtraction(BaseModel):
    file_id: str
    name: str
    slides_count: int
    extracted_text: List[SlideContent]
    total_text_length: int

    class Config:
        schema_extra = {
            "example": {
                "file_id": "course_12345",
                "name": "示例课件.pptx",
                "slides_count": 3,
                "extracted_text": [
                    {"slide_id": 1, "title": "课程介绍", "content": "这是第一页的内容", "notes": "讲师备注"},
                    {"slide_id": 2, "title": "第一章", "content": "这是第二页的内容", "notes": None},
                    {"slide_id": 3, "title": "总结", "content": "这是第三页的内容", "notes": "总结要点"}
                ],
                "total_text_length": 150
            }
        }

class CoursewareUploadResponse(BaseModel):
    file_id: str
    name: str
    status: str  # uploaded, processing, completed, failed
    message: Optional[str] = None
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "file_id": "course_12345",
                "name": "示例课件.pptx",
                "status": "uploaded",
                "message": "课件上传成功"
            }
        }

class CoursewareTaskStatus(BaseModel):
    task_id: str
    name: str
    status: str  # processing, completed, failed
    progress: float = Field(0.0, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None  # 添加完成时间字段
    slides_processed: int = 0
    total_slides: int = 0
    output_filename: Optional[str] = None
    file_path: Optional[str] = None  # 添加文件路径字段
    manifest_path: Optional[str] = None  # 添加清单文件路径字段
    total_duration: Optional[float] = None  # 添加总时长字段
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None  # 添加详细错误信息字段
    stop_polling: bool = False  # 添加停止轮询标志

    class Config:
        schema_extra = {
            "example": {
                "task_id": "course_task_12345",
                "name": "示例课件.pptx",
                "status": "processing",
                "progress": 0.5,
                "created_at": "2023-03-01T12:00:00Z",
                "updated_at": "2023-03-01T12:01:30Z",
                "slides_processed": 5,
                "total_slides": 10,
                "output_filename": "有声示例课件.pptx"
            }
        }

class CoursewareDB(BaseModel):
    file_id: str = Field(default_factory=lambda: f"course_{uuid.uuid4().hex[:12]}")
    name: str
    original_filename: str
    file_path: str
    content_type: str
    file_size: int
    slides_count: int = 0
    extracted_text: List[SlideContent] = []
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

class CoursewareTaskDB(BaseModel):
    task_id: str = Field(default_factory=lambda: f"course_task_{uuid.uuid4().hex[:12]}")
    file_id: str
    name: str
    voice_id: str
    params: Dict[str, Any]
    status: str = "processing"  # processing, completed, failed
    progress: float = 0.0
    slides_processed: int = 0
    total_slides: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None  # 添加完成时间字段
    file_path: Optional[str] = None
    manifest_path: Optional[str] = None
    output_filename: Optional[str] = None
    total_duration: Optional[float] = None  # 添加总时长字段
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None