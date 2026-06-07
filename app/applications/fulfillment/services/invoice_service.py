"""
发票验证服务
Invoice Validator Service

提供发票真伪验证、信息提取和履约数据存储功能

功能:
- validate_invoice(): 验证发票真伪并提取信息
- call_tax_api(): 调用税务API验证发票
- extract_invoice_info(): 提取发票关键信息
- store_fulfillment_data(): 存储履约数据到数据库
"""

import logging
from datetime import datetime, date
from typing import Dict, Optional
import requests
from flask import current_app

from app import db
from app.models import Enterprise, Transaction

logger = logging.getLogger(__name__)

# 验证失败计数器（用于触发人工审核）
_validation_failure_counts = {}


class InvoiceValidationError(Exception):
    """发票验证异常"""
    pass


class TaxAPIError(Exception):
    """税务API调用异常"""
    pass


def validate_invoice(invoice_data: Dict) -> Dict:
    """
    验证发票真伪并提取信息
    
    Args:
        invoice_data: 发票数据字典，包含:
            - invoice_no: 发票号码 (必填)
            - invoice_code: 发票代码 (可选)
            - invoice_date: 开票日期 (必填)
            - invoice_amount: 发票金额 (必填)
            - buyer_tax_no: 购方税号 (可选)
            - seller_tax_no: 销方税号 (可选)
            - file_path: 发票文件路径 (可选)
    
    Returns:
        验证结果字典:
        {
            'valid': bool,
            'invoice_no': str,
            'invoice_code': str,
            'amount': float,
            'date': str,
            'buyer': str,
            'seller': str,
            'buyer_tax_no': str,
            'seller_tax_no': str,
            'error': str,  # 如果验证失败
            'manual_review_required': bool  # 是否需要人工审核
        }
    """
    invoice_no = invoice_data.get('invoice_no', '')
    
    try:
        # 1. 基础字段验证
        required_fields = ['invoice_no', 'invoice_date', 'invoice_amount']
        missing_fields = [f for f in required_fields if not invoice_data.get(f)]
        
        if missing_fields:
            return {
                'valid': False,
                'error': f'缺少必填字段: {", ".join(missing_fields)}',
                'manual_review_required': False
            }
        
        # 2. 金额验证
        try:
            amount = float(invoice_data.get('invoice_amount', 0))
            if amount <= 0:
                return {
                    'valid': False,
                    'error': '发票金额必须大于0',
                    'manual_review_required': False
                }
        except (ValueError, TypeError):
            return {
                'valid': False,
                'error': '发票金额格式不正确',
                'manual_review_required': False
            }
        
        # 3. 调用税务API验证发票真伪（带重试机制）
        tax_api_result = call_tax_api(
            invoice_no=invoice_data['invoice_no'],
            invoice_code=invoice_data.get('invoice_code', ''),
            invoice_date=invoice_data.get('invoice_date', ''),
            invoice_amount=amount
        )
        
        if not tax_api_result.get('valid'):
            # 记录验证失败次数
            _increment_failure_count(invoice_no)
            failure_count = _get_failure_count(invoice_no)
            
            logger.warning(
                f"发票验证失败: {invoice_no}, "
                f"原因: {tax_api_result.get('error')}, "
                f"失败次数: {failure_count}"
            )
            
            # 超过3次失败触发人工审核
            manual_review = failure_count >= 3
            
            return {
                'valid': False,
                'error': tax_api_result.get('error', '发票验证失败'),
                'manual_review_required': manual_review,
                'failure_count': failure_count
            }
        
        # 4. 验证成功，清除失败计数
        _clear_failure_count(invoice_no)
        
        # 5. 提取发票信息
        invoice_info = extract_invoice_info(invoice_data, tax_api_result)
        
        # 6. 返回验证成功结果
        logger.info(f"发票验证成功: {invoice_no}, 金额: {invoice_info.get('amount')}")
        
        return {
            'valid': True,
            'manual_review_required': False,
            **invoice_info
        }
        
    except TaxAPIError as e:
        logger.error(f"税务API调用失败: {str(e)}")
        return {
            'valid': False,
            'error': f'税务API调用失败: {str(e)}',
            'manual_review_required': False
        }
    except Exception as e:
        logger.error(f"发票验证异常: {str(e)}", exc_info=True)
        return {
            'valid': False,
            'error': f'发票验证异常: {str(e)}',
            'manual_review_required': False
        }


def call_tax_api(invoice_no: str, invoice_code: str = '', 
                 invoice_date: str = '', invoice_amount: float = 0) -> Dict:
    """
    调用税务API验证发票
    
    Args:
        invoice_no: 发票号码
        invoice_code: 发票代码
        invoice_date: 开票日期
        invoice_amount: 发票金额
    
    Returns:
        税务API返回结果:
        {
            'valid': bool,
            'invoice_no': str,
            'invoice_code': str,
            'amount': float,
            'date': str,
            'buyer_name': str,
            'seller_name': str,
            'buyer_tax_no': str,
            'seller_tax_no': str,
            'error': str  # 如果失败
        }
    """
    # 获取税务API配置
    tax_api_url = current_app.config.get('TAX_API_URL', '')
    tax_api_key = current_app.config.get('TAX_API_KEY', '')
    
    # 如果未配置税务API，使用模拟验证（开发/演示模式）
    if not tax_api_url or not tax_api_key:
        logger.warning("税务API未配置，使用模拟验证模式")
        return _mock_tax_api_validation(invoice_no, invoice_code, invoice_date, invoice_amount)
    
    try:
        # 构建请求参数
        params = {
            'invoice_no': invoice_no,
            'invoice_code': invoice_code,
            'invoice_date': invoice_date,
            'invoice_amount': invoice_amount,
            'api_key': tax_api_key
        }
        
        # 调用税务API（最多重试3次）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    tax_api_url,
                    json=params,
                    timeout=5
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result
                elif response.status_code == 404:
                    return {
                        'valid': False,
                        'error': '发票不存在或已作废'
                    }
                elif response.status_code == 401:
                    return {
                        'valid': False,
                        'error': 'API密钥无效'
                    }
                else:
                    logger.warning(f"税务API返回异常状态码: {response.status_code}")
                    
            except requests.Timeout:
                if attempt == max_retries - 1:
                    raise TaxAPIError(f"税务API超时（已重试{max_retries}次）")
                logger.warning(f"税务API超时，重试 {attempt + 1}/{max_retries}")
                continue
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    raise TaxAPIError(f"税务API请求失败: {str(e)}")
                logger.warning(f"税务API请求失败，重试 {attempt + 1}/{max_retries}: {str(e)}")
                continue
        
        # 所有重试都失败
        raise TaxAPIError("税务API调用失败，已达最大重试次数")
        
    except TaxAPIError:
        raise
    except Exception as e:
        raise TaxAPIError(f"税务API调用异常: {str(e)}")


def _mock_tax_api_validation(invoice_no: str, invoice_code: str, 
                             invoice_date: str, invoice_amount: float) -> Dict:
    """
    模拟税务API验证（用于开发和演示）
    
    模拟规则:
    - 发票号码以"INVALID"开头视为无效发票
    - 其他发票视为有效
    """
    if invoice_no.startswith('INVALID'):
        return {
            'valid': False,
            'error': '发票不存在或已作废'
        }
    
    # 模拟返回有效发票信息
    return {
        'valid': True,
        'invoice_no': invoice_no,
        'invoice_code': invoice_code,
        'amount': invoice_amount,
        'date': invoice_date,
        'buyer_name': '模拟买方企业',
        'seller_name': '模拟卖方企业',
        'buyer_tax_no': '91110000000000000X',
        'seller_tax_no': '91110000000000001Y'
    }


def extract_invoice_info(invoice_data: Dict, tax_api_result: Dict) -> Dict:
    """
    提取发票关键信息
    
    Args:
        invoice_data: 原始发票数据
        tax_api_result: 税务API返回结果
    
    Returns:
        提取的发票信息字典
    """
    # 合并原始数据和API返回数据
    extracted = {
        'invoice_no': tax_api_result.get('invoice_no') or invoice_data.get('invoice_no'),
        'invoice_code': tax_api_result.get('invoice_code') or invoice_data.get('invoice_code'),
        'amount': float(tax_api_result.get('amount') or invoice_data.get('invoice_amount', 0)),
        'date': tax_api_result.get('date') or invoice_data.get('invoice_date'),
        'buyer': tax_api_result.get('buyer_name', ''),
        'seller': tax_api_result.get('seller_name', ''),
        'buyer_tax_no': tax_api_result.get('buyer_tax_no') or invoice_data.get('buyer_tax_no', ''),
        'seller_tax_no': tax_api_result.get('seller_tax_no') or invoice_data.get('seller_tax_no', '')
    }
    
    # 添加额外字段
    if 'collaboration_code' in invoice_data:
        extracted['collaboration_code'] = invoice_data['collaboration_code']
    
    if 'delivery_date' in invoice_data:
        extracted['delivery_date'] = invoice_data['delivery_date']
    
    if 'quality_rating' in invoice_data:
        extracted['quality_rating'] = invoice_data['quality_rating']
    
    return extracted


def store_fulfillment_data(
    invoice_info: Dict, buyer_id: int, seller_id: int
) -> Optional[Transaction]:
    """
    存储履约数据到 transactions.invoice_info（替代 fulfillment_data 表）。
    """
    try:
        invoice_date = None
        if invoice_info.get("date"):
            if isinstance(invoice_info["date"], str):
                try:
                    invoice_date = datetime.strptime(
                        invoice_info["date"], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    try:
                        invoice_date = datetime.strptime(
                            invoice_info["date"], "%Y%m%d"
                        ).date()
                    except ValueError:
                        logger.warning(f"无法解析发票日期: {invoice_info['date']}")
            elif isinstance(invoice_info["date"], (date, datetime)):
                invoice_date = (
                    invoice_info["date"]
                    if isinstance(invoice_info["date"], date)
                    else invoice_info["date"].date()
                )

        delivery_date = None
        if invoice_info.get("delivery_date"):
            if isinstance(invoice_info["delivery_date"], str):
                try:
                    delivery_date = datetime.strptime(
                        invoice_info["delivery_date"], "%Y-%m-%d"
                    ).date()
                except ValueError:
                    logger.warning(
                        f"无法解析交付日期: {invoice_info['delivery_date']}"
                    )
            elif isinstance(invoice_info["delivery_date"], (date, datetime)):
                delivery_date = (
                    invoice_info["delivery_date"]
                    if isinstance(invoice_info["delivery_date"], date)
                    else invoice_info["delivery_date"].date()
                )

        on_time = True
        if delivery_date and invoice_date:
            on_time = (delivery_date - invoice_date).days <= 7

        inv_payload = {
            "invoice_no": invoice_info.get("invoice_no"),
            "invoice_code": invoice_info.get("invoice_code"),
            "invoice_amount": invoice_info.get("amount"),
            "invoice_date": invoice_date.isoformat() if invoice_date else None,
            "delivery_date": delivery_date.isoformat() if delivery_date else None,
            "on_time": on_time,
            "quality_rating": invoice_info.get("quality_rating", 5),
            "verified": True,
            "collaboration_code": invoice_info.get("collaboration_code"),
        }

        tx = Transaction(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name=invoice_info.get("product_name") or "履约订单",
            quantity=invoice_info.get("quantity"),
            price=invoice_info.get("amount"),
            status="completed",
            match_code=invoice_info.get("collaboration_code"),
            invoice_info=inv_payload,
            fulfillment_status="verified" if on_time else "pending",
        )
        db.session.add(tx)
        db.session.commit()

        logger.info(
            f"履约数据已存储(Transaction): 发票号={invoice_info.get('invoice_no')}, "
            f"买方={buyer_id}, 卖方={seller_id}"
        )

        return tx

    except Exception as e:
        db.session.rollback()
        logger.error(f"存储履约数据失败: {str(e)}", exc_info=True)
        return None


# ============================================================
# 辅助函数 - 验证失败计数
# ============================================================

def _increment_failure_count(invoice_no: str) -> int:
    """增加发票验证失败计数"""
    if invoice_no not in _validation_failure_counts:
        _validation_failure_counts[invoice_no] = 0
    _validation_failure_counts[invoice_no] += 1
    return _validation_failure_counts[invoice_no]


def _get_failure_count(invoice_no: str) -> int:
    """获取发票验证失败计数"""
    return _validation_failure_counts.get(invoice_no, 0)


def _clear_failure_count(invoice_no: str) -> None:
    """清除发票验证失败计数"""
    if invoice_no in _validation_failure_counts:
        del _validation_failure_counts[invoice_no]


def get_manual_review_list() -> list:
    """
    获取需要人工审核的发票列表
    
    Returns:
        需要人工审核的发票号码列表
    """
    return [
        {'invoice_no': invoice_no, 'failure_count': count}
        for invoice_no, count in _validation_failure_counts.items()
        if count >= 3
    ]
