# EchoAgent

Echo 是一个**观察型桌面 AI Agent**：它优先理解你当前的屏幕上下文，再给出协作建议，而不是接管你的操作。

---

## 项目定位

和传统自动化 Agent 的差异：

- **不是代操作**：Echo 不默认替用户执行动作。
- **强调协作感**：基于当前场景给出提示、提醒与建议。
- **保留决策权**：最终操作始终由用户确认。
- **能力按需调用**：仅在需要时使用工具、视觉、记忆、RAG 等能力。

---

## 核心能力

- 文本对话（流式输出）
- 视觉理解（聊天模式 / 观察模式）
- 分层记忆（L0/L1/L2）
- 工具调用（时间、剪贴板、文件等）
- TTS 语音播报
- RAG（领域知识检索）
- Electron 桌面交互

---

## 项目结构（当前）

```text
EchoAgent/
├── api_server.py              # FastAPI + WebSocket 服务入口
├── app.py                     # Streamlit 入口（简化体验）
├── config.py                  # 配置读取
├── core/
│   ├── agent.py               # Agent 主流程
│   ├── memory.py              # 分层记忆
│   ├── llm_service.py         # LLM 调用
│   ├── vision_service.py      # 视觉模型调用
│   ├── tts_service.py         # 语音合成
│   ├── rag_service.py         # 检索增强
│   ├── crawler/               # 网页抓取与清洗
│   └── tools/                 # 工具系统
└── desktop-app/
    ├── index.html             # 前端页面入口
    ├── main.js                # Electron 主进程
    ├── preload.js             # Electron 预加载
    ├── motion.html            # 动作面板
    └── assets/                # Live2D 与依赖资源
```

---

## 本地启动

### 1) 安装依赖

```bash
pip install -r requirements.txt
```

### 2) 启动后端（桌面联动）

```bash
python api_server.py
```

默认监听 `0.0.0.0:18000`。

### 3) 启动简化前端（可选）

```bash
streamlit run app.py
```

---

## 前端重构建议（高优先级）

你提到已完成“2000 行 HTML 拆分”，这是非常正确的方向。建议按以下目标持续推进：

- 拆分为 `modules/*`（连接、观察、音频、字幕、设置）
- 将状态集中到单一 store（避免全局变量散落）
- UI 与业务逻辑分离（DOM 操作和业务流程不要混写）
- 引入事件总线 / 命令流（减少跨模块直接调用）

可参考：`docs/frontend-architecture-review.md` 与 `docs/frontend-engineering-constraints.md`。

---

## 文档导航

- `docs/frontend-architecture-review.md`：前端结构评审与拆分建议
- `docs/frontend-engineering-constraints.md`：防止“再次屎山化”的工程约束清单

---

## License

MIT
