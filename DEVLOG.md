# Reasonix Web Bridge — 项目开发记录 (2026-07-17)

## 项目目标

将 Chrome/Edge 浏览器中的网页版 Gemini 接入 Reasonix，实现「Gemini 出脑力、本地模型出体力」的协同架构。
用户只需 `/gemini-mode` 激活，之后的每条消息都会自动转发给 Gemini，拿到回复后由本地 Agent 执行文件操作。

---

## 架构

```
用户 → Reasonix (DeepSeek 底座模型) → MCP 调用 → gemini_web_bridge.py
    → Edge CDP WebSocket (port 9222) → 网页 Gemini → 抓取回复 → 返回 Reasonix
```

- **脑（规划）**：网页 Gemini（长上下文、顶级推理、免费）
- **手（执行）**：Reasonix / DeepSeek（读取 Gemini 回复 → 创建文件、目录）

---

## 已实现功能

### ✅ MCP 服务器 (`gemini_web_bridge.py`)
- 纯 Python stdio MCP，零第三方 SDK 依赖（仅 websockets）
- 3 个工具：
  - `ask_gemini_web` — 发 prompt 到 Gemini 网页，返回回复
  - `setup_gemini_browser` — 跨平台自动检测 Chrome/Edge/Brave/Chromium，启动调试模式
  - `check_gemini_status` — 检查浏览器连接和登录状态
- CDP 支持：多浏览器（Chrome/Edge/Brave/Chromium）、多平台（Win/macOS/Linux）
- 中文 UTF-8 支持（`ensure_ascii=False`）
- WebSocket 大消息支持（`max_size=None`）

### ✅ Skill (`gemini-mode`)
- `/gemini-mode` 一键激活
- 自动检查 Edge CDP 端口
- 自动启动浏览器并提示登录
- 自动将消息转发 Gemini，然后本地执行

### ✅ 一键安装脚本 (`install.py`)
- `pip install websockets`
- 生成 `.mcp.json`（含 `PYTHONIOENCODING=utf-8` 环境变量）
- 安装 Skill
- Skill 支持自举（环境缺失时自动触发安装）

### ✅ GitHub 仓库就绪
- 仓库：`slowside45/reasonix-web-bridge`
- 文件：`gemini_web_bridge.py` + `install.py` + `SKILL.md` + `README.md`
- 跨平台：浏览器自动检测 + OS 自动适配

---

## 未解决 / 待改进

### ❌ 多模态图片上传未成功
**状态**：图片可以注入 Gemini 输入框（用户亲眼确认），但 WebSocket 连接在文本发送阶段断开。

**尝试过的方案**：
| 方案 | 结果 | 失败原因 |
|------|------|----------|
| `DOM.setFileInputFiles` → 已有 input[type=file] | ❌ | Gemini 没有暴露传统 file input |
| `navigator.clipboard.write()` + Ctrl+V | ❌ | CDP 环境无用户手势授权 |
| `ClipboardEvent('paste')` 直接 dispatch | ❌ | `clipboardData` 不被 React 合成事件处理 |
| 创建隐藏 input → `setFileInputFiles` | ⚠️ 图片出现但 WS 断开 | 文本注入阶段 WebSocket 崩溃 |

**问题分析**：纯 CDP WebSocket 方案在图片+文本的**序列化操作**中不够可靠。注入图片后输入框状态改变，CDP 连接可能因 `Input.dispatchKeyEvent` 等调用而断连。

**建议后续方向**：
1. 接受纯文本输入（无图）
2. 引入 Playwright 替换纯 CDP（如 AgentChat 的做法）
3. 在 prompt 中嵌入 base64 数据 URL，用 DeepSeek 的本地视觉能力处理

---

## 发布文件清单

```
reasonix-web-bridge/
├── install.py                # 一键安装（依赖安装 + 配置生成 + Skill 安装）
├── gemini_web_bridge.py      # MCP 服务器主脚本（跨平台）
├── .reasonix/skills/gemini-mode/
│   └── SKILL.md              # gemini-mode Skill
└── README.md                 # 文档（中文，跨平台说明）
```

---

## 致谢

灵感来自 ziwang-Physics/AgentChat 项目（Node.js + Playwright 多 Provider 架构）
