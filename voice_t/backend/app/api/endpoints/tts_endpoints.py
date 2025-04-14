"""CosyVoice TTS API 端点 - 实时简化版本

专注于实时语音合成，无需历史任务管理。
"""
from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect, Response
from fastapi import Query, Path, Body, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import os
import traceback
import urllib.parse
import time
from app.models.tts import TTSResponse
from app.services.modified_cosyvoice_tts import (
    synthesize_speech_unified,
    get_task_status,
    get_task_result,
)
from app.services.cosyvoice_tts import (
    get_cosyvoice_model,
    synthesize_speech_streaming
)
from app.services.unified_voice_service import get_voice_by_id
from app.services.shared_storage import IN_MEMORY_AUDIO

router = APIRouter()



class UnifiedTTSRequest(BaseModel):
    """统一TTS请求模型"""
    text: str = Field(..., min_length=1, description="要合成的文本")
    voice_id: str = Field(..., description="声音ID")
    params: Dict[str, Any] = Field(default_factory=dict, description="合成参数")
    
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
    request: UnifiedTTSRequest = Body(...),
):
    """创建TTS任务，支持选择是否保存到本地"""
    # 验证文本长度
    if len(request.text) < 1:
        raise HTTPException(status_code=400, detail="文本不能为空")
    
    try:
        # 修改参数，添加保存到内存的选项
        params = {**request.params}
        
        # 提交合成任务
        task_id = await synthesize_speech_unified(
            background_tasks, 
            request.text, 
            request.voice_id, 
            params
        )
        
        return TTSResponse(
            task_id=task_id,
            status="pending",
            message="语音合成任务已提交"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error in create_tts_task: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"合成错误: {str(e)}")

@router.get("/status/{task_id}")
async def check_task_status(
    task_id: str = Path(..., title="任务ID")
):
    """检查任务状态"""
    try:
        status = get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="任务未找到")
        
        return status
    except HTTPException:
        raise
    except Exception as e:
        print(f"检查任务状态时出错: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"状态检查错误: {str(e)}")
@router.get("/download/{task_id}")
async def download_tts_result(
    task_id: str = Path(..., title="任务ID")
):
    """下载指定任务的完整音频或最新音频"""
    from app.services.shared_storage import get_audio_for_task, LATEST_AUDIO
    
    # 尝试获取指定任务的音频
    audio_data = get_audio_for_task(task_id)
    
    if audio_data and audio_data.get("complete_audio"):
        # 有完整音频，返回它
        filename = f"voice_synthesis_{task_id}_{int(time.time())}.wav"
        
        # 确保是bytes类型
        audio_bytes = audio_data["complete_audio"]
        if isinstance(audio_bytes, bytearray):
            audio_bytes = bytes(audio_bytes)
            
        print(f"下载任务 {task_id} 的完整音频，大小: {len(audio_bytes)} 字节")
        
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "audio/wav",
                "X-Audio-Duration": str(audio_data["duration"]),
                "X-Audio-Timestamp": str(audio_data["timestamp"])
            }
        )
    
    # 向后兼容 - 如果找不到指定任务的音频，使用最新音频
    if LATEST_AUDIO["data"]:
        print(f"未找到任务 {task_id} 的音频，使用最新音频")
        filename = f"voice_synthesis_{int(time.time())}.wav"
        
        # 确保是bytes类型
        audio_bytes = LATEST_AUDIO["data"]
        if isinstance(audio_bytes, bytearray):
            audio_bytes = bytes(audio_bytes)
            
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "audio/wav",
                "X-Audio-Duration": str(LATEST_AUDIO["duration"]),
                "X-Audio-Timestamp": str(LATEST_AUDIO["timestamp"])
            }
        )
    
    # 没有可用音频
    raise HTTPException(status_code=404, detail="没有可用的音频数据")


@router.get("/preview_audio/{task_id}")
async def preview_audio(
    task_id: str = Path(..., title="任务ID")
):
    """返回指定任务ID的完整音频或最新音频"""
    from app.services.shared_storage import get_audio_for_task, LATEST_AUDIO
    
    # 尝试获取指定任务的音频
    audio_data = get_audio_for_task(task_id)
    
    if audio_data and audio_data.get("complete_audio"):
        # 有完整音频，返回它
        try:
            duration = float(audio_data["duration"]) if audio_data["duration"] is not None else 0.0
            timestamp = int(audio_data["timestamp"]) if audio_data["timestamp"] is not None else 0
            
            # 确保是bytes类型
            audio_bytes = audio_data["complete_audio"]
            if isinstance(audio_bytes, bytearray):
                audio_bytes = bytes(audio_bytes)
                
            print(f"返回任务 {task_id} 的完整音频，大小: {len(audio_bytes)} 字节")
            
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "inline",
                    "X-Audio-Duration": str(duration),
                    "X-Audio-Timestamp": str(timestamp)
                }
            )
        except Exception as e:
            print(f"处理音频响应时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 回退到基本响应
            audio_bytes = audio_data["complete_audio"]
            if isinstance(audio_bytes, bytearray):
                audio_bytes = bytes(audio_bytes)
                
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": "inline"}
            )
    
    # 向后兼容 - 如果找不到指定任务的音频，使用最新音频
    if LATEST_AUDIO["data"]:
        print(f"未找到任务 {task_id} 的音频，使用最新音频")
        try:
            duration = float(LATEST_AUDIO["duration"]) if LATEST_AUDIO["duration"] is not None else 0.0
            timestamp = int(LATEST_AUDIO["timestamp"]) if LATEST_AUDIO["timestamp"] is not None else 0
            
            # 确保是bytes类型
            audio_bytes = LATEST_AUDIO["data"]
            if isinstance(audio_bytes, bytearray):
                audio_bytes = bytes(audio_bytes)
            
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "inline",
                    "X-Audio-Duration": str(duration),
                    "X-Audio-Timestamp": str(timestamp)
                }
            )
        except Exception as e:
            print(f"处理最新音频响应时出错: {e}")
            import traceback
            traceback.print_exc()
            
            # 确保是bytes类型
            audio_bytes = LATEST_AUDIO["data"]
            if isinstance(audio_bytes, bytearray):
                audio_bytes = bytes(audio_bytes)
                
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={"Content-Disposition": "inline"}
            )
    
    # 没有可用音频
    raise HTTPException(status_code=404, detail="没有可用的音频数据")

@router.websocket("/synthesize/stream")
async def websocket_tts_stream(websocket: WebSocket):
    """通过WebSocket进行流式合成"""
    try:
        await websocket.accept()
        
        # 获取请求参数
        request_data = await websocket.receive_json()
        
        # 验证参数
        if 'text' not in request_data:
            await websocket.send_json({"type": "error", "message": "缺少text参数"})
            await websocket.close()
            return
        
        if 'voice_id' not in request_data:
            await websocket.send_json({"type": "error", "message": "缺少voice_id参数"})
            await websocket.close()
            return
        
        # 提取参数
        text = request_data['text']
        voice_id = request_data['voice_id']
        params = request_data.get('params', {})
        
        # 获取声音信息
        voice = get_voice_by_id(voice_id)
        if not voice:
            await websocket.send_json({
                "type": "error", 
                "message": f"找不到声音: {voice_id}"
            })
            await websocket.close()
            return
        
        # 根据声音类型配置合成
        if voice["type"] == "pretrained":
            # 预训练声音，使用SFT模式
            await websocket.send_json({"type": "info", "message": "使用预训练音色合成..."})
            
            # 设置合成模式
            params["mode"] = "sft"
            
            # 开始流式合成
            await synthesize_speech_streaming(
                websocket,
                text,
                voice_id,
                params
            )
            
        elif voice["type"] == "user-uploaded":
            # 用户上传声音，使用zero-shot克隆
            await websocket.send_json({"type": "info", "message": "使用声音复刻合成..."})
            
            # 获取参考音频和文本
            prompt_audio = voice.get("reference_audio")
            prompt_text = voice.get("reference_text")
            
            # 自动查找参考资料
            if not prompt_audio or not prompt_text:
                await websocket.send_json({
                    "type": "info", 
                    "message": "尝试自动获取参考音频和文本..."
                })
                
                # 尝试标准路径
                if voice_id.startswith("user_"):
                    # 导入设置
                    from app.core.config import settings
                    
                    # 构建参考路径
                    reference_path = os.path.join(settings.UPLOAD_DIR, "user_voices", voice_id, "reference.wav")
                    if os.path.exists(reference_path):
                        await websocket.send_json({
                            "type": "info", 
                            "message": "已找到参考音频"
                        })
                        prompt_audio = reference_path
                        
                        # 默认文本
                        if not prompt_text:
                            prompt_text = "这是一段用于语音合成的参考音频。"
                            await websocket.send_json({
                                "type": "info", 
                                "message": "使用默认参考文本"
                            })
            
            # 检查是否有必要资源
            if not prompt_audio or not prompt_text:
                await websocket.send_json({
                    "type": "error", 
                    "message": f"缺少参考音频或文本: {voice_id}"
                })
                await websocket.close()
                return
            
            # 设置合成模式
            params["mode"] = "zero_shot"
            
            # 开始流式合成
            await synthesize_speech_streaming(
                websocket,
                text,
                voice_id,
                params,
                prompt_audio,
                prompt_text
            )
            
        else:
            await websocket.send_json({
                "type": "error", 
                "message": f"不支持的声音类型: {voice['type']}"
            })
            await websocket.close()
            
    except WebSocketDisconnect:
        print("WebSocket连接断开")
    except Exception as e:
        print(f"流式合成错误: {traceback.format_exc()}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
        finally:
            try:
                await websocket.close()
            except:
                pass
@router.get("/latest_audio")
async def get_latest_audio():
    """直接返回最新生成的音频"""
    from app.services.shared_storage import LATEST_AUDIO
    
    if not LATEST_AUDIO["data"]:
        raise HTTPException(status_code=404, detail="没有可用的音频数据")
    
    return Response(
        content=LATEST_AUDIO["data"],
        media_type="audio/wav",
        headers={
            "Content-Disposition": "inline",
            "X-Audio-Duration": str(LATEST_AUDIO["duration"]),
            "X-Audio-Timestamp": str(LATEST_AUDIO["timestamp"])
        }
    )