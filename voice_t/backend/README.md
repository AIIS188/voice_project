# 声教助手 - 后端服务

声教助手是一款基于AI语音合成的教学声音处理软件，后端基于FastAPI构建。

## 环境要求

- Python 3.9 或更高版本
- 依赖包见 requirements.txt

## 安装与运行

1. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # 在Windows上使用: venv\Scripts\activate
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 运行服务

```bash
python run.py
```

服务将在 http://localhost:8000 上启动，API文档可在 http://localhost:8000/docs 访问。

## 功能模块

- **声音样本库**: 管理声音样本文件，支持上传和录制
- **语音合成**: 文本转语音，支持自定义声音和参数
- **课件处理**: 上传课件并提取文本，生成有声课件
- **声音置换**: 替换音视频中的声音，生成字幕

## API接口

详细的API接口文档请参考 http://localhost:8000/docs

## 文件存储

上传的文件默认保存在 `./uploads` 目录下，可通过环境变量 `UPLOAD_DIR` 修改。

## 配置

主要配置位于 `app/core/config.py`，可通过环境变量进行覆盖。

可用的环境变量：

- `MONGODB_URL`: MongoDB连接URL（如果使用数据库）
- `DATABASE_NAME`: 数据库名称
- `SECRET_KEY`: 安全密钥
- `UPLOAD_DIR`: 上传文件存储目录
- `MODELS_DIR`: 模型文件目录