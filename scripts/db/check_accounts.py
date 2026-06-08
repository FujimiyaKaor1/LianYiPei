"""
直接检查数据库中的账号
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import Enterprise

def check_accounts():
    app = create_app()
    with app.app_context():
        print("=" * 50)
        print("检查数据库中的账号...")
        print("=" * 50)
        
        # 检查 admin 账号
        admin = Enterprise.query.filter_by(name='admin').first()
        if admin:
            print(f"\n[admin 账号]")
            print(f"  ID: {admin.id}")
            print(f"  名称: {admin.name}")
            print(f"  is_admin: {admin.is_admin}")
            print(f"  role: {admin.role}")
            print(f"  password_hash: {admin.password_hash[:50]}..." if admin.password_hash else "  password_hash: None")
            
            # 测试密码
            print(f"\n  密码验证测试:")
            print(f"    check_password('admin'): {admin.check_password('admin')}")
            print(f"    check_password('123456'): {admin.check_password('123456')}")
            print(f"    check_password(''): {admin.check_password('')}")
            
            # 重新设置密码
            print(f"\n  重新设置密码为 'admin'...")
            admin.set_password('admin')
            db.session.commit()
            
            # 再次验证
            print(f"  设置后 check_password('admin'): {admin.check_password('admin')}")
        else:
            print("\n[admin 账号] 不存在!")
        
        # 检查 test_ent 账号
        test_ent = Enterprise.query.filter_by(name='test_ent').first()
        if test_ent:
            print(f"\n[test_ent 账号]")
            print(f"  ID: {test_ent.id}")
            print(f"  名称: {test_ent.name}")
            print(f"  is_admin: {test_ent.is_admin}")
            print(f"  role: {test_ent.role}")
            print(f"  password_hash: {test_ent.password_hash[:50]}..." if test_ent.password_hash else "  password_hash: None")
            
            # 测试密码
            print(f"\n  密码验证测试:")
            print(f"    check_password('123456'): {test_ent.check_password('123456')}")
            print(f"    check_password('admin'): {test_ent.check_password('admin')}")
            print(f"    check_password(''): {test_ent.check_password('')}")
            
            # 重新设置密码
            print(f"\n  重新设置密码为 '123456'...")
            test_ent.set_password('123456')
            db.session.commit()
            
            # 再次验证
            print(f"  设置后 check_password('123456'): {test_ent.check_password('123456')}")
        else:
            print("\n[test_ent 账号] 不存在!")
        
        print("\n" + "=" * 50)

if __name__ == '__main__':
    check_accounts()
