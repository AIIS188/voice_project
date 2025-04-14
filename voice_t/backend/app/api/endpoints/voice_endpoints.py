"""Voice API Endpoints

This module provides API endpoints for the unified voice library.
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Optional
import urllib.parse
import os
import tempfile
from app.core.config import settings
from app.services.unified_voice_service import (
    get_all_voices, 
    get_voice_by_id, 
    get_voice_preview_path,
    add_user_voice,
    delete_voice,
    # Removed generate_pretrained_previews as it's no longer needed
)

PREVIEW_DIR = os.path.join(settings.UPLOAD_DIR, "voice_previews")
USER_VOICES_DIR = os.path.join(settings.UPLOAD_DIR, "user_voices")
router = APIRouter()

@router.get("/list")
async def list_voices():
    """List all available voices"""
    voices = get_all_voices()
    return {"items": voices}

@router.get("/{voice_id}")
async def get_voice(voice_id: str):
    """Get a specific voice by ID"""
    voice = get_voice_by_id(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")
    return voice

@router.get("/preview/{voice_id}")
async def get_voice_preview(voice_id: str):
    try:
        # URL 解码
        decoded_voice_id = urllib.parse.unquote(voice_id)
        print(f"查找音频预览: {decoded_voice_id} (原始: {voice_id})")
        
        # 尝试获取预览文件路径
        preview_path = get_voice_preview_path(decoded_voice_id)
        
        if preview_path and os.path.exists(preview_path):
            print(f"找到匹配文件: {preview_path}")
            
            # 获取文件名，并确保正确处理编码
            filename = os.path.basename(preview_path)
            # 使用 UTF-8 编码处理文件名
            safe_filename = urllib.parse.quote(filename)
            
            # 返回预览文件，添加合适的头信息来确保正确播放
            headers = {
                # 使用 attachment 而不是 inline 以避免编码问题
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Accept-Ranges": "bytes"  # 支持范围请求，对音频流式传输很重要
            }
            
            return FileResponse(
                path=preview_path,
                media_type="audio/wav",  # 确保正确的媒体类型
                headers=headers
            )
        
        # 如果到达这里，说明没有找到预览文件
        print(f"没有可用的预览: {decoded_voice_id}")
        raise HTTPException(status_code=404, detail=f"未找到音频预览: {decoded_voice_id}")
        
    except Exception as e:
        print(f"获取预览时出错: {e}")
        # 提供更详细的错误信息以便调试
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/upload")
async def upload_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    reference_text: str = Form(""),
):
    """上传新的声音样本"""
    try:
        # 打印接收到的数据用于调试
        print(f"接收上传请求 - 文件: {file.filename}, 名称: {name}")
        print(f"描述: {description}, 标签: {tags}, 参考文本: {reference_text}")
        
        # 验证输入
        if not file.filename or not file.filename.lower().endswith(('.wav', '.mp3')):
            raise HTTPException(status_code=400, detail="文件必须是WAV或MP3格式")
        
        # 检查参考文本是否提供
        if not reference_text:
            raise HTTPException(status_code=400, detail="必须提供参考文本")
        
        # 处理标签
        tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
        print(f"处理后的标签列表: {tag_list}")
        
        # 确保上传目录存在
        os.makedirs(USER_VOICES_DIR, exist_ok=True)
        
        # 保存上传文件到临时位置
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        print(f"文件已保存到临时路径: {temp_path}")
        
        try:
            # 添加声音到库
            voice = await add_user_voice(
                name=name,
                description=description,
                tags=tag_list,
                audio_file_path=temp_path,
                reference_text=reference_text
            )
            
            if not voice:
                raise HTTPException(status_code=500, detail="添加声音失败")
            
            print(f"声音添加成功: {voice['id']}")
            return {"success": True, "voice": voice}
        except Exception as e:
            print(f"添加声音时出错: {e}")
            raise HTTPException(status_code=500, detail=f"添加声音失败: {str(e)}")
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
                print(f"已删除临时文件: {temp_path}")
    except HTTPException:
        # 直接重新抛出HTTP异常
        raise
    except Exception as e:
        # 记录详细错误信息并返回友好的错误消息
        import traceback
        error_detail = traceback.format_exc()
        print(f"上传处理未捕获异常:\n{error_detail}")
        raise HTTPException(status_code=500, detail=f"上传处理失败: {str(e)}")

@router.delete("/{voice_id}")
async def remove_voice(voice_id: str):
    """Delete a voice from the library"""
    result = await delete_voice(voice_id)
    if not result:
        raise HTTPException(status_code=404, detail="Voice not found or cannot be deleted")
    
    return {"success": True}

# Removed the '/generate-previews' endpoint as it's no longer needed

@router.get("/direct-preview/{voice_id}")
async def get_direct_preview(voice_id: str):
    """
    直接通过语音ID提供音频预览，使用标准文件名格式
    例如: /api/voice/direct-preview/中文女
    """
    try:
        # URL 解码语音ID
        decoded_voice_id = urllib.parse.unquote(voice_id)
        print(f"直接获取预览文件，语音ID: {decoded_voice_id}")
        
        # 构建标准文件名
        filename = f"{decoded_voice_id}_preview.wav"
        
        # 构建完整路径
        full_path = os.path.join(PREVIEW_DIR, filename)
        
        if not os.path.exists(full_path):
            print(f"标准文件不存在，尝试其他匹配: {full_path}")
            
            # 尝试查找匹配的文件
            try:
                files = os.listdir(PREVIEW_DIR)
                for file in files:
                    if decoded_voice_id in file:
                        full_path = os.path.join(PREVIEW_DIR, file)
                        print(f"找到匹配文件: {full_path}")
                        break
                else:
                    print(f"无法找到匹配文件")
                    raise HTTPException(status_code=404, detail=f"未找到语音ID的预览文件: {decoded_voice_id}")
            except Exception as e:
                print(f"尝试查找匹配文件时出错: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        print(f"提供文件: {full_path}")
        
        # 返回文件响应
        response = FileResponse(
            path=full_path,
            media_type="audio/wav",
            headers={"Accept-Ranges": "bytes"}
        )
        
        return response
    except Exception as e:
        print(f"直接提供预览时出错: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))