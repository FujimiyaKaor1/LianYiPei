"""
为 password_hash 为空的 Enterprise 设置统一演示密码（默认 password123）。

用于修复历史数据或手工入库未设密码导致的登录 500 / 全员无法登录假象。

用法（项目根目录）:
    python scripts/fix_missing_enterprise_passwords.py

⚠️ 生产环境请勿默认运行；可先读后改 DEFAULT_PASSWORD。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Enterprise

DEFAULT_PASSWORD = "password123"


def main() -> None:
    app = create_app()
    with app.app_context():
        q = Enterprise.query.filter(
            (Enterprise.password_hash.is_(None)) | (Enterprise.password_hash == "")
        )
        rows = q.all()
        if not rows:
            print("无需修复：没有 password_hash 为空的记录。")
            return
        for e in rows:
            e.set_password(DEFAULT_PASSWORD)
            print(f"已设置密码: {e.name} (id={e.id})")
        db.session.commit()
        print(f"完成，共 {len(rows)} 条。统一密码 = {DEFAULT_PASSWORD}")


if __name__ == "__main__":
    main()
