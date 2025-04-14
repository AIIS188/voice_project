#!/bin/bash

# 安装CosyVoice脚本
# 将CosyVoice集成到声教助手项目中

set -e  # 任何命令失败就退出

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 恢复颜色

echo -e "${GREEN}开始安装CosyVoice到声教助手项目中...${NC}"

# 检查项目环境
if [ ! -d "voice_t" ]; then
  echo -e "${RED}错误: 未找到声教助手项目目录，请在项目根目录运行此脚本${NC}"
  exit 1
fi

# 创建必要的目录
echo -e "${YELLOW}创建必要的目录...${NC}"
mkdir -p voice_t/backend/third_party
mkdir -p voice_t/backend/pretrained_models
mkdir -p voice_t/backend/logs

# 克隆CosyVoice代码库
echo -e "${YELLOW}克隆CosyVoice代码库...${NC}"
if [ ! -d "voice_t/backend/third_party/CosyVoice" ]; then
  cd voice_t/backend/third_party
  git clone https://github.com/FunAudioLLM/CosyVoice.git
  cd ../../..
else
  echo -e "${YELLOW}CosyVoice代码库已存在，跳过克隆${NC}"
fi

# 安装依赖项
echo -e "${YELLOW}安装CosyVoice依赖项...${NC}"
cd voice_t/backend
pip install torch torchaudio librosa soundfile
cd ../..

# 询问是否需要下载预训练模型
echo -e "${YELLOW}是否需要下载CosyVoice预训练模型? (y/n)${NC}"
read -p "选择: " download_model
if [[ $download_model == "y" || $download_model == "Y" ]]; then
  echo -e "${YELLOW}开始下载CosyVoice预训练模型...${NC}"
  echo -e "${YELLOW}提示: 这可能需要一些时间，请耐心等待${NC}"
  
  # 安装modelscope命令行工具(如果没有)
  pip install modelscope-cli
  
  # 下载模型
  cd voice_t/backend/pretrained_models
  
  echo -e "${YELLOW}下载CosyVoice-300M-SFT模型...${NC}"
  ms-cli download --model iic/CosyVoice-300M-SFT --target CosyVoice-300M-SFT
  
  echo -e "${YELLOW}是否需要下载CosyVoice-300M-Instruct模型(支持指令控制)? (y/n)${NC}"
  read -p "选择: " download_instruct
  if [[ $download_instruct == "y" || $download_instruct == "Y" ]]; then
    echo -e "${YELLOW}下载CosyVoice-300M-Instruct模型...${NC}"
    ms-cli download --model iic/CosyVoice-300M-Instruct --target CosyVoice-300M-Instruct
  fi
  
  cd ../../..
fi

# 复制服务和API文件
echo -e "${YELLOW}复制CosyVoice服务和API文件...${NC}"
cp -f scripts/templates/cosyvoice_tts.py voice_t/backend/app/services/
cp -f scripts/templates/cosyvoice_tts_api.py voice_t/backend/app/api/endpoints/cosyvoice_tts.py

# 更新配置文件
echo -e "${YELLOW}更新配置文件...${NC}"
if [ ! -f "voice_t/backend/.env" ]; then
  echo "# CosyVoice配置" >> voice_t/backend/.env
  echo "COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice-300M-SFT" >> voice_t/backend/.env
  echo "COSYVOICE_ENABLED=true" >> voice_t/backend/.env
else
  # 检查是否已经有CosyVoice配置
  if ! grep -q "COSYVOICE_MODEL_DIR" voice_t/backend/.env; then
    echo "" >> voice_t/backend/.env
    echo "# CosyVoice配置" >> voice_t/backend/.env
    echo "COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice-300M-SFT" >> voice_t/backend/.env
    echo "COSYVOICE_ENABLED=true" >> voice_t/backend/.env
  fi
fi

# 复制前端组件
echo -e "${YELLOW}复制前端组件...${NC}"
mkdir -p voice_t/frontend/src/components
mkdir -p voice_t/frontend/src/pages
cp -f scripts/templates/CosyVoiceTTS.jsx voice_t/frontend/src/components/
cp -f scripts/templates/CosyVoicePage.jsx voice_t/frontend/src/pages/

# 安装完成
echo -e "${GREEN}CosyVoice安装成功!${NC}"
echo -e "${YELLOW}请按照以下步骤完成配置:${NC}"
echo -e "1. 确保更新了路由配置，添加了CosyVoice路由"
echo -e "2. 重启后端服务: cd voice_t/backend && uvicorn app.main:app --reload"
echo -e "3. 重启前端服务: cd voice_t/frontend && npm start"
echo -e "${GREEN}现在您可以通过'CosyVoice高级合成'菜单访问CosyVoice功能!${NC}"