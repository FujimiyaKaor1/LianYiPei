import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db  # noqa: E402
import app.models  # noqa: F401,E402  # 注册 ORM 模型


def init_db():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("数据库表创建成功（11 张核心表 + 关联）。")


if __name__ == "__main__":
    init_db()
