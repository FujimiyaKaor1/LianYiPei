# Qwen3-4B 模型服务接入指南（链易配）

目标：将 **Qwen3-4B** 封装成独立 HTTP 服务（OpenAI 兼容 `/v1/chat/completions`），主 Flask 应用通过 `LLMBASEURL/LLM_BASE_URL` 调用该服务完成“智能问答（Text-to-SQL/可选Cypher）”。

---

## 零、本机 Ollama（可选，无需启动 model_service）

若已安装 [Ollama](https://ollama.com/) 并拉取模型，可在项目根目录 `.env` 中配置（OpenAI 兼容 API，默认端口 **11434**）：

```
LLMBASEURL=http://localhost:11434/v1
LLMMODEL=qwen2.5
LLMAPKEY=ollama
```

说明：`app/services/llm_query.py` 会在 base 已含 `/v1` 时请求 `{base}/chat/completions`；若 base **不含** `/v1`（如远程 `model_service`），则请求 `{base}/v1/chat/completions`。请将 `LLMMODEL` 设为 `ollama list` 中存在的名称。

---

## 一、模型服务端（GPU 服务器）

### 1) 环境要求

- Python 3.10+
- NVIDIA 驱动 + CUDA（与 PyTorch 匹配）
- 推荐显存：8GB+（4B 量级一般可跑；CPU 也能跑但会很慢）

### 2) 下载模型

```bash
pip install huggingface-hub
huggingface-cli download Qwen/Qwen3-4B-Instruct --local-dir ./Qwen3-4B
```

### 3) 安装依赖 & 启动服务

```bash
cd model_service
pip install -r requirements.txt

# 设置模型路径（指向下载目录）
set MODEL_PATH=./Qwen3-4B

# 启动（默认 0.0.0.0:5001）
python app.py
```

健康检查：

- `GET http://<GPU服务器IP>:5001/health`

---

## 二、主应用端（链易配后端）

### 1) 配置 .env

在链易配项目根目录 `.env` 中加入（两套命名均兼容，推荐用 LLMBASEURL）：：

```
LLMBASEURL=http://<GPU服务器IP>:5001
LLMMODEL=Qwen3-4B
LLMAPKEY=anykey

# 兼容旧命名（也可只用这一套）
LLM_BASE_URL=http://<GPU服务器IP>:5001
LLM_MODEL=Qwen3-4B
LLM_API_KEY=anykey
```

说明：
- `LLMBASEURL/LLM_BASE_URL`：模型服务根地址。**自建 model_service**：一般不带 `/v1`。**Ollama**：填 `http://<主机>:11434/v1`
- `LLMMODEL/LLM_MODEL`：透传字段（服务端可不校验）
- `LLMAPKEY/LLM_API_KEY`：可选（服务端未校验也可填任意）

### 2) 安装依赖并启动主应用

```bash
pip install -r requirements.txt
python run.py
```

### 3) 验证

访问主应用的「智能问答」页面，输入：
- “有多少家企业入驻？”

若返回 SQL 查询结果，即表示主应用已通过 HTTP 成功调用模型服务。

---

## 三、代码落点（你可以快速定位）

- 模型服务：`model_service/app.py`
  - `POST /v1/chat/completions`
  - `GET /health`
- 主应用调用：`app/services/llm_query.py`（会解析模型 JSON 输出并执行 SQL/Cypher）
  - 优先使用 `LLM_BASE_URL` 走 HTTP（`requests`）
  - 未配置时回退到 OpenAI SDK（若设置 `OPENAI_API_KEY`）

---

## 四、常见问题

### 1) tokenizer 没有 chat_template 报错？

本服务端已做兜底：若 tokenizer 没有 `chat_template`，自动用简单 prompt 拼接。

### 2) 主应用报“未配置大模型调用方式”？

检查主应用 `.env` 是否已配置其一：
- 本机 Ollama：`LLM_BASE_URL=http://localhost:11434/v1`（并确认 `ollama serve` 可用）
- 远程 model_service：`LLM_BASE_URL=http://<GPU服务器IP>:5001`

并确认网络可访问对应地址与端口。

### 3) GPU 显存不够？

你可以调整：`MODEL_DTYPE=float16`，或改用更轻的推理框架（如 vLLM/TGI）。当前实现以“最小可跑通”为主。

