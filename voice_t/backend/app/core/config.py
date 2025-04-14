import os
from typing import List, Dict, Any,ClassVar
from pydantic_settings import BaseSettings
from pydantic import Field
import os
from pathlib import Path



class Settings(BaseSettings):
    # API配置
    API_V1_STR: str = "/v1"
    PROJECT_NAME: str = "声教助手"

    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["*"]  # 允许所有来源访问

    # 数据库配置
    MONGODB_URL: str = Field(default="mongodb://localhost:27017")
    DATABASE_NAME: str = Field(default="voice_assistant")

    # 安全配置
    SECRET_KEY: str = Field(default="your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天

    # 文件存储配置

    # 获取项目根目录
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent.parent

    # 精确定位上传目录
    UPLOAD_DIR : str = os.path.join(BASE_DIR, "uploads")
    MAX_UPLOAD_SIZE: int = 20 * 1024 * 1024  # 20MB


    # TTS模型配置
    TTS_MODELS_DIR: str = ""
    TTS_VOICE_ENCODER_PATH: str = ""
    TTS_METRICS_MODEL_PATH: str = ""
    TTS_DEFAULT_PARAMS: Dict[str, Any] = {
        "speed": 1.0,
        "pitch": 0.0,
        "energy": 1.0,
        "emotion": "neutral",
        "pause_factor": 1.0,
        "language": "zh-CN"
    }

    # CosyVoice配置
    MODELS_DIR: str = os.path.join(BASE_DIR, "pretrained_models/CosyVoice-300M-SFT")
    COSYVOICE_ENABLED: bool = Field(default=True)
    THIRD_PARTY_DIR: str = ""

    # 算法配置
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"

    def __init__(self, **data):
        super().__init__(**data)
        # 设置派生字段
        self.TTS_MODELS_DIR = self.MODELS_DIR
        self.THIRD_PARTY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "third_party")

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.THIRD_PARTY_DIR, exist_ok=True)