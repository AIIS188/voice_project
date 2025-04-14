from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

class VoiceSampleBase(BaseModel):
    name: str
    description: Optional[str] = None
    tags: List[str] = []

class VoiceSampleCreate(VoiceSampleBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str
    original_filename: str
    file_size: int
    content_type: str
    created_at: datetime = Field(default_factory=datetime.now)
    embedding_path: Optional[str] = None
    model_path: Optional[str] = None
    quality_score: Optional[float] = None
    
class VoiceSampleDB(VoiceSampleCreate):
    status: str = "pending"  # pending, processing, ready, failed
    error: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)

class VoiceSampleResponse(VoiceSampleBase):
    id: str
    created_at: datetime
    status: str
    quality_score: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "name": "教师男声",
                "description": "清晰标准的教师男声",
                "tags": ["male", "teacher", "clear"],
                "created_at": "2023-03-01T12:00:00Z",
                "status": "ready",
                "quality_score": 0.92,
                "message": "声音样本处理完成"
            }
        }

class VoiceSampleList(BaseModel):
    total: int
    items: List[VoiceSampleResponse]