# Frontend 架构评审（本次）

> 目标：你要求的第 1 件事——快速审查前端拆分后的结构、边界、命名。

## 结论摘要

- 当前仓库中 `desktop-app` 仍以 `index.html` 为核心入口，尚未看到显式的 `modules/` 或 `src/` 多文件拆分结构。
- 这意味着：
  1. 你的“史诗级拆分”可能还未提交到当前分支；或
  2. 拆分是在其它目录/分支中完成。

不影响结论：你的方向是正确的，建议继续按下面的边界模型收敛。

---

## 建议的目标目录

```text
desktop-app/
├── index.html                  # 只保留容器 DOM 和资源入口
├── styles/
│   ├── base.css
│   ├── panel.css
│   └── subtitle.css
├── modules/
│   ├── app-init.js             # 启动编排
│   ├── ws-client.js            # WebSocket 通信
│   ├── settings-store.js       # 设置状态与持久化
│   ├── observer-controller.js  # 观察模式
│   ├── subtitle-controller.js  # 字幕/打字机
│   ├── audio-queue.js          # 音频流排队与播放
│   ├── live2d-controller.js    # Live2D 动作与焦点追踪
│   └── motion-panel.js         # 动作面板逻辑
└── utils/
    ├── logger.js
    ├── event-bus.js
    └── normalize.js
```

---

## 模块边界建议（关键）

### 1) ws-client.js

**只负责**连接、重连、消息收发。

- 输入：server 地址、回调注册
- 输出：`onChunk/onDone/onError/onAudio`
- 禁止：直接操作 DOM

### 2) observer-controller.js

**只负责**屏幕采样、变化检测、触发策略。

- 输入：Observer 开关、采样参数
- 输出：结构化事件（`{type, frame, level}`）
- 禁止：直接调用字幕、音频逻辑

### 3) subtitle-controller.js

**只负责**字幕状态机（append/flush/hide timer）。

- 输入：文本片段
- 输出：DOM 更新
- 禁止：理解 WebSocket 业务字段

### 4) settings-store.js

**只负责**读取、校验、保存配置。

- 输入：表单对象
- 输出：规范化配置对象
- 禁止：发请求、弹 UI 提示

### 5) app-init.js

**唯一编排层**：把各模块串起来。

---

## 命名与接口规范（建议）

- 事件名：`domain.action`（如 `ws.chunk`、`observer.frame_ready`）
- 方法命名：`verb + target`（`connectSocket`, `saveSettings`）
- 对外数据统一对象：避免裸字符串多处拼接

---

## 风险清单（若不拆）

- 修改字幕逻辑误伤 WebSocket 流程
- 观察模式与音频队列耦合导致重构困难
- Electron 与 Browser 兼容分支散落，调试成本高

---

## 下一步落地建议（可执行）

1. 先拆 `settings-store.js` 与 `ws-client.js`（风险最低，收益最高）
2. 再拆 `subtitle-controller.js`（减少 UI 噪音）
3. 最后拆 `observer-controller.js`（复杂度最高）

每次拆分后做一次 smoke test：

- 文本对话可用
- 设置可保存
- 观察模式可开关
- 音频流顺序播放正常
