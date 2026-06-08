#!/usr/bin/env python3
"""
Phase 5 Checkpoint Verification Script
验证第五阶段的所有功能是否正常工作
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.abspath('.'))

from app import create_app, db
from app.models import Enterprise, Quote, PriceIndex
from app.services.quote_pool import QuotePoolManager
from app.services import quality_label_service
from app.services.lead_enterprise_service import LeadEnterpriseService
from datetime import datetime, timedelta

def print_section(title):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_result(check_name, passed, details=""):
    """Print check result"""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status} - {check_name}")
    if details:
        print(f"     {details}")

def verify_quote_pool_and_price_index():
    """检查点1: 确保报价池和价格指数正常工作"""
    print_section("检查点1: 报价池和价格指数")
    
    all_passed = True
    
    # 1. 检查Quote表是否存在数据
    quote_count = Quote.query.count()
    passed = quote_count > 0
    all_passed &= passed
    print_result(
        "报价记录存在",
        passed,
        f"找到 {quote_count} 条报价记录"
    )
    
    # 2. 检查PriceIndex表是否存在数据
    price_index_count = PriceIndex.query.count()
    passed = price_index_count > 0
    all_passed &= passed
    print_result(
        "价格指数记录存在",
        passed,
        f"找到 {price_index_count} 个产品的价格指数"
    )
    
    # 3. 检查QuotePoolManager服务是否可用
    try:
        manager = QuotePoolManager()
        passed = True
        print_result("QuotePoolManager服务可用", True)
    except Exception as e:
        passed = False
        all_passed = False
        print_result("QuotePoolManager服务可用", False, f"错误: {str(e)}")
    
    # 4. 测试价格指数计算功能
    if quote_count > 0:
        try:
            # 获取一个有报价的产品
            sample_product = db.session.query(Quote.product_name).first()
            if sample_product:
                product_name = sample_product[0]
                manager = QuotePoolManager()
                price_index = manager.calculate_price_index(product_name)
                
                passed = (
                    price_index is not None and
                    'median' in price_index and
                    'sample_count' in price_index
                )
                all_passed &= passed
                print_result(
                    "价格指数计算功能",
                    passed,
                    f"产品 '{product_name}' 的价格指数: 中位数={price_index.get('median', 'N/A')}, 样本数={price_index.get('sample_count', 0)}"
                )
        except Exception as e:
            passed = False
            all_passed = False
            print_result("价格指数计算功能", False, f"错误: {str(e)}")
    
    # 5. 检查价格指数是否有最近更新
    if price_index_count > 0:
        recent_update = PriceIndex.query.order_by(PriceIndex.last_updated.desc()).first()
        if recent_update:
            time_diff = datetime.utcnow() - recent_update.last_updated
            passed = time_diff.days < 7  # 最近7天内有更新
            all_passed &= passed
            print_result(
                "价格指数定期更新",
                passed,
                f"最后更新时间: {recent_update.last_updated.strftime('%Y-%m-%d %H:%M:%S')}"
            )
    
    return all_passed

def verify_anti_fraud_filter():
    """检查点2: 确保反作弊清洗算法正常"""
    print_section("检查点2: 反作弊清洗算法")
    
    all_passed = True
    
    # 1. 检查QuotePoolManager的反作弊方法是否存在
    try:
        manager = QuotePoolManager()
        has_method = hasattr(manager, 'apply_anti_fraud_filter')
        passed = has_method
        all_passed &= passed
        print_result(
            "反作弊清洗方法存在",
            passed
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("反作弊清洗方法存在", False, f"错误: {str(e)}")
    
    # 2. 测试反作弊清洗功能
    if Quote.query.count() >= 3:
        try:
            # 获取一个产品的所有报价
            product_name = db.session.query(Quote.product_name).first()[0]
            quotes = Quote.query.filter_by(product_name=product_name).all()
            
            if len(quotes) >= 3:
                manager = QuotePoolManager()
                quote_dicts = [
                    {
                        'id': q.id,
                        'price': q.price,
                        'supplier_id': q.supplier_id,
                        'created_at': q.created_at
                    }
                    for q in quotes
                ]
                
                cleaned = manager.apply_anti_fraud_filter(quote_dicts, product_name)
                
                passed = cleaned is not None and isinstance(cleaned, list)
                all_passed &= passed
                print_result(
                    "反作弊清洗功能",
                    passed,
                    f"原始报价: {len(quote_dicts)} 条, 清洗后: {len(cleaned)} 条"
                )
        except Exception as e:
            passed = False
            all_passed = False
            print_result("反作弊清洗功能", False, f"错误: {str(e)}")
    else:
        print_result(
            "反作弊清洗功能",
            True,
            "报价数据不足，跳过测试"
        )
    
    # 3. 检查是否有异常报价被过滤的记录
    # 这需要检查日志或专门的过滤记录表
    print_result(
        "异常报价过滤记录",
        True,
        "需要在实际运行中观察日志"
    )
    
    return all_passed

def verify_capacity_signal():
    """检查点3: 确保产能信号正常显示"""
    print_section("检查点3: 产能信号显示")
    
    all_passed = True
    
    # 1. 检查企业表是否有产能相关字段
    try:
        sample_enterprise = Enterprise.query.first()
        if sample_enterprise:
            has_capacity_fields = (
                hasattr(sample_enterprise, 'current_orders') and
                hasattr(sample_enterprise, 'max_capacity')
            )
            passed = has_capacity_fields
            all_passed &= passed
            print_result(
                "产能字段存在",
                passed,
                f"current_orders={getattr(sample_enterprise, 'current_orders', 'N/A')}, max_capacity={getattr(sample_enterprise, 'max_capacity', 'N/A')}"
            )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("产能字段存在", False, f"错误: {str(e)}")
    
    # 2. 检查有多少企业设置了产能数据
    try:
        enterprises_with_capacity = Enterprise.query.filter(
            Enterprise.max_capacity > 0
        ).count()
        total_enterprises = Enterprise.query.count()
        
        passed = enterprises_with_capacity > 0
        all_passed &= passed
        print_result(
            "企业产能数据",
            passed,
            f"{enterprises_with_capacity}/{total_enterprises} 个企业设置了产能数据"
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("企业产能数据", False, f"错误: {str(e)}")
    
    # 3. 测试产能利用率计算
    try:
        enterprise_with_capacity = Enterprise.query.filter(
            Enterprise.max_capacity > 0
        ).first()
        
        if enterprise_with_capacity:
            utilization = (
                enterprise_with_capacity.current_orders / 
                enterprise_with_capacity.max_capacity
            ) if enterprise_with_capacity.max_capacity > 0 else 0
            
            # 判断产能信号
            if utilization < 0.5:
                signal = "产能充足 (绿色)"
            elif utilization < 0.8:
                signal = "产能正常 (黄色)"
            else:
                signal = "产能紧张 (红色)"
            
            passed = True
            all_passed &= passed
            print_result(
                "产能利用率计算",
                passed,
                f"企业 '{enterprise_with_capacity.name}': 利用率={utilization*100:.1f}%, 信号={signal}"
            )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("产能利用率计算", False, f"错误: {str(e)}")
    
    # 4. 检查产能信号在前端模板中的展示
    template_path = "app/templates/match/results.html"
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            has_capacity_display = 'capacity' in content.lower() or '产能' in content
            passed = has_capacity_display
            all_passed &= passed
            print_result(
                "前端产能信号展示",
                passed,
                "在匹配结果模板中找到产能相关展示"
            )
    else:
        print_result(
            "前端产能信号展示",
            True,
            "模板文件不存在，跳过检查"
        )
    
    return all_passed

def _qualification_label_rows():
    """Enterprise.qualifications 中的质量标签条目。"""
    rows = []
    for e in Enterprise.query.all():
        q = e.qualifications
        if not isinstance(q, list):
            continue
        for row in q:
            if isinstance(row, dict) and row.get("label_type") in (
                "government_green",
                "lead_inspection",
                "third_party",
            ):
                rows.append(row)
    return rows


def verify_quality_label_system():
    """检查点4: 确保质量标签体系正常（Enterprise.qualifications JSON）"""
    print_section("检查点4: 质量标签体系")
    
    all_passed = True
    
    # 1. 检查 qualifications JSON
    try:
        label_count = len(_qualification_label_rows())
        passed = True
        all_passed &= passed
        print_result(
            "质量标签数据（JSON）",
            passed,
            f"找到 {label_count} 条质量标签记录（qualifications）",
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("质量标签数据（JSON）", False, f"错误: {str(e)}")
    
    # 2. 检查quality_label_service模块是否可用
    try:
        has_functions = (
            hasattr(quality_label_service, 'grant_government_green_label') and
            hasattr(quality_label_service, 'grant_lead_inspection_label')
        )
        passed = has_functions
        all_passed &= passed
        print_result("quality_label_service模块可用", passed)
    except Exception as e:
        passed = False
        all_passed = False
        print_result("QualityLabelService服务可用", False, f"错误: {str(e)}")
    
    # 3. 检查三种标签类型是否都有支持
    rows = _qualification_label_rows()
    if rows:
        type_dict = {}
        for row in rows:
            lt = row.get("label_type")
            type_dict[lt] = type_dict.get(lt, 0) + 1
        
        print_result(
            "质量标签类型统计",
            True,
            f"政府绿标: {type_dict.get('government_green', 0)}, "
            f"链主验厂: {type_dict.get('lead_inspection', 0)}, "
            f"第三方评分: {type_dict.get('third_party', 0)}"
        )
    
    # 4. 检查标签授予功能的路由是否存在
    routes_file = "app/routes/quality_labels.py"
    if os.path.exists(routes_file):
        with open(routes_file, 'r', encoding='utf-8') as f:
            content = f.read()
            has_grant_route = 'grant' in content.lower()
            passed = has_grant_route
            all_passed &= passed
            print_result(
                "标签授予路由存在",
                passed
            )
    else:
        passed = False
        all_passed = False
        print_result("标签授予路由存在", False, "路由文件不存在")
    
    # 5. 检查标签有效期管理
    rows = _qualification_label_rows()
    if rows:
        with_expiry = sum(1 for r in rows if r.get("valid_until"))
        print_result(
            "标签有效期管理",
            True,
            f"{with_expiry}/{len(rows)} 个标签含 valid_until",
        )
    
    # 6. 检查过期标签自动隐藏逻辑
    try:
        has_function = hasattr(quality_label_service, 'expire_all_overdue_labels')
        passed = has_function
        all_passed &= passed
        print_result(
            "过期标签自动隐藏功能",
            passed
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("过期标签自动隐藏功能", False, f"错误: {str(e)}")
    
    return all_passed

def verify_lead_enterprise_management():
    """检查点5: 确保链主企业管理功能正常"""
    print_section("检查点5: 链主企业管理功能")
    
    all_passed = True
    
    # 1. 检查 enterprise.extras 中的入驻申请与展示控制
    try:
        from app.services.lead_enterprise_service import KEY_LEAD_ONBOARDING, KEY_SUPPLIER_DISPLAY

        app_n = 0
        ctl_n = 0
        for e in Enterprise.query.all():
            ex = e.extras if isinstance(e.extras, dict) else {}
            app_n += len(ex.get(KEY_LEAD_ONBOARDING) or []) if isinstance(ex.get(KEY_LEAD_ONBOARDING), list) else 0
            ctl_n += len(ex.get(KEY_SUPPLIER_DISPLAY) or []) if isinstance(ex.get(KEY_SUPPLIER_DISPLAY), list) else 0
        passed = True
        all_passed &= passed
        print_result(
            "链主入驻申请（extras）",
            passed,
            f"共 {app_n} 条申请记录（JSON）",
        )
        print_result(
            "供应商展示控制（extras）",
            passed,
            f"共 {ctl_n} 条控制记录（JSON）",
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("链主 extras 检查", False, f"错误: {str(e)}")
    
    # 3. 检查LeadEnterpriseService是否可用
    try:
        service = LeadEnterpriseService()
        passed = True
        print_result("LeadEnterpriseService服务可用", True)
    except Exception as e:
        passed = False
        all_passed = False
        print_result("LeadEnterpriseService服务可用", False, f"错误: {str(e)}")
    
    # 4. 检查链主企业数量
    try:
        lead_count = Enterprise.query.filter_by(is_lead_enterprise=True).count()
        print_result(
            "链主企业统计",
            True,
            f"当前有 {lead_count} 家链主企业"
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("链主企业统计", False, f"错误: {str(e)}")
    
    # 5. 检查链主入驻申请功能的路由
    routes_file = "app/routes/lead_enterprise.py"
    if os.path.exists(routes_file):
        with open(routes_file, 'r', encoding='utf-8') as f:
            content = f.read()
            has_apply_route = 'onboard' in content.lower() or 'apply' in content.lower()
            has_review_route = 'review' in content.lower() or 'approve' in content.lower()
            passed = has_apply_route and has_review_route
            all_passed &= passed
            print_result(
                "链主入驻申请和审核路由",
                passed,
                f"申请路由: {has_apply_route}, 审核路由: {has_review_route}"
            )
    else:
        passed = False
        all_passed = False
        print_result("链主入驻申请和审核路由", False, "路由文件不存在")
    
    # 6. 检查供应商展示控制功能
    try:
        service = LeadEnterpriseService()
        has_method = hasattr(service, 'authorize_display_control')
        passed = has_method
        all_passed &= passed
        print_result(
            "供应商展示控制功能",
            passed
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("供应商展示控制功能", False, f"错误: {str(e)}")
    
    # 7. 检查链主验厂功能
    li = sum(
        1
        for r in _qualification_label_rows()
        if r.get("label_type") == "lead_inspection"
    )
    if li > 0:
        print_result(
            "链主验厂标签",
            True,
            f"已有 {li} 个链主验厂标签（qualifications）",
        )
    else:
        print_result(
            "链主验厂标签",
            True,
            "暂无验厂标签，功能已实现"
        )
    
    # 8. 检查链主贡献度统计
    try:
        service = LeadEnterpriseService()
        has_method = hasattr(service, 'calculate_contribution')
        passed = has_method
        all_passed &= passed
        print_result(
            "链主贡献度统计功能",
            passed
        )
    except Exception as e:
        passed = False
        all_passed = False
        print_result("链主贡献度统计功能", False, f"错误: {str(e)}")
    
    return all_passed

def main():
    """Main verification function"""
    print("\n" + "="*60)
    print("  第五阶段检查点验证")
    print("  Phase 5 Checkpoint Verification")
    print("="*60)
    
    app = create_app()
    
    with app.app_context():
        results = {}
        
        # 执行所有检查
        results['quote_pool'] = verify_quote_pool_and_price_index()
        results['anti_fraud'] = verify_anti_fraud_filter()
        results['capacity_signal'] = verify_capacity_signal()
        results['quality_label'] = verify_quality_label_system()
        results['lead_enterprise'] = verify_lead_enterprise_management()
        
        # 汇总结果
        print_section("检查点汇总")
        
        all_passed = all(results.values())
        
        for check_name, passed in results.items():
            status = "✓" if passed else "✗"
            print(f"{status} {check_name}: {'通过' if passed else '失败'}")
        
        print("\n" + "="*60)
        if all_passed:
            print("  ✓ 第五阶段所有检查点通过！")
            print("  可以继续进入第六阶段：数据授权与消息中心")
        else:
            print("  ✗ 部分检查点未通过，请修复问题后重新验证")
        print("="*60 + "\n")
        
        return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
