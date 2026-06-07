"""
企业定期抽查服务

功能：
1. 随机抽取企业进行工商状态抽查
2. 调用工商API查询企业是否存续/注销/吊销
3. 对异常企业自动下架产品
4. 记录抽查日志
"""
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional

from app import db
from app.models import Enterprise, Product
from app.services.external_data_service import industrial_commerce_service
from app.services.collaboration_service import send_message

logger = logging.getLogger(__name__)


# 抽查配置
DEFAULT_CHECK_CONFIG = {
    'enabled': True,
    'check_interval_hours': 24,  # 每24小时抽查一次
    'sample_size': 10,  # 每次抽查10家企业
    'auto_delist_enabled': True,  # 是否自动下架异常企业产品
}


# 抽查记录表（内存中，或可用数据库表存储）
_check_history: List[Dict] = []


def get_check_config() -> Dict:
    """获取抽查配置"""
    from config import EXTERNAL_INTERFACES
    custom = EXTERNAL_INTERFACES.get('enterprise_check', {})
    return {**DEFAULT_CHECK_CONFIG, **custom}


def batch_check_enterprises(sample_size: Optional[int] = None, force: bool = False) -> Dict:
    """
    批量抽查企业工商状态
    
    Args:
        sample_size: 抽查企业数量，默认从配置读取
        
    Returns:
        Dict包含:
            - total_checked: 检查企业数
            - active_count: 正常企业数
            - inactive_count: 异常企业数
            - delisted_count: 已下架产品企业数
            - results: 每家企业的检查结果
            - errors: 错误信息
    """
    config = get_check_config()

    # 定时任务尊重 enabled；管理端「立即执行」传 force=True，不受 enabled 限制
    if not force and not config.get('enabled', True):
        return {
            'success': False,
            'error': '自动抽查已关闭，定时任务不会执行。请点击「立即执行」进行手动抽查。',
            'message': '企业抽查功能已禁用',
            'total_checked': 0,
            'active_count': 0,
            'inactive_count': 0,
            'delisted_count': 0,
            'results': [],
            'errors': [],
        }
    
    # 获取已审核通过的企业
    verified_ents = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.verification_status == 'approved',
        Enterprise.is_verified == True,
    ).all()
    
    if not verified_ents:
        return {
            'success': True,
            'message': '没有可抽查的企业',
            'total_checked': 0,
            'active_count': 0,
            'inactive_count': 0,
            'delisted_count': 0,
            'results': [],
            'errors': [],
        }
    
    # 随机抽取
    size = sample_size or config.get('sample_size', 10)
    if len(verified_ents) <= size:
        sampled_ents = verified_ents
    else:
        sampled_ents = random.sample(verified_ents, size)
    
    results = []
    errors = []
    active_count = 0
    inactive_count = 0
    delisted_count = 0
    
    for ent in sampled_ents:
        try:
            # 调用工商API查询状态
            status_result = industrial_commerce_service.check_enterprise_status(ent.name)
            
            # 更新企业状态
            ent.business_status = status_result.get('status')
            ent.biz_data_updated_at = datetime.utcnow()
            
            # 检查结果记录
            record = {
                'enterprise_id': ent.id,
                'enterprise_name': ent.name,
                'status': status_result.get('status'),
                'is_active': status_result.get('is_active', True),
                'is_mock': status_result.get('is_mock', False),
                'check_date': datetime.utcnow().isoformat(),
            }
            
            if status_result.get('is_active', True):
                active_count += 1
                record['action'] = 'none'
            else:
                inactive_count += 1
                # 异常企业处理
                if config.get('auto_delist_enabled', True):
                    # 下架该企业的所有产品
                    delisted_products = _delist_enterprise_products(ent)
                    record['action'] = 'delisted'
                    record['delisted_products'] = delisted_products
                    delisted_count += 1
                    
                    # 标记企业为休眠
                    ent.is_dormant = True
                    
                    # 发送通知
                    send_message(
                        recipient_id=ent.id,
                        message_type='system',
                        title='企业状态异常通知',
                        content=f'经工商数据核查，贵司企业状态为"{status_result.get("status")}"，'
                               f'系统已暂时下架所有产品。如有疑问请联系管理员。',
                        priority='high',
                    )
                    
                    # 创建预警
                    from app.models import Alert
                    alert = Alert(
                        product_name=ent.name,
                        message=f'企业"{ent.name}"工商状态异常：{status_result.get("status")}',
                        level='yellow',
                        dimension='business',
                        alert_type='enterprise_status_anomaly',
                        severity_score=0.7,
                        suggestion=f'建议联系企业核实情况，确认后决定是否恢复。',
                    )
                    db.session.add(alert)
                else:
                    record['action'] = 'flagged'
            
            results.append(record)
            
        except Exception as e:
            logger.error(f"抽查企业{ent.id}({ent.name})失败: {e}")
            errors.append({
                'enterprise_id': ent.id,
                'enterprise_name': ent.name,
                'error': str(e),
            })
    
    # 保存历史记录
    global _check_history
    _check_history.append({
        'check_time': datetime.utcnow().isoformat(),
        'total_checked': len(sampled_ents),
        'active_count': active_count,
        'inactive_count': inactive_count,
        'delisted_count': delisted_count,
        'results': results,
    })
    
    # 保持最近100条记录
    if len(_check_history) > 100:
        _check_history = _check_history[-100:]
    
    try:
        db.session.commit()
        logger.info(f"企业抽查完成: 检查{len(sampled_ents)}家，异常{inactive_count}家，下架{delisted_count}家")
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存抽查结果失败: {e}")
    
    return {
        'success': True,
        'message': '抽查完成',
        'check_time': datetime.utcnow().isoformat(),
        'total_checked': len(sampled_ents),
        'active_count': active_count,
        'inactive_count': inactive_count,
        'delisted_count': delisted_count,
        'results': results,
        'errors': errors,
    }


def _delist_enterprise_products(ent: Enterprise) -> int:
    """下架企业的所有产品，返回下架数量"""
    try:
        products = Product.query.filter_by(enterprise_id=ent.id).all()
        count = 0
        for product in products:
            # 可以直接删除或标记为下架
            # 这里选择标记而非删除，保留数据
            product.status = 'delisted' if hasattr(product, 'status') else None
            count += 1
        
        logger.info(f"下架企业{ent.id}({ent.name})的产品: {count}个")
        return count
    except Exception as e:
        logger.error(f"下架产品失败: {e}")
        return 0


def get_check_history(limit: int = 10) -> List[Dict]:
    """获取抽查历史记录"""
    global _check_history
    return _check_history[-limit:] if _check_history else []


def get_check_history_flat(limit: int = 50) -> List[Dict]:
    """供 SPA 风控中心：将批量抽查记录摊平为「每企业一行」（含 id/result/details）。"""
    global _check_history
    if not _check_history:
        return []
    flat: List[Dict] = []
    nid = 1
    for batch in reversed(_check_history):
        chk_time = batch.get('check_time') or ''
        for rec in batch.get('results') or []:
            ct = rec.get('check_date') or chk_time
            if isinstance(ct, str) and 'T' in ct:
                ct = ct.replace('T', ' ')[:19]
            flat.append(
                {
                    'id': nid,
                    'enterprise_id': rec.get('enterprise_id'),
                    'enterprise_name': rec.get('enterprise_name') or '',
                    'check_time': ct,
                    'result': 'normal' if rec.get('is_active', True) else 'abnormal',
                    'details': (rec.get('status') or '') + (
                        f" · {rec.get('action')}" if rec.get('action') else ''
                    ),
                }
            )
            nid += 1
            if len(flat) >= limit:
                return flat
    return flat


def check_single_enterprise(enterprise_id: int) -> Dict:
    """单独检查一家企业的工商状态"""
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return {
            'success': False,
            'message': '企业不存在',
        }
    
    try:
        status_result = industrial_commerce_service.check_enterprise_status(ent.name)
        
        # 更新企业状态
        ent.business_status = status_result.get('status')
        ent.biz_data_updated_at = datetime.utcnow()
        
        config = get_check_config()
        action = 'none'
        delisted_products = 0
        
        if not status_result.get('is_active', True):
            if config.get('auto_delist_enabled', True):
                delisted_products = _delist_enterprise_products(ent)
                ent.is_dormant = True
                action = 'delisted'
            else:
                action = 'flagged'
        
        db.session.commit()
        
        return {
            'success': True,
            'enterprise_id': ent.id,
            'enterprise_name': ent.name,
            'status': status_result.get('status'),
            'is_active': status_result.get('is_active', True),
            'is_mock': status_result.get('is_mock', False),
            'action': action,
            'delisted_products': delisted_products,
            'check_date': datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"检查企业{enterprise_id}失败: {e}")
        return {
            'success': False,
            'message': str(e),
        }


def restore_enterprise(enterprise_id: int, reason: str = '') -> Dict:
    """恢复异常企业的正常状态"""
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return {
            'success': False,
            'message': '企业不存在',
        }
    
    try:
        # 恢复企业状态
        ent.business_status = '存续'
        ent.is_dormant = False
        
        # 可选：恢复产品上架状态
        # Product.query.filter_by(enterprise_id=enterprise_id).update({'status': 'active'})
        
        db.session.commit()
        logger.info(f"恢复企业{enterprise_id}({ent.name})正常状态，原因: {reason}")
        
        # 发送通知
        send_message(
            recipient_id=enterprise_id,
            message_type='system',
            title='企业状态恢复通知',
            content=f'经管理员审核，贵司企业状态已恢复，所有产品已重新上架。',
            priority='normal',
        )
        
        return {
            'success': True,
            'message': '企业状态已恢复',
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"恢复企业{enterprise_id}失败: {e}")
        return {
            'success': False,
            'message': str(e),
        }
