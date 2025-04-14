import os
import shutil
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings

async def save_upload_file(
    file: UploadFile,
    base_dir: str,
    sub_dir: str = None
) -> str:
    """保存上传的文件"""
    # 创建目录
    upload_dir = Path(base_dir)
    if sub_dir:
        upload_dir = upload_dir / sub_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件路径
    file_path = upload_dir / file.filename
    
    # 保存文件
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()
    
    return str(file_path)

def ensure_dir(directory: str) -> None:
    """确保目录存在"""
    Path(directory).mkdir(parents=True, exist_ok=True)

def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return os.path.splitext(filename)[1].lower()

def is_allowed_file(filename: str, allowed_extensions: list[str]) -> bool:
    """检查文件扩展名是否允许"""
    return get_file_extension(filename) in allowed_extensions

def get_file_size(file_path: str) -> int:
    """获取文件大小（字节）"""
    return os.path.getsize(file_path)

def delete_file(file_path: str) -> bool:
    """删除文件"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception:
        return False 