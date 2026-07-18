# Reasonix Web Bridge

将 Chrome/Edge 浏览器中的 Gemini 网页端接入 Reasonix，实现「Gemini 出脑力、本地模型出体力」的协同架构。支持纯文本和图片上传。

[![Platform](https://img.shields.io/badge/platform-Windows-blue)]()
[![Browser](https://img.shields.io/badge/browser-Edge%20%7C%20Chrome-green)]()
[![Python](https://img.shields.io/badge/python-3.7%2B-yellow)]()

---

## 怎么用

```
git clone https://github.com/slowside45/reasonix-web-bridge.git
cd reasonix-web-bridge
```

用 Reasonix 打开目录，输入 `/gemini-mode`。首次运行自动安装依赖。

---

## 提供的能力

| 功能 | 说明 |
|------|------|
| 纯文本发送 | 100% 可靠，支持中文，自动去重，流式回复不截断 |
| 图片上传 | PowerShell 复制图片到剪贴板 → pyautogui Ctrl+V 粘贴到 Gemini |
| `ask_gemini_web` | MCP 工具：发送文本+图片，自动等待回复 |
| `setup_gemini_browser` | 自动检测 Edge/Chrome，一键启动 CDP 调试模式 |
| `check_gemini_status` | 检查浏览器连接和登录状态 |

---

## 依赖

```bash
pip install websockets pyautogui pyperclip
python install.py
```

---

## 回复检测（已冻结）

| 参数 | 值 |
|------|:--:|
| 文本阈值 | `>0`（不过滤任何长度） |
| 去重方式 | `__KNOWN_TEXTS` Set（JS 端动态快照） |
| 稳定性检测 | 5s 预热 + 连续 10 次长度不变 |
| 超时 | 90s |
| count 依赖 | 无（paste 后 DOM 重建不可靠） |

---

## 图片上传方案

1. PowerShell `SetForegroundWindow` 激活 Edge
2. PowerShell `System.Windows.Forms.Clipboard::SetImage` 复制图片数据
3. pyautogui `hotkey('ctrl','v')` 物理粘贴
4. 等待预览出现 → 注入文本 → 发送

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GEMINI_CDP_PORT` | `9222` | 远程调试端口 |
| `GEMINI_USER_DATA_DIR` | `~/.gemini-mcp-browser-profile` | 浏览器 Profile |
| `PYTHONIOENCODING` | `utf-8` | 自动配置 |

---

## 文件结构

```
reasonix-web-bridge/
├── gemini_web_bridge.py               # MCP 服务器 + CDP 逻辑
├── install.py                         # 一键安装
├── .mcp.json                          # MCP 配置
├── .reasonix/skills/gemini-mode/
│   └── SKILL.md                       # gemini-mode Skill
└── README.md
```

## 注意

- 首次使用需在浏览器登录 Google 账号
- Edge 150+ 必须 `--disable-background-mode`
- 图片上传需要 Edge 窗口可见（自动激活）

## 致谢

灵感来自 @ziwang-Physics AgentChat 项目对低成本高性能 Agent 协同架构的探索。
