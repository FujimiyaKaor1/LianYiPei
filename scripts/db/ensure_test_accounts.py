"""
链易配 - 确保测试账号正确
检查并修复政府端账号、基础企业账号，以及完整占位演示企业账号。
"""
import sys
import os
# This file lives in ``scripts/db``; the application package is one more
# directory above it.  Keep direct execution working in the production image
# as well as ``python -m scripts.db.ensure_test_accounts``.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app import create_app, db
from app.models import Enterprise

def ensure_test_accounts():
    if os.getenv("APP_ENV", "development").strip().lower() == "production":
        raise SystemExit(
            "拒绝在 APP_ENV=production 中创建或重置固定测试账号；"
            "请使用预生产环境执行此脚本。"
        )
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
            admin.verification_status = 'approved'
            admin.is_verified = True
        else:
            admin = Enterprise(
                name='admin',
                address='系统管理员',
                contact='管理员',
                phone='00000000000',
                is_admin=True,
                role='admin',
                credit_score=100,
                verification_status='approved',
                is_verified=True,
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
            test_ent.verification_status = 'approved'
            test_ent.is_verified = True
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
                verification_status='approved',
                is_verified=True,
            )
            test_ent.set_password('123456')
            db.session.add(test_ent)
            print("\n[企业账号] test_ent 已创建")
            print("  - 用户名: test_ent")
            print("  - 密码: 123456")
            print("  - 角色: enterprise (企业端)")

        # 完整演示企业：使用项目内置的营业执照图片走注册 Agent 识别流程。
        # 业务数据仍然全部标记为 demo，不代表真实企业事实。
        demo_ent = Enterprise.query.filter(
            Enterprise.name.in_(['演示企业全功能账号', '长沙德远智造科技有限公司'])
        ).first()
        if demo_ent:
            print(f"\n[演示企业账号] {demo_ent.name} 已存在")
            print(f"  - ID: {demo_ent.id}")
        else:
            demo_ent = Enterprise(
                name='长沙德远智造科技有限公司',
                address='中国（湖南）自由贸易试验区长沙片区长沙经开区区块东六路南段77号C6栋三一众创21层D016号',
                province='湖南',
                city='长沙',
                contact='岳雅慧（演示账号）',
                phone='13800000000',
                business_scope='许可项目：建筑智能化系统设计；一般项目：工业设计服务、机械设备研发、新材料技术研发、工程和技术研究和试验发展、人工智能应用软件开发、软件开发、数字技术服务、信息系统集成服务、技术服务、技术开发、技术咨询、技术交流、技术转让、技术推广、工业工程设计服务、金属制品销售、金属制品修理、金属制品研发、企业管理咨询。',
                industry_code='C34',
                registered_capital=200.0,
                unified_social_credit_code='91430100MAK1QW4U4E',
                credit_score=92.0,
                capacity=850,
                max_capacity=1200,
                role='enterprise',
                is_admin=False,
                verification_status='approved',
                is_verified=True,
                extras={
                    'is_demo': True,
                    'demo_account': True,
                    'demo_dataset': 'license_material_registration_demo_2026',
                    'data_notice': '企业身份来自用户提供的营业执照演示图片；业务字段和账号权限仅供产品演示，不代表真实企业事实。',
                    'demo_materials': [
                        {'label': '营业执照（注册 Agent 演示）', 'path': '/static/demo/registration/business-license.jpg', 'kind': 'business_license', 'is_demo': True},
                        {'label': '电子发票 1（材料识别演示）', 'path': '/static/demo/registration/invoice-1.jpg', 'kind': 'invoice', 'is_demo': True},
                        {'label': '电子发票 2（材料识别演示）', 'path': '/static/demo/registration/invoice-2.jpg', 'kind': 'invoice', 'is_demo': True},
                    ],
                    'registration_material': {
                        'source': 'bundled_demo_license_image',
                        'file': 'app/static/demo/registration/business-license.jpg',
                        'review_status': 'approved_demo',
                        'unified_social_credit_code': '91430100MAK1QW4U4E',
                        'legal_representative': '岳雅慧',
                    },
                    'trust_profile': {
                        'claim_status': 'claimed',
                        'contact_authorized': True,
                        'sources': [{'name': '演示占位数据', 'source_type': 'demo_seed', 'is_mock': True}],
                    },
                },
            )
            db.session.add(demo_ent)
            print("\n[演示企业账号] 长沙德远智造科技有限公司 已创建")
            print("  - 用户名: 长沙德远智造科技有限公司")
            print("  - 密码: demo123456")
            print("  - 角色: enterprise (完整占位演示数据)")
        if not demo_ent.check_password('demo123456'):
            demo_ent.set_password('demo123456')
        demo_ent.role = 'enterprise'
        demo_ent.is_admin = False
        demo_ent.verification_status = 'approved'
        demo_ent.is_verified = True
        demo_ent.name = '长沙德远智造科技有限公司'
        demo_ent.address = '中国（湖南）自由贸易试验区长沙片区长沙经开区区块东六路南段77号C6栋三一众创21层D016号'
        demo_ent.province = '湖南'
        demo_ent.city = '长沙'
        demo_ent.registered_capital = 200.0
        demo_ent.unified_social_credit_code = '91430100MAK1QW4U4E'
        demo_ent.business_scope = '许可项目：建筑智能化系统设计；一般项目：工业设计服务、机械设备研发、新材料技术研发、工程和技术研究和试验发展、人工智能应用软件开发、软件开发、数字技术服务、信息系统集成服务、技术服务、技术开发、技术咨询、技术交流、技术转让、技术推广、工业工程设计服务、金属制品销售、金属制品修理、金属制品研发、企业管理咨询。'
        extras = demo_ent.extras if isinstance(demo_ent.extras, dict) else {}
        extras.update({
            'is_demo': True,
            'demo_account': True,
            'demo_dataset': 'license_material_registration_demo_2026',
            'data_notice': '企业身份来自用户提供的营业执照演示图片；业务字段和账号权限仅供产品演示，不代表真实企业事实。',
            'demo_materials': [
                {'label': '营业执照（注册 Agent 演示）', 'path': '/static/demo/registration/business-license.jpg', 'kind': 'business_license', 'is_demo': True},
                {'label': '电子发票 1（材料识别演示）', 'path': '/static/demo/registration/invoice-1.jpg', 'kind': 'invoice', 'is_demo': True},
                {'label': '电子发票 2（材料识别演示）', 'path': '/static/demo/registration/invoice-2.jpg', 'kind': 'invoice', 'is_demo': True},
            ],
        })
        demo_ent.extras = extras

        # 供应商侧完整演示企业，与买方演示企业配对使用。
        # 所有资料均为演示占位数据，不代表真实企业事实。
        seller_demo = Enterprise.query.filter_by(name='湖南星瀚精密制造有限公司').first()
        if not seller_demo:
            seller_demo = Enterprise(
                name='湖南星瀚精密制造有限公司',
                address='湖南省长沙市经开区智能制造产业园（演示地址）',
                province='湖南',
                city='长沙',
                contact='周工（演示账号）',
                phone='13900000002',
                business_scope='精密零部件加工、金属制品研发与制造、工业设计服务、机械设备研发。',
                tech_keywords='精密零部件,数控加工,金属制品,机械加工,CNC',
                industry_code='C34',
                registered_capital=500.0,
                unified_social_credit_code='91430100MAK2DEMO88',
                credit_score=90.0,
                capacity=500,
                max_capacity=800,
                role='enterprise',
                is_admin=False,
                verification_status='approved',
                is_verified=True,
            )
            db.session.add(seller_demo)
            print("\n[供应商演示企业] 湖南星瀚精密制造有限公司 已创建")
        seller_demo.set_password('seller123456')
        seller_demo.role = 'enterprise'
        seller_demo.is_admin = False
        seller_demo.verification_status = 'approved'
        seller_demo.is_verified = True
        seller_demo.business_scope = '精密零部件加工、金属制品研发与制造、工业设计服务、机械设备研发。'
        seller_demo.tech_keywords = '精密零部件,数控加工,金属制品,机械加工,CNC'
        seller_extras = seller_demo.extras if isinstance(seller_demo.extras, dict) else {}
        seller_extras.update({
            'is_demo': True,
            'demo_account': True,
            'demo_dataset': 'enterprise_collaboration_demo_2026',
            'data_notice': '企业身份、联系方式和业务字段均为演示占位数据，不代表真实企业事实。',
        })
        seller_demo.extras = seller_extras
        
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

        demo_check = Enterprise.query.filter_by(name='长沙德远智造科技有限公司').first()
        if demo_check and demo_check.check_password('demo123456'):
            print("\n✓ 完整占位演示企业账号验证成功")
            print("  - 用户名: 长沙德远智造科技有限公司")
            print("  - 密码: demo123456")
        else:
            print("\n✗ 完整占位演示企业账号验证失败!")

        seller_demo_check = Enterprise.query.filter_by(name='湖南星瀚精密制造有限公司').first()
        if seller_demo_check and seller_demo_check.check_password('seller123456'):
            print("\n✓ 供应商演示企业账号验证成功")
            print("  - 用户名: 湖南星瀚精密制造有限公司")
            print("  - 密码: seller123456")
        else:
            print("\n✗ 供应商演示企业账号验证失败!")
        
        print("\n" + "=" * 50)
        print("测试账号检查完成!")
        print("=" * 50)
        print("\n登录信息:")
        print("  政府端账号: admin / admin")
        print("  企业端账号: test_ent / 123456")
        print("  完整演示企业: 长沙德远智造科技有限公司 / demo123456")
        print("  供应商演示企业: 湖南星瀚精密制造有限公司 / seller123456")
        print("\n权限说明:")
        print("  政府端账号 (admin): 可访问政府大屏、产业链图谱、预警设置")
        print("  企业端账号 (test_ent): 可访问智能匹配、企业中心、供需信息")
        print("=" * 50)

if __name__ == '__main__':
    ensure_test_accounts()
