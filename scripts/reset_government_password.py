"""
一键修复政府端登录：将「政府产业监管局」或任意 role=government 的账号密码设为 123456。

适用场景：
- 曾用旧版 seed_data（政府账号密码实为 password123）；
- 用 seed_all_data 时库里已有数据，未自动补政府用户。

用法（项目根目录）:
  python scripts/reset_government_password.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from app import create_app, db
    from app.models import Enterprise

    app = create_app()
    with app.app_context():
        gov = Enterprise.query.filter_by(role="government").first()
        if gov is None:
            gov = Enterprise.query.filter_by(name="政府产业监管局").first()
        if gov is None:
            gov = Enterprise(
                name="政府产业监管局",
                address="广东省深圳市（监管演示）",
                contact="监管",
                phone="00000000002",
                role="government",
                is_admin=True,
                credit_score=88.0,
                province="广东",
                city="深圳",
                verification_status="approved",
                is_verified=True,
            )
            db.session.add(gov)
            print("已新建政府用户：政府产业监管局")
        else:
            if gov.role != "government":
                gov.role = "government"
            gov.verification_status = "approved"
            gov.is_verified = True
            print(f"已更新政府用户：id={gov.id} name={gov.name!r}")

        gov.set_password("123456")
        db.session.commit()
        print("密码已设为: 123456")
        print('登录时请填写企业名称与上条 name 完全一致（默认：政府产业监管局）')


if __name__ == "__main__":
    main()
