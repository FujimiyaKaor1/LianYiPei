"""
数据库迁移脚本
===============

添加收藏、名片交换相关新表。

运行方式：python -m scripts.migrate_new_tables
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from app import create_app, db
from app.models import FavoriteSupplier, IntentQuote, BusinessCard


def run_migration():
    app = create_app()
    with app.app_context():
        print("[开始] 数据库迁移...")
        
        # 创建新表
        db.create_all()
        print("[OK] FavoriteSupplier 表已创建/更新")
        print("[OK] IntentQuote 表已创建/更新")
        print("[OK] BusinessCard 表已创建/更新")
        
        print("\n[完成] 数据库迁移成功!")


if __name__ == "__main__":
    run_migration()
