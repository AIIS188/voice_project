from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class ActivityRecord(BaseModel):
    """记录单个活动的模型"""
    type: str
    timestamp: str
    quality_score: Optional[float] = None
    duration: Optional[float] = None
    processing_time: Optional[float] = None
    slides_count: Optional[int] = None

class AppMetrics(BaseModel):
    """应用指标模型"""
    voice_samples_count: int
    tts_tasks_count: int
    courseware_tasks_count: int
    replace_tasks_count: int
    total_processed_audio: str
    average_processing_time: str
    average_quality_score: str
    recent_activity: List[ActivityRecord]
    
    class Config:
        schema_extra = {
            "example": {
                "voice_samples_count": 5,
                "tts_tasks_count": 12,
                "courseware_tasks_count": 3,
                "replace_tasks_count": 2,
                "total_processed_audio": "324.50 seconds",
                "average_processing_time": "2.35 seconds",
                "average_quality_score": "0.85",
                "recent_activity": [
                    {
                        "type": "voice_sample",
                        "timestamp": "2023-03-01T14:30:25",
                        "quality_score": 0.92
                    },
                    {
                        "type": "tts",
                        "timestamp": "2023-03-01T14:45:10",
                        "duration": 42.3,
                        "processing_time": 3.2
                    }
                ]
            }
        }