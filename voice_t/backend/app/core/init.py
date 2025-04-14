from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware


import os
import sys
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)
from app.core.config import settings
from app.api.router import api_router
from app.services.integration import register_startup, get_app_metrics
from app.services.cosyvoice_tts import init_cosyvoice_tts_service, cosyvoice_model
from app.models.metrics import AppMetrics
from prometheus_client import Counter, Histogram, start_http_server


# 监控指标
TTS_REQUESTS = Counter('tts_requests_total', 'Total number of TTS requests')
TTS_ERRORS = Counter('tts_errors_total', 'Total number of TTS errors')
TTS_PROCESSING_TIME = Histogram('tts_processing_seconds', 'Time spent processing TTS requests')


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    description = """
    声教助手 API - 基于AI语音合成的教学声音处理软件

    ## 功能

    * **声音样本库**: 管理声音样本，支持上传、录制与分析
    * **个性化语音讲解**: 将文本转换为自然流畅的语音，支持多种参数调整
    * **标准语言输出**: 生成标准语言发音，如普通话、英语等
    * **课件语音化**: 解析PPT课件并生成语音讲解，制作有声课件
    * **声音置换**: 替换音视频中的声音，自动生成字幕
    * **CosyVoice语音合成**: 使用通义千问实验室CosyVoice进行高质量语音合成
    """

    app = FastAPI(
        title="声教助手 API",
        description=description,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 配置CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(api_router)
    
    # 添加应用指标路由
    @app.get("/api/metrics", response_model=AppMetrics, tags=["系统"])
    async def get_metrics():
        """获取系统运行指标"""
        return await get_app_metrics()
        
    # 首页
    @app.get("/", tags=["系统"])
    async def root():
        """API根路径"""
        return {
            "name": "声教助手 API",
            "description": "基于AI语音合成的教学声音处理软件API",
            "version": "1.0.0",
            "docs_url": "/api/docs"
        }
    
    # 健康检查
    @app.get("/health", tags=["系统"])
    async def health_check():
        """API健康检查"""
        return {"status": "ok", "service": "voice-teaching-assistant"}
    
    # 注册启动事件
    register_startup(app)
    
    return app

# 启动监控服务器
def start_metrics_server(port=8000):
    start_http_server(port)
    print(f"Metrics server started on port {port}")

# 注册应用启动函数
async def startup_event():
    """服务启动时执行的初始化任务"""
    # 导入必要的模块
    from app.services.unified_voice_service import load_voice_db
    from app.services.cosyvoice_tts import init_cosyvoice_tts_service
    
    # 初始化声音库
    load_voice_db()
    
    # 初始化TTS服务
    await init_cosyvoice_tts_service()
    
    print("服务初始化完成")