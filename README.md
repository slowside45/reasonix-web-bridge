# Reasonix Web Bridge

将 Chrome/Edge 浏览器中的 Gemini 网页端接入 Reasonix，实现「Gemini 出脑力、本地模型出体力」的协同架构。支持 Windows、macOS、Linux。

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)]()
[![Browser](https://img.shields.io/badge/browser-Chrome%20%7C%20Edge%20%7C%20Brave%20%7C%20Chromium-green)]()
[![Python](https://img.shields.io/badge/python-3.7%2B-yellow)]()

---

## 怎么用（只需两步）

```
git clone https://github.com/slowside45/reasonix-web-bridge.git
cd reasonix-web-bridge
```

然后用 Reasonix 打开这个目录，输入 `/gemini-mode`。

**首次运行会自动安装依赖、生成配置**，完成后提示重启。重启后再次 `/gemini-mode` 即可使用，之后每条消息都会自动转发给 Gemini 并本地执行。

---

## 提供的能力

| MCP 工具 | 作用 |
|----------|------|
| `ask_gemini_web` | 注入提示词到浏览器 Gemini，自动发送并抓取回复 |
| `setup_gemini_browser` | 自动检测 Chrome/Edge，一键启动调试模式 |
| `check_gemini_status` | 检查浏览器连接和登录状态 |

Skill `/gemini-mode` 激活后，Agent 会把每条消息自动转发给 Gemini、获取回复、在本地创建文件。

---

## 手动安装（备用）

如果自动安装失败，手动执行：

```bash
pip install websockets
python install.py
```

`install.py` 会：
1. 安装 `websockets` 依赖
2. 生成 `gemini_web_bridge.py`
3. 写入 `.mcp.json`（含 UTF-8 编码等环境变量）
4. 无需装 Skill（仓库自带）

---

## 兼容性

| 系统 | 浏览器 |
|------|--------|
| Windows 10/11 | Chrome、Edge |
| macOS | Chrome、Edge |
| Linux | Chrome、Chromium、Edge |

> Brave、Opera 等 Chromium 内核浏览器同样支持。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GEMINI_CDP_PORT` | `9222` | 远程调试端口 |
| `GEMINI_USER_DATA_DIR` | `~/.gemini-mcp-browser-profile` | 浏览器 Profile 目录 |
| `PYTHONIOENCODING` | `utf-8` | 自动配置，无需手动设置 |

---

## 注意

- 首次使用需在浏览器中登录 Google 账号
- Edge 150+ 远程调试必须指定 `--user-data-dir`（脚本自动处理）
- 调试端口仅绑定 `127.0.0.1`

---

## 文件结构

```
reasonix-web-bridge/
├── gemini_web_bridge.py               # MCP 服务器
├── install.py                         # 一键安装
├── .reasonix/skills/gemini-mode/
│   └── SKILL.md                       # gemini-mode Skill
└── README.md
```

## 致谢
灵感来自@ziwang-Physics AgentChatAgentChat项目对低成本高性能 Agent 协同架构的探索，同时感谢 Reasonix 社区提供的优秀文档、实践案例🙏 