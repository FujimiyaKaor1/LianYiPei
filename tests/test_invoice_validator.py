"""
发票验证服务单元测试
Tests for Invoice Validator Service
"""

import pytest
from datetime import datetime, date
from unittest.mock import patch, MagicMock
from app.services.invoice_validator import (
    validate_invoice,
    call_tax_api,
    extract_invoice_info,
    store_fulfillment_data,
    InvoiceValidationError,
    TaxAPIError
)


class TestValidateInvoice:
    """测试 validate_invoice 函数"""
    
    def test_valid_invoice_success(self, app):
        """测试有效发票的验证流程"""
        with app.app_context():
            invoice_data = {
                'invoice_no': '12345678',
                'invoice_code': '1234567890',
                'invoice_date': '2024-01-15',
                'invoice_amount': 10000.00,
                'buyer_tax_no': '91110000000000000X',
                'seller_tax_no': '91110000000000001Y'
            }
            
            result = validate_invoice(invoice_data)
            
            assert result['valid'] is True
            assert result['invoice_no'] == '12345678'
            assert result['amount'] == 10000.00
            assert 'error' not in result
    
    def test_invalid_invoice_rejected(self, app):
        """测试无效发票的拒绝逻辑"""
        with app.app_context():
            # 使用INVALID前缀模拟无效发票
            invoice_data = {
                'invoice_no': 'INVALID12345',
                'invoice_code': '1234567890',
                'invoice_date': '2024-01-15',
                'invoice_amount': 10000.00
            }
            
            result = validate_invoice(invoice_data)
            
            assert result['valid'] is False
            assert 'error' in result
            assert '不存在' in result['error'] or '作废' in result['error']
    
    def test_missing_required_fields(self, app):
        """测试缺少必填字段的情况"""
        with app.app_context():
            # 缺少invoice_no
            invoice_data = {
                'invoice_code': '1234567890',
                'invoice_date': '2024-01-15',
                'invoice_amount': 10000.00
            }
            
            result = validate_invoice(invoice_data)
            
            assert result['valid'] is False
            assert 'error' in result
            assert '缺少必填字段' in result['error']
    
    def test_tax_api_unavailable_fallback(self, app):
        """测试税务API不可用时的降级处理"""
        with app.app_context():
            with patch('app.services.invoice_validator.call_tax_api') as mock_api:
                # 模拟API超时
                mock_api.side_effect = TaxAPIError('税务API超时')
                
                invoice_data = {
                    'invoice_no': '12345678',
                    'invoice_code': '1234567890',
                    'invoice_date': '2024-01-15',
                    'invoice_amount': 10000.00
                }
                
                result = validate_invoice(invoice_data)
                
                assert result['valid'] is False
                assert 'error' in result
                assert 'API' in result['error']


class TestCallTaxAPI:
    """测试 call_tax_api 函数"""
    
    def test_mock_validation_valid_invoice(self, app):
        """测试模拟验证模式 - 有效发票"""
        with app.app_context():
            result = call_tax_api(
                invoice_no='12345678',
                invoice_code='1234567890',
                invoice_date='2024-01-15',
                invoice_amount=10000.00
            )
            
            assert result['valid'] is True
            assert result['invoice_no'] == '12345678'
            assert result['amount'] == 10000.00
    
    def test_mock_validation_invalid_invoice(self, app):
        """测试模拟验证模式 - 无效发票"""
        with app.app_context():
            result = call_tax_api(
                invoice_no='INVALID12345',
                invoice_code='1234567890',
                invoice_date='2024-01-15',
                invoice_amount=10000.00
            )
            
            assert result['valid'] is False
            assert 'error' in result
    
    @patch('app.services.invoice_validator.requests.post')
    def test_real_api_success(self, mock_post, app):
        """测试真实API调用成功"""
        with app.app_context():
            # 配置税务API
            app.config['TAX_API_URL'] = 'http://test-api.com/verify'
            app.config['TAX_API_KEY'] = 'test-key'
            
            # 模拟API响应
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'valid': True,
                'invoice_no': '12345678',
                'amount': 10000.00
            }
            mock_post.return_value = mock_response
            
            result = call_tax_api(
                invoice_no='12345678',
                invoice_code='1234567890'
            )
            
            assert result['valid'] is True
            assert mock_post.called
    
    @patch('app.services.invoice_validator.requests.post')
    def test_api_timeout_retry(self, mock_post, app):
        """测试API超时重试机制"""
        with app.app_context():
            app.config['TAX_API_URL'] = 'http://test-api.com/verify'
            app.config['TAX_API_KEY'] = 'test-key'
            
            # 模拟超时
            import requests
            mock_post.side_effect = requests.Timeout()
            
            with pytest.raises(TaxAPIError) as exc_info:
                call_tax_api(invoice_no='12345678')
            
            assert '超时' in str(exc_info.value)
            assert mock_post.call_count == 3  # 应该重试3次


class TestExtractInvoiceInfo:
    """测试 extract_invoice_info 函数"""
    
    def test_extract_basic_info(self, app):
        """测试发票信息提取的准确性"""
        with app.app_context():
            invoice_data = {
                'invoice_no': '12345678',
                'invoice_code': '1234567890',
                'invoice_amount': 10000.00,
                'invoice_date': '2024-01-15'
            }
            
            tax_api_result = {
                'valid': True,
                'invoice_no': '12345678',
                'invoice_code': '1234567890',
                'amount': 10000.00,
                'date': '2024-01-15',
                'buyer_name': '测试买方',
                'seller_name': '测试卖方',
                'buyer_tax_no': '91110000000000000X',
                'seller_tax_no': '91110000000000001Y'
            }
            
            result = extract_invoice_info(invoice_data, tax_api_result)
            
            assert result['invoice_no'] == '12345678'
            assert result['amount'] == 10000.00
            assert result['buyer'] == '测试买方'
            assert result['seller'] == '测试卖方'
    
    def test_extract_with_optional_fields(self, app):
        """测试提取包含可选字段的发票信息"""
        with app.app_context():
            invoice_data = {
                'invoice_no': '12345678',
                'invoice_code': '1234567890',
                'invoice_amount': 10000.00,
                'invoice_date': '2024-01-15',
                'collaboration_code': 'LYP2401151234ABCDE',
                'delivery_date': '2024-01-20',
                'quality_rating': 5
            }
            
            tax_api_result = {
                'valid': True,
                'invoice_no': '12345678',
                'amount': 10000.00,
                'date': '2024-01-15'
            }
            
            result = extract_invoice_info(invoice_data, tax_api_result)
            
            assert result['collaboration_code'] == 'LYP2401151234ABCDE'
            assert result['delivery_date'] == '2024-01-20'
            assert result['quality_rating'] == 5


class TestStoreFulfillmentData:
    """测试 store_fulfillment_data 函数"""
    
    def test_store_valid_fulfillment(self, app, db_session, test_enterprises):
        """测试存储有效的履约数据"""
        with app.app_context():
            buyer = test_enterprises['buyer']
            seller = test_enterprises['seller']
            
            invoice_info = {
                'invoice_no': '12345678',
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
            
            assert fulfillment is not None
            inv = fulfillment.invoice_info or {}
            assert inv.get('invoice_no') == '12345678'
            assert inv.get('invoice_amount') == 10000.00
            assert fulfillment.buyer_id == buyer.id
            assert fulfillment.seller_id == seller.id
            assert inv.get('verified') is True
    
    def test_on_time_delivery_calculation(self, app, db_session, test_enterprises):
        """测试按时交付判断逻辑"""
        with app.app_context():
            buyer = test_enterprises['buyer']
            seller = test_enterprises['seller']
            
            # 测试按时交付（交付日期在发票日期后7天内）
            invoice_info = {
                'invoice_no': '12345678',
                'amount': 10000.00,
                'date': '2024-01-15',
                'delivery_date': '2024-01-20'  # 5天后
            }
            
            fulfillment = store_fulfillment_data(
                invoice_info=invoice_info,
                buyer_id=buyer.id,
                seller_id=seller.id
            )
            
            assert fulfillment.invoice_info.get('on_time') is True
            
            # 测试延迟交付（交付日期在发票日期后超过7天）
            invoice_info_late = {
                'invoice_no': '87654321',
                'amount': 10000.00,
                'date': '2024-01-15',
                'delivery_date': '2024-01-30'  # 15天后
            }
            
            fulfillment_late = store_fulfillment_data(
                invoice_info=invoice_info_late,
                buyer_id=buyer.id,
                seller_id=seller.id
            )
            
            assert fulfillment_late.invoice_info.get('on_time') is False
    
    def test_date_parsing_formats(self, app, db_session, test_enterprises):
        """测试不同日期格式的解析"""
        with app.app_context():
            buyer = test_enterprises['buyer']
            seller = test_enterprises['seller']
            
            # 测试 YYYY-MM-DD 格式
            invoice_info = {
                'invoice_no': '12345678',
                'amount': 10000.00,
                'date': '2024-01-15'
            }
            
            fulfillment = store_fulfillment_data(
                invoice_info=invoice_info,
                buyer_id=buyer.id,
                seller_id=seller.id
            )
            
            assert fulfillment.invoice_info.get('invoice_date') == '2024-01-15'
            
            # 测试 YYYYMMDD 格式
            invoice_info2 = {
                'invoice_no': '87654321',
                'amount': 10000.00,
                'date': '20240115'
            }
            
            fulfillment2 = store_fulfillment_data(
                invoice_info=invoice_info2,
                buyer_id=buyer.id,
                seller_id=seller.id
            )
            
            assert fulfillment2.invoice_info.get('invoice_date') == '2024-01-15'
