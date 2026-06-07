# Ollama BizMind 自定义模型（Modelfile）

1. 将 **`qwen2.5.gguf`**（或你的 GGUF 文件名）放到本目录 **`ollama/`**，与 **`Modelfile`** 同级；若文件名不同，请修改 `Modelfile` 里的 `FROM ./...`。
2. 在本目录执行：

   ```bash
   cd ollama
   ollama create bizmind -f Modelfile
   ```

3. 在项目 `.env` 中设置：

   ```env
   BIZMIND_OLLAMA_MODEL=bizmind
   ```

4. 重启后端。应用仍会通过 `app/services/llm_service.py` 里的 **ChatPromptTemplate** 再叠一层业务指令；Modelfile 的 `SYSTEM` 与 **PARAMETER stop** 在模型侧提供基础行为。
