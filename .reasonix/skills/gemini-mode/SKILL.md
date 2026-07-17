---
name: gemini-mode
description: 自动将每次提问转发给网页 Gemini，根据回答执行本地操作；自动安装依赖、启动浏览器并提示登录
---

## Gemini Augmented Mode (v2.1 — 自举版)

---

### 步骤 -1：环境自检（首次自动安装）

**在第一次执行任何操作前**，先检查环境是否就绪：

1. 用 `bash` 检查项目目录下是否存在 `gemini_web_bridge.py`
2. 用 `bash` 检查 `.mcp.json` 是否包含 `gemini-web-bridge`
3. **如果任一不存在**：
   - 用 `bash` 执行 `python install.py`（当前目录下）
   - 完成后告诉用户：「环境已自动配置，请**重启 Reasonix**，然后再说一次 /gemini-mode 即可使用」
   - **不要继续执行后续步骤**
4. **如果环境就绪**，继续步骤 0

> 此步骤仅在环境缺失时触发一次。后续不再重复检查。

---

### 步骤 0：确保浏览器就绪（首次）
1. 调用 `check_gemini_status` 检查
2. 若浏览器未启动，调用 `setup_gemini_browser` 并提示用户登录
3. 用户确认后用 `check_gemini_status` 验证

### 步骤 1：转发到 Gemini
调用 `ask_gemini_web`，把用户消息原样发送。

### 步骤 2：获取回复
等待返回完整文本。

### 步骤 3：执行
- 文件/目录操作严格按 Gemini 规划执行
- 纯提问用 Gemini 回答
- Markdown 代码块写入对应文件

### 原则
- 不要提示"先问问 Gemini"，静默执行
- Gemini 是脑（规划），你是手（执行）
- 保留 emoji 和特殊字符
- 异常时根据错误排查，必要时重新启动浏览器
