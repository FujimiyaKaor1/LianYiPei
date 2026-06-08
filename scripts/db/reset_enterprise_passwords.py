"""
一次性脚本：将 enterprises 表中所有企业的 password_hash 更新为「123456」的 Werkzeug 哈希。

用法（在项目根目录）：
    python scripts/reset_enterprise_passwords.py

依赖：已配置 .env 中的 DATABASE_URL，且能连上 MySQL。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import Enterprise

DEFAULT_PASSWORD = "123456"


def main() -> None:
    app = create_app()
    with app.app_context():
        pwd_hash = generate_password_hash(DEFAULT_PASSWORD)
        rows = Enterprise.query.all()
        if not rows:
            print("enterprises 表为空，未做任何更新。")
            return

        for ent in rows:
            ent.password_hash = pwd_hash

        db.session.commit()
        print(
            f"已更新 {len(rows)} 家企业的 password_hash（明文密码均为 {DEFAULT_PASSWORD!r}）。"
        )
        for ent in rows:
            print(f"  - id={ent.id} name={ent.name!r}")


if __name__ == "__main__":
    main()
