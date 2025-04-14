from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VoiceSample(Base):
    __tablename__ = "voice_samples"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    file_path = Column(String)
    duration = Column(Integer)  # 音频时长（秒）
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Courseware(Base):
    __tablename__ = "coursewares"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class VoiceReplacement(Base):
    __tablename__ = "voice_replacements"

    id = Column(Integer, primary_key=True, index=True)
    original_voice_id = Column(Integer, ForeignKey("voice_samples.id"))
    target_voice_id = Column(Integer, ForeignKey("voice_samples.id"))
    courseware_id = Column(Integer, ForeignKey("coursewares.id"))
    status = Column(String)  # 处理状态
    result_path = Column(String)  # 处理结果文件路径
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    original_voice = relationship("VoiceSample", foreign_keys=[original_voice_id])
    target_voice = relationship("VoiceSample", foreign_keys=[target_voice_id])
    courseware = relationship("Courseware") 