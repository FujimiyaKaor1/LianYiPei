"""
预警分级与响应机制 (AlertNotifier)
- 红色预警：微信推送 + 短信通知
- 黄色预警：站内消息通知
- 蓝色预警：仅在预警中心显示
- 预警自动升级规则（黄色3天未处理 → 红色）
需求: 33.1-33.7
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from app import db
from app.models import Alert, Enterprise, Message

logger = logging.getLogger(__name__)
ops_logger = logging.getLogger("app.ops")

# 预警等级常量
LEVEL_RED = 'red'
LEVEL_YELLOW = 'yellow'
LEVEL_BLUE = 'blue'

# 自动升级规则：黄色预警超过N天未处理 → 升级为红色
AUTO_ESCALATE_DAYS = 3


# ── 预警分级判定 ──────────────────────────────────────────────────────────

def get_level_label(level: str) -> str:
    """返回预警等级的中文标签。"""
    return {'red': '红色预警（严重）', 'yellow': '黄色预警（警告）', 'blue': '蓝色预警（提示）'}.get(level, level)


def get_level_priority(level: str) -> str:
    """将预警等级映射为消息优先级。"""
    return {'red': 'high', 'yellow': 'normal', 'blue': 'low'}.get(level, 'normal')


# ── 通知分发 ──────────────────────────────────────────────────────────────

def notify_alert(
    alert: Alert,
    recipients: Optional[List[int]] = None,
    push_wechat: bool = True,
) -> None:
    """
    根据预警等级分发通知。
    - 红色：微信推送 + 短信 + 站内消息
    - 黄色：站内消息
    - 蓝色：仅记录，不主动推送
    需求: 33.2, 33.3, 33.4
    """
    if recipients is None:
        # 默认通知所有 admin 用户
        recipients = [
            e.id for e in Enterprise.query.filter_by(role='admin').all()
        ]

    if not recipients:
        logger.debug(f"[AlertNotifier] 预警 {alert.id} 无接收人，跳过通知")
        return

    level = alert.level

    if level == LEVEL_RED:
        _send_hermes_alert(alert, recipients)
        if push_wechat:
            _send_wechat_push(alert, recipients)
        else:
            logger.info(f"[AlertNotifier] 红色预警 {alert.id} 微信推送已按限流策略跳过")
        _send_sms(alert, recipients)
        _send_in_site_message(alert, recipients)
        channel_label = "微信+短信+站内消息" if push_wechat else "短信+站内消息"
        logger.info(f"[AlertNotifier] 红色预警 {alert.id} 已发送{channel_label}")

    elif level == LEVEL_YELLOW:
        _send_in_site_message(alert, recipients)
        logger.info(f"[AlertNotifier] 黄色预警 {alert.id} 已发送站内消息")

    else:  # blue
        logger.info(f"[AlertNotifier] 蓝色预警 {alert.id} 仅在预警中心显示，不主动推送")

    # 标记已推送
    if hasattr(alert, 'auto_pushed'):
        alert.auto_pushed = True


def _send_in_site_message(alert: Alert, recipient_ids: List[int]) -> None:
    """创建站内消息记录。需求: 33.3"""
    from app.services.message_service import MessageService
    
    level_label = get_level_label(alert.level)
    priority = get_level_priority(alert.level)

    for rid in recipient_ids:
        MessageService.create_message(
            recipient_id=rid,
            message_type='alert',
            title=f'【{level_label}】{alert.product_name}',
            content=alert.message,
            link_url=f'/dashboard/alert-center?alert_id={alert.id}',
            priority=priority
        )


def _send_wechat_push(alert: Alert, recipient_ids: List[int]) -> None:
    """
    微信推送（红色预警）。
    需求: 33.2, 26.3
    """
    from app.services.wechat_push_service import wechat_push_service
    
    level_label = get_level_label(alert.level)
    title = f'【{level_label}】{alert.product_name}'
    content = alert.message
    url = f'/dashboard/alert-center?alert_id={alert.id}'
    
    for rid in recipient_ids:
        try:
            # 使用微信推送服务，失败时自动回退到站内消息
            success = wechat_push_service.push_with_fallback(
                enterprise_id=rid,
                message_type='alert',
                title=title,
                content=content,
                url=url,
                is_urgent=True  # 红色预警为紧急消息
            )
            
            if success:
                logger.info(
                    f"[AlertNotifier] 微信推送成功 -> user={rid} "
                    f"alert={alert.id} [{level_label}] {alert.product_name}"
                )
            else:
                logger.warning(
                    f"[AlertNotifier] 微信推送失败 user={rid}，已回退到站内消息"
                )
        except Exception as e:
            logger.error(f"[AlertNotifier] 微信推送异常 user={rid}: {e}")
            # 确保至少有站内消息
            _send_in_site_message(alert, [rid])


def _send_hermes_alert(alert: Alert, recipient_ids: List[int]) -> dict:
    """将红色预警交给本机 Hermes 总结/转发；失败时只记录，不影响旧通知链路。"""
    try:
        from app.services.hermes_notification_service import send_alert_to_hermes

        result = send_alert_to_hermes(alert, recipient_ids)
        if result.get("success"):
            logger.info("[AlertNotifier] Hermes 预警交接成功 alert=%s", alert.id)
        else:
            logger.info(
                "[AlertNotifier] Hermes 预警交接跳过/失败 alert=%s reason=%s",
                alert.id,
                result.get("message"),
            )
        return result
    except Exception as e:
        logger.warning("[AlertNotifier] Hermes 预警交接异常 alert=%s: %s", alert.id, e)
        return {"success": False, "message": str(e)}


def _send_sms(alert: Alert, recipient_ids: List[int]) -> None:
    """
    短信通知（红色预警）。
    实际集成时替换为真实短信API；当前仅记录日志。
    需求: 33.2
    """
    for rid in recipient_ids:
        try:
            # TODO: 集成短信服务商 API
            logger.info(
                f"[AlertNotifier] 短信通知 -> user={rid} "
                f"alert={alert.id} {alert.product_name}"
            )
        except Exception as e:
            logger.warning(f"[AlertNotifier] 短信发送失败 user={rid}: {e}")


# ── 预警自动升级 ──────────────────────────────────────────────────────────

def auto_escalate_alerts() -> int:
    """
    检查黄色预警是否超过 AUTO_ESCALATE_DAYS 天未处理，若是则升级为红色。
    需求: 33.6
    返回升级数量。
    """
    cutoff = datetime.utcnow() - timedelta(days=AUTO_ESCALATE_DAYS)
    escalated = 0

    yellow_alerts = Alert.query.filter(
        Alert.level == LEVEL_YELLOW,
        Alert.is_active == True,
        Alert.created_at <= cutoff,
    ).all()

    for alert in yellow_alerts:
        hist = alert.workflow_history if isinstance(alert.workflow_history, list) else []
        if any(
            isinstance(h, dict) and h.get("status") == "completed"
            for h in hist
        ):
            continue

        old_level = alert.level
        alert.level = LEVEL_RED

        ops_logger.info(
            "auto_escalate alert_id=%s %s→%s days=%s",
            alert.id,
            old_level,
            LEVEL_RED,
            AUTO_ESCALATE_DAYS,
        )

        # 发送升级通知
        notify_alert(alert)
        escalated += 1
        logger.info(f"[AlertNotifier] 预警 {alert.id} 已自动升级: {old_level} → red")

    if escalated:
        db.session.commit()

    return escalated


# ── 通用消息发送 ──────────────────────────────────────────────────────────

def send_message(
    recipient_id: int,
    message_type: str,
    title: str,
    content: str = '',
    link_url: str = '',
    priority: str = 'normal',
) -> None:
    """
    发送站内消息（通用接口，供其他服务调用）。
    需求: 25.1, 38.4, 38.8
    """
    try:
        from app.services.message_service import MessageService
        MessageService.create_message(
            recipient_id=recipient_id,
            message_type=message_type,
            title=title,
            content=content,
            link_url=link_url,
            priority=priority
        )
    except Exception as e:
        logger.warning(f"[AlertNotifier] send_message 失败: {e}")



# ── 预警统计 ──────────────────────────────────────────────────────────────

def get_alert_stats() -> dict:
    """
    获取预警统计数据（用于预警中心页面）。
    需求: 33.7
    """
    from sqlalchemy import func

    total = Alert.query.filter_by(is_active=True).count()
    by_level = dict(
        db.session.query(Alert.level, func.count(Alert.id))
        .filter(Alert.is_active == True)
        .group_by(Alert.level)
        .all()
    )

    completed_workflows = []
    for a in Alert.query.all():
        hist = a.workflow_history if isinstance(a.workflow_history, list) else []
        for h in hist:
            if not isinstance(h, dict) or h.get("status") != "completed":
                continue
            ca = h.get("completed_at")
            aa = h.get("assigned_at")
            if ca and aa:
                try:
                    def _p(x):
                        if isinstance(x, datetime):
                            return x
                        if isinstance(x, str):
                            return datetime.fromisoformat(x.replace("Z", "+00:00"))
                        return None

                    adt, cdt = _p(aa), _p(ca)
                    if adt and cdt:
                        completed_workflows.append((adt, cdt))
                except Exception:
                    pass

    avg_response_hours = None
    if completed_workflows:
        total_hours = sum(
            (c - a).total_seconds() / 3600 for a, c in completed_workflows
        )
        avg_response_hours = round(total_hours / len(completed_workflows), 1)

    total_wf = 0
    completed_c = 0
    for a in Alert.query.all():
        hist = a.workflow_history if isinstance(a.workflow_history, list) else []
        for h in hist:
            if isinstance(h, dict):
                total_wf += 1
                if h.get("status") == "completed":
                    completed_c += 1
    resolution_rate = round(completed_c / total_wf * 100, 1) if total_wf else 0

    return {
        'total': total,
        'red': by_level.get('red', 0),
        'yellow': by_level.get('yellow', 0),
        'blue': by_level.get('blue', 0),
        'avg_response_hours': avg_response_hours,
        'resolution_rate': resolution_rate,
    }
