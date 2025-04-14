from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

class Segment(BaseModel):
    start: float  # 开始时间（秒）
    end: float    # 结束时间（秒）
    text: str     # 文本内容

class Transcription(BaseModel):
    segments: List[Segment]
    language: str
    total_duration: float

class VoiceReplaceResponse(BaseModel):
    file_id: str
    name: str
    status: str  # uploaded, processing, completed, failed
    message: Optional[str] = None
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "file_id": "replace_12345",
                "name": "示例视频.mp4",
                "status": "uploaded",
                "message": "媒体文件上传成功"
            }
        }

class SubtitleResponse(BaseModel):
    task_id: str
    content: str
    format: str  # srt, vtt
    language: str
    segments_count: int

class VoiceReplaceStatus(BaseModel):
    task_id: str
    name: str
    status: str  # processing, completed, failed
    task_type: str  # transcribe, replace
    progress: float = Field(0.0, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    original_duration: Optional[float] = None
    output_filename: Optional[str] = None
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "task_id": "replace_task_12345",
                "name": "示例视频.mp4",
                "status": "processing",
                "task_type": "replace",
                "progress": 0.5,
                "created_at": "2023-03-01T12:00:00Z",
                "updated_at": "2023-03-01T12:01:30Z",
                "original_duration": 120.5,
                "output_filename": "替换后_示例视频.mp4"
            }
        }

class MediaFileDB(BaseModel):
    file_id: str = Field(default_factory=lambda: f"media_{uuid.uuid4().hex[:12]}")
    name: str
    original_filename: str
    file_path: str
    content_type: str
    file_size: int
    duration: Optional[float] = None
    is_video: bool
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

class TranscriptionTaskDB(BaseModel):
    task_id: str = Field(default_factory=lambda: f"transcribe_{uuid.uuid4().hex[:12]}")
    file_id: str
    name: str
    status: str = "processing"  # processing, completed, failed
    progress: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    transcription: Optional[Transcription] = None
    subtitles_path: Optional[Dict[str, str]] = None  # 格式 -> 路径
    error: Optional[str] = None

class ReplaceTaskDB(BaseModel):
    task_id: str = Field(default_factory=lambda: f"replace_{uuid.uuid4().hex[:12]}")
    transcription_task_id: str
    name: str
    voice_id: str
    params: Dict[str, Any]
    status: str = "processing"  # processing, completed, failed
    progress: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    file_path: Optional[str] = None
    output_filename: Optional[str] = None
    error: Optional[str] = None