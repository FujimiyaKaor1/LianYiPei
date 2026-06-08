"""
为 MySQL `enterprises` 表补齐与 app/models.py 一致的列（按需 ALTER + commit）。

含微信绑定字段；若无法执行完整 `flask db upgrade`，可先运行本脚本补列，
再在确认库结构与 migrations 一致后执行 `flask db stamp head`（避免重复执行会失败的迁移）。

用法（在项目根目录）：
    python scripts/fix_db_columns.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from app import create_app, db


def _column_exists(table: str, column: str) -> bool:
    q = text(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :table
          AND COLUMN_NAME = :column
        """
    )
    n = db.session.execute(q, {"table": table, "column": column}).scalar()
    return int(n or 0) > 0


def main() -> None:
    # 与 app/models.Enterprise 一致：business_scope=Text, province=VARCHAR(20), city=VARCHAR(200)
    app = create_app()
    with app.app_context():
        alters: list[tuple[str, str]] = [
            (
                "business_scope",
                "ALTER TABLE enterprises ADD COLUMN business_scope TEXT NULL",
            ),
            (
                "province",
                "ALTER TABLE enterprises ADD COLUMN province VARCHAR(20) NULL",
            ),
            (
                "city",
                "ALTER TABLE enterprises ADD COLUMN city VARCHAR(200) NULL",
            ),
            (
                "wechat_bound",
                "ALTER TABLE enterprises ADD COLUMN wechat_bound TINYINT(1) NOT NULL DEFAULT 0",
            ),
            (
                "wechat_work_userid",
                "ALTER TABLE enterprises ADD COLUMN wechat_work_userid VARCHAR(100) NULL",
            ),
            (
                "wechat_work_openid",
                "ALTER TABLE enterprises ADD COLUMN wechat_work_openid VARCHAR(100) NULL",
            ),
            (
                "wechat_service_openid",
                "ALTER TABLE enterprises ADD COLUMN wechat_service_openid VARCHAR(100) NULL",
            ),
            (
                "wechat_bound_at",
                "ALTER TABLE enterprises ADD COLUMN wechat_bound_at DATETIME NULL",
            ),
            (
                "wechat_push_preference",
                "ALTER TABLE enterprises ADD COLUMN wechat_push_preference VARCHAR(20) NOT NULL DEFAULT 'all'",
            ),
        ]
        for col, sql in alters:
            if _column_exists("enterprises", col):
                print(f"跳过（已存在）: {col}")
                continue
            db.session.execute(text(sql))
            print(f"已执行: {col}")
        db.session.commit()
        print("已 commit。")


if __name__ == "__main__":
    main()
