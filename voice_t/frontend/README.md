# 声教助手 - 前端

声教助手是一款基于AI语音合成的教学声音处理软件，前端基于React和Ant Design构建。

## 环境要求

- Node.js 14.0.0 或更高版本
- npm 6.14.0 或更高版本

## 安装与运行

1. 安装依赖

```bash
npm install
```

2. 开发模式运行

```bash
npm run dev
```

应用将在 http://localhost:3000 上运行

3. 构建生产版本

```bash
npm run build
```

## 功能模块

- **声音样本库**：管理声音样本，支持上传和录制
- **个性化语音讲解**：文本转语音，支持自定义声音和参数
- **标准语言输出**：生成标准发音语音
- **课件语音化**：将PPT课件转换为有声课件
- **声音置换与字幕**：替换音视频中的声音，自动生成字幕

## 技术栈

- **React**：用户界面构建
- **Ant Design**：UI组件库
- **React Router**：路由管理
- **Axios**：API请求
- **Vite**：构建工具

## 项目结构

```
src/
├── assets/           # 静态资源
├── components/       # 公共组件
├── pages/            # 页面组件
├── services/         # API服务
├── utils/            # 工具函数
├── App.jsx           # 应用主组件
├── main.jsx          # 入口文件
└── index.css         # 全局样式
```

## API接口

前端通过以下接口与后端通信：

- **声音样本**: `/api/voice/...`
- **语音合成**: `/api/tts/...`
- **课件处理**: `/api/course/...`
- **声音置换**: `/api/replace/...`

详细API文档请参考后端服务文档。