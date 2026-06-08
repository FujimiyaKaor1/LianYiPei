"""
修复企业审核状态 - 为现有企业设置审核通过

用法:
    python scripts/fix_verification_status.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from app import create_app, db
from app.models import Enterprise

app = create_app()

def fix_verification_status():
    with app.app_context():
        fixed_count = 0
        
        # 修复 enterprise 角色
        enterprises = Enterprise.query.filter(
            Enterprise.role == 'enterprise'
        ).all()
        for ent in enterprises:
            if not ent.verification_status or ent.verification_status == 'pending':
                ent.verification_status = 'approved'
                ent.is_verified = True
                if not ent.registered_at:
                    ent.registered_at = datetime.utcnow()
                fixed_count += 1
        
        # 修复 admin 角色
        admins = Enterprise.query.filter(
            Enterprise.role == 'admin'
        ).all()
        for ent in admins:
            if not ent.verification_status or ent.verification_status == 'pending':
                ent.verification_status = 'approved'
                ent.is_verified = True
                if not ent.registered_at:
                    ent.registered_at = datetime.utcnow()
                fixed_count += 1
        
        db.session.commit()
        
        # 显示所有可用账号
        all_enterprises = Enterprise.query.order_by(Enterprise.role, Enterprise.name).all()
        admin_accounts = []
        enterprise_accounts = []
        
        for ent in all_enterprises:
            info = {
                'name': ent.name,
                'password': 'password123',
                'status': 'approved' if ent.verification_status == 'approved' else 'pending'
            }
            if ent.role == 'admin' or ent.is_admin:
                admin_accounts.append(info)
            else:
                enterprise_accounts.append(info)
        
        print("=" * 60)
        print("Fix complete! Fixed {} accounts.".format(fixed_count))
        print("=" * 60)
        print("\n--- Admin Accounts ---")
        for acc in admin_accounts:
            print("  Name: {} | Password: {} | Status: {}".format(acc['name'], acc['password'], acc['status']))
        
        print("\n--- Enterprise Accounts (first 20) ---")
        for i, acc in enumerate(enterprise_accounts[:20]):
            print("  {}. Name: {} | Password: {} | Status: {}".format(i+1, acc['name'], acc['password'], acc['status']))
        if len(enterprise_accounts) > 20:
            print("  ... and {} more".format(len(enterprise_accounts) - 20))
        
        return fixed_count

if __name__ == '__main__':
    fix_verification_status()
