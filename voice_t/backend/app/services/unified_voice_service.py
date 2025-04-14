"""Unified Voice Service

This module provides a unified interface for managing both pre-trained and user-uploaded voices.
"""
import os
import sys
import json
import uuid
import time
import shutil
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Import existing services
from app.services.cosyvoice_tts import get_cosyvoice_model, synthesize_speech

# Import configuration
from app.core.config import settings

# Voice storage paths
VOICE_DB_PATH = os.path.join(settings.UPLOAD_DIR, "voice_library.json")
PREVIEW_DIR = os.path.join(settings.UPLOAD_DIR, "voice_previews")
USER_VOICES_DIR = os.path.join(settings.UPLOAD_DIR, "user_voices")

# Ensure directories exist
os.makedirs(PREVIEW_DIR, exist_ok=True)
os.makedirs(USER_VOICES_DIR, exist_ok=True)

# Global voice database
VOICE_DB = []


def get_voice_by_id(voice_id: str) -> Optional[Dict[str, Any]]:
    """
    通过ID获取语音，并改进不同ID格式的处理
    """
    # 检查是否提供了语音ID
    if not voice_id:
        print("警告：未提供语音ID")
        return None
    
    # 始终对语音ID进行URL解码以保持一致性
    try:
        decoded_voice_id = urllib.parse.unquote(voice_id)
    except Exception as e:
        print(f"解码语音ID '{voice_id}' 时发生错误: {e}")
        decoded_voice_id = voice_id  # 如果解码失败，使用原始ID
    
    print(f"正在查找语音ID：{decoded_voice_id} (原始ID: {voice_id})")
    
    # 尝试1：精确匹配ID
    exact_match = next((v for v in VOICE_DB if v["id"] == decoded_voice_id), None)
    if exact_match:
        print(f"找到精确匹配的ID：{decoded_voice_id}")
        return exact_match
    
    # 尝试2：检查是否存在双重编码的URL字符
    try:
        if '%' in decoded_voice_id:
            double_decoded = urllib.parse.unquote(decoded_voice_id)
            if double_decoded != decoded_voice_id:
                print(f"尝试使用双重解码的ID：{double_decoded}")
                double_match = next((v for v in VOICE_DB if v["id"] == double_decoded), None)
                if double_match:
                    print(f"找到双重解码ID的匹配：{double_decoded}")
                    return double_match
    except Exception:
        pass  # 忽略双重解码中的错误
    
    # 尝试3：模糊匹配 - ID包含在语音ID或名称中
    for v in VOICE_DB:
        db_id = v["id"]
        db_name = v.get("name", "")
        
        if (decoded_voice_id in db_id or 
            db_id in decoded_voice_id or 
            decoded_voice_id in db_name or 
            db_name in decoded_voice_id):
            print(f"找到模糊匹配 - 数据库ID：{db_id}，数据库名称：{db_name}")
            return v
    
    # 尝试4：对于中文语音，尝试按名称匹配
    for v in VOICE_DB:
        # 检查名称是否包含中文字符
        if any('\u4e00' <= char <= '\u9fff' for char in v.get("name", "")):
            if any('\u4e00' <= char <= '\u9fff' for char in decoded_voice_id):
                print(f"潜在的中文语音匹配：{v['name']} 查询：{decoded_voice_id}")
                return v
    
    # 如果到达这里，未找到匹配
    print(f"未找到匹配的语音ID：{decoded_voice_id}")
    
    # 如果有可用语音，返回第一个作为备用
    # if VOICE_DB:
    #     print(f"使用第一个可用语音作为备用：{VOICE_DB[0]['id']}")
    #     return VOICE_DB[0]
    
    return None


def get_voice_preview_path(voice_id: str) -> Optional[str]:
    """
    Get the preview file path for a voice with improved handling
    """
    try:
        # Always URL decode for consistency
        decoded_voice_id = urllib.parse.unquote(voice_id)
        
        print(f"Looking for preview file - Voice ID: {decoded_voice_id}")
        
        # Try 1: Standard preview filename format
        standard_filename = f"{decoded_voice_id}_preview.wav"
        standard_path = os.path.join(PREVIEW_DIR, standard_filename)
        
        if os.path.exists(standard_path):
            print(f"Found standard preview file: {standard_path}")
            return standard_path
        
        # Try 2: Get the voice info and check if it has a preview_url
        voice = get_voice_by_id(decoded_voice_id)
        if voice and voice.get("preview_url"):
            # Extract filename from preview_url
            preview_url = voice["preview_url"]
            filename = os.path.basename(preview_url)
            if filename:
                preview_path = os.path.join(PREVIEW_DIR, filename)
                if os.path.exists(preview_path):
                    print(f"Found preview file from voice preview_url: {preview_path}")
                    return preview_path
        
        # Try 3: Look for any file containing the voice ID
        try:
            files = os.listdir(PREVIEW_DIR)
            
            # First check for exact filename match
            if f"{decoded_voice_id}.wav" in files:
                path = os.path.join(PREVIEW_DIR, f"{decoded_voice_id}.wav")
                print(f"Found exact filename match: {path}")
                return path
            
            # Then check for partial matches
            for file in files:
                if decoded_voice_id in file:
                    path = os.path.join(PREVIEW_DIR, file)
                    print(f"Found partial match file: {path}")
                    return path
        except Exception as e:
            print(f"Error listing preview directory: {e}")
        
        # No preview file found
        print(f"No preview file found for voice ID: {decoded_voice_id}")
        return None
        
    except Exception as e:
        print(f"Error getting preview path: {e}")
        import traceback
        traceback.print_exc()
        return None

def load_voice_db():
    """Load the voice database from disk"""
    global VOICE_DB
    if os.path.exists(VOICE_DB_PATH):
        try:
            with open(VOICE_DB_PATH, 'r', encoding='utf-8') as f:
                VOICE_DB = json.load(f)
            print(f"Loaded {len(VOICE_DB)} voices from database")
        except Exception as e:
            print(f"Error loading voice database: {e}")
            VOICE_DB = []
    
    # If empty, initialize with pretrained voices
    if not VOICE_DB:
        print("Voice database is empty, initializing with pretrained voices")
        initialize_pretrained_voices()

def save_voice_db():
    """Save the voice database to disk"""
    try:
        with open(VOICE_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(VOICE_DB, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(VOICE_DB)} voices to database")
    except Exception as e:
        print(f"Error saving voice database: {e}")

def initialize_pretrained_voices():
    """Initialize the voice database with pretrained voices"""
    global VOICE_DB
    
    # Get CosyVoice model
    cosyvoice_model = get_cosyvoice_model()
    if not cosyvoice_model or not hasattr(cosyvoice_model, 'available_spks'):
        print("CosyVoice model not available, cannot initialize pretrained voices")
        return
    
    # Get available pretrained voices
    pretrained_spks = cosyvoice_model.available_spks
    print(f"Found {len(pretrained_spks)} pretrained voices")
    
    # Create voice entries
    for i, spk_id in enumerate(pretrained_spks):
        display_name = f"预训练音色 {i+1}"
        if spk_id == "":
            display_name = "默认音色"
        elif "中文女" in spk_id or "女声" in spk_id:
            display_name = "中文女声"
        elif "中文男" in spk_id or "男声" in spk_id:
            display_name = "中文男声"
        
        # Create a voice entry
        voice = {
            "id": spk_id if spk_id else f"pretrained_default",
            "name": display_name,
            "type": "pretrained",
            "description": f"CosyVoice预训练音色: {spk_id}",
            "tags": ["预训练", "cosyvoice"],
            "created_at": datetime.now().isoformat(),
            "status": "ready",
            "quality_score": 0.95,
            "preview_url": f"/api/voice/preview/{urllib.parse.quote(spk_id if spk_id else 'pretrained_default')}"
        }
        
        VOICE_DB.append(voice)
        print(f"Added pretrained voice: {voice['id']} ({voice['name']})")
    
    # Save the database
    save_voice_db()

async def add_user_voice(
    name: str,
    description: str,
    tags: List[str],
    audio_file_path: str,
    reference_text: str
) -> Optional[Dict[str, Any]]:
    """
    Add a user-uploaded voice to the database
    
    This function creates a new user voice entry with:
    - A unique ID in the format "user_[uuid]_[timestamp]"
    - Reference audio path pointing to user_voices/[voice_id]/reference.wav
    - Stores the reference text for zero-shot synthesis
    """
    """Add a user-uploaded voice to the database"""
    try:
        print(f"Adding user voice - Name: {name}, Audio path: {audio_file_path}")
        
        # Validate parameters
        if not name or not name.strip():
            print("Error: Voice name cannot be empty")
            return None
            
        if not audio_file_path or not os.path.exists(audio_file_path):
            print(f"Error: Audio file does not exist - {audio_file_path}")
            return None
            
        if not reference_text or not reference_text.strip():
            print("Error: Reference text cannot be empty")
            return None
        
        # Check if the file is a valid audio file (simplified check)
        file_size = os.path.getsize(audio_file_path)
        if file_size < 1024:  # Less than 1KB
            print(f"Warning: File is very small ({file_size} bytes)")
        
        # Generate unique ID
        voice_id = f"user_{uuid.uuid4().hex[:8]}_{int(time.time())}"
        
        # Create voice directory
        voice_dir = os.path.join(USER_VOICES_DIR, voice_id)
        os.makedirs(voice_dir, exist_ok=True)
        
        # Copy audio file to voice directory
        dest_path = os.path.join(voice_dir, "reference.wav")
        
        print(f"Copying audio file from {audio_file_path} to {dest_path}")
        shutil.copy(audio_file_path, dest_path)
        
        if not os.path.exists(dest_path):
            print(f"Error: Failed to copy audio file, destination does not exist: {dest_path}")
            return None
            
        print(f"Successfully copied audio file, size: {os.path.getsize(dest_path)} bytes")
        
        # Create voice entry
        voice = {
            "id": voice_id,
            "name": name,
            "type": "user-uploaded",
            "description": description,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "status": "ready",
            "quality_score": 0.9,
            "preview_url": f"/api/voice/preview/{urllib.parse.quote(voice_id)}",
            "reference_audio": dest_path,
            "reference_text": reference_text
        }
        
        # Add to database
        global VOICE_DB
        VOICE_DB.append(voice)
        save_voice_db()
        
        # Use reference audio as preview
        preview_path = os.path.join(PREVIEW_DIR, f"{voice_id}_preview.wav")
        
        print(f"Creating preview file: {preview_path}")
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        shutil.copy(dest_path, preview_path)
        
        if not os.path.exists(preview_path):
            print(f"Warning: Failed to create preview file, but voice was added")
        
        print(f"Successfully added voice: {voice_id}")
        return voice
    except Exception as e:
        print(f"Exception adding user voice: {e}")
        import traceback
        traceback.print_exc()
        return None

async def delete_voice(voice_id: str) -> bool:
    """Delete a voice from the database"""
    global VOICE_DB
    
    # URL decode the voice_id
    decoded_voice_id = urllib.parse.unquote(voice_id)
    
    # Find the voice
    voice = next((v for v in VOICE_DB if v["id"] == decoded_voice_id), None)
    if not voice:
        print(f"Voice not found for deletion: {decoded_voice_id}")
        return False
    
    # Cannot delete pretrained voices
    if voice["type"] == "pretrained":
        print(f"Cannot delete pretrained voice: {decoded_voice_id}")
        return False
    
    # Remove from database
    VOICE_DB = [v for v in VOICE_DB if v["id"] != decoded_voice_id]
    save_voice_db()
    
    # Delete files
    if voice["type"] == "user-uploaded":
        voice_dir = os.path.join(USER_VOICES_DIR, decoded_voice_id)
        if os.path.exists(voice_dir):
            shutil.rmtree(voice_dir)
            print(f"Deleted voice directory: {voice_dir}")
        
        # Delete preview
        preview_path = os.path.join(PREVIEW_DIR, f"{decoded_voice_id}_preview.wav")
        if os.path.exists(preview_path):
            os.remove(preview_path)
            print(f"Deleted preview file: {preview_path}")
    
    print(f"Successfully deleted voice: {decoded_voice_id}")
    return True

def get_all_voices() -> List[Dict[str, Any]]:
    """Get all voices from the database"""
    return VOICE_DB

# Initialize on module load
load_voice_db()