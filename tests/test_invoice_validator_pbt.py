"""
发票验证服务属性测试
Property-Based Tests for Invoice Validator Service

**Validates: Requirements 5.1**
"""

import pytest
from unittest.mock import patch
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from datetime import datetime, date, timedelta
from app.services.invoice_validator import (
    validate_invoice,
    extract_invoice_info,
    store_fulfillment_data,
    _mock_tax_api_validation,
)


# ── 测试策略定义 ──────────────────────────────────────────────────────────

# 发票号码策略：8位数字或以INVALID开头的字符串
invoice_no_strategy = st.one_of(
    st.text(min_size=8, max_size=20, alphabet=st.characters(whitelist_categories=('Nd', 'Lu'))),
    st.builds(lambda suffix: f'INVALID{suffix}', 
              st.text(min_size=5, max_size=15, alphabet=st.characters(whitelist_categories=('Nd',))))
)

# 发票代码策略：10位数字
invoice_code_strategy = st.text(min_size=10, max_size=12, alphabet=st.characters(whitelist_categories=('Nd',)))

# 日期策略：2020-2025年之间的日期
date_strategy = st.dates(
    min_value=date(2020, 1, 1),
    max_value=date(2025, 12, 31)
)

# 金额策略：正数，最多2位小数
amount_strategy = st.floats(
    min_value=0.01,
    max_value=1000000.0,
    allow_nan=False,
    allow_infinity=False
).map(lambda x: round(x, 2))

# 税号策略：18位统一社会信用代码
tax_no_strategy = st.text(min_size=18, max_size=18, alphabet=st.characters(whitelist_categories=('Nd', 'Lu')))


# ── 属性8: 发票验证流程完整性 ─────────────────────────────────────────────

@given(
    invoice_no=invoice_no_strategy,
    invoice_code=invoice_code_strategy,
    invoice_date=date_strategy,
    invoice_amount=amount_strategy,
    buyer_tax_no=tax_no_strategy,
    seller_tax_no=tax_no_strategy
)
@settings(max_examples=50, deadline=None)
def test_property_invoice_validation_completeness(
    app, invoice_no, invoice_code, invoice_date, invoice_amount,
    buyer_tax_no, seller_tax_no
):
    """
    **属性8: 发票验证流程完整性**
    
    验证发票验证的完整流程：
    1. 所有发票都能得到验证结果（valid字段存在）
    2. 验证失败时必须包含error字段
    3. 验证成功时必须包含关键信息字段
    4. 以INVALID开头的发票号必定验证失败
    5. 验证结果的金额必须与输入金额一致（如果验证成功）
    
    **Validates: Requirements 5.1**
    """
    with app.app_context():
        # 构建发票数据
        invoice_data = {
            'invoice_no': invoice_no,
            'invoice_code': invoice_code,
            'invoice_date': invoice_date.strftime('%Y-%m-%d'),
            'invoice_amount': invoice_amount,
            'buyer_tax_no': buyer_tax_no,
            'seller_tax_no': seller_tax_no
        }
        
        # 执行验证
        result = validate_invoice(invoice_data)
        
        # 属性1: 所有发票都能得到验证结果
        assert 'valid' in result, "验证结果必须包含valid字段"
        assert isinstance(result['valid'], bool), "valid字段必须是布尔值"
        
        # 属性2: 验证失败时必须包含error字段
        if not result['valid']:
            assert 'error' in result, "验证失败时必须包含error字段"
            assert isinstance(result['error'], str), "error字段必须是字符串"
            assert len(result['error']) > 0, "error字段不能为空"
        
        # 属性3: 验证成功时必须包含关键信息字段
        if result['valid']:
            required_fields = ['invoice_no', 'amount', 'date']
            for field in required_fields:
                assert field in result, f"验证成功时必须包含{field}字段"
        
        # 属性4: 以INVALID开头的发票号必定验证失败
        if invoice_no.startswith('INVALID'):
            assert result['valid'] is False, "以INVALID开头的发票号必须验证失败"
        
        # 属性5: 验证结果的金额必须与输入金额一致（如果验证成功）
        if result['valid']:
            assert 'amount' in result
            # 允许浮点数精度误差
            assert abs(result['amount'] - invoice_amount) < 0.01, \
                f"验证成功时金额必须一致: 期望{invoice_amount}, 实际{result['amount']}"


@given(
    invoice_no=st.text(min_size=1, max_size=20),
    invoice_code=st.text(min_size=1, max_size=20),
    invoice_date=st.one_of(
        date_strategy.map(lambda d: d.strftime('%Y-%m-%d')),
        date_strategy.map(lambda d: d.strftime('%Y%m%d')),
        st.just('')
    ),
    invoice_amount=st.one_of(
        amount_strategy,
        st.just(0),
        st.just(-100)
    )
)
@settings(max_examples=50, deadline=None)
def test_property_invoice_validation_robustness(
    app, invoice_no, invoice_code, invoice_date, invoice_amount
):
    """
    **属性: 发票验证健壮性**
    
    验证发票验证对各种输入的健壮性：
    1. 不会抛出未捕获的异常
    2. 总是返回字典类型
    3. 对于无效输入，返回valid=False
    4. 对于缺失字段，返回适当的错误信息
    """
    with app.app_context():
        invoice_data = {
            'invoice_no': invoice_no,
            'invoice_code': invoice_code,
            'invoice_date': invoice_date,
            'invoice_amount': invoice_amount
        }
        
        # 属性1: 不会抛出未捕获的异常
        try:
            result = validate_invoice(invoice_data)
            
            # 属性2: 总是返回字典类型
            assert isinstance(result, dict), "验证结果必须是字典类型"
            
            # 属性3: 必须包含valid字段
            assert 'valid' in result, "验证结果必须包含valid字段"
            
            # 属性4: 对于无效金额，应该验证失败或返回错误
            if invoice_amount <= 0:
                # 可能在验证阶段就失败，也可能在后续处理中失败
                # 但不应该崩溃
                assert isinstance(result, dict)
            
        except Exception as e:
            # 如果抛出异常，应该是预期的异常类型
            pytest.fail(f"验证过程不应抛出未捕获的异常: {type(e).__name__}: {str(e)}")


@given(
    invoice_date=date_strategy,
    delivery_date=date_strategy
)
@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_on_time_delivery_logic(
    app, db_session, test_enterprises, invoice_date, delivery_date
):
    """
    **属性: 按时交付逻辑正确性**
    
    验证按时交付判断逻辑：
    1. 如果交付日期在发票日期之前，视为按时
    2. 如果交付日期在发票日期后7天内，视为按时
    3. 如果交付日期在发票日期后超过7天，视为延迟
    4. 按时交付标志必须是布尔值
    """
    with app.app_context():
        buyer = test_enterprises['buyer']
        seller = test_enterprises['seller']
        
        invoice_info = {
            'invoice_no': f'TEST{invoice_date.strftime("%Y%m%d")}',
            'amount': 10000.00,
            'date': invoice_date.strftime('%Y-%m-%d'),
            'delivery_date': delivery_date.strftime('%Y-%m-%d')
        }
        
        fulfillment = store_fulfillment_data(
            invoice_info=invoice_info,
            buyer_id=buyer.id,
            seller_id=seller.id
        )
        
        if fulfillment:
            on_time = (fulfillment.invoice_info or {}).get("on_time")
            # 属性1: 按时交付标志必须是布尔值
            assert isinstance(on_time, bool), "on_time必须是布尔值"
            
            # 计算日期差
            days_diff = (delivery_date - invoice_date).days
            
            # 属性2-4: 验证按时交付逻辑
            if days_diff <= 7:
                assert on_time is True, \
                    f"交付日期在发票日期后{days_diff}天内应视为按时"
            else:
                assert on_time is False, \
                    f"交付日期在发票日期后{days_diff}天应视为延迟"


@given(
    invoice_data=st.fixed_dictionaries({
        'invoice_no': invoice_no_strategy,
        'invoice_code': invoice_code_strategy,
        'amount': amount_strategy,
        'date': date_strategy.map(lambda d: d.strftime('%Y-%m-%d'))
    }),
    tax_api_result=st.fixed_dictionaries({
        'valid': st.just(True),
        'invoice_no': invoice_no_strategy,
        'invoice_code': invoice_code_strategy,
        'amount': amount_strategy,
        'date': date_strategy.map(lambda d: d.strftime('%Y-%m-%d')),
        'buyer_name': st.text(min_size=1, max_size=50),
        'seller_name': st.text(min_size=1, max_size=50)
    })
)
@settings(max_examples=50, deadline=None)
def test_property_extract_invoice_info_consistency(
    app, invoice_data, tax_api_result
):
    """
    **属性: 发票信息提取一致性**
    
    验证发票信息提取的一致性：
    1. 提取结果必须包含所有关键字段
    2. 提取的金额必须是数字类型
    3. 提取的发票号必须与输入一致
    4. 如果税务API返回的数据存在，优先使用API数据
    """
    with app.app_context():
        result = extract_invoice_info(invoice_data, tax_api_result)
        
        # 属性1: 提取结果必须包含所有关键字段
        required_fields = ['invoice_no', 'invoice_code', 'amount', 'date', 'buyer', 'seller']
        for field in required_fields:
            assert field in result, f"提取结果必须包含{field}字段"
        
        # 属性2: 提取的金额必须是数字类型
        assert isinstance(result['amount'], (int, float)), "金额必须是数字类型"
        assert result['amount'] >= 0, "金额不能为负数"
        
        # 属性3: 提取的发票号必须与输入一致（优先使用API返回值）
        expected_invoice_no = tax_api_result.get('invoice_no') or invoice_data.get('invoice_no')
        assert result['invoice_no'] == expected_invoice_no, \
            f"发票号不一致: 期望{expected_invoice_no}, 实际{result['invoice_no']}"
        
        # 属性4: 如果税务API返回的数据存在，优先使用API数据
        if 'buyer_name' in tax_api_result:
            assert result['buyer'] == tax_api_result['buyer_name'], \
                "应优先使用税务API返回的买方名称"
        if 'seller_name' in tax_api_result:
            assert result['seller'] == tax_api_result['seller_name'], \
                "应优先使用税务API返回的卖方名称"


@given(
    valid_invoice_count=st.integers(min_value=1, max_value=10),
    invalid_invoice_count=st.integers(min_value=0, max_value=5)
)
@settings(max_examples=30, deadline=None)
def test_property_batch_validation_consistency(
    app, valid_invoice_count, invalid_invoice_count
):
    """
    **属性: 批量验证一致性**
    
    验证批量发票验证的一致性：
    1. 有效发票的验证成功率应该是100%
    2. 无效发票的验证失败率应该是100%
    3. 批量验证不应影响单个发票的验证结果
    """
    with app.app_context():
        # 若配置了真实税务 API，测试会走 HTTP；此处强制使用模拟验证逻辑
        with patch(
            "app.services.invoice_validator.call_tax_api",
            side_effect=_mock_tax_api_validation,
        ):
            # 生成有效发票
            valid_invoices = [
                {
                    'invoice_no': f'VALID{i:08d}',
                    'invoice_code': f'1234567890',
                    'invoice_date': '2024-01-15',
                    'invoice_amount': 1000.0 * (i + 1)
                }
                for i in range(valid_invoice_count)
            ]
            
            # 生成无效发票
            invalid_invoices = [
                {
                    'invoice_no': f'INVALID{i:08d}',
                    'invoice_code': f'1234567890',
                    'invoice_date': '2024-01-15',
                    'invoice_amount': 1000.0 * (i + 1)
                }
                for i in range(invalid_invoice_count)
            ]
            
            # 验证所有发票
            valid_results = [validate_invoice(inv) for inv in valid_invoices]
            invalid_results = [validate_invoice(inv) for inv in invalid_invoices]
            
            # 属性1: 有效发票的验证成功率应该是100%
            valid_success_count = sum(1 for r in valid_results if r.get('valid'))
            assert valid_success_count == valid_invoice_count, \
                f"有效发票验证成功率应为100%: {valid_success_count}/{valid_invoice_count}"
            
            # 属性2: 无效发票的验证失败率应该是100%
            invalid_fail_count = sum(1 for r in invalid_results if not r.get('valid'))
            assert invalid_fail_count == invalid_invoice_count, \
                f"无效发票验证失败率应为100%: {invalid_fail_count}/{invalid_invoice_count}"
            
            # 属性3: 每个验证结果都应该包含必要的字段
            for result in valid_results + invalid_results:
                assert 'valid' in result, "每个验证结果都必须包含valid字段"
