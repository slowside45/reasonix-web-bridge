# Reasonix Web Bridge

将 Edge 浏览器中的 Gemini 网页端接入 Reasonix，实现「Gemini 出脑力、本地模型出体力」。支持纯文本和图片上传。Windows。

[![Python](https://img.shields.io/badge/python-3.7%2B-yellow)]()
[![Browser](https://img.shields.io/badge/browser-Edge-green)]()

---

## 快速开始

```
git clone https://github.com/slowside45/reasonix-web-bridge.git
cd reasonix-web-bridge
```

用 Reasonix 打开目录，输入 `/gemini-mode`。首次运行会自动：
1. 安装依赖（websockets, pyautogui, pyperclip）
2. 生成 MCP 配置
3. 安装 Skill
4. 启动 Edge 浏览器 → 提示登录 Gemini

之后每条消息自动转发给 Gemini。

---

## 功能

| 功能 | 说明 |
|------|------|
| 纯文本 | 100% 可靠，中文支持，流式回复不截断 |
| 图片上传 | PowerShell 剪贴板 + pyautogui 物理 Ctrl+V |
| 最小化支持 | 自动激活 Edge 窗口 |
| MCP 工具 | ask_gemini_web / setup_gemini_browser / check_gemini_status |

---

## 手动安装

```bash
pip install websockets pyautogui pyperclip
python install.py
```

---

## 文件结构

```
reasonix-web-bridge/
├── gemini_web_bridge.py    # CDP 核心逻辑
├── install.py              # 一键安装
├── .mcp.json               # MCP 配置
├── .reasonix/skills/gemini-mode/
│   └── SKILL.md            # gemini-mode Skill
└── README.md
```

## 注意

- 首次使用需在浏览器登录 Google 账号
- Edge 150+ 必须 `--disable-background-mode`
- 图片上传需要 Edge 窗口可见（自动激活）
- Python 需在 PATH 中

## 致谢

灵感来自 @ziwang-Physics AgentChat 项目。
