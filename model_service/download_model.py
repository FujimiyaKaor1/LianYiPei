"""
使用 HuggingFace 镜像下载 Qwen2.5-3B-Instruct 模型
"""
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from huggingface_hub import snapshot_download

print("=" * 50)
print("使用 HuggingFace 镜像下载 Qwen2.5-3B-Instruct 模型")
print("镜像地址: https://hf-mirror.com")
print("=" * 50)

model_dir = snapshot_download(
    'Qwen/Qwen2.5-3B-Instruct',
    cache_dir=os.path.join(os.path.dirname(__file__), 'model_cache'),
    local_dir=os.path.join(os.path.dirname(__file__), 'models', 'Qwen2.5-3B-Instruct')
)

print(f"\n模型下载完成！保存路径: {model_dir}")
print("\n现在可以启动模型服务了。")
