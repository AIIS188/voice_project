@echo off
TITLE 声教助手启动脚本 (Conda版，含CosyVoice)
chcp 65001 >nul

echo [信息] 正在启动声教助手...

REM 设置颜色
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
set "GREEN=%ESC%[92m"
set "YELLOW=%ESC%[93m"
set "RED=%ESC%[91m"
set "RESET=%ESC%[0m"

REM Conda环境名称
set "CONDA_ENV_NAME=cosyvoice3"

REM 创建日志目录
if not exist logs mkdir logs

REM 检查Conda是否已安装
echo %GREEN%[信息] 检查Conda环境...%RESET%
where conda >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo %RED%[错误] Conda未安装，请先安装Anaconda或Miniconda%RESET%
    pause
    exit /b 1
)

REM 检查Conda环境是否存在，不存在则创建
conda env list | findstr /C:"%CONDA_ENV_NAME%" >nul
if %ERRORLEVEL% NEQ 0 (
    echo %GREEN%[信息] 创建Conda虚拟环境: %CONDA_ENV_NAME%%RESET%
    call conda create -n %CONDA_ENV_NAME% python=3.10 -y
) else (
    echo %GREEN%[信息] Conda虚拟环境已存在: %CONDA_ENV_NAME%%RESET%
)

REM 检查CosyVoice相关目录
echo %GREEN%[信息] 检查CosyVoice服务...%RESET%
if not exist backend\third_party mkdir backend\third_party
if not exist backend\pretrained_models mkdir backend\pretrained_models

REM 检查CosyVoice模型
if not exist backend\pretrained_models\CosyVoice-300M-SFT (
    echo %YELLOW%[警告] CosyVoice模型未找到%RESET%
    echo %YELLOW%[警告] 首次使用时，您需要手动下载CosyVoice模型%RESET%
    echo %YELLOW%[警告] 您可以在启动后通过管理界面下载，或使用以下命令：%RESET%
    echo %YELLOW%[警告] conda activate %CONDA_ENV_NAME%%RESET%
    echo %YELLOW%[警告] pip install modelscope-cli%RESET%
    echo %YELLOW%[警告] cd backend\pretrained_models%RESET%
    echo %YELLOW%[警告] ms-cli download --model iic/CosyVoice-300M-SFT --target CosyVoice-300M-SFT%RESET%
) else (
    echo %GREEN%[信息] CosyVoice模型已存在%RESET%
)

REM 更新配置文件
if exist backend\.env (
    findstr /C:"COSYVOICE_MODEL_DIR" backend\.env >nul
    if %ERRORLEVEL% NEQ 0 (
        echo %GREEN%[信息] 更新配置文件：添加CosyVoice配置%RESET%
        echo. >> backend\.env
        echo # CosyVoice配置 >> backend\.env
        echo COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice-300M-SFT >> backend\.env
        echo COSYVOICE_ENABLED=true >> backend\.env
    )
) else (
    echo %GREEN%[信息] 创建配置文件：添加CosyVoice配置%RESET%
    echo # CosyVoice配置 > backend\.env
    echo COSYVOICE_MODEL_DIR=pretrained_models/CosyVoice-300M-SFT >> backend\.env
    echo COSYVOICE_ENABLED=true >> backend\.env
)

REM 使用Conda激活环境并安装依赖
echo %GREEN%[信息] 在Conda环境中安装依赖...%RESET%
call conda activate %CONDA_ENV_NAME%

REM 安装系统级依赖
echo %GREEN%[信息] 安装基础系统依赖...%RESET%
call conda install -y numpy scipy pandas scikit-learn matplotlib ffmpeg libsndfile

REM 安装Python依赖
echo %GREEN%[信息] 安装Python依赖...%RESET%
cd backend
pip install -r requirements.txt

REM 安装CosyVoice特定依赖
echo %GREEN%[信息] 安装CosyVoice依赖...%RESET%
pip install torch torchaudio librosa soundfile

REM 启动后端服务
echo %GREEN%[信息] 启动后端服务...%RESET%
start cmd /k "title 声教助手后端服务 & call conda activate %CONDA_ENV_NAME% & python run.py > ..\logs\backend.log 2>&1"
cd ..

REM 启动前端服务
echo %GREEN%[信息] 启动前端服务...%RESET%
cd frontend
call npm install
start cmd /k "title 声教助手前端服务 & npm run dev > ..\logs\frontend.log 2>&1"
cd ..

echo %GREEN%[信息] 声教助手已启动！%RESET%
echo 前端服务地址: http://localhost:3000
echo 后端服务地址: http://localhost:8000
echo.
echo CosyVoice高级合成功能已启用，可通过菜单访问

pause