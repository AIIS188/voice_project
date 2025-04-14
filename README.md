# 声教助手 - 基于AI语音合成的教学声音处理软件

![声教助手标志](https://placekitten.com/800/200)

声教助手是一款专为教育领域设计的AI语音合成软件，帮助教师和学生创建高质量的教学语音内容。通过简单的操作，即可实现声音克隆、语音合成、课件语音化和声音置换等功能。

## 功能概述

- **声音样本库**：管理声音样本，支持上传和录制个性化声音
- **个性化语音讲解**：将文本转换为自然流畅的语音，可选择不同声音和参数
- **标准语言输出**：生成标准语言发音，适用于语言学习和发音示范
- **课件语音化**：将PPT等课件转换为有声课件，提高教学内容吸引力
- **声音置换与字幕**：替换音视频中的声音，自动生成同步字幕

## 系统架构

该项目采用前后端分离架构：

- **前端**：基于React和Ant Design构建的Web应用
- **后端**：基于FastAPI构建的RESTful API服务
- **算法模型**：基于深度学习的语音合成和处理模型

## 技术特点

- **低样本声音克隆**：仅需5-30秒的声音样本即可复制声音特征
- **高质量语音合成**：自然流畅的语音输出，MOS评分>4.0
- **实时处理能力**：响应时间<2秒，提供良好用户体验
- **教育场景定制**：针对教学内容优化的语音参数和流程

## 安装与使用

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # 在Windows上使用: venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## 应用场景

- **课件制作**：教师可以快速为PPT添加语音讲解
- **语言学习**：提供标准发音示范和练习材料
- **远程教育**：制作有声课件，方便学生自主学习
- **特殊教育**：为视障学生提供有声教材，为听障学生添加字幕

## 演示视频

[点击观看演示视频](https://example.com/demo)

## 项目文档

- [系统架构文档](./docs/architecture.md)
- [API文档](./backend/README.md)
- [前端开发指南](./frontend/README.md)
- [用户手册](./docs/user-manual.md)

## 技术栈

- **前端**：React, Ant Design, Vite
- **后端**：Python, FastAPI, librosa
- **AI模型**：FastSpeech2, HiFi-GAN, YourTTS, Whisper

## 开发团队

- 张三 - 项目负责人
- 李四 - 前端开发
- 王五 - 后端开发
- 赵六 - AI算法工程师

## 许可证

本项目采用 MIT 许可证。详情见 [LICENSE](LICENSE) 文件。