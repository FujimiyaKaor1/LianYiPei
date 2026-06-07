"""
链易配 - 创建测试账号
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Enterprise

def create_test_accounts():
    app = create_app()
    
    print("=" * 50)
    print("数据库配置:")
    print(f"  URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("=" * 50)
    
    with app.app_context():
        # 创建表
        db.create_all()
        print("\n数据库表已创建/确认")
        
        # 检查现有账号
        print("\n现有账号:")
        all_enterprises = Enterprise.query.all()
        for ent in all_enterprises:
            print(f"  - ID: {ent.id}, 名称: {ent.name}, 角色: {ent.role}, is_admin: {ent.is_admin}")
        
        # 创建/更新政府端账号 admin
        print("\n创建/更新政府端账号 admin...")
        admin = Enterprise.query.filter_by(name='admin').first()
        if admin:
            print(f"  admin 账号已存在 (ID: {admin.id})")
            admin.set_password('admin')
            admin.role = 'admin'
            admin.is_admin = True
            print("  密码已重置为 'admin'")
        else:
            admin = Enterprise(
                name='admin',
                address='系统管理员',
                contact='管理员',
                phone='00000000000',
                is_admin=True,
                role='admin',
                credit_score=100,
            )
            admin.set_password('admin')
            db.session.add(admin)
            print("  admin 账号已创建")
        
        # 创建/更新企业端账号 test_ent
        print("\n创建/更新企业端账号 test_ent...")
        test_ent = Enterprise.query.filter_by(name='test_ent').first()
        if test_ent:
            print(f"  test_ent 账号已存在 (ID: {test_ent.id})")
            test_ent.set_password('123456')
            test_ent.role = 'enterprise'
            test_ent.is_admin = False
            print("  密码已重置为 '123456'")
        else:
            test_ent = Enterprise(
                name='test_ent',
                address='测试企业',
                contact='测试',
                phone='13900000001',
                credit_score=80.0,
                capacity=60,
                role='enterprise',
                is_admin=False,
            )
            test_ent.set_password('123456')
            db.session.add(test_ent)
            print("  test_ent 账号已创建")
        
        db.session.commit()
        print("\n更改已提交到数据库")
        
        # 验证
        print("\n验证账号:")
        admin_check = Enterprise.query.filter_by(name='admin').first()
        if admin_check:
            pwd_ok = admin_check.check_password('admin')
            print(f"  admin: 密码验证 {'成功' if pwd_ok else '失败'}")
        else:
            print("  admin: 账号不存在!")
        
        test_ent_check = Enterprise.query.filter_by(name='test_ent').first()
        if test_ent_check:
            pwd_ok = test_ent_check.check_password('123456')
            print(f"  test_ent: 密码验证 {'成功' if pwd_ok else '失败'}")
        else:
            print("  test_ent: 账号不存在!")
        
        print("\n" + "=" * 50)
        print("测试账号创建完成!")
        print("  政府端账号: admin / admin")
        print("  企业端账号: test_ent / 123456")
        print("=" * 50)

if __name__ == '__main__':
    create_test_accounts()
