# 文件名：gnn_model.py
# 作用：一键运行 GNN 图神经网络训练，验证产业链图谱嵌入能力
# 使用方法：在项目根目录执行  python gnn_model.py
import time
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.gnn_model import train_han_bpr, HanBprConfig

if __name__ == '__main__':
    print("=" * 45)
    print("  链易配 - 产业链 GNN 图神经网络训练")
    print("=" * 45)

    start = time.time()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始加载数据并初始化模型...")

    app = create_app()
    with app.app_context():
        config = HanBprConfig(epochs=30)
        output_dir = train_han_bpr(config)

    elapsed = time.time() - start
    print("=" * 45)
    print(f"  [OK] 训练完成！")
    print(f"  [OK] 嵌入向量已保存至: {output_dir}")
    print(f"  [OK] 生成 FAISS 索引文件")
    print(f"  [OK] 总耗时 {elapsed:.1f} 秒")
    print("=" * 45)
