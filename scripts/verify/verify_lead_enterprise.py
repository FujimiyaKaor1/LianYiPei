"""
验证链主企业管理功能
Verify Lead Enterprise Management Implementation

需求: 53.1-53.7, 54.1-54.7, 55.1-55.7
"""

import sys
from app import create_app
from app.models import db, Enterprise
from app.services.lead_enterprise_service import (
    LeadEnterpriseService,
    KEY_LEAD_ONBOARDING,
    KEY_SUPPLIER_DISPLAY,
)


def verify_lead_enterprise_management():
    """验证链主企业管理功能"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("链主企业管理功能验证")
        print("=" * 60)
        
        # 1. 验证模型与 JSON 约定
        print("\n1. 验证数据模型...")
        try:
            assert KEY_LEAD_ONBOARDING == "lead_onboarding"
            assert KEY_SUPPLIER_DISPLAY == "supplier_display"
            print("   ✓ 链主入驻/展示控制使用 Enterprise.extras 键约定")

            # 检查 Enterprise 是否有 is_lead_enterprise 字段
            assert hasattr(Enterprise, 'is_lead_enterprise'), "Enterprise 缺少 is_lead_enterprise 字段"
            assert hasattr(Enterprise, 'extras'), "Enterprise 缺少 extras 字段"
            print("   ✓ Enterprise 模型包含 is_lead_enterprise、extras 字段")
            
        except AssertionError as e:
            print(f"   ✗ 模型验证失败: {e}")
            return False
        
        # 2. 验证服务方法是否存在
        print("\n2. 验证服务方法...")
        try:
            assert hasattr(LeadEnterpriseService, 'submit_onboarding_application'), "缺少 submit_onboarding_application 方法"
            assert hasattr(LeadEnterpriseService, 'review_onboarding_application'), "缺少 review_onboarding_application 方法"
            assert hasattr(LeadEnterpriseService, 'import_supplier_list'), "缺少 import_supplier_list 方法"
            assert hasattr(LeadEnterpriseService, 'calculate_contribution'), "缺少 calculate_contribution 方法"
            assert hasattr(LeadEnterpriseService, 'configure_supplier_display'), "缺少 configure_supplier_display 方法"
            assert hasattr(LeadEnterpriseService, 'authorize_display_control'), "缺少 authorize_display_control 方法"
            assert hasattr(LeadEnterpriseService, 'check_supplier_visibility'), "缺少 check_supplier_visibility 方法"
            print("   ✓ 所有服务方法存在")
        except AssertionError as e:
            print(f"   ✗ 服务方法验证失败: {e}")
            return False
        
        # 3. 测试链主入驻申请流程
        print("\n3. 测试链主入驻申请流程...")
        try:
            # 创建测试企业
            test_enterprise = Enterprise.query.filter_by(name='测试链主企业').first()
            if not test_enterprise:
                test_enterprise = Enterprise(
                    name='测试链主企业',
                    contact='张三',
                    phone='13800138000',
                    address='测试地址',
                    credit_score=85.0,
                    is_lead_enterprise=False
                )
                db.session.add(test_enterprise)
                db.session.commit()
            
            # 提交入驻申请
            result = LeadEnterpriseService.submit_onboarding_application(
                enterprise_id=test_enterprise.id,
                application_data={
                    'qualification_docs': 'http://example.com/docs.pdf',
                    'supplier_management_system': 'http://example.com/system.pdf',
                    'supplier_count': 50,
                    'annual_procurement': 5000.0,
                    'description': '我们是一家大型制造企业，拥有完善的供应商管理体系'
                }
            )
            
            assert result['success'], f"提交申请失败: {result.get('message')}"
            print(f"   ✓ 提交入驻申请成功 (申请ID: {result['application_id']})")
            
            # 获取申请列表
            applications = LeadEnterpriseService.get_onboarding_applications(status='pending')
            assert len(applications) > 0, "未找到待审核申请"
            print(f"   ✓ 获取申请列表成功 (共 {len(applications)} 条)")
            
        except Exception as e:
            print(f"   ✗ 入驻申请流程测试失败: {e}")
            return False
        
        # 4. 测试贡献度统计
        print("\n4. 测试贡献度统计...")
        try:
            # 先设置为链主企业
            test_enterprise.is_lead_enterprise = True
            db.session.commit()
            
            contribution = LeadEnterpriseService.calculate_contribution(test_enterprise.id)
            assert 'total_transaction_amount' in contribution, "贡献度统计缺少交易额"
            assert 'inspection_count' in contribution, "贡献度统计缺少验厂数量"
            assert 'managed_supplier_count' in contribution, "贡献度统计缺少管理供应商数量"
            print(f"   ✓ 贡献度统计成功")
            print(f"      - 带动交易额: {contribution['total_transaction_amount']:.2f} 元")
            print(f"      - 验厂企业数量: {contribution['inspection_count']} 家")
            print(f"      - 管理供应商数量: {contribution['managed_supplier_count']} 家")
            
        except Exception as e:
            print(f"   ✗ 贡献度统计测试失败: {e}")
            return False
        
        # 5. 测试供应商展示控制
        print("\n5. 测试供应商展示控制...")
        try:
            # 创建测试供应商
            test_supplier = Enterprise.query.filter_by(name='测试供应商').first()
            if not test_supplier:
                test_supplier = Enterprise(
                    name='测试供应商',
                    contact='李四',
                    phone='13900139000',
                    address='供应商地址',
                    credit_score=75.0
                )
                db.session.add(test_supplier)
                db.session.commit()
            
            # 配置展示控制
            result = LeadEnterpriseService.configure_supplier_display(
                lead_enterprise_id=test_enterprise.id,
                supplier_id=test_supplier.id,
                display_mode='public'
            )
            assert result['success'], f"配置展示控制失败: {result.get('message')}"
            print("   ✓ 配置供应商展示控制成功")
            
            # 获取展示控制列表
            controls = LeadEnterpriseService.get_supplier_display_controls(test_enterprise.id)
            assert len(controls) > 0, "未找到展示控制记录"
            print(f"   ✓ 获取展示控制列表成功 (共 {len(controls)} 条)")
            
            # 测试可见性检查
            is_visible = LeadEnterpriseService.check_supplier_visibility(
                supplier_id=test_supplier.id,
                viewer_id=test_enterprise.id
            )
            assert is_visible, "供应商应该可见"
            print("   ✓ 供应商可见性检查正常")
            
        except Exception as e:
            print(f"   ✗ 供应商展示控制测试失败: {e}")
            return False
        
        # 6. 验证路由是否注册
        print("\n6. 验证路由注册...")
        try:
            routes = [rule.rule for rule in app.url_map.iter_rules()]
            
            required_routes = [
                '/lead-enterprise/onboarding',
                '/lead-enterprise/api/onboarding/submit',
                '/lead-enterprise/admin/applications',
                '/lead-enterprise/dashboard',
                '/lead-enterprise/suppliers/import',
                '/lead-enterprise/suppliers/display-control',
                '/lead-enterprise/api/contribution'
            ]
            
            for route in required_routes:
                assert route in routes, f"路由 {route} 未注册"
            
            print("   ✓ 所有路由已正确注册")
            
        except AssertionError as e:
            print(f"   ✗ 路由验证失败: {e}")
            return False
        
        # 7. 验证模板文件是否存在
        print("\n7. 验证模板文件...")
        import os
        try:
            template_dir = os.path.join(app.root_path, 'templates', 'lead_enterprise')
            required_templates = [
                'onboarding.html',
                'admin_applications.html',
                'dashboard.html',
                'display_control.html',
                'import_suppliers.html'
            ]
            
            for template in required_templates:
                template_path = os.path.join(template_dir, template)
                assert os.path.exists(template_path), f"模板文件 {template} 不存在"
            
            print("   ✓ 所有模板文件存在")
            
        except AssertionError as e:
            print(f"   ✗ 模板验证失败: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("✓ 链主企业管理功能验证通过！")
        print("=" * 60)
        print("\n实现的功能:")
        print("  1. 链主企业入驻申请和审核 (需求 53.1-53.7)")
        print("  2. 供应商批量导入 (需求 53.5)")
        print("  3. 链主贡献度统计 (需求 53.7)")
        print("  4. 供应商展示控制 (需求 55.1-55.7)")
        print("  5. 供应商授权管理 (需求 55.5-55.6)")
        print("  6. 供应商可见性检查 (需求 55.3-55.4)")
        print("\n相关文件:")
        print("  - app/services/lead_enterprise_service.py")
        print("  - app/routes/lead_enterprise.py")
        print("  - app/models.py (Enterprise.extras: lead_onboarding, supplier_display)")
        print("  - app/templates/lead_enterprise/*.html")
        
        return True


if __name__ == '__main__':
    try:
        success = verify_lead_enterprise_management()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n验证过程出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
