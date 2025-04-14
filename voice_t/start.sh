#!/bin/bash

# 声教助手启动脚本 (Conda版，含CosyVoice)

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 日志函数
log() {
    echo -e "${GREEN}[声教助手] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[警告] $1${NC}"
}

error() {
    echo -e "${RED}[错误] $1${NC}" >&2
    exit 1
}

# Conda 环境名称
CONDA_ENV_NAME="voice_assistant"

# 项目根目录
PROJECT_ROOT=$(pwd)

# 检查 Conda 是否已安装
check_conda() {
    if ! command -v conda &> /dev/null; then
        error "Conda 未安装，请先安装 Anaconda 或 Miniconda"
    fi
}

# 创建或激活 Conda 环境
setup_conda_env() {
    # 检查环境是否存在
    if ! conda env list | grep -q "$CONDA_ENV_NAME"; then
        log "创建 Conda 虚拟环境：$CONDA_ENV_NAME"
        conda create -n "$CONDA_ENV_NAME" python=3.10 -y
    fi

    # 激活环境
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$CONDA_ENV_NAME"
}

# 安装后端依赖
setup_backend_deps() {
    log "安装后端依赖"
    
    # 使用 conda 安装系统级依赖
    conda install -y \
        numpy \
        scipy \
        pandas \
        scikit-learn \
        matplotlib \
        ffmpeg \
        libsndfile

    # 使用 pip 安装 Python 特定依赖
    pip install --upgrade pip

    # 安装核心依赖
    pip install \
        fastapi \
        uvicorn \
        pydantic \
        pydantic-settings \
        sqlalchemy \
        alembic

    # 音频处理依赖
    pip install \
        librosa \
        soundfile \
        torch \
        torchaudio

    # PaddlePaddle 及 PaddleSpeech
    # pip install \
    #     paddlepaddle \
    #     paddlespeech

    # 其他依赖
    pip install \
        python-jose \
        passlib \
        python-multipart
}

# 检查和安装 CosyVoice
setup_cosyvoice() {
    log "检查和设置 CosyVoice 服务"
    
    COSYVOICE_DIR="$PROJECT_ROOT/backend/third_party/CosyVoice"
    COSYVOICE_MODEL_DIR="$PROJECT_ROOT/backend/pretrained_models"
    
    # 创建必要的目录
    mkdir -p "$PROJECT_ROOT/backend/third_party"
    mkdir -p "$COSYVOICE_MODEL_DIR"
    
    # 检查 CosyVoice 代码库是否已存在
    if [ ! -d "$COSYVOICE_DIR" ]; then
        log "克隆 CosyVoice 代码库"
        cd "$PROJECT_ROOT/backend/third_party"
        git clone https://github.com/FunAudioLLM/CosyVoice.git
        if [ $? -ne 0 ]; then
            warn "克隆 CosyVoice 代码库失败，尝试继续启动"
        fi
        cd "$PROJECT_ROOT"
    else
        log "CosyVoice 代码库已存在"
    fi
    
    # 检查 CosyVoice 模型是否已存在
    MODEL_SFT="$COSYVOICE_MODEL_DIR/CosyVoice-300M-SFT"
    if [ ! -d "$MODEL_SFT" ]; then
        log "CosyVoice 模型未找到"
        warn "首次使用时，您需要手动下载 CosyVoice 模型"
        warn "您可以在启动后通过管理界面下载，或使用以下命令："
        warn "pip install modelscope-cli"
        warn "cd $COSYVOICE_MODEL_DIR"
        warn "ms-cli download --model iic/CosyVoice-300M-SFT --target CosyVoice-300M-SFT"
    else
        log "CosyVoice 模型已存在：$MODEL_SFT"
    fi
    
    # 安装 CosyVoice 相关依赖
    log "安装 CosyVoice 依赖"
    pip install \
        torch>=1.12.0 \
        torchaudio>=0.12.0 \
        librosa>=0.9.2 \
        soundfile>=0.12.1
    
    # 检查配置文件
    ENV_FILE="$PROJECT_ROOT/backend/.env"
    if [ -f "$ENV_FILE" ]; then
        # 检查是否已经有CosyVoice配置
        if ! grep -q "COSYVOICE_MODEL_DIR" "$ENV_FILE"; then
            log "更新配置文件：添加 CosyVoice 配置"
            echo "" >> "$ENV_FILE"
            echo "# CosyVoice配置" >> "$ENV_FILE"
            echo "COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice-300M-SFT" >> "$ENV_FILE"
            echo "COSYVOICE_ENABLED=true" >> "$ENV_FILE"
        fi
    else
        log "创建配置文件：添加 CosyVoice 配置"
        echo "# CosyVoice配置" > "$ENV_FILE"
        echo "COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice-300M-SFT" >> "$ENV_FILE"
        echo "COSYVOICE_ENABLED=true" >> "$ENV_FILE"
    fi
}

# 启动后端服务
start_backend() {
    log "启动后端服务"
    cd "$PROJECT_ROOT/backend"
    python run.py > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
    BACKEND_PID=$!
    cd "$PROJECT_ROOT"
}

# 启动前端服务
start_frontend() {
    log "启动前端服务"
    cd "$PROJECT_ROOT/frontend"
    npm install
    npm run dev > "$PROJECT_ROOT/logs/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    cd "$PROJECT_ROOT"
}

# 主启动流程
main() {
    # 创建日志目录
    mkdir -p "$PROJECT_ROOT/logs"

    # 检查并设置 Conda 环境
    check_conda
    setup_conda_env

    # 安装依赖
    setup_backend_deps
    
    # 设置 CosyVoice
    setup_cosyvoice

    # 启动服务
    start_backend
    start_frontend

    # 等待并处理中断
    trap "conda deactivate; kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM
    wait
}

# 执行主流程
main

log "声教助手已启动！"
echo "前端服务地址: http://localhost:3000"
echo "后端服务地址: http://localhost:8000"
echo ""
echo "CosyVoice高级合成功能已启用，可通过菜单访问"