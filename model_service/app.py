import os
from flask import Flask, request, jsonify


def _build_prompt(messages: list[dict]) -> str:
    parts = []
    for m in messages or []:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        parts.append(f"{role.upper()}: {content}")
    parts.append("ASSISTANT:")
    return "\n".join(parts)


def create_app() -> Flask:
    app = Flask(__name__)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    hf_endpoint = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')
    os.environ['HF_ENDPOINT'] = hf_endpoint
    print(f"[model_service] Using HuggingFace mirror: {hf_endpoint}")

    model_path = os.environ.get("MODEL_PATH", "Qwen/Qwen2.5-0.5B-Instruct")
    device = os.environ.get("DEVICE", "auto")
    device_dtype = os.environ.get("MODEL_DTYPE", "bfloat16")
    max_new_tokens_default = int(os.environ.get("MAX_NEW_TOKENS", "512"))

    state = {"model": None, "tokenizer": None}

    def load_model():
        if state["model"] is not None and state["tokenizer"] is not None:
            return

        print(f"[model_service] Loading model: {model_path}")
        print("[model_service] Downloading model (this may take a few minutes)...")
        
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(device_dtype.lower(), torch.bfloat16)

        print(f"[model_service] Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(
            model_path, 
            trust_remote_code=True,
            force_download=True
        )
        
        print(f"[model_service] Loading model weights...")
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch_dtype,
            device_map="auto" if device == "auto" else None,
            trust_remote_code=True,
            force_download=True
        )
        if device != "auto":
            model = model.to(device)
        model.eval()

        state["model"] = model
        state["tokenizer"] = tokenizer
        print("[model_service] Model loaded successfully!")

    load_model()

    @app.get("/health")
    def health():
        ok = state["model"] is not None and state["tokenizer"] is not None
        return jsonify({
            "ok": ok, 
            "model_path": model_path,
            "hf_endpoint": hf_endpoint
        })

    @app.post("/v1/chat/completions")
    def chat_completions():
        try:
            data = request.get_json(force=True) or {}
            messages = data.get("messages") or []
            temperature = float(data.get("temperature", 0.7))
            max_tokens = data.get("max_tokens")
            max_new_tokens = int(data.get("max_new_tokens", max_tokens or max_new_tokens_default))

            tokenizer = state["tokenizer"]
            model = state["model"]

            prompt = None
            try:
                if getattr(tokenizer, "chat_template", None):
                    prompt = tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
            except Exception:
                prompt = None
            if not prompt:
                prompt = _build_prompt(messages)

            import torch

            inputs = tokenizer(prompt, return_tensors="pt")
            inputs = {k: v.to(model.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=temperature > 0,
                    temperature=temperature if temperature > 0 else 1.0,
                )

            gen_tokens = outputs[0][inputs["input_ids"].shape[1]:]
            text = tokenizer.decode(gen_tokens, skip_special_tokens=True).strip()

            return jsonify({"choices": [{"message": {"content": text}}]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5001"))
    print(f"[model_service] Starting server on {host}:{port}")
    create_app().run(host=host, port=port, debug=False, threaded=True)
