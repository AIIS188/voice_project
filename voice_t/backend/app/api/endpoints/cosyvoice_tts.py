"""CosyVoice TTS API Endpoints

Updated endpoints for the unified voice system with streaming support.
"""
from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi import Query, Path, Body, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import traceback
import urllib.parse
import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(ROOT_DIR)
from app.models.tts import TTSResponse, TTSTaskStatus
from app.services.modified_cosyvoice_tts import synthesize_speech_unified
from app.services.cosyvoice_tts import (
    get_tts_task_status,
    get_tts_task_result,
    get_cosyvoice_model,
    synthesize_speech_streaming
    
)
from app.services.unified_voice_service import get_voice_by_id

router = APIRouter()

class UnifiedTTSRequest(BaseModel):
    """Unified TTS request model"""
    text: str = Field(..., min_length=1, description="Text to synthesize")
    voice_id: str = Field(..., description="Voice ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="Synthesis parameters")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "欢迎使用语音合成系统",
                "voice_id": "voice_id_123",
                "params": {
                    "speed": 1.0,
                    "seed": 123456
                }
            }
        }

@router.post("/synthesize", response_model=TTSResponse)
async def create_tts_task(
    background_tasks: BackgroundTasks,
    request: UnifiedTTSRequest = Body(...)
):
    """
    创建统一的文本转语音任务，
    根据选择的语音类型自动选择合适的合成方法。
    """
    # 验证文本长度
    if len(request.text) < 1:
        raise HTTPException(status_code=400, detail="文本不能为空")
    
    try:
        # 提交语音合成任务
        task_id = await synthesize_speech_unified(
            background_tasks, 
            request.text, 
            request.voice_id, 
            request.params
        )
        
        return TTSResponse(
            task_id=task_id,
            status="pending",
            message="语音合成任务已提交"
        )
    except ValueError as e:
        # 处理值错误
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # 记录并处理其他异常
        print(f"在创建TTS任务时发生错误: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"合成错误: {str(e)}")
    
@router.websocket("/synthesize/stream")
async def websocket_tts_stream(websocket: WebSocket):
    """
    Stream synthesis via WebSocket with automatic method selection
    """
    await websocket.accept()
    
    try:
        # Get request parameters
        request_data = await websocket.receive_json()
        
        # Validate parameters
        if 'text' not in request_data:
            await websocket.send_json({"type": "error", "message": "Missing text parameter"})
            await websocket.close()
            return
        
        if 'voice_id' not in request_data:
            await websocket.send_json({"type": "error", "message": "Missing voice_id parameter"})
            await websocket.close()
            return
        
        # Extract parameters
        text = request_data['text']
        voice_id = request_data['voice_id']
        params = request_data.get('params', {})
        
        # URL decode voice_id if needed
        decoded_voice_id = urllib.parse.unquote(voice_id)
        print(f"Stream synthesis request - Voice ID: {decoded_voice_id}")
        
        # Get voice information
        voice = get_voice_by_id(decoded_voice_id)
        if not voice:
            await websocket.send_json({
                "type": "error", 
                "message": f"Voice not found: {decoded_voice_id}"
            })
            await websocket.close()
            return
        
        # Use voice ID from the database for consistency
        voice_id_from_db = voice["id"]
        
        # Configure streaming based on voice type
        if voice["type"] == "pretrained":
            # For pretrained voices, use SFT mode
            await websocket.send_json({"type": "info", "message": "使用预训练音色合成..."})
            
            # Set synthesis mode
            params["mode"] = "sft"
            
            # Start streaming
            await synthesize_speech_streaming(
                websocket,
                text,
                voice_id_from_db,
                params
            )
            
        elif voice["type"] == "user-uploaded":
            # For user-uploaded voices, use zero-shot cloning
            await websocket.send_json({"type": "info", "message": "使用声音复刻合成..."})
            
            # Get reference audio and text
            prompt_audio = voice.get("reference_audio")
            prompt_text = voice.get("reference_text")
            
            if not prompt_audio or not prompt_text:
                await websocket.send_json({
                    "type": "info", 
                    "message": "尝试自动获取参考音频和文本..."
                })
                
                # Try to find the reference path based on voice_id format
                if voice_id_from_db.startswith("user_"):
                    # Import settings if needed
                    from app.core.config import settings
                    import os
                    
                    # Construct the expected reference path based on voice_library.json format
                    reference_path = os.path.join(settings.UPLOAD_DIR, "user_voices", voice_id_from_db, "reference.wav")
                    if os.path.exists(reference_path):
                        await websocket.send_json({
                            "type": "info", 
                            "message": "已找到参考音频"
                        })
                        prompt_audio = reference_path
                        
                        # If we have audio but no text, use a default text
                        if not prompt_text:
                            prompt_text = "这是一段用于语音合成的参考音频。"
                            await websocket.send_json({
                                "type": "info", 
                                "message": "使用默认参考文本"
                            })
            
            # Still missing required data after recovery attempt
            if not prompt_audio or not prompt_text:
                await websocket.send_json({
                    "type": "error", 
                    "message": f"Missing reference audio or text for voice: {voice_id_from_db}"
                })
                await websocket.close()
                return
            
            # Set synthesis mode
            params["mode"] = "zero_shot"
            
            # Start streaming
            await synthesize_speech_streaming(
                websocket,
                text,
                voice_id_from_db,
                params,
                prompt_audio,
                prompt_text
            )
            
        else:
            await websocket.send_json({
                "type": "error", 
                "message": f"Unsupported voice type: {voice['type']}"
            })
            await websocket.close()
            
    except WebSocketDisconnect:
        print("WebSocket connection disconnected")
    except Exception as e:
        print(f"Error in streaming synthesis: {traceback.format_exc()}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
        finally:
            try:
                await websocket.close()
            except:
                pass

@router.get("/status/{task_id}", response_model=TTSTaskStatus)
async def check_task_status(
    task_id: str = Path(..., title="Task ID")
):
    """
    Check TTS task status
    """
    try:
        # Check if task_id is URL encoded
        if '%' in task_id:
            decoded_task_id = urllib.parse.unquote(task_id)
            print(f"URL-decoded task ID: {decoded_task_id}")
            status = await get_tts_task_status(decoded_task_id)
        else:
            status = await get_tts_task_status(task_id)
        
        if not status:
            # Try with original task_id in case decoding was not needed
            if '%' in task_id:
                status = await get_tts_task_status(task_id)
                
            if not status:
                print(f"Task not found: {task_id}")
                raise HTTPException(status_code=404, detail="Task not found")
        
        return status
    except Exception as e:
        print(f"Error checking task status: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")

@router.get("/download/{task_id}")
async def download_tts_result(
    task_id: str = Path(..., title="Task ID")
):
    """
    Download TTS result
    """
    try:
        # Check if task_id is URL encoded
        if '%' in task_id:
            decoded_task_id = urllib.parse.unquote(task_id)
            print(f"URL-decoded task ID for download: {decoded_task_id}")
            result = await get_tts_task_result(decoded_task_id)
        else:
            result = await get_tts_task_result(task_id)
        
        if not result:
            # Try with original task_id in case decoding was not needed
            if '%' in task_id:
                result = await get_tts_task_result(task_id)
                
            if not result:
                raise HTTPException(status_code=404, detail="Task not found or not complete")
        
        if result.status != "completed":
            raise HTTPException(status_code=400, detail=f"Task status is {result.status}, cannot download")
        
        return FileResponse(
            result.file_path,
            media_type="audio/wav",
            filename=f"voice_synthesis_{task_id}.wav"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error downloading result: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

@router.get("/preview", response_model=TTSResponse)
async def preview_tts(
    background_tasks: BackgroundTasks,
    text: str = Query(..., description="Text to synthesize"),
    voice_id: str = Query(..., description="Voice ID")
):
    """
    Preview TTS with a short text
    """
    try:
        # URL decode voice_id
        decoded_voice_id = urllib.parse.unquote(voice_id)
        print(f"Preview request - Voice ID: {decoded_voice_id}")
        
        # Truncate text to 200 characters
        preview_text = text[:200]
        
        # Create preview task
        params = {
            "speed": 1.0,
            "is_preview": True
        }
        
        task_id = await synthesize_speech_unified(
            background_tasks,
            preview_text,
            decoded_voice_id,
            params
        )
        
        return TTSResponse(
            task_id=task_id,
            status="pending",
            message="Preview task submitted"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error in preview_tts: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Preview error: {str(e)}")