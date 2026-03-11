# EchoAgent

<div align="center">

### 🫧 Echo — 观察型桌面 AI Agent  
**不是替你操作，而是陪你观察、理解、提示、协作。**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)](#)
[![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?logo=electron&logoColor=white)](#)
[![Status](https://img.shields.io/badge/Stage-MVP-orange)](#)
[![License](https://img.shields.io/badge/License-MIT-green)](#)

</div>

---

## ✨ 项目简介

**EchoAgent** 是一个强调“观察与协作”的桌面 AI Agent。  
和传统自动化 Agent 不同，Echo 的设计理念是：

- 👀 **理解当前屏幕与上下文**
- 🧠 **结合短中期记忆进行辅助判断**
- 🛟 **在关键时刻主动提醒，而不是接管控制**
- 🙋 **始终把最终决策权交给用户**

> Echo 的目标不是“替你做事”，而是“在你做事时，成为更懂你的智能搭子”。

---

## 🧩 核心能力

- **多模态交互**：文本 / 图片 / 语音输入  
- **观察模式（Observer）**：屏幕状态感知 + 变化检测 + 分级触发提醒  
- **分层记忆系统**：L0 观察、L1 行为片段、L2 上下文事件  
- **工具调用能力**：时间、剪贴板、文件等系统工具  
- **流式回复与 TTS**：低延迟输出 + 语音播报  
- **RAG 知识检索**：支持领域知识增强（如 Terraria 场景）  
- **运行时模型配置**：可在前端设置中填写 API / Base URL / 模型名，便于同学快速试用

---

## 🏗️ 架构概览

```text
Desktop UI (Electron / Browser)
        │
        │ WebSocket / HTTP
        ▼
    FastAPI Server
        │
        ├─ EchoAgent
        │   ├─ LLMService
        │   ├─ VisionService
        │   ├─ MemoryManager (L0/L1/L2)
        │   ├─ ToolRegistry
        │   └─ RAGService (optional)
        │
        └─ TTSService
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd EchoAgent
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
python api_server.py
```

默认服务地址：

```
http://127.0.0.1:18000
```

### 4. 打开前端

桌面版：

```
启动 Electron 客户端
```

浏览器版：

```
http://127.0.0.1:18000/ui/index.html
```

---

## ⚙️ 配置方式

你有两种方式配置模型：

### A. `.env`（传统方式）

适合本机长期开发。

### B. 前端设置页（推荐）

在设置弹窗中填写：

- Chat API Key / Base URL / Model  
- Vision API Key / Base URL / Model  

保存后即可下发到后端运行时生效（无需重启进程），并保存在本地浏览器存储中。

---

## 🧪 典型使用场景

- 写代码时让 Echo 观察任务上下文，在关键时刻提醒  
- 游戏场景（如 Terraria）中进行状态识别与节奏辅助  
- 日常学习 / 办公中的轻量协作与陪伴式 AI 反馈  

---

## 📁 项目结构（简版）

```text
.
├── api_server.py           # FastAPI + WebSocket 主入口
├── app.py                  # Streamlit 入口（可选）
├── config.py               # 配置读取
├── core/
│   ├── agent.py            # EchoAgent 主流程
│   ├── llm_service.py      # LLM 调用
│   ├── vision_service.py   # 视觉模型调用
│   ├── memory.py           # 分层记忆管理
│   ├── tts_service.py      # 语音合成
│   ├── rag_service.py      # 检索增强
│   └── tools/              # 工具系统
└── desktop-app/
    ├── index.html          # 前端 UI
    └── main.js             # Electron 主进程
```

---

## 🛣️ Roadmap

- 更完整的工具权限控制与审计日志  
- 更稳定的多轮工具调用策略  
- 记忆层 TTL / 清理策略可视化  
- Docker 一键部署  
- 多角色 Agent 协作模式  

---

## 🤝 贡献指南

欢迎提 Issue / PR，一起把“协作型 Agent”这条路线做深。

建议提交前：

- 保持变更最小闭环  
- 补充必要说明与验证步骤  
- 避免引入与目标无关的大改  

---

## 📜 License

MIT License.

---

<div align="center">

EchoAgent = 观察 + 理解 + 协作，而不是接管。  

如果你也相信 **更自然的人机协作**，欢迎一起打磨这个项目 ✨

</div>
