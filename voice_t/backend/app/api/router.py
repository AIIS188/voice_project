from fastapi import APIRouter
from app.api.endpoints import course, cosyvoice_tts, course_service
from app.api.endpoints.voice_endpoints import router as voice_router
from app.api.endpoints.tts_endpoints import router as unified_tts_router

api_router = APIRouter(prefix="/api")

# Voice library management
api_router.include_router(voice_router, prefix="/voice", tags=["声音库"])

# Course processing
api_router.include_router(course.router, prefix="/course", tags=["课件处理"])

# Course service processing
api_router.include_router(course_service.router, prefix="/course_service", tags=["课件服务"])

# Legacy CosyVoice TTS endpoints (for backward compatibility)
api_router.include_router(cosyvoice_tts.router, prefix="/cosyvoice", tags=["CosyVoice语音合成"])

# New unified TTS endpoints
api_router.include_router(unified_tts_router, prefix="/tts", tags=["统一语音合成"])