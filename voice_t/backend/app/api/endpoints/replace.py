from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, FileResponse
import uuid
import os
import sys
from pathlib import Path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from app.core.config import settings

# Import the video_changer function from changer module
from app.services.changer import video_changer

router = APIRouter()

# Storage directories
UPLOAD_DIR = r'C:\Users\mingyue\Desktop\voice_t0号机\backend\uploads\media'
PROCESSED_DIR = r'C:\Users\mingyue\Desktop\voice_t0号机\backend\uploads\replaced_media'
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
if not os.path.exists(PROCESSED_DIR):
    os.makedirs(PROCESSED_DIR)


@router.get("/list", response_model=None)
async def list_voice_samples(
    skip: int = 0,
    limit: int = 10,
    tags: str = None
):
    """
    Get the list of voice samples
    """
    # Forward call to existing voice API
    # This will be handled by the existing API in the frontend
    pass


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a media file for processing
    """
    try:
        # Save the uploaded file
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{file_id}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        return JSONResponse(content={
            "file_id": file_id,
            "file_path": file_path,
            "original_name": file.filename
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/process")
async def process_video(file: str, voice_id: str = Form(...)):
    """
    Process video with the selected voice
    """
    try:
        # Find the file path from file ID
        file_id = file
        files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(file_id)]
        
        if not files:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        file_path = os.path.join(UPLOAD_DIR, files[0])
        
        # Pass the voice_id to video_changer function
        processed_file_path = video_changer(file_path, voice_id=voice_id)
        
        # Get the filename from the returned path
        processed_filename = os.path.basename(processed_file_path)
        
        # Construct access URL for the processed video
        processed_video_url = f"/api/replace/download/{processed_filename}"
        
        return JSONResponse(content={
            "processed_video_url": processed_video_url,
            "file_name": processed_filename
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"视频处理失败: {str(e)}")


@router.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download a processed file
    """
    # Use the same output directory as defined in changer.py
    file_path = Path(os.path.join(ROOT_DIR, 'app', 'services', 'output_video')) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="video/mp4"
    )


@router.get("/status/{file_id}")
async def check_processing_status(file_id: str):
    """
    Check the status of video processing
    """
    try:
        # 修改1：使用正确的输出目录路径
        output_dir = Path(os.path.join(ROOT_DIR, 'app', 'services', 'output_video'))
        matching_files = list(output_dir.glob(f"*{file_id}*"))
        
        if matching_files:
            return JSONResponse(content={
                "status": "completed",
                "progress": 100,
                "processed_video_url": f"/api/replace/download/{matching_files[0].name}"
            })
        else:
            # 修改2：添加更准确的进度判断逻辑
            upload_dir = Path(UPLOAD_DIR)
            if not list(upload_dir.glob(f"*{file_id}*")):
                raise HTTPException(status_code=404, detail="文件不存在")
                
            return JSONResponse(content={
                "status": "processing",
                "progress": 75  # 更准确的进度估计
            })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检查状态失败: {str(e)}")