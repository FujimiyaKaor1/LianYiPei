# 本仓库使用工厂函数创建应用，请使用 create_app()（若你的项目有 from run import app，可改为那种写法）
from app import create_app, db
from app.models import Enterprise
from werkzeug.security import generate_password_hash

app = create_app()


def fix_passwords():
    # 必须在 Flask 应用上下文中执行数据库操作
    with app.app_context():
        # 找出所有密码为空的企业
        enterprises = Enterprise.query.filter(Enterprise.password_hash.is_(None)).all()

        if not enterprises:
            print("没有发现密码为空的企业，是不是已经改过了？")
            return

        for ent in enterprises:
            # 统一生成 123456 的安全哈希值
            ent.password_hash = generate_password_hash('123456')
            print(f"✅ 已重置企业密码: {ent.name}")

        # 这一步最关键！提交到数据库保存
        db.session.commit()
        print("🎉 所有企业密码初始化成功！")


if __name__ == '__main__':
    fix_passwords()
