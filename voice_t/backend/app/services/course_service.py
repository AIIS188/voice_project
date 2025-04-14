"""Course Service Module

This module provides functions for courseware processing and voiced courseware generation.
"""
import os
import json
import shutil
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from fastapi import UploadFile, BackgroundTasks

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COSYVOICE_PATH = os.path.join(ROOT_DIR, "cosyvoice")
sys.path.append(COSYVOICE_PATH)

from pydantic import BaseModel

from app.models.course import CoursewareDB, CoursewareTaskDB, CoursewareTextExtraction, CoursewareTaskStatus, SlideContent
from app.services.cosyvoice_tts import (
    synthesize_speech, get_tts_task_status, get_tts_task_result,
    get_cosyvoice_model, synthesize_speech_streaming, COSYVOICE_AVAILABLE
)
from app.core.config import settings

# Import PPT processing and lecture generation related modules
from app.core.extractor_main import run_pipeline
from app.core.outppt import PPTExtractor
from app.core.ppt_lecture import LectureGenerator
from app.services.llm_service import generate_lecture_content, generate_coherent_lecture
# Simulated database storage
COURSEWARE_DB = []
COURSEWARE_TASKS_DB = []

# Cache for completed tasks that have been queried
COMPLETED_TASKS_CACHE = {}

# Database file paths
COURSEWARE_FILE = os.path.join(settings.BASE_DIR, "data", "courseware.json")
COURSEWARE_TASKS_FILE = os.path.join(settings.BASE_DIR, "data", "courseware_tasks.json")

# Load database from file
def load_courseware_db():
    """Load courseware database from file"""
    global COURSEWARE_DB
    try:
        if os.path.exists(COURSEWARE_FILE):
            with open(COURSEWARE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COURSEWARE_DB = [CoursewareDB(**item) for item in data]
        return True
    except Exception as e:
        print(f"Error loading courseware database: {e}")
        return False

def load_courseware_tasks_db():
    """Load courseware tasks database from file"""
    global COURSEWARE_TASKS_DB
    try:
        if os.path.exists(COURSEWARE_TASKS_FILE):
            with open(COURSEWARE_TASKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COURSEWARE_TASKS_DB = [CoursewareTaskDB(**item) for item in data]
        return True
    except Exception as e:
        print(f"Error loading courseware tasks database: {e}")
        return False

# Save database to file

async def save_courseware_db():
    """Save courseware database to file"""
    try:
        os.makedirs(os.path.dirname(COURSEWARE_FILE), exist_ok=True)
        with open(COURSEWARE_FILE, 'w', encoding='utf-8') as f:
            # 使用 dict() 方法，兼容所有版本的 Pydantic
            data = [item.dict() for item in COURSEWARE_DB]
            json.dump(data, f, default=str, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving courseware database: {e}")
        return False

async def save_courseware_tasks_db():
    """Save courseware tasks database to file"""
    try:
        os.makedirs(os.path.dirname(COURSEWARE_TASKS_FILE), exist_ok=True)
        with open(COURSEWARE_TASKS_FILE, 'w', encoding='utf-8') as f:
            data = [item.dict() for item in COURSEWARE_TASKS_DB]
            json.dump(data, f, default=str, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving courseware tasks database: {e}")
        return False

# Initialize function
async def init_course_service():
    """Initialize course service"""
    global COURSEWARE_DB, COURSEWARE_TASKS_DB

    # Create necessary directories
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "courseware"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "voiced_courseware"), exist_ok=True)

    # Load courseware database
    if os.path.exists(COURSEWARE_FILE):
        try:
            with open(COURSEWARE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COURSEWARE_DB = [CoursewareDB(**item) for item in data]
        except Exception as e:
            print(f"Failed to initialize courseware service: {e}")

    # Load courseware tasks database
    if os.path.exists(COURSEWARE_TASKS_FILE):
        try:
            with open(COURSEWARE_TASKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                COURSEWARE_TASKS_DB = [CoursewareTaskDB(**item) for item in data]
        except Exception as e:
            print(f"Failed to initialize courseware tasks service: {e}")

# Load database on module import
load_courseware_db()
load_courseware_tasks_db()

# Initialize service
import asyncio
try:
    asyncio.create_task(init_course_service())
except RuntimeError:
    # Handle case when not in an event loop
    pass

# Extract from PPT function
def extract_from_ppt(file_path):
    """
    Extract content from PPT and get lecture notes. This function uses run_pipeline to process PPT files.

    Args:
        file_path: PPT file path

    Returns:
        slides_count: Number of slides
        slides: List of SlideContent objects
    """
    print(f"Starting to extract content from PPT file: {file_path}")

    # Create temporary output directory
    temp_dir = os.path.join(os.path.dirname(file_path), "temp_extraction")
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Run PPT processing pipeline to get lecture notes path and slide count
        lecture_path, slides_count = run_pipeline(
            pptx_file=file_path,
            output_dir=temp_dir,
            temp_format="json",
            lecture_mode="auto",
            output_format="json",
            save_intermediate=True
        )

        # Read generated lecture notes file
        with open(lecture_path, 'r', encoding='utf-8') as f:
            lecture_data = json.load(f)

        # Create SlideContent objects list
        slides = []

        # Process lecture data
        lecture_title = lecture_data.get("# 讲案标题", "")
        opening = lecture_data.get("## 开场白", "")

        # Get all slide keys
        slide_keys = [key for key in lecture_data.keys() if key.startswith("## 幻灯片")]
        slide_keys.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0)

        for key in slide_keys:
            try:
                # Extract slide number
                slide_id = int(re.search(r'(\d+)', key).group(1)) - 1  # 0-based index
                slide_data = lecture_data[key]

                # Process slide data
                if isinstance(slide_data, dict):
                    # Extract content and notes
                    content = slide_data.get("讲解", "")
                    notes = ""

                    # Combine important points into notes
                    if "重点总结" in slide_data:
                        points = slide_data["重点总结"]
                        if isinstance(points, list):
                            notes += "重点总结:\n- " + "\n- ".join(points) + "\n\n"
                        else:
                            notes += "重点总结:\n" + str(points) + "\n\n"

                    # Add interaction section to notes
                    if "互动环节" in slide_data:
                        interactions = slide_data["互动环节"]
                        if isinstance(interactions, list):
                            notes += "互动环节:\n- " + "\n- ".join(interactions)
                        else:
                            notes += "互动环节:\n" + str(interactions)

                    # Try to extract title (use first line of content or title field)
                    title = ""
                    if content:
                        lines = content.split('\n')
                        if lines:
                            title = lines[0].strip()
                            # If first line is short, it might be the title
                            if len(title) < 50:
                                content = '\n'.join(lines[1:]).strip()

                    # Create SlideContent object
                    slide_content = SlideContent(
                        slide_id=slide_id,
                        title=title,
                        content=content,
                        notes=notes
                    )

                    slides.append(slide_content)
                else:
                    # Handle case where slide data is a string
                    print(f"Warning: Slide {key} data format is incorrect, skipping processing")

            except Exception as e:
                print(f"Error processing slide {key}: {e}")
                import traceback
                traceback.print_exc()

        # Sort by slide number
        slides.sort(key=lambda x: x.slide_id)

        # If it's the first slide, add opening statement to content
        if slides and opening:
            first_slide = slides[0]
            first_slide.content = f"{opening}\n\n{first_slide.content}"

        # If there's no slide content (parsing may have failed), create a default slide
        if not slides:
            default_slide = SlideContent(
                slide_id=0,
                title=lecture_title if lecture_title else "Course Content",
                content="Could not extract specific slide content, please check the original PPT file.",
                notes=""
            )
            slides.append(default_slide)

        # Clean up temporary directory (optional)
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass

        return slides_count, slides

    except Exception as e:
        print(f"Error extracting PPT content: {e}")
        import traceback
        traceback.print_exc()

        # Create a default slide
        default_slide = SlideContent(
            slide_id=0,
            title="Processing Error",
            content=f"Error processing PPT file: {str(e)}",
            notes=""
        )

        return 1, [default_slide]

# Courseware upload function
async def upload_courseware(file: UploadFile, name: str) -> str:
    """Upload a courseware file"""
    # Generate a unique file ID
    timestamp = int(datetime.now().timestamp())
    random_suffix = os.urandom(2).hex()
    file_id = f"course_{timestamp}_{random_suffix}"

    # Create upload directory if it doesn't exist
    upload_dir = os.path.join(settings.UPLOAD_DIR, "courseware")
    os.makedirs(upload_dir, exist_ok=True)

    # Save the file
    file_path = os.path.join(upload_dir, f"{file_id}_{file.filename}")

    # Get file size
    file.file.seek(0, 2)  # Move to end of file
    file_size = file.file.tell()  # Get position (file size)
    file.file.seek(0)  # Move back to beginning

    # Read and save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Add to database
    courseware = CoursewareDB(
        file_id=file_id,
        name=name,
        original_filename=file.filename,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
        slides_count=0,  # Will be updated after extraction
        created_at=datetime.now().isoformat()
    )
    COURSEWARE_DB.append(courseware)

    # Save database
    await save_courseware_db()

    return file_id

# Extract text from courseware
async def extract_text(file_id: str) -> CoursewareTextExtraction:
    """Extract text from a courseware file"""
    # Find courseware in database
    courseware = next((cw for cw in COURSEWARE_DB if cw.file_id == file_id), None)
    if not courseware:
        return None

    # Check if file exists
    if not os.path.exists(courseware.file_path):
        print(f"File not found: {courseware.file_path}")
        return None

    # Extract text using the pipeline
    try:
        # Get file extension
        file_ext = Path(courseware.file_path).suffix.lower()

        # Extract text based on file type
        if file_ext in [".ppt", ".pptx"]:
            # Use extract_from_ppt function to process the file
            slides_count, slide_contents = extract_from_ppt(courseware.file_path)

            # Update courseware with slides count
            for i, cw in enumerate(COURSEWARE_DB):
                if cw.file_id == file_id:
                    COURSEWARE_DB[i].slides_count = slides_count
                    break

            # Save the updated database
            await save_courseware_db()

            # Generate combined text content
            text_content = ""
            for slide in slide_contents:
                slide_text = f"Slide {slide.slide_id+1}: {slide.title or ''}\n{slide.content or ''}\n\n"
                text_content += slide_text

            # Calculate total text length
            total_text_length = len(text_content)

            # Create extraction result
            result = CoursewareTextExtraction(
                file_id=file_id,
                name=courseware.name,
                slides_count=slides_count,
                extracted_text=slide_contents,
                total_text_length=total_text_length
            )

            # Save extraction result to voiced_courseware directory
            voiced_courseware_dir = os.path.join(settings.UPLOAD_DIR, "voiced_courseware")
            os.makedirs(voiced_courseware_dir, exist_ok=True)

            # Create JSON file path
            extraction_json_path = os.path.join(voiced_courseware_dir, f"{file_id}_extraction.json")

            # Save as JSON
            with open(extraction_json_path, 'w', encoding='utf-8') as f:
                # Convert to dict and save
                extraction_data = {
                    "file_id": file_id,
                    "name": courseware.name,
                    "original_filename": courseware.original_filename,
                    "slides_count": slides_count,
                    "slides": [{
                        "slide_id": slide.slide_id,
                        "title": slide.title,
                        "content": slide.content,
                        "notes": slide.notes
                    } for slide in slide_contents],
                    "extraction_time": datetime.now().isoformat()
                }
                json.dump(extraction_data, f, ensure_ascii=False, indent=2)

            print(f"Saved extraction result to {extraction_json_path}")

            return result
        elif file_ext in [".pdf"]:
            # For PDF files, use a simpler extraction method
            # This is a placeholder - implement PDF text extraction
            return CoursewareTextExtraction(
                file_id=file_id,
                name=courseware.name,
                slides_count=0,
                extracted_text=[],
                total_text_length=0
            )
        else:
            print(f"Unsupported file type: {file_ext}")
            return None
    except Exception as e:
        print(f"Error extracting text: {e}")
        import traceback
        traceback.print_exc()
        return None

# Generate voiced courseware
async def generate_voiced_courseware(
    background_tasks: BackgroundTasks,
    file_id: str,
    voice_id: str,
    speed: float = 1.0,
    emotion: str = "neutral",
    pitch: float = 0.0,
    energy: float = 1.0,
    pause_factor: float = 1.0
) -> str:
    """Generate voiced courseware"""
    # Find courseware in database
    courseware = next((cw for cw in COURSEWARE_DB if cw.file_id == file_id), None)
    if not courseware:
        raise ValueError(f"Courseware not found: {file_id}")

    # Check if file exists
    if not os.path.exists(courseware.file_path):
        raise ValueError(f"Courseware file not found: {courseware.file_path}")

    # Generate a unique task ID
    timestamp = int(datetime.now().timestamp())
    random_suffix = os.urandom(2).hex()
    task_id = f"{timestamp}_{random_suffix}"

    # Create task
    task = CoursewareTaskDB(
        task_id=task_id,
        file_id=file_id,
        name=courseware.name,
        status="pending",
        created_at=datetime.now().isoformat(),
        voice_id=voice_id,
        params={
            "mode": "sft",
            "speed": speed,
            "emotion": emotion,
            "pitch": pitch,
            "energy": energy,
            "pause_factor": pause_factor,
            "seed": int(timestamp % 10000)
        }
    )
    COURSEWARE_TASKS_DB.append(task)

    # Save database
    await save_courseware_tasks_db()

    # Start processing in background
    background_tasks.add_task(
        process_courseware_task,
        task_id
    )

    return task_id

# Create task
async def create_task(
    file_id: str,
    voice_id: str,
    speed: float = 1.0,
    emotion: str = "neutral",
    pitch: float = 0.0,
    energy: float = 1.0,
    pause_factor: float = 1.0
) -> str:
    """Create a voiced courseware generation task"""
    # Find courseware in database
    courseware = next((cw for cw in COURSEWARE_DB if cw.file_id == file_id), None)
    if not courseware:
        raise ValueError(f"Courseware not found: {file_id}")

    # Generate a unique task ID
    # 使用更稳定的ID生成方式，确保任务ID在整个流程中保持一致
    timestamp = int(datetime.now().timestamp())
    # 使用文件ID的前8位作为后缀，确保任务ID与文件ID相关
    file_suffix = file_id[:8] if len(file_id) >= 8 else file_id
    task_id = f"{timestamp}_{file_suffix}"

    # 打印任务ID信息，便于调试
    print(f"Created task with ID: {task_id} for file: {file_id}")

    # Create task
    task = CoursewareTaskDB(
        task_id=task_id,
        file_id=file_id,
        name=courseware.name,
        status="pending",
        created_at=datetime.now().isoformat(),
        voice_id=voice_id,
        speed=speed,
        emotion=emotion,
        pitch=pitch,
        energy=energy,
        pause_factor=pause_factor
    )
    COURSEWARE_TASKS_DB.append(task)

    # Save database
    await save_courseware_tasks_db()

    return task_id

# Update task
async def update_task(
    task_id: str,
    status: Optional[str] = None,
    progress: Optional[float] = None,
    error: Optional[str] = None,
    file_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
    slides_processed: Optional[int] = None,
    total_duration: Optional[float] = None,
    output_filename: Optional[str] = None,
    error_details: Optional[Dict[str, Any]] = None
) -> bool:
    """Update a task's status and progress"""
    # Find task in database
    task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == task_id), None)
    if not task:
        print(f"Task not found: {task_id}")
        return False

    # Update task
    if status:
        task.status = status
    if progress is not None:
        task.progress = progress
    if error:
        task.error = error
    if file_path:
        task.file_path = file_path
    if manifest_path:
        task.manifest_path = manifest_path
    if slides_processed:
        task.slides_processed = slides_processed
    if total_duration:
        task.total_duration = total_duration
    if output_filename:
        task.output_filename = output_filename
    if error_details:
        task.error_details = error_details

    # Update completion time if status is completed or failed
    if status in ["completed", "failed"]:
        task.completed_at = datetime.now()

    # Save database
    await save_courseware_tasks_db()

    return True

# Get task status
async def get_task_status(task_id: str) -> CoursewareTaskStatus:
    """Get a task's status"""
    global COMPLETED_TASKS_CACHE

    # Check if this is a completed task that has already been queried
    if task_id in COMPLETED_TASKS_CACHE:
        # If the task has been queried more than 3 times after completion,
        # return a special status to tell the frontend to stop polling
        query_count = COMPLETED_TASKS_CACHE[task_id]
        if query_count >= 3:
            print(f"Task {task_id} has been queried {query_count} times after completion. Returning stop polling status.")
            # Return a special status with a flag to stop polling
            current_time = datetime.now().isoformat()
            return CoursewareTaskStatus(
                task_id=task_id,
                file_id="stop_polling",
                name="Task Completed",
                status="completed",  # Keep status as completed
                progress=1.0,
                created_at=current_time,
                completed_at=current_time,
                stop_polling=True  # Special flag to tell frontend to stop polling
            )
        else:
            # Increment the query count
            COMPLETED_TASKS_CACHE[task_id] += 1

    # Find task in database
    task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == task_id), None)
    if not task:
        return None

    # Check if the task is completed or failed
    is_terminal_state = task.status in ["completed", "failed"]

    # If the task is in a terminal state and not in the cache, add it to the cache
    if is_terminal_state and task_id not in COMPLETED_TASKS_CACHE:
        COMPLETED_TASKS_CACHE[task_id] = 1
        print(f"Task {task_id} has reached terminal state {task.status}. Adding to cache.")

    # Convert to status model
    status = CoursewareTaskStatus(
        task_id=task.task_id,
        file_id=task.file_id,
        name=task.name,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at if hasattr(task, "completed_at") else None,
        error=task.error if hasattr(task, "error") else None,
        file_path=task.file_path if hasattr(task, "file_path") else None,
        manifest_path=task.manifest_path if hasattr(task, "manifest_path") else None,
        slides_processed=task.slides_processed if hasattr(task, "slides_processed") else None,
        total_duration=task.total_duration if hasattr(task, "total_duration") else None,
        output_filename=task.output_filename if hasattr(task, "output_filename") else None,
        error_details=task.error_details if hasattr(task, "error_details") else None,
        stop_polling=False  # Default is to continue polling
    )

    return status

# Get task result
async def get_task_result(task_id: str) -> CoursewareTaskStatus:
    """Get a task's result"""
    # Get task status
    status = await get_task_status(task_id)
    if not status:
        return None

    # Check if task is completed
    if status.status not in ["completed", "failed"]:
        print(f"Task not completed: {task_id}, status: {status.status}")
        return status

    return status

# Get all courseware
async def get_all_courseware():
    """Get all courseware files"""
    return COURSEWARE_DB

# List all courseware
async def list_all_courseware() -> List[Dict[str, Any]]:
    """List all courseware"""
    return [cw.dict() for cw in COURSEWARE_DB]

# Get all tasks
async def get_all_tasks():
    """Get all courseware tasks"""
    return COURSEWARE_TASKS_DB

# List all tasks
async def list_all_tasks() -> List[Dict[str, Any]]:
    """List all tasks"""
    return [t.dict() for t in COURSEWARE_TASKS_DB]

# Wait for task completion
async def wait_for_task_completion(task_id: str, timeout: float = 60.0) -> CoursewareTaskStatus:
    """Wait for a task to complete"""
    import asyncio
    start_time = asyncio.get_event_loop().time()

    while True:
        # Get task status
        status = await get_task_status(task_id)
        if not status:
            return None

        # Check if task is completed
        if status.status in ["completed", "failed"]:
            return status

        # Check timeout
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            print(f"Timeout waiting for task completion: {task_id}")
            return None

        # Wait a bit
        await asyncio.sleep(1.0)

# Optimize TTS parameters
async def optimize_tts_params(voice_id: str, text_sample: Optional[str] = None) -> Dict[str, Any]:
    """Optimize TTS parameters for a specific voice"""
    # Default parameters
    params = {
        "speed": 1.0,
        "pitch": 0.0,
        "energy": 1.0,
        "pause_factor": 1.0
    }

    # Optimize based on voice ID
    if "male" in voice_id.lower():
        # Male voices often sound better with slightly lower pitch
        params["pitch"] = -2.0
    elif "female" in voice_id.lower():
        # Female voices often sound better with slightly higher energy
        params["energy"] = 1.2

    # Language-specific optimizations
    if "chinese" in voice_id.lower() or "中文" in voice_id:
        # Chinese voices often sound better with slightly slower speed
        params["speed"] = 0.9
    elif "english" in voice_id.lower() or "英文" in voice_id:
        # English voices often sound better with slightly faster speed
        params["speed"] = 1.1

    return params

# Process courseware task
async def process_courseware_task(
    task_id: str
):
    """Process a courseware task"""
    import os
    print(f"Processing courseware task: {task_id}")

    # Find task in database
    task = next((t for t in COURSEWARE_TASKS_DB if t.task_id == task_id), None)
    if not task:
        print(f"Task not found: {task_id}")
        return

    # Get parameters from task
    file_id = task.file_id
    voice_id = task.voice_id
    params = task.params

    # Extract parameters
    speed = params.get("speed", 1.0)
    emotion = params.get("emotion", "neutral")
    pitch = params.get("pitch", 0.0)
    energy = params.get("energy", 1.0)
    pause_factor = params.get("pause_factor", 1.0)

    print(f"File ID: {file_id}")
    print(f"Voice ID: {voice_id}")
    print(f"Parameters: speed={speed}, emotion={emotion}, pitch={pitch}, energy={energy}, pause_factor={pause_factor}")

    # Update task status
    await update_task(task_id, status="processing", progress=0.1)

    try:
        # Find courseware in database
        courseware = next((cw for cw in COURSEWARE_DB if cw.file_id == file_id), None)
        if not courseware:
            raise ValueError(f"Courseware not found: {file_id}")

        # 1. 确保 voiced_courseware 目录存在
        voiced_courseware_dir = os.path.join(settings.UPLOAD_DIR, "voiced_courseware")
        os.makedirs(voiced_courseware_dir, exist_ok=True)

        # 2. 将上传的 PPT 文件复制到 voiced_courseware 目录
        original_ppt_path = courseware.file_path
        voiced_ppt_filename = f"{file_id}_{courseware.original_filename}"
        voiced_ppt_path = os.path.join(voiced_courseware_dir, voiced_ppt_filename)

        # 如果文件不存在，则复制
        if not os.path.exists(voiced_ppt_path):
            try:
                shutil.copy2(original_ppt_path, voiced_ppt_path)
                print(f"Copied original PPT to voiced_courseware: {voiced_ppt_path}")
            except Exception as e:
                print(f"Failed to copy PPT file: {e}")
                # 如果复制失败，使用原始文件路径
                voiced_ppt_path = original_ppt_path
        else:
            print(f"PPT file already exists in voiced_courseware: {voiced_ppt_path}")

        # 3. 检查是否已经有提取的 JSON 文件
        extraction_json_path = os.path.join(voiced_courseware_dir, f"{file_id}_extraction.json")

        if os.path.exists(extraction_json_path):
            print(f"Found existing extraction JSON file: {extraction_json_path}")
            # 直接使用现有的 JSON 文件
            with open(extraction_json_path, 'r', encoding='utf-8') as f:
                extraction_data = json.load(f)
                slide_count = extraction_data.get("slides_count", 0)
                print(f"Using existing extraction data with {slide_count} slides")

                # 确保 extraction_data 的格式正确
                if "slides" not in extraction_data or not isinstance(extraction_data["slides"], list):
                    print(f"Warning: extraction_data format is incorrect, slides field is missing or not a list")
                    # 创建一个空的 slides 列表
                    extraction_data["slides"] = []

            # 检查是否需要生成讲案
            lecture_json_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_lecture.json")
            enhanced_lecture_json_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_enhanced_lecture.json")

            # 优先检查是否有增强版讲案文件
            if os.path.exists(enhanced_lecture_json_path):
                print(f"Using existing enhanced lecture JSON file: {enhanced_lecture_json_path}")
                # 更新任务状态
                await update_task(task_id, progress=0.35, status="using_enhanced_lecture")
            elif os.path.exists(lecture_json_path):
                print(f"Found basic lecture JSON file, generating enhanced version")
                # 更新任务状态
                await update_task(task_id, progress=0.3, status="enhancing_lecture")
                # 使用大模型生成增强版讲案
                await generate_enhanced_lecture_script(extraction_data, task_id, voiced_courseware_dir)
            else:
                print(f"No lecture JSON file found, generating enhanced lecture from scratch")
                # 更新任务状态
                await update_task(task_id, progress=0.3, status="generating_enhanced_lecture")
                # 直接使用大模型生成增强版讲案
                await generate_enhanced_lecture_script(extraction_data, task_id, voiced_courseware_dir)
        else:
            # 如果没有现有的 JSON 文件，则进行内容提取
            print(f"Extracting content and generating lecture script from: {voiced_ppt_path}")

            # 创建临时目录用于存储中间文件
            temp_dir = os.path.join(settings.UPLOAD_DIR, f"course_task_{task_id}_temp")
            os.makedirs(temp_dir, exist_ok=True)

            # 使用 run_pipeline 函数进行内容提取和讲案生成
            from app.core.extractor_main import run_pipeline

            # 更新任务状态
            await update_task(task_id, progress=0.2, status="extracting_content")

            # 运行 PPT 处理流程
            lecture_path, slide_count = run_pipeline(
                pptx_file=voiced_ppt_path,
                output_dir=temp_dir,
                temp_format="json",
                lecture_mode="auto",
                output_format="json",
                save_intermediate=True
            )

            print(f"Generated lecture script: {lecture_path}")
            print(f"Total slides: {slide_count}")

            # 将生成的讲案文件复制到 voiced_courseware 目录
            # 使用 course_task_{task_id}_lecture.json 格式保存
            lecture_json_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_lecture.json")
            try:
                shutil.copy2(lecture_path, lecture_json_path)
                print(f"Copied lecture script to: {lecture_json_path}")
            except Exception as e:
                print(f"Failed to copy lecture script: {e}")

            # 如果没有提取数据，则调用 extract_text 函数生成
            if not os.path.exists(extraction_json_path):
                print("Generating extraction data...")
                await extract_text(file_id)
                # 重新检查文件是否存在
                if os.path.exists(extraction_json_path):
                    with open(extraction_json_path, 'r', encoding='utf-8') as f:
                        extraction_data = json.load(f)
                        print(f"Generated extraction data with {len(extraction_data.get('slides', []))} slides")
                else:
                    print("Warning: Failed to generate extraction data")
                    # 创建一个空的提取数据
                    extraction_data = {
                        "file_id": file_id,
                        "name": courseware.name,
                        "original_filename": courseware.original_filename,
                        "slides_count": slide_count,
                        "slides": []
                    }

                # 生成增强版讲案
                print(f"No lecture JSON file found, generating enhanced lecture from scratch")
                # 更新任务状态
                await update_task(task_id, progress=0.3, status="generating_enhanced_lecture")
                # 直接使用大模型生成增强版讲案
                await generate_enhanced_lecture_script(extraction_data, task_id, voiced_courseware_dir)

        # 更新任务状态
        await update_task(task_id, progress=0.4, status="generating_audio", slides_processed=slide_count)

        # 4. 使用 cosyvoice_tts.py 进行语音合成
        # 检查 CosyVoice 是否可用
        if not COSYVOICE_AVAILABLE:
            raise ValueError("TTS engine not available")

        # 获取 CosyVoice 模型
        model = get_cosyvoice_model()
        if not model:
            raise ValueError("CosyVoice model not available")

        # 检查语音ID是否有效
        if voice_id not in model.available_spks:
            print(f"Warning: Voice ID '{voice_id}' not found in available speakers. Using default voice.")
            # 使用默认语音ID
            if model.available_spks:
                voice_id = model.available_spks[0]
            else:
                raise ValueError("No available voices found")

        # 创建音频输出目录
        audio_dir = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_audio")
        os.makedirs(audio_dir, exist_ok=True)

        # 创建音频清单
        manifest = {
            "task_id": task_id,
            "file_id": file_id,
            "voice_id": voice_id,
            "slides": []
        }

        # 创建清单文件
        manifest_json_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_manifest.json")
        manifest = {
            "task_id": task_id,
            "courseware": {
                "file_id": file_id,
                "name": courseware.name,
                "original_filename": courseware.original_filename
            },
            "output_file": os.path.join(voiced_courseware_dir, f"course_task_{task_id}_voiced_{courseware.name}.pptx"),
            "total_duration": 0.0,
            "slides": [],
            "tts_params": params
        }

        # 检查是否有讲案文件
        lecture_json_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_lecture.json")
        enhanced_lecture_json_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_enhanced_lecture.json")

        # 优先使用基础讲案
        if os.path.exists(lecture_json_path):
            print(f"Using existing lecture JSON file: {lecture_json_path}")
            with open(lecture_json_path, 'r', encoding='utf-8') as f:
                lecture_data = json.load(f)
        # 如果没有基础讲案，则生成一个
        else:
            print(f"No lecture JSON file found, generating lecture from scratch")
            # 更新任务状态
            await update_task(task_id, progress=0.3, status="generating_lecture")

            # 生成讲案
            lecture_data = await generate_lecture_script(extraction_data, task_id, voiced_courseware_dir)

        # 提取讲案内容
        slides_data = []
        title = lecture_data.get("# 讲案标题", "")
        opening = lecture_data.get("## 开场白", "")

        # 先提取所有幻灯片内容，然后再处理开场白和结束语
        slide_contents = {}

        # 提取幻灯片内容
        for key, value in lecture_data.items():
            if key.startswith("## 幻灯片"):
                # 提取幻灯片编号
                try:
                    slide_num = int(re.search(r'\d+', key).group())
                    slide_id = slide_num - 1  # 转为0-based索引

                    # 只使用讲解部分和结束语
                    content = {}
                    if isinstance(value, dict):
                        if "讲解" in value:
                            content["讲解"] = value["讲解"]
                        if "结束语" in value:
                            content["结束语"] = value["结束语"]

                    # 将内容存储到字典中
                    slide_contents[slide_id] = content
                except Exception as e:
                    print(f"Error processing slide: {key}, error: {e}")
                    continue

        # 处理幻灯片内容，将开场白与第一页幻灯片合并，结束语与最后一页幻灯片合并
        if slide_contents:
            # 获取所有幻灯片ID
            slide_ids = sorted(slide_contents.keys())

            # 如果有幻灯片
            if slide_ids:
                # 第一张幻灯片
                first_slide_id = slide_ids[0]
                first_slide_content = slide_contents[first_slide_id]

                # 如果有标题和开场白，添加到第一张幻灯片
                if title or opening:
                    intro_text = ""
                    if title:
                        intro_text += title + "\n\n"
                    if opening:
                        intro_text += opening + "\n\n"

                    # 如果第一张幻灯片有讲解内容，将开场白添加到讲解内容前面
                    if "讲解" in first_slide_content:
                        first_slide_content["讲解"] = intro_text + first_slide_content["讲解"]
                    else:
                        first_slide_content["讲解"] = intro_text

                # 获取实际PPT的幻灯片数量
                try:
                    from pptx import Presentation
                    prs = Presentation(voiced_ppt_path)
                    actual_slides_count = len(prs.slides)
                    print(f"Actual slides count in PPT: {actual_slides_count}")
                except Exception as e:
                    print(f"Failed to get actual slides count: {e}")
                    # 如果无法获取实际幻灯片数量，假设为2
                    actual_slides_count = 2

                # 如果实际幻灯片数量小于JSON中的幻灯片数量
                if actual_slides_count < len(slide_ids):
                    print(f"JSON has more slides ({len(slide_ids)}) than actual PPT ({actual_slides_count})")
                    print("Will merge extra slides content to the last actual slide")

                    # 实际最后一张幻灯片的ID
                    actual_last_slide_id = actual_slides_count - 1

                    # 确保实际最后一张幻灯片存在于字典中
                    if actual_last_slide_id not in slide_contents:
                        slide_contents[actual_last_slide_id] = {}

                    # 合并所有超出实际幻灯片数量的内容到最后一张实际幻灯片
                    for slide_id in slide_ids:
                        if slide_id >= actual_slides_count:
                            extra_content = slide_contents[slide_id]

                            # 合并讲解内容
                            if "讲解" in extra_content:
                                if "讲解" in slide_contents[actual_last_slide_id]:
                                    slide_contents[actual_last_slide_id]["讲解"] += "\n\n" + extra_content["讲解"]
                                else:
                                    slide_contents[actual_last_slide_id]["讲解"] = extra_content["讲解"]

                            # 合并结束语
                            if "结束语" in extra_content:
                                if "讲解" in slide_contents[actual_last_slide_id]:
                                    slide_contents[actual_last_slide_id]["讲解"] += "\n\n" + extra_content["结束语"]
                                else:
                                    slide_contents[actual_last_slide_id]["讲解"] = extra_content["结束语"]

                    # 删除超出实际幻灯片数量的内容
                    slide_contents = {k: v for k, v in slide_contents.items() if k < actual_slides_count}

                    # 更新幻灯片ID列表
                    slide_ids = sorted(slide_contents.keys())

            # 将处理后的内容添加到slides_data
            for slide_id, content in slide_contents.items():
                slides_data.append({
                    "slide_id": slide_id,
                    "content": content
                })

            # 按幻灯片编号排序
            slides_data.sort(key=lambda x: x["slide_id"])

        # 如果没有幻灯片数据，则使用提取数据中的内容作为备选
        if not slides_data:
            print(f"No slides data found in lecture JSON, using extraction data as fallback")
            for slide in extraction_data.get("slides", []):
                slide_id = slide.get("slide_id", 0)
                title = slide.get("title", "")
                content = slide.get("content", "")
                notes = slide.get("notes", "")

                # 组合标题和内容
                slide_text = ""
                if title:
                    slide_text += title + "\n\n"
                if content:
                    slide_text += content
                if notes:
                    slide_text += "\n\n" + notes

                slides_data.append({
                    "slide_id": slide_id,
                    "content": {
                        "讲解": slide_text
                    }
                })

        # TTS 任务列表
        tts_tasks = []
        total_duration = 0.0

        # 处理每张幻灯片
        for i, slide_data in enumerate(slides_data):
            slide_id = slide_data["slide_id"]
            content = slide_data["content"]

            print(f"Processing slide {slide_id+1}/{len(slides_data)}")

            # 更新任务状态
            progress = 0.4 + (0.5 * (i / len(slides_data)))
            await update_task(task_id, progress=progress, slides_processed=i+1)

            # 提取讲解内容
            lecture_text = content.get("讲解", "")

            # 如果是最后一张幻灯片，添加结束语
            if i == len(slides_data) - 1 and "结束语" in content:
                lecture_text += "\n" + content["结束语"]

            # 跳过空内容
            if not lecture_text.strip():
                print(f"Skipping empty slide {slide_id+1}")
                continue

            # 分割文本为块
            chunks = split_text_into_chunks(lecture_text)
            print(f"Split slide {slide_id+1} into {len(chunks)} chunks")

            # 处理每个文本块
            chunk_tasks = []
            for j, chunk in enumerate(chunks):
                print(f"Processing chunk {j+1}/{len(chunks)} of slide {slide_id+1}")

                try:
                    # 生成音频文件名
                    audio_file = os.path.join(audio_dir, f"slide_{slide_id+1}_chunk_{j+1}.wav")

                    # 合成语音
                    audio_data, duration = await synthesize_speech(
                        text=chunk,
                        voice_id=voice_id,
                        speed=speed,
                        emotion=emotion,
                        pitch=pitch,
                        energy=energy,
                        pause_factor=pause_factor
                    )

                    # 手动保存音频文件
                    import soundfile as sf
                    import os

                    # 确保目录存在
                    os.makedirs(os.path.dirname(audio_file), exist_ok=True)

                    # 保存音频文件
                    sf.write(audio_file, audio_data, 16000, format='WAV')

                    # 添加到块任务
                    chunk_task = {
                        "chunk_id": j,
                        "text": chunk,
                        "audio_file": audio_file,
                        "duration": duration
                    }
                    chunk_tasks.append(chunk_task)
                    total_duration += duration

                    # 添加到清单
                    manifest["slides"].append({
                        "slide_id": slide_id,
                        "chunk_id": j,
                        "text": chunk,
                        "audio_file": os.path.basename(audio_file),
                        "duration": duration
                    })

                except Exception as e:
                    print(f"Failed to process text chunk: {e}")
                    import traceback
                    traceback.print_exc()

            # 计算幻灯片总时长
            slide_duration = sum(chunk.get("duration", 0) for chunk in chunk_tasks)

            # 保存幻灯片任务信息
            tts_tasks.append({
                "slide_id": slide_id,
                "chunks": chunk_tasks,
                "total_duration": slide_duration
            })

            # 添加到 manifest 文件
            manifest["slides"].append({
                "slide_id": slide_id + 1,  # 转为1-based索引以与讲案一致
                "title": lecture_text[:50] + "..." if len(lecture_text) > 50 else lecture_text,
                "chunks": [{
                    "chunk_id": chunk["chunk_id"],
                    "audio_file": chunk["audio_file"],
                    "duration": chunk.get("duration", 0)
                } for chunk in chunk_tasks],
                "total_duration": slide_duration
            })

            # 更新总时长
            total_duration += slide_duration

        # 更新进度
        await update_task(task_id, progress=0.9, slides_processed=len(slides_data))

        # 5. 将生成的音频插入对应的幻灯片
        try:
            # 导入音频插入模块
            from app.services.fix_audio_insertion import insert_audio_to_ppt, collect_audio_files_by_slide, create_audio_zip

            # 获取幻灯片总数
            try:
                from pptx import Presentation
                prs = Presentation(voiced_ppt_path)
                total_slides = len(prs.slides)
                print(f"Total slides in PPT: {total_slides}")
            except Exception as e:
                print(f"Failed to get slides count: {e}")
                total_slides = slide_count

            # 收集每个幻灯片的音频文件
            audio_files_by_slide, all_audio_files = collect_audio_files_by_slide(tts_tasks, total_slides)

            # 将音频插入到 PPT 中
            result_file = insert_audio_to_ppt(voiced_ppt_path, tts_tasks, voiced_courseware_dir, task_id)
            if result_file:
                output_path = result_file
                print(f"Successfully processed audio insertion: {output_path}")
            else:
                print(f"Failed to insert audio to PPT: {voiced_ppt_path}")
                # 创建音频 ZIP 包作为备选方案
                zip_file = create_audio_zip(voiced_courseware_dir, task_id, all_audio_files)
                if zip_file:
                    print(f"Created audio ZIP file: {zip_file}")
                    # 添加错误信息但不标记为失败
                    error_message = "Failed to insert audio to PPT. Audio files have been packaged as a ZIP file."
                    await update_task(task_id, error=error_message)
                else:
                    # 创建错误信息
                    error_message = "Failed to insert audio to PPT. Audio files have been generated and can be downloaded separately."
                    await update_task(task_id, error=error_message)

                # 使用原始 PPT 文件作为输出文件
                output_path = voiced_ppt_path

            # 更新 manifest 文件中的总时长和输出文件路径
            manifest["total_duration"] = total_duration
            manifest["output_file"] = output_path

            # 保存 manifest 文件
# Insert this code into the process_courseware_task function after creating manifest file
# Add this inside the try-except block, where the manifest file is being saved

            # Make sure the output file has a predictable name pattern that includes both task_id and file_id
            output_filename = f"course_task_{task_id}_voiced_{courseware.file_id}.pptx"
            output_path = os.path.join(voiced_courseware_dir, output_filename)
            
            # Update the manifest with this standardized output path
            manifest["output_file"] = output_path
            
            # Save manifest file with standardized path
            manifest_file_path = os.path.join(voiced_courseware_dir, f"course_task_{task_id}_manifest.json")
            with open(manifest_file_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
                
            print(f"Saved manifest file to {manifest_file_path}")
            
            # If we have a result from insert_audio_to_ppt, make sure to copy it to our standardized path
            if result_file and result_file != output_path and os.path.exists(result_file):
                try:
                    shutil.copy2(result_file, output_path)
                    print(f"Copied result file to standardized path: {output_path}")
                except Exception as e:
                    print(f"Failed to copy to standardized path: {e}")
                    # If copy fails, use the original path
                    output_path = result_file
                    
            # Update task status with clear file paths
            await update_task(
                task_id,
                status="completed",
                progress=1.0,
                file_path=output_path,
                manifest_path=manifest_file_path,
                total_duration=total_duration,
                output_filename=os.path.basename(output_path)
            )

            # 完成任务
            print(f"Task {task_id} completed successfully")
        except Exception as e:
            # 创建有声课件失败
            print(f"Failed to create voiced courseware: {e}")
            import traceback
            traceback.print_exc()

            # 更新任务状态
            error_message = f"Failed to create voiced courseware: {e}"
            await update_task(task_id, status="failed", error=error_message)

        # 保存清单已经在上面完成，这里不需要重复保存

    except Exception as e:
        print(f"Error processing courseware task: {e}")
        import traceback
        traceback.print_exc()

        # 更新任务状态
        error_message = f"Error processing courseware task: {e}"
        await update_task(task_id, status="failed", progress=0.0, error=error_message)
# Generate lecture script using large language model
async def generate_lecture_script(extraction_data: Dict[str, Any], task_id: str, output_dir: str) -> Dict[str, Any]:
    """
    Generate lecture script using large language model based on extraction data.

    Args:
        extraction_data: The extraction data from PPT
        task_id: The task ID
        output_dir: The output directory

    Returns:
        The generated lecture script data
    """
    try:
        # Import the large language model module
        from app.services.llm_service import generate_lecture_content

        print(f"Generating lecture script using large language model...")

        # Create lecture script data structure
        lecture_data = {
            "# 讲案标题": extraction_data.get("name", "Lecture"),
            "## 开场白": "\u5927\u5bb6\u597d\uff0c\u6b22\u8fce\u6765\u5230\u4eca\u5929\u7684\u8bfe\u7a0b\u3002"
        }

        # Generate lecture content for each slide
        slides = extraction_data.get("slides", [])
        print(f"Found {len(slides)} slides in extraction_data")

        for i, slide in enumerate(slides):
            slide_id = slide.get("slide_id", i)
            title = slide.get("title", "")
            content = slide.get("content", "")
            notes = slide.get("notes", "")

            print(f"Processing slide {slide_id}: title={title[:20]}...")

            # Combine slide content for input to LLM
            slide_content = ""
            if title:
                slide_content += f"\u6807\u9898\uff1a{title}\n"
            if content:
                slide_content += f"\u5185\u5bb9\uff1a{content}\n"
            if notes:
                slide_content += f"\u5907\u6ce8\uff1a{notes}\n"

            # Skip empty slides
            if not slide_content.strip():
                continue

            # Generate lecture content for this slide
            try:
                lecture_content = await generate_lecture_content(slide_content)

                # Add to lecture data
                lecture_data[f"## 幻灯片{slide_id+1}"] = {
                    "讲解": lecture_content
                }

                print(f"Generated lecture content for slide {slide_id+1}")
            except Exception as e:
                print(f"Failed to generate lecture content for slide {slide_id+1}: {e}")
                # Use slide content as fallback
                lecture_data[f"## 幻灯片{slide_id+1}"] = {
                    "讲解": f"{title}\n{content}"
                }

        # Add ending
        lecture_data["结束语"] = "\u4ee5\u4e0a\u5c31\u662f\u4eca\u5929\u7684\u5168\u90e8\u5185\u5bb9\uff0c\u611f\u8c22\u5927\u5bb6\u7684\u8010\u5fc3\u542c\u8bb2\u3002"

        # Save lecture data to file
        lecture_json_path = os.path.join(output_dir, f"course_task_{task_id}_lecture.json")
        with open(lecture_json_path, 'w', encoding='utf-8') as f:
            json.dump(lecture_data, f, ensure_ascii=False, indent=2)

        print(f"Saved generated lecture script to {lecture_json_path}")

        return lecture_data
    except Exception as e:
        print(f"Failed to generate lecture script: {e}")
        import traceback
        traceback.print_exc()

        # Return empty lecture data as fallback
        return {
            "# 讲案标题": extraction_data.get("name", "Lecture"),
            "## 开场白": "\u5927\u5bb6\u597d\uff0c\u6b22\u8fce\u6765\u5230\u4eca\u5929\u7684\u8bfe\u7a0b\u3002",
            "结束语": "\u4ee5\u4e0a\u5c31\u662f\u4eca\u5929\u7684\u5168\u90e8\u5185\u5bb9\uff0c\u611f\u8c22\u5927\u5bb6\u7684\u8010\u5fc3\u542c\u8bb2\u3002"
        }
async def generate_enhanced_lecture_script(extraction_data: Dict[str, Any], task_id: str, output_dir: str) -> Dict[str, Any]:
    """
    Generate an enhanced lecture script with more coherent and comprehensive content based on extraction data.
    This creates a more natural, flowing narrative suitable for speech synthesis.

    Args:
        extraction_data: The extraction data from PPT
        task_id: The task ID
        output_dir: The output directory

    Returns:
        The generated enhanced lecture script data
    """
    try:
        # Import the large language model module
        from app.services.llm_service import generate_lecture_content, generate_coherent_lecture

        print(f"Generating enhanced lecture script using large language model...")

        # Extract course name and create lecture script data structure
        course_name = extraction_data.get("name", "Lecture")
        lecture_data = {
            "# 讲案标题": course_name,
            "## 开场白": "各位同学大家好，欢迎来到今天的课程。今天我们将学习关于" + course_name + "的内容。希望大家能够积极参与，认真思考。"
        }

        # Get all slides data for context
        slides = extraction_data.get("slides", [])
        print(f"Found {len(slides)} slides in extraction_data")

        # First pass: analyze all slides to understand the complete narrative
        all_slide_content = []
        for i, slide in enumerate(slides):
            slide_id = slide.get("slide_id", i)
            title = slide.get("title", "")
            content = slide.get("content", "")
            notes = slide.get("notes", "")

            # Build comprehensive slide content
            slide_info = {
                "slide_id": slide_id,
                "title": title,
                "content": content,
                "notes": notes
            }
            all_slide_content.append(slide_info)

        # Generate coherent narrative across all slides
        try:
            # This new function would create a coherent narrative across slides
            coherent_lecture = await generate_coherent_lecture(all_slide_content, course_name)

            # Process each slide with context from the coherent narrative
            for i, slide in enumerate(slides):
                slide_id = slide.get("slide_id", i)
                title = slide.get("title", "")
                content = slide.get("content", "")
                notes = slide.get("notes", "")

                # Combine slide content for input
                slide_content = ""
                if title:
                    slide_content += f"标题：{title}\n"
                if content:
                    slide_content += f"内容：{content}\n"
                if notes:
                    slide_content += f"备注：{notes}\n"

                # Skip empty slides
                if not slide_content.strip():
                    continue

                # Get the coherent content for this slide from the overall narrative
                if str(slide_id) in coherent_lecture:
                    enhanced_content = coherent_lecture[str(slide_id)]
                    lecture_data[f"## 幻灯片{slide_id+1}"] = {
                        "讲解": enhanced_content
                    }
                    print(f"Added coherent lecture content for slide {slide_id+1}")
                else:
                    # Fallback: generate individual content
                    lecture_content = await generate_lecture_content(slide_content)
                    lecture_data[f"## 幻灯片{slide_id+1}"] = {
                        "讲解": lecture_content
                    }
                    print(f"Generated individual lecture content for slide {slide_id+1}")

                # Add transition to next slide if not the last slide
                if i < len(slides) - 1:
                    next_slide = slides[i+1]
                    next_title = next_slide.get("title", "")
                    if next_title:
                        transition = f'接下来，我们将学习"{next_title}"。'
                        current_content = lecture_data[f"## 幻灯片{slide_id+1}"]["讲解"]
                        lecture_data[f"## 幻灯片{slide_id+1}"]["讲解"] = current_content + "\n\n" + transition

        except Exception as e:
            print(f"Failed to generate coherent lecture: {e}")
            # Fallback to individual slide processing
            for i, slide in enumerate(slides):
                slide_id = slide.get("slide_id", i)
                title = slide.get("title", "")
                content = slide.get("content", "")
                notes = slide.get("notes", "")

                slide_content = ""
                if title:
                    slide_content += f"标题：{title}\n"
                if content:
                    slide_content += f"内容：{content}\n"
                if notes:
                    slide_content += f"备注：{notes}\n"

                if not slide_content.strip():
                    continue

                try:
                    lecture_content = await generate_lecture_content(slide_content)
                    lecture_data[f"## 幻灯片{slide_id+1}"] = {
                        "讲解": lecture_content
                    }
                except Exception as e:
                    print(f"Failed to generate content for slide {slide_id+1}: {e}")
                    lecture_data[f"## 幻灯片{slide_id+1}"] = {
                        "讲解": f"{title}\n{content}"
                    }

        # Add a more comprehensive ending
        lecture_data["结束语"] = "以上就是今天课程的全部内容。希望大家通过今天的学习，能够掌握" + course_name + "的相关知识。如果有任何问题，欢迎随时提问。谢谢大家的听讲，下次课程再见！"

        # Save enhanced lecture data to file with a different name
        enhanced_lecture_json_path = os.path.join(output_dir, f"course_task_{task_id}_enhanced_lecture.json")
        with open(enhanced_lecture_json_path, 'w', encoding='utf-8') as f:
            json.dump(lecture_data, f, ensure_ascii=False, indent=2)

        print(f"Saved enhanced lecture script to {enhanced_lecture_json_path}")

        return lecture_data

    except Exception as e:
        print(f"Failed to generate enhanced lecture script: {e}")
        import traceback
        traceback.print_exc()

        # Return basic lecture data as fallback
        return {
            "# 讲案标题": extraction_data.get("name", "Lecture"),
            "## 开场白": "大家好，欢迎来到今天的课程。",
            "结束语": "以上就是今天的全部内容，感谢大家的耐心听讲。"
        }
# Split text into chunks
def split_text_into_chunks(text: str, max_length: int = 200) -> List[str]:
    """Split text into chunks for TTS processing"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # If text is short enough, return as is
    if len(text) <= max_length:
        return [text]

    # Split by sentences
    sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # If sentence is too long, split by commas
        if len(sentence) > max_length:
            comma_parts = re.split(r'(?<=[,，])\s*', sentence)
            for part in comma_parts:
                if len(current_chunk) + len(part) <= max_length:
                    current_chunk += part + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = part + " "
        else:
            # If adding this sentence would make the chunk too long, start a new chunk
            if len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
