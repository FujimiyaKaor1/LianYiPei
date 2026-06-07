#!/usr/bin/env python
"""
发票验证系统功能验证脚本
Verification script for invoice validation system

验证内容:
1. InvoiceValidator类的核心方法
2. 发票验证流程
3. 履约数据存储
4. 失败重试机制
5. 人工审核触发
"""

import sys
from app import create_app, db
from app.models import Enterprise, Transaction
from app.services.invoice_validator import (
    validate_invoice,
    call_tax_api,
    extract_invoice_info,
    store_fulfillment_data,
    get_manual_review_list,
    _increment_failure_count,
    _get_failure_count,
    _clear_failure_count
)


def print_section(title):
    """打印分节标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_invoice_validator_methods(app):
    """测试 InvoiceValidator 类的核心方法"""
    print_section("测试 1: InvoiceValidator 核心方法")
    
    with app.app_context():
        # 测试有效发票
        print("1.1 测试有效发票验证...")
        valid_invoice = {
            'invoice_no': 'TEST12345678',
            'invoice_code': '1234567890',
            'invoice_date': '2024-01-15',
            'invoice_amount': 10000.00,
            'buyer_tax_no': '91110000000000000X',
            'seller_tax_no': '91110000000000001Y'
        }
        
        result = validate_invoice(valid_invoice)
        assert result['valid'] is True, "有效发票验证失败"
        assert result['invoice_no'] == 'TEST12345678', "发票号码不匹配"
        assert result['amount'] == 10000.00, "发票金额不匹配"
        print("✓ 有效发票验证通过")
        
        # 测试无效发票
        print("\n1.2 测试无效发票验证...")
        invalid_invoice = {
            'invoice_no': 'INVALID12345',
            'invoice_code': '1234567890',
            'invoice_date': '2024-01-15',
            'invoice_amount': 10000.00
        }
        
        result = validate_invoice(invalid_invoice)
        assert result['valid'] is False, "无效发票应该被拒绝"
        assert 'error' in result, "应该返回错误信息"
        print("✓ 无效发票正确拒绝")
        
        # 测试缺少必填字段
        print("\n1.3 测试缺少必填字段...")
        incomplete_invoice = {
            'invoice_code': '1234567890',
            'invoice_date': '2024-01-15'
            # 缺少 invoice_no 和 invoice_amount
        }
        
        result = validate_invoice(incomplete_invoice)
        assert result['valid'] is False, "缺少必填字段应该被拒绝"
        assert '缺少必填字段' in result['error'], "错误信息不正确"
        print("✓ 缺少必填字段正确处理")
        
        print("\n✅ InvoiceValidator 核心方法测试通过")


def test_tax_api_integration(app):
    """测试税务API集成"""
    print_section("测试 2: 税务API集成")
    
    with app.app_context():
        print("2.1 测试税务API调用（模拟模式）...")
        result = call_tax_api(
            invoice_no='TEST12345678',
            invoice_code='1234567890',
            invoice_date='2024-01-15',
            invoice_amount=10000.00
        )
        
        assert result['valid'] is True, "税务API调用失败"
        assert result['invoice_no'] == 'TEST12345678', "返回的发票号码不匹配"
        print("✓ 税务API调用成功（模拟模式）")
        
        print("\n2.2 测试无效发票的API响应...")
        result = call_tax_api(
            invoice_no='INVALID12345',
            invoice_code='1234567890',
            invoice_date='2024-01-15',
            invoice_amount=10000.00
        )
        
        assert result['valid'] is False, "无效发票应该返回失败"
        assert 'error' in result, "应该包含错误信息"
        print("✓ 无效发票API响应正确")
        
        print("\n✅ 税务API集成测试通过")


def test_invoice_info_extraction():
    """测试发票信息提取"""
    print_section("测试 3: 发票信息提取")
    
    invoice_data = {
        'invoice_no': 'TEST12345678',
        'invoice_code': '1234567890',
        'invoice_amount': 10000.00,
        'invoice_date': '2024-01-15',
        'collaboration_code': 'LYP2401151234ABCDE',
        'delivery_date': '2024-01-20',
        'quality_rating': 5
    }
    
    tax_api_result = {
        'valid': True,
        'invoice_no': 'TEST12345678',
        'invoice_code': '1234567890',
        'amount': 10000.00,
        'date': '2024-01-15',
        'buyer_name': '测试买方企业',
        'seller_name': '测试卖方企业',
        'buyer_tax_no': '91110000000000000X',
        'seller_tax_no': '91110000000000001Y'
    }
    
    print("3.1 提取发票基本信息...")
    result = extract_invoice_info(invoice_data, tax_api_result)
    
    assert result['invoice_no'] == 'TEST12345678', "发票号码提取错误"
    assert result['amount'] == 10000.00, "发票金额提取错误"
    assert result['buyer'] == '测试买方企业', "买方信息提取错误"
    assert result['seller'] == '测试卖方企业', "卖方信息提取错误"
    print("✓ 基本信息提取正确")
    
    print("\n3.2 提取可选字段...")
    assert result['collaboration_code'] == 'LYP2401151234ABCDE', "撮合码提取错误"
    assert result['delivery_date'] == '2024-01-20', "交付日期提取错误"
    assert result['quality_rating'] == 5, "质量评分提取错误"
    print("✓ 可选字段提取正确")
    
    print("\n✅ 发票信息提取测试通过")


def test_fulfillment_data_storage(app):
    """测试履约数据存储"""
    print_section("测试 4: 履约数据存储")
    
    with app.app_context():
        # 查找测试企业
        buyer = Enterprise.query.filter_by(name='测试买方企业').first()
        seller = Enterprise.query.filter_by(name='测试卖方企业').first()
        
        if not buyer:
            buyer = Enterprise(
                name='测试买方企业',
                address='北京市朝阳区',
                credit_score=75.0
            )
            db.session.add(buyer)
        
        if not seller:
            seller = Enterprise(
                name='测试卖方企业',
                address='北京市海淀区',
                credit_score=80.0
            )
            db.session.add(seller)
        
        db.session.commit()
        
        print(f"4.1 存储履约数据（买方ID: {buyer.id}, 卖方ID: {seller.id}）...")
        
        invoice_info = {
            'invoice_no': 'TEST12345678',
            'invoice_code': '1234567890',
            'amount': 10000.00,
            'date': '2024-01-15',
            'collaboration_code': 'LYP2401151234ABCDE',
            'delivery_date': '2024-01-20',
            'quality_rating': 5
        }
        
        fulfillment = store_fulfillment_data(
            invoice_info=invoice_info,
            buyer_id=buyer.id,
            seller_id=seller.id
        )
        
        assert fulfillment is not None, "履约数据存储失败"
        assert fulfillment.invoice_no == 'TEST12345678', "发票号码存储错误"
        assert fulfillment.invoice_amount == 10000.00, "发票金额存储错误"
        assert fulfillment.buyer_id == buyer.id, "买方ID存储错误"
        assert fulfillment.seller_id == seller.id, "卖方ID存储错误"
        assert fulfillment.verified is True, "验证状态应为True"
        assert fulfillment.on_time is True, "应判断为按时交付"
        print("✓ 履约数据存储成功")
        
        print("\n4.2 验证按时交付判断...")
        # 测试延迟交付
        late_invoice_info = {
            'invoice_no': 'TEST87654321',
            'amount': 5000.00,
            'date': '2024-01-15',
            'delivery_date': '2024-01-30'  # 15天后，超过7天阈值
        }
        
        late_fulfillment = store_fulfillment_data(
            invoice_info=late_invoice_info,
            buyer_id=buyer.id,
            seller_id=seller.id
        )
        
        assert late_fulfillment.on_time is False, "应判断为延迟交付"
        print("✓ 延迟交付判断正确")
        
        print("\n✅ 履约数据存储测试通过")


def test_failure_retry_mechanism():
    """测试失败重试机制"""
    print_section("测试 5: 失败重试机制")
    
    test_invoice_no = 'TEST_RETRY_12345'
    
    print("5.1 测试失败计数...")
    _clear_failure_count(test_invoice_no)
    
    count1 = _increment_failure_count(test_invoice_no)
    assert count1 == 1, "第一次失败计数应为1"
    print(f"✓ 第1次失败，计数: {count1}")
    
    count2 = _increment_failure_count(test_invoice_no)
    assert count2 == 2, "第二次失败计数应为2"
    print(f"✓ 第2次失败，计数: {count2}")
    
    count3 = _increment_failure_count(test_invoice_no)
    assert count3 == 3, "第三次失败计数应为3"
    print(f"✓ 第3次失败，计数: {count3}")
    
    print("\n5.2 测试人工审核触发...")
    current_count = _get_failure_count(test_invoice_no)
    assert current_count >= 3, "失败次数应该触发人工审核"
    print(f"✓ 失败次数达到 {current_count}，应触发人工审核")
    
    print("\n5.3 测试失败计数清除...")
    _clear_failure_count(test_invoice_no)
    cleared_count = _get_failure_count(test_invoice_no)
    assert cleared_count == 0, "清除后计数应为0"
    print("✓ 失败计数已清除")
    
    print("\n✅ 失败重试机制测试通过")


def test_manual_review_trigger(app):
    """测试人工审核触发"""
    print_section("测试 6: 人工审核触发")
    
    with app.app_context():
        print("6.1 模拟多次验证失败...")
        test_invoice = {
            'invoice_no': 'INVALID_MANUAL_REVIEW',
            'invoice_code': '1234567890',
            'invoice_date': '2024-01-15',
            'invoice_amount': 10000.00
        }
        
        # 清除之前的计数
        _clear_failure_count(test_invoice['invoice_no'])
        
        # 第1次失败
        result1 = validate_invoice(test_invoice)
        assert result1['valid'] is False, "第1次应该失败"
        assert result1.get('manual_review_required') is False, "第1次不应触发人工审核"
        print(f"✓ 第1次失败，manual_review_required: {result1.get('manual_review_required')}")
        
        # 第2次失败
        result2 = validate_invoice(test_invoice)
        assert result2['valid'] is False, "第2次应该失败"
        assert result2.get('manual_review_required') is False, "第2次不应触发人工审核"
        print(f"✓ 第2次失败，manual_review_required: {result2.get('manual_review_required')}")
        
        # 第3次失败
        result3 = validate_invoice(test_invoice)
        assert result3['valid'] is False, "第3次应该失败"
        assert result3.get('manual_review_required') is True, "第3次应触发人工审核"
        print(f"✓ 第3次失败，manual_review_required: {result3.get('manual_review_required')}")
        
        print("\n6.2 检查人工审核列表...")
        manual_review_list = get_manual_review_list()
        assert len(manual_review_list) > 0, "应该有需要人工审核的发票"
        
        found = False
        for item in manual_review_list:
            if item['invoice_no'] == test_invoice['invoice_no']:
                found = True
                print(f"✓ 发票 {item['invoice_no']} 在人工审核列表中，失败次数: {item['failure_count']}")
                break
        
        assert found, "测试发票应该在人工审核列表中"
        
        # 清理
        _clear_failure_count(test_invoice['invoice_no'])
        
        print("\n✅ 人工审核触发测试通过")


def main():
    """主函数"""
    print("\n" + "="*60)
    print("  发票验证系统功能验证")
    print("  Invoice Validation System Verification")
    print("="*60)
    
    # 创建应用上下文
    app = create_app()
    
    try:
        # 运行测试
        test_invoice_validator_methods(app)
        test_tax_api_integration(app)
        test_invoice_info_extraction()
        test_fulfillment_data_storage(app)
        test_failure_retry_mechanism()
        test_manual_review_trigger(app)
        
        # 总结
        print_section("验证总结")
        print("✅ 所有测试通过！")
        print("\n已验证功能:")
        print("  1. ✓ InvoiceValidator 类的核心方法")
        print("  2. ✓ 税务API集成（模拟模式）")
        print("  3. ✓ 发票信息提取")
        print("  4. ✓ 履约数据存储")
        print("  5. ✓ 失败重试机制")
        print("  6. ✓ 人工审核触发（失败3次）")
        print("\n发票验证系统已就绪！")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {str(e)}")
        return 1
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
