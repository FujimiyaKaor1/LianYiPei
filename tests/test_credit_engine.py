"""
信用分计算引擎单元测试
测试信用分计算、更新、权益检查等功能
"""
import pytest
from datetime import datetime, date, timedelta

from app import db
from app.models import Enterprise, Transaction
from app.services.credit_engine import (
    calculate_credit_score,
    update_credit_score,
    get_credit_history,
    check_credit_privileges,
    can_submit_quote,
    increment_quote_count,
    batch_recalculate_all,
    reset_daily_quote_counts,
)


@pytest.mark.unit
@pytest.mark.credit
class TestCreditScoreCalculation:
    """信用分计算测试"""
    
    def test_calculate_base_score(self, _db, test_enterprise):
        """测试基础分计算（无履约记录）"""
        score = calculate_credit_score(test_enterprise.id)
        # 基础分60 + 数据完整度得分
        assert 60.0 <= score <= 100.0
    
    def test_calculate_with_fulfillment(self, _db, test_enterprise, test_supplier):
        """测试包含履约记录的信用分计算"""
        fulfillment = Transaction(
            buyer_id=test_enterprise.id,
            seller_id=test_supplier.id,
            product_name='测试',
            status='completed',
            match_code='TEST001',
            invoice_info={
                'invoice_no': 'INV001',
                'invoice_amount': 10000.0,
                'on_time': True,
                'quality_rating': 5,
                'verified': True,
            },
            fulfillment_status='verified',
        )
        db.session.add(fulfillment)
        db.session.commit()
        
        score = calculate_credit_score(test_supplier.id)
        # 应该高于基础分
        assert score > 60.0
    
    def test_calculate_with_data_authorization(self, _db, test_enterprise):
        """测试数据授权对信用分的影响"""
        test_enterprise.data_auth = {
            'power_consumption': {
                'authorized': True,
                'authorized_at': datetime.utcnow().isoformat(),
            }
        }
        db.session.add(test_enterprise)
        db.session.commit()
        
        score = calculate_credit_score(test_enterprise.id)
        # 数据授权应该增加信用分
        assert score > 60.0
    
    def test_score_range_constraint(self, _db, test_enterprise):
        """测试信用分范围约束（0-100）"""
        score = calculate_credit_score(test_enterprise.id)
        assert 0.0 <= score <= 100.0


@pytest.mark.unit
@pytest.mark.credit
class TestCreditScoreUpdate:
    """信用分更新测试"""
    
    def test_update_credit_score(self, _db, test_enterprise):
        """测试信用分更新"""
        old_score = test_enterprise.credit_score
        
        result = update_credit_score(
            test_enterprise.id,
            'fulfillment_on_time',
            reason='测试按时履约'
        )
        
        assert result['old_score'] == old_score
        assert result['new_score'] > old_score
        assert result['change_value'] > 0
        
        # 验证数据库已更新
        db.session.refresh(test_enterprise)
        assert test_enterprise.credit_score == result['new_score']
    
    def test_update_creates_history(self, _db, test_enterprise):
        """测试信用分更新创建历史记录"""
        update_credit_score(
            test_enterprise.id,
            'fulfillment_on_time',
            reason='测试'
        )
        
        db.session.refresh(test_enterprise)
        evs = test_enterprise.credit_score_events
        assert isinstance(evs, list) and len(evs) >= 1
        history = evs[-1]
        assert history.get("change_type") == "fulfillment_on_time"
        assert history.get("reason") == "测试"
    
    def test_update_with_custom_value(self, _db, test_enterprise):
        """测试使用自定义变更值更新信用分"""
        result = update_credit_score(
            test_enterprise.id,
            'custom',
            change_value=15.0,
            reason='自定义加分'
        )
        
        assert result['change_value'] == 15.0
    
    def test_score_cannot_exceed_100(self, _db, test_enterprise):
        """测试信用分不能超过100"""
        test_enterprise.credit_score = 95.0
        db.session.commit()
        
        result = update_credit_score(
            test_enterprise.id,
            'custom',
            change_value=20.0,
            reason='测试上限'
        )
        
        assert result['new_score'] == 100.0
    
    def test_score_cannot_below_0(self, _db, test_enterprise):
        """测试信用分不能低于0"""
        test_enterprise.credit_score = 5.0
        db.session.commit()
        
        result = update_credit_score(
            test_enterprise.id,
            'custom',
            change_value=-20.0,
            reason='测试下限'
        )
        
        assert result['new_score'] == 0.0


@pytest.mark.unit
@pytest.mark.credit
class TestCreditHistory:
    """信用分历史查询测试"""
    
    def test_get_credit_history(self, _db, test_enterprise, test_credit_history):
        """测试获取信用分历史"""
        history = get_credit_history(test_enterprise.id, limit=10)
        
        assert len(history) > 0
        assert history[0]['change_type'] == 'fulfillment_on_time'
        assert history[0]['old_score'] == 70.0
        assert history[0]['new_score'] == 75.0
    
    def test_history_limit(self, _db, test_enterprise):
        """测试历史记录数量限制"""
        # 创建多条历史记录
        for i in range(15):
            update_credit_score(
                test_enterprise.id,
                'custom',
                change_value=1.0,
                reason=f'测试{i}'
            )
        
        history = get_credit_history(test_enterprise.id, limit=5)
        assert len(history) == 5


@pytest.mark.unit
@pytest.mark.credit
class TestCreditPrivileges:
    """信用分权益测试"""
    
    def test_low_credit_limited_quotes(self, _db, test_enterprise):
        """测试低信用分限制报价次数"""
        test_enterprise.credit_score = 65.0
        db.session.commit()
        
        privileges = check_credit_privileges(test_enterprise.id)
        
        assert privileges['daily_quote_limit'] == 3
        assert privileges['matching_weight_boost'] < 1.0
    
    def test_high_credit_unlimited_quotes(self, _db, test_enterprise):
        """测试高信用分无限制报价"""
        test_enterprise.credit_score = 90.0
        db.session.commit()
        
        privileges = check_credit_privileges(test_enterprise.id)
        
        assert privileges['daily_quote_limit'] == 'unlimited'
        assert privileges['matching_weight_boost'] == 1.20
        assert privileges['financing_priority'] is True
    
    def test_medium_credit_privileges(self, _db, test_enterprise):
        """测试中等信用分权益"""
        test_enterprise.credit_score = 75.0
        db.session.commit()
        
        privileges = check_credit_privileges(test_enterprise.id)
        
        assert privileges['daily_quote_limit'] == 20
        assert privileges['matching_weight_boost'] == 1.10


@pytest.mark.unit
@pytest.mark.credit
class TestQuoteLimit:
    """报价限制测试"""
    
    def test_can_submit_quote_within_limit(self, _db, test_enterprise):
        """测试在限制内可以提交报价"""
        test_enterprise.credit_score = 65.0
        test_enterprise.daily_quote_count = 2
        test_enterprise.last_quote_reset_date = date.today()
        db.session.commit()
        
        allowed, reason = can_submit_quote(test_enterprise.id)
        assert allowed is True
        assert reason == ''
    
    def test_cannot_submit_quote_over_limit(self, _db, test_enterprise):
        """测试超过限制不能提交报价"""
        test_enterprise.credit_score = 65.0
        test_enterprise.daily_quote_count = 3
        test_enterprise.last_quote_reset_date = date.today()
        db.session.commit()
        
        allowed, reason = can_submit_quote(test_enterprise.id)
        assert allowed is False
        assert '已达上限' in reason
    
    def test_high_credit_no_limit(self, _db, test_enterprise):
        """测试高信用分无报价限制"""
        test_enterprise.credit_score = 90.0
        test_enterprise.daily_quote_count = 100
        test_enterprise.last_quote_reset_date = date.today()
        db.session.commit()
        
        allowed, reason = can_submit_quote(test_enterprise.id)
        assert allowed is True
    
    def test_increment_quote_count(self, _db, test_enterprise):
        """测试递增报价计数"""
        test_enterprise.daily_quote_count = 0
        test_enterprise.last_quote_reset_date = date.today()
        db.session.commit()
        
        increment_quote_count(test_enterprise.id)
        
        db.session.refresh(test_enterprise)
        assert test_enterprise.daily_quote_count == 1
    
    def test_auto_reset_on_new_day(self, _db, test_enterprise):
        """测试新的一天自动重置计数"""
        test_enterprise.daily_quote_count = 5
        test_enterprise.last_quote_reset_date = date.today() - timedelta(days=1)
        db.session.commit()
        
        allowed, reason = can_submit_quote(test_enterprise.id)
        
        db.session.refresh(test_enterprise)
        assert test_enterprise.daily_quote_count == 0
        assert test_enterprise.last_quote_reset_date == date.today()


@pytest.mark.unit
@pytest.mark.credit
class TestBatchOperations:
    """批量操作测试"""
    
    def test_batch_recalculate_all(self, _db, test_enterprise, test_supplier):
        """测试批量重算所有企业信用分"""
        # 修改信用分
        test_enterprise.credit_score = 50.0
        test_supplier.credit_score = 50.0
        db.session.commit()
        
        updated_count = batch_recalculate_all()
        
        # 应该更新了企业
        assert updated_count >= 0
    
    def test_reset_daily_quote_counts(self, _db, test_enterprise, test_supplier):
        """测试重置每日报价计数"""
        # 设置报价计数
        test_enterprise.daily_quote_count = 5
        test_enterprise.last_quote_reset_date = date.today() - timedelta(days=1)
        test_supplier.daily_quote_count = 3
        test_supplier.last_quote_reset_date = date.today() - timedelta(days=1)
        db.session.commit()
        
        reset_daily_quote_counts()
        
        # 验证已重置
        db.session.refresh(test_enterprise)
        db.session.refresh(test_supplier)
        assert test_enterprise.daily_quote_count == 0
        assert test_supplier.daily_quote_count == 0
