"""
链易配 - 确保测试账号正确
检查并修复政府端账号 (admin/admin) 和企业端账号 (test_ent/123456)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Enterprise

def ensure_test_accounts():
    app = create_app()
    with app.app_context():
        print("=" * 50)
        print("检查测试账号...")
        print("=" * 50)
        
        # 检查/创建政府端账号 admin
        admin = Enterprise.query.filter_by(name='admin').first()
        if admin:
            print(f"\n[政府账号] admin 已存在")
            print(f"  - ID: {admin.id}")
            print(f"  - is_admin: {admin.is_admin}")
            print(f"  - role: {admin.role}")
            # 确保密码正确
            if not admin.check_password('admin'):
                admin.set_password('admin')
                print("  - 密码已重置为: admin")
            # 确保 role 正确
            if admin.role != 'admin' or not admin.is_admin:
                admin.role = 'admin'
                admin.is_admin = True
                print("  - 角色已修正为: admin")
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
            print("\n[政府账号] admin 已创建")
            print("  - 用户名: admin")
            print("  - 密码: admin")
            print("  - 角色: admin (政府端)")
        
        # 检查/创建企业端账号 test_ent
        test_ent = Enterprise.query.filter_by(name='test_ent').first()
        if test_ent:
            print(f"\n[企业账号] test_ent 已存在")
            print(f"  - ID: {test_ent.id}")
            print(f"  - is_admin: {test_ent.is_admin}")
            print(f"  - role: {test_ent.role}")
            # 确保密码正确
            if not test_ent.check_password('123456'):
                test_ent.set_password('123456')
                print("  - 密码已重置为: 123456")
            # 确保 role 正确
            if test_ent.role != 'enterprise' or test_ent.is_admin:
                test_ent.role = 'enterprise'
                test_ent.is_admin = False
                print("  - 角色已修正为: enterprise")
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
            print("\n[企业账号] test_ent 已创建")
            print("  - 用户名: test_ent")
            print("  - 密码: 123456")
            print("  - 角色: enterprise (企业端)")
        
        db.session.commit()
        
        # 验证账号
        print("\n" + "=" * 50)
        print("验证测试账号...")
        print("=" * 50)
        
        # 验证 admin 账号
        admin_check = Enterprise.query.filter_by(name='admin').first()
        if admin_check and admin_check.check_password('admin'):
            print("\n✓ 政府账号验证成功")
            print(f"  - 用户名: admin")
            print(f"  - 密码: admin")
            print(f"  - 角色: {admin_check.role}")
            print(f"  - is_admin: {admin_check.is_admin}")
        else:
            print("\n✗ 政府账号验证失败!")
        
        # 验证 test_ent 账号
        test_ent_check = Enterprise.query.filter_by(name='test_ent').first()
        if test_ent_check and test_ent_check.check_password('123456'):
            print("\n✓ 企业账号验证成功")
            print(f"  - 用户名: test_ent")
            print(f"  - 密码: 123456")
            print(f"  - 角色: {test_ent_check.role}")
            print(f"  - is_admin: {test_ent_check.is_admin}")
        else:
            print("\n✗ 企业账号验证失败!")
        
        print("\n" + "=" * 50)
        print("测试账号检查完成!")
        print("=" * 50)
        print("\n登录信息:")
        print("  政府端账号: admin / admin")
        print("  企业端账号: test_ent / 123456")
        print("\n权限说明:")
        print("  政府端账号 (admin): 可访问政府大屏、产业链图谱、预警设置")
        print("  企业端账号 (test_ent): 可访问智能匹配、企业中心、供需信息")
        print("=" * 50)

if __name__ == '__main__':
    ensure_test_accounts()
