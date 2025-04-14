"""Course Service API Endpoints

API endpoints for courseware processing and voiced courseware generation.
"""
from fastapi import APIRouter, BackgroundTasks, UploadFile, Form, Path, Query, HTTPException, File
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import traceback
import os
import urllib.parse
import sys
import json
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)

from app.models.course import CoursewareUploadResponse, CoursewareTaskStatus, CoursewareTextExtraction
from app.services.course_service import (
    upload_courseware,
    extract_text,
    generate_voiced_courseware,
    get_task_status,
    get_task_result,
    list_all_courseware,
    list_all_tasks,
    wait_for_task_completion,
    optimize_tts_params,
    COURSEWARE_TASKS_DB,
    save_courseware_tasks_db
)
from app.core.config import settings

router = APIRouter()

class VoicedCoursewareRequest(BaseModel):
    """Request model for voiced courseware generation"""
    file_id: str = Field(..., description="Courseware file ID")
    voice_id: str = Field(..., description="Voice ID")
    speed: float = Field(1.0, description="Speech speed")
    emotion: str = Field("neutral", description="Voice emotion")
    pitch: float = Field(0.0, description="Voice pitch adjustment")
    energy: float = Field(1.0, description="Voice energy level")
    pause_factor: float = Field(1.0, description="Pause duration factor")

    class Config:
        schema_extra = {
            "example": {
                "file_id": "course_1234567890_1234",
                "voice_id": "chinese_female",
                "speed": 1.0,
                "emotion": "neutral",
                "pitch": 0.0,
                "energy": 1.0,
                "pause_factor": 1.0
            }
        }

@router.post("/upload", response_model=CoursewareUploadResponse)
async def upload_courseware_endpoint(
    file: UploadFile = File(...),
    name: str = Form(..., description="Courseware name")
):
    """
    Upload a courseware file (PPT/PPTX)
    """
    try:
        # Check file type
        if file.content_type not in [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/pdf"
        ]:
            raise HTTPException(
                status_code=400,
                detail="Only PowerPoint (PPT/PPTX) and PDF files are supported"
            )

        # Upload the file
        file_id = await upload_courseware(file, name)

        return CoursewareUploadResponse(
            file_id=file_id,
            name=name,
            status="uploaded",
            message="Courseware uploaded successfully"
        )
    except Exception as e:
        print(f"Error uploading courseware: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@router.get("/extract/{file_id}", response_model=CoursewareTextExtraction)
async def extract_courseware_text(
    file_id: str = Path(..., title="Courseware File ID")
):
    """
    Extract text from a courseware file
    """
    try:
        # Extract text from the file
        result = await extract_text(file_id)

        if not result:
            raise HTTPException(status_code=404, detail="Courseware not found or text extraction failed")

        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error extracting text: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Text extraction error: {str(e)}")

@router.post("/generate")
async def generate_voiced_courseware_endpoint(
    background_tasks: BackgroundTasks,
    request: VoicedCoursewareRequest
):
    """
    Generate voiced courseware from an uploaded file
    """
    try:
        # Check if file_id is URL encoded
        decoded_file_id = urllib.parse.unquote(request.file_id)

        # Check if voice_id is URL encoded
        decoded_voice_id = urllib.parse.unquote(request.voice_id)

        # Generate voiced courseware
        task_id = await generate_voiced_courseware(
            background_tasks,
            decoded_file_id,
            decoded_voice_id,
            request.speed,
            request.emotion,
            request.pitch,
            request.energy,
            request.pause_factor
        )

        # Get courseware name
        from app.services.course_service import COURSEWARE_DB
        courseware = next((cw for cw in COURSEWARE_DB if cw.file_id == decoded_file_id), None)
        name = courseware.name if courseware else ""

        # Construct response
        response = {
            "file_id": request.file_id,
            "name": name,
            "status": "pending",
            "message": "Voiced courseware generation task submitted",
            "task_id": task_id
        }

        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error generating voiced courseware: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

@router.get("/status/{task_id}", response_model=CoursewareTaskStatus)
async def check_task_status_endpoint(
    task_id: str = Path(..., title="Task ID")
):
    """
    Check the status of a voiced courseware generation task
    """
    try:
        # Check if task_id is URL encoded
        if '%' in task_id:
            decoded_task_id = urllib.parse.unquote(task_id)
            print(f"URL-decoded task ID: {decoded_task_id}")
            status = await get_task_status(decoded_task_id)
        else:
            status = await get_task_status(task_id)

        if not status:
            # Try with original task_id in case decoding was not needed
            if '%' in task_id:
                status = await get_task_status(task_id)

            if not status:
                print(f"Task not found: {task_id}")
                raise HTTPException(status_code=404, detail="Task not found")

        return status
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error checking task status: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")

# Improved download_courseware_result function in course_service.py API routes

@router.get("/download/{task_id}")
async def download_courseware_result(
    task_id: str = Path(..., title="Task ID")
):
    """
    Download the voiced courseware result
    """
    try:
        # Decode URL encoded task ID if needed
        if '%' in task_id:
            decoded_task_id = urllib.parse.unquote(task_id)
            print(f"URL-decoded task ID for download: {decoded_task_id}")
        else:
            decoded_task_id = task_id
            
        print(f"Processing download request for task: {decoded_task_id}")
        
        # Get task status from database
        task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == decoded_task_id), None)
        
        # If task not found with decoded ID, try original ID
        if not task and decoded_task_id != task_id:
            task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == task_id), None)
            
        # If task exists and has a file_path
        if task and hasattr(task, 'file_path') and task.file_path and os.path.exists(task.file_path):
            print(f"Found task with file path: {task.file_path}")
            filename = task.output_filename if hasattr(task, 'output_filename') and task.output_filename else f"voiced_courseware_{task_id}.pptx"
            
            # Return the file directly
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
            
            return FileResponse(
                path=task.file_path,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=filename,
                headers=headers
            )
        
        # Search for files with patterns matching task ID
        voiced_courseware_dir = os.path.join(settings.UPLOAD_DIR, "voiced_courseware")
        print(f"Searching for files in: {voiced_courseware_dir}")
        
        # Check if directory exists
        if not os.path.exists(voiced_courseware_dir):
            print(f"Directory not found: {voiced_courseware_dir}")
            raise HTTPException(status_code=404, detail="Voiced courseware directory not found")
            
        # Try different file pattern matches
        possible_patterns = [
            f"course_task_{decoded_task_id}_voiced*.pptx",
            f"course_task_{task_id}_voiced*.pptx",
            f"*{decoded_task_id}*voiced*.pptx",
            f"*{task_id}*voiced*.pptx"
        ]
        
        found_file = None
        
        # Try each pattern
        for pattern in possible_patterns:
            import glob
            matches = glob.glob(os.path.join(voiced_courseware_dir, pattern))
            if matches:
                found_file = matches[0]
                print(f"Found file using pattern {pattern}: {found_file}")
                break
        
        # If file found, return it
        if found_file and os.path.exists(found_file):
            filename = os.path.basename(found_file)
            
            # Return the file
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
            
            return FileResponse(
                path=found_file,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=filename,
                headers=headers
            )
        
        # If task exists in database but no file found, check if we should look for the file through task's file_id
        if task and hasattr(task, 'file_id') and task.file_id:
            file_id = task.file_id
            print(f"Trying to find file using file_id: {file_id}")
            
            # Find any file matching this file_id
            file_patterns = [
                f"course_task_*_{file_id}*.pptx",
                f"*{file_id}*_voiced*.pptx",
                f"*{file_id}*.pptx"
            ]
            
            for pattern in file_patterns:
                import glob
                matches = glob.glob(os.path.join(voiced_courseware_dir, pattern))
                if matches:
                    found_file = matches[0]
                    print(f"Found file using file_id pattern {pattern}: {found_file}")
                    
                    # Update task's file_path for future reference
                    task.file_path = found_file
                    task.output_filename = os.path.basename(found_file)
                    await save_courseware_tasks_db()
                    
                    # Return the file
                    headers = {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Content-Disposition": f'attachment; filename="{os.path.basename(found_file)}"'
                    }
                    
                    return FileResponse(
                        path=found_file,
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        filename=os.path.basename(found_file),
                        headers=headers
                    )
                    
        # If still no file found, search for any PPT file that might be related to this task
        manifest_path = None
        
        # Check if there's a manifest file for this task
        manifest_patterns = [
            f"course_task_{decoded_task_id}_manifest.json",
            f"course_task_{task_id}_manifest.json",
            f"*{decoded_task_id}*manifest*.json",
            f"*{task_id}*manifest*.json"
        ]
        
        for pattern in manifest_patterns:
            import glob
            matches = glob.glob(os.path.join(voiced_courseware_dir, pattern))
            if matches:
                manifest_path = matches[0]
                print(f"Found manifest file: {manifest_path}")
                break
                
        if manifest_path and os.path.exists(manifest_path):
            # Try to read the manifest file to find the output file
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                    
                if 'output_file' in manifest_data and os.path.exists(manifest_data['output_file']):
                    output_file = manifest_data['output_file']
                    print(f"Found output file from manifest: {output_file}")
                    
                    filename = os.path.basename(output_file)
                    
                    # If task exists, update its file_path
                    if task:
                        task.file_path = output_file
                        task.output_filename = filename
                        await save_courseware_tasks_db()
                    
                    # Return the file
                    headers = {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Content-Disposition": f'attachment; filename="{filename}"'
                    }
                    
                    return FileResponse(
                        path=output_file,
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        filename=filename,
                        headers=headers
                    )
            except Exception as e:
                print(f"Error reading manifest file: {e}")
        
        # Last resort: look for any PPTX files in the task-specific directory
        task_dir_pattern = f"course_task_{decoded_task_id}*"
        task_dirs = glob.glob(os.path.join(voiced_courseware_dir, task_dir_pattern))
        
        for task_dir in task_dirs:
            if os.path.isdir(task_dir):
                pptx_files = glob.glob(os.path.join(task_dir, "*.pptx"))
                if pptx_files:
                    found_file = pptx_files[0]
                    print(f"Found PPTX in task directory: {found_file}")
                    
                    filename = os.path.basename(found_file)
                    
                    # Return the file
                    headers = {
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                        "Access-Control-Allow-Headers": "Content-Type",
                        "Content-Disposition": f'attachment; filename="{filename}"'
                    }
                    
                    return FileResponse(
                        path=found_file,
                        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        filename=filename,
                        headers=headers
                    )
        
        # If we get here, we couldn't find the file
        print(f"No file found for task: {task_id}")
        raise HTTPException(status_code=404, detail="Voiced courseware file not found")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading result: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

@router.get("/manifest/{task_id}")
async def get_courseware_manifest(
    task_id: str = Path(..., title="Task ID")
):
    """
    Get the manifest file containing slide and audio information
    """
    try:
        # Decode URL encoded task ID if needed
        if '%' in task_id:
            decoded_task_id = urllib.parse.unquote(task_id)
            print(f"URL-decoded task ID for manifest: {decoded_task_id}")
        else:
            decoded_task_id = task_id
            
        print(f"Processing manifest request for task: {decoded_task_id}")
        
        # Get task status from database
        task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == decoded_task_id), None)
        
        # If task not found with decoded ID, try original ID
        if not task and decoded_task_id != task_id:
            task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == task_id), None)
            
        # If task exists and has a manifest_path
        if task and hasattr(task, 'manifest_path') and task.manifest_path and os.path.exists(task.manifest_path):
            print(f"Found task with manifest path: {task.manifest_path}")
            
            # Return the manifest file directly
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Disposition": f'attachment; filename="manifest_{task_id}.json"'
            }
            
            return FileResponse(
                path=task.manifest_path,
                media_type="application/json",
                filename=f"manifest_{task_id}.json",
                headers=headers
            )
        
        # Search for manifest files with patterns matching task ID
        voiced_courseware_dir = os.path.join(settings.UPLOAD_DIR, "voiced_courseware")
        print(f"Searching for manifest in: {voiced_courseware_dir}")
        
        # Check if directory exists
        if not os.path.exists(voiced_courseware_dir):
            print(f"Directory not found: {voiced_courseware_dir}")
            raise HTTPException(status_code=404, detail="Voiced courseware directory not found")
            
        # Try different file pattern matches
        possible_patterns = [
            f"course_task_{decoded_task_id}_manifest.json",
            f"course_task_{task_id}_manifest.json"
        ]
        
        found_file = None
        
        # Try each pattern
        for pattern in possible_patterns:
            import glob
            matches = glob.glob(os.path.join(voiced_courseware_dir, pattern))
            if matches:
                found_file = matches[0]
                print(f"Found manifest using pattern {pattern}: {found_file}")
                break
                
        # If no exact match, try more general patterns
        if not found_file:
            general_patterns = [
                f"*{decoded_task_id}*manifest*.json",
                f"*{task_id}*manifest*.json"
            ]
            
            for pattern in general_patterns:
                import glob
                matches = glob.glob(os.path.join(voiced_courseware_dir, pattern))
                if matches:
                    found_file = matches[0]
                    print(f"Found manifest using general pattern {pattern}: {found_file}")
                    break
        
        # If file found, return it
        if found_file and os.path.exists(found_file):
            # If task exists, update its manifest_path
            if task:
                task.manifest_path = found_file
                await save_courseware_tasks_db()
                
            # Return the manifest file
            headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Disposition": f'attachment; filename="manifest_{task_id}.json"'
            }
            
            return FileResponse(
                path=found_file,
                media_type="application/json",
                filename=f"manifest_{task_id}.json",
                headers=headers
            )
        
        # If we get here, we couldn't find the file
        print(f"No manifest file found for task: {task_id}")
        raise HTTPException(status_code=404, detail="Manifest file not found")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving manifest: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Manifest retrieval error: {str(e)}")
    
@router.get("/list", response_model=List[Dict[str, Any]])
async def list_courseware():
    """
    List all uploaded courseware files
    """
    try:
        return await list_all_courseware()
    except Exception as e:
        print(f"Error listing courseware: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Listing error: {str(e)}")

@router.get("/tasks", response_model=List[Dict[str, Any]])
async def list_tasks():
    """
    List all voiced courseware generation tasks
    """
    try:
        return await list_all_tasks()
    except Exception as e:
        print(f"Error listing tasks: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Listing error: {str(e)}")

@router.get("/optimize-params/{voice_id}")
async def get_optimized_params(
    voice_id: str = Path(..., title="Voice ID"),
    text_sample: Optional[str] = Query(None, description="Sample text for parameter optimization")
):
    """
    Get optimized TTS parameters for a specific voice
    """
    try:
        # Decode voice_id if URL encoded
        decoded_voice_id = urllib.parse.unquote(voice_id)

        # Get optimized parameters
        params = await optimize_tts_params(decoded_voice_id, text_sample)

        return JSONResponse(content=params)
    except Exception as e:
        print(f"Error optimizing parameters: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Parameter optimization error: {str(e)}")

@router.post("/wait-completion/{task_id}", response_model=CoursewareTaskStatus)
async def wait_for_completion(
    task_id: str = Path(..., title="Task ID"),
    timeout: float = Query(60.0, description="Maximum wait time in seconds")
):
    """
    Wait for a task to complete (for synchronous workflows)
    """
    try:
        # Decode task_id if URL encoded
        if '%' in task_id:
            decoded_task_id = urllib.parse.unquote(task_id)
        else:
            decoded_task_id = task_id

        # Wait for completion
        result = await wait_for_task_completion(decoded_task_id, timeout)

        if not result:
            raise HTTPException(status_code=408, detail="Request timeout waiting for task completion")

        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error waiting for completion: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Wait error: {str(e)}")