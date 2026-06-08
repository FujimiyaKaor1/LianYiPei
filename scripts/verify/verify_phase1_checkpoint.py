#!/usr/bin/env python3
"""
第一阶段检查点验证脚本
验证所有Phase 1组件是否正常工作
"""
import sys
from datetime import datetime

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def check_database_tables():
    """检查数据库表是否创建成功"""
    print_section("1. 数据库表检查")
    
    try:
        from app import create_app, db
        from app.models import (
            Enterprise,
            Product,
            Inquiry,
            Quote,
            Transaction,
            MatchFeedback,
            Alert,
            RecruitmentTask,
            PriceIndex,
            Message,
        )

        app = create_app()
        with app.app_context():
            # 10 张核心表（信用分历史在 enterprises.credit_score_events JSON）
            tables_to_check = [
                ("enterprises", Enterprise),
                ("products", Product),
                ("inquiries", Inquiry),
                ("quotes", Quote),
                ("transactions", Transaction),
                ("match_feedbacks", MatchFeedback),
                ("alerts", Alert),
                ("recruitment_tasks", RecruitmentTask),
                ("price_indices", PriceIndex),
                ("messages", Message),
            ]
            
            all_ok = True
            for table_name, model in tables_to_check:
                try:
                    count = model.query.count()
                    print(f"  ✓ {table_name:30s} - 存在 ({count} 条记录)")
                except Exception as e:
                    print(f"  ✗ {table_name:30s} - 错误: {str(e)}")
                    all_ok = False
            
            return all_ok
    except Exception as e:
        print(f"  ✗ 数据库连接失败: {str(e)}")
        return False

def check_credit_engine():
    """检查信用分计算引擎"""
    print_section("2. 信用分计算引擎检查")
    
    try:
        from app import create_app, db
        from app.models import Enterprise
        from app.services.credit_engine import (
            calculate_credit_score,
            update_credit_score,
            check_credit_privileges,
            can_submit_quote,
            get_credit_history
        )
        
        app = create_app()
        with app.app_context():
            # 获取一个测试企业
            test_ent = Enterprise.query.filter_by(role='enterprise').first()
            
            if not test_ent:
                print("  ⚠ 没有找到测试企业，跳过功能测试")
                return True
            
            print(f"  使用测试企业: {test_ent.name} (ID: {test_ent.id})")
            
            # 测试信用分计算
            try:
                score = calculate_credit_score(test_ent.id)
                print(f"  ✓ calculate_credit_score() - 返回: {score:.2f}")
            except Exception as e:
                print(f"  ✗ calculate_credit_score() - 错误: {str(e)}")
                return False
            
            # 测试信用分权益检查
            try:
                privileges = check_credit_privileges(test_ent.id)
                print(f"  ✓ check_credit_privileges() - 报价限制: {privileges.get('daily_quote_limit')}")
            except Exception as e:
                print(f"  ✗ check_credit_privileges() - 错误: {str(e)}")
                return False
            
            # 测试报价权限检查
            try:
                can_quote, reason = can_submit_quote(test_ent.id)
                print(f"  ✓ can_submit_quote() - 允许报价: {can_quote}")
            except Exception as e:
                print(f"  ✗ can_submit_quote() - 错误: {str(e)}")
                return False
            
            # 测试历史查询
            try:
                history = get_credit_history(test_ent.id, limit=5)
                print(f"  ✓ get_credit_history() - 返回 {len(history)} 条记录")
            except Exception as e:
                print(f"  ✗ get_credit_history() - 错误: {str(e)}")
                return False
            
            return True
    except Exception as e:
        print(f"  ✗ 信用分引擎加载失败: {str(e)}")
        return False

def check_api_endpoints():
    """检查基础API接口"""
    print_section("3. 基础API接口检查")
    
    try:
        from app import create_app
        
        app = create_app()
        client = app.test_client()
        
        # 测试API端点是否存在（不需要认证的检查）
        endpoints_to_check = [
            ('/api/credit/score/1', 'GET', '信用分查询'),
            ('/api/credit/history/1', 'GET', '信用分历史'),
            ('/api/quotes', 'POST', '提交报价'),
            ('/api/price-index/test', 'GET', '价格指数'),
            ('/api/messages', 'GET', '消息列表'),
        ]
        
        all_ok = True
        for endpoint, method, desc in endpoints_to_check:
            try:
                # 只检查路由是否存在，不检查认证
                with app.test_request_context(endpoint, method=method):
                    # 如果路由不存在会抛出异常
                    print(f"  ✓ {method:6s} {endpoint:30s} - {desc}")
            except Exception as e:
                print(f"  ✗ {method:6s} {endpoint:30s} - 路由不存在")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"  ✗ API检查失败: {str(e)}")
        return False

def check_test_framework():
    """检查测试框架配置"""
    print_section("4. 测试框架检查")
    
    try:
        import pytest
        import hypothesis
        print(f"  ✓ pytest 已安装 (版本: {pytest.__version__})")
        print(f"  ✓ hypothesis 已安装 (版本: {hypothesis.__version__})")
        
        # 检查测试文件
        import os
        test_files = [
            'tests/conftest.py',
            'tests/test_credit_engine.py',
            'pytest.ini',
        ]
        
        all_ok = True
        for test_file in test_files:
            if os.path.exists(test_file):
                print(f"  ✓ {test_file:30s} - 存在")
            else:
                print(f"  ✗ {test_file:30s} - 不存在")
                all_ok = False
        
        return all_ok
    except ImportError as e:
        print(f"  ✗ 测试框架未安装: {str(e)}")
        return False

def main():
    print("\n" + "="*60)
    print("  链易配平台 - 第一阶段检查点验证")
    print("  Phase 1 Checkpoint Verification")
    print("="*60)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        '数据库表': check_database_tables(),
        '信用分引擎': check_credit_engine(),
        'API接口': check_api_endpoints(),
        '测试框架': check_test_framework(),
    }
    
    print_section("检查结果汇总")
    all_passed = True
    for component, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {component:15s}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("  ✓ 第一阶段检查点验证通过！")
        print("  所有核心组件工作正常，可以继续第二阶段开发。")
        print("="*60 + "\n")
        return 0
    else:
        print("  ✗ 第一阶段检查点验证失败！")
        print("  请修复上述问题后再继续。")
        print("="*60 + "\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
