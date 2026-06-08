"""
确保存在演示企业「测试账号1」，密码固定为 password123。

用法（在项目根目录）:
    python scripts/ensure_test_account1.py

已存在同名企业时仅重置密码与基础字段，不删除关联数据。
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Enterprise

TEST_NAME = "测试账号1"
TEST_PASSWORD = "password123"


def main() -> None:
    app = create_app()
    with app.app_context():
        e = Enterprise.query.filter_by(name=TEST_NAME).first()
        if e is None:
            e = Enterprise(
                name=TEST_NAME,
                role="enterprise",
                is_admin=False,
                credit_score=78.0,
                city="深圳",
                province="广东",
                is_lead_enterprise=False,
                daily_quote_count=0,
                daily_quote_limit=999,
                last_quote_reset_date=date.today(),
                address="广东省深圳市演示账号",
                business_scope="电子元器件制造、精密加工、新能源设备",
            )
            db.session.add(e)
            print(f"创建企业: {TEST_NAME}")
        else:
            print(f"已存在企业: {TEST_NAME}，更新密码与基础信息")
        e.set_password(TEST_PASSWORD)
        e.role = "enterprise"
        e.is_admin = False
        e.credit_score = float(e.credit_score or 78.0)
        db.session.commit()
        print(f"登录说明：企业名称（用户名）= {TEST_NAME}，密码 = {TEST_PASSWORD}")


if __name__ == "__main__":
    main()
