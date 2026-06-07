# model_service（Qwen3-4B）

独立模型服务：加载 **Qwen3-4B** 并提供 OpenAI 兼容接口：

- `POST /v1/chat/completions`
- `GET /health`

## 1. 安装依赖

```bash
cd model_service
pip install -r requirements.txt
```

## 2. 配置环境变量（可选）

你可以通过环境变量或 `.env` 设置：

```
MODEL_PATH=Qwen/Qwen3-4B-Instruct
DEVICE=auto
MODEL_DTYPE=bfloat16
HOST=0.0.0.0
PORT=5001
MAX_NEW_TOKENS=512
```

## 3. 启动

```bash
python app.py
```

验证：

- `http://<模型服务器IP>:5001/health`

