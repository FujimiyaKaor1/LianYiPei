"""
Inbound WeChat command handling for the Hermes alert bridge.

This module deliberately maps WeChat text messages to a small business-action
whitelist. It does not execute arbitrary shell commands.
"""
from __future__ import annotations

import re
import time
from typing import Optional
from xml.etree import ElementTree as ET

from app import db
from app.models import Alert, Enterprise, HermesPendingAction
from app.services.hermes_action_service import (
    CONFIRMATION_PHRASE,
    HermesActionError,
    execute_action,
    get_alert,
    list_alerts,
    preview_action,
)
from app.services.wechat_push_service import normalize_wechat_openid

MAX_INBOUND_XML_BYTES = 64 * 1024


class WeChatInboundError(ValueError):
    """Raised when a WeChat callback payload is invalid."""


def parse_wechat_xml(raw: bytes) -> dict[str, str]:
    if len(raw or b"") > MAX_INBOUND_XML_BYTES:
        raise WeChatInboundError("payload_too_large")

    text = (raw or b"").decode("utf-8", errors="replace")
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise WeChatInboundError("unsafe_xml")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise WeChatInboundError("invalid_xml") from exc

    def field(name: str) -> str:
        node = root.find(name)
        return (node.text or "").strip() if node is not None else ""

    return {
        "to_user": field("ToUserName"),
        "from_user": normalize_wechat_openid(field("FromUserName")),
        "msg_type": field("MsgType").lower(),
        "content": field("Content"),
        "event": field("Event").lower(),
        "event_key": field("EventKey"),
        "msg_id": field("MsgId"),
        "create_time": field("CreateTime"),
    }


def build_text_reply(*, to_user: str, from_user: str, content: str) -> str:
    """Build a passive WeChat text reply XML body."""
    return (
        "<xml>"
        f"<ToUserName>{_cdata(to_user)}</ToUserName>"
        f"<FromUserName>{_cdata(from_user)}</FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content>{_cdata(_clip_reply(content))}</Content>"
        "</xml>"
    )


def handle_wechat_message(message: dict[str, str]) -> str:
    channel = "work_wechat" if message.get("channel") == "work_wechat" else "service_account"
    msg_type = (message.get("msg_type") or "").lower()
    if msg_type == "event":
        event = (message.get("event") or "").lower()
        if event == "subscribe":
            return _help_text("已关注链易配预警助手。")
        return "已收到。发送“帮助”查看可用指令。"

    if msg_type != "text":
        return "当前只支持文字指令。发送“帮助”查看可用指令。"

    openid = normalize_wechat_openid(message.get("from_user") or "")
    content = _normalize_text(message.get("content") or "")
    if not content:
        return "请输入文字指令。发送“帮助”查看可用指令。"

    if _is_help(content):
        return _help_text()

    from app.services.supplier_quote_intake import is_supplier_quote_command

    if is_supplier_quote_command(content):
        return _handle_supplier_quote(openid, content, channel)

    if content == CONFIRMATION_PHRASE:
        return _execute_latest_pending(openid, channel)

    if _is_status_command(content):
        return _status_text()

    assign_match = re.search(r"(?:准备派发|派发)\s*#?(\d+)\s*(?:给|到|至)?\s*#?(\d+)", content)
    if assign_match:
        return _preview_assign_alert(openid, int(assign_match.group(1)), int(assign_match.group(2)), channel)

    close_match = re.search(r"(?:准备关闭|关闭预警|关闭)\s*#?(\d+)(?:\s+(.+))?$", content)
    if close_match:
        reason = (close_match.group(2) or "微信确认关闭预警").strip()
        return _preview_close_alert(openid, int(close_match.group(1)), reason, channel)

    read_match = re.search(r"(?:准备标记已读|标记已读|已读)\s*#?(\d+)", content)
    if read_match:
        return _preview_mark_alert_read(openid, int(read_match.group(1)), channel)

    detail_match = re.search(r"(?:查看|详情|预警)\s*#?(\d+)", content)
    if detail_match:
        return _alert_detail_text(int(detail_match.group(1)))

    if _is_list_alerts_command(content):
        return _alert_list_text(content)

    return _help_text("没有识别这个指令。")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _is_help(text: str) -> bool:
    return text in {"帮助", "help", "?", "？", "菜单", "指令"}


def _is_status_command(text: str) -> bool:
    return text in {"状态", "服务状态", "系统状态", "本地状态", "status"}


def _is_list_alerts_command(text: str) -> bool:
    return text in {"查预警", "最新预警", "预警", "红色预警", "黄色预警", "蓝色预警", "alerts"}


def _help_text(prefix: str = "") -> str:
    lines = []
    if prefix:
        lines.append(prefix)
    lines.extend(
        [
            "可用指令：",
            "1. 查预警 / 红色预警",
            "2. 查看 763812",
            "3. 关闭 763812 原因说明",
            "4. 已读 763812",
            "5. 派发 763812 给 3060",
            "6. 确认执行",
            "7. 服务状态",
            "8. 报价 询价ID 单价12.8元 含税13% 交期25天",
            "写操作会先生成预览，必须再回复“确认执行”才会生效。",
        ]
    )
    return "\n".join(lines)


def _handle_supplier_quote(openid: str, content: str, channel: str) -> str:
    supplier_id = _operator_id_for_openid(openid, channel)
    if not supplier_id:
        return "当前微信账号未绑定到链易配供应商账号，无法提交报价。"

    from app.models import IntentQuote
    from app.services.intent_quote_service import intent_quote_service
    from app.services.supplier_quote_intake import (
        SupplierQuoteParseError,
        format_quote_preview,
        parse_supplier_quote,
    )

    try:
        parsed = parse_supplier_quote(content)
    except SupplierQuoteParseError as exc:
        return f"报价格式有误：{exc}"

    quote = IntentQuote.query.get(parsed["quote_id"])
    if not quote or quote.seller_id != supplier_id:
        return "未找到可报价的询价或当前账号无权操作。"
    if quote.status != "pending":
        return f"询价 #{quote.id} 当前状态为 {quote.status}，不能重复报价。"
    if not parsed["confirmed"]:
        return format_quote_preview(parsed, quote.product_name)

    accepted, error = intent_quote_service.accept_intent_quote(
        quote_id=quote.id,
        seller_id=supplier_id,
        reply_price=parsed["reply_price"],
        reply_notes=f"通过{channel}确认提交",
        reply_details=parsed["reply_details"],
        reply_channel=channel,
    )
    if error or not accepted:
        return f"报价提交失败：{error or '未知错误'}"
    return (
        f"报价已提交 #{accepted.id}：{accepted.product_name}\n"
        f"单价：{accepted.seller_reply_price:g} "
        f"{(accepted.seller_reply_details or {}).get('currency', 'CNY')}\n"
        "采购方现在可以在链小易中汇总比较该报价。"
    )


def _status_text() -> str:
    red = Alert.query.filter_by(level="red", is_active=True).count()
    yellow = Alert.query.filter_by(level="yellow", is_active=True).count()
    blue = Alert.query.filter_by(level="blue", is_active=True).count()
    pending = HermesPendingAction.query.filter_by(status="pending").count()
    return (
        "链易配本地服务正常。\n"
        f"活跃预警：红 {red} / 黄 {yellow} / 蓝 {blue}\n"
        f"待确认 Hermes 动作：{pending}\n"
        "微信入站链路：已接通"
    )


def _alert_list_text(content: str) -> str:
    level = "red"
    if "黄" in content:
        level = "yellow"
    elif "蓝" in content:
        level = "blue"
    alerts = list_alerts(level=level, status="active", limit=3)
    if not alerts:
        return f"暂无活跃{_level_label(level)}。"
    lines = [f"最新{_level_label(level)}："]
    for item in alerts:
        lines.append(
            f"#{item['id']} {item.get('product_name') or '-'}\n"
            f"{_short(item.get('message') or '', 54)}"
        )
    lines.append("回复“查看 预警ID”查看详情。")
    return "\n".join(lines)


def _alert_detail_text(alert_id: int) -> str:
    alert = get_alert(alert_id)
    if not alert:
        return f"未找到预警 #{alert_id}。"
    lines = [
        f"预警 #{alert['id']}：{alert.get('product_name') or '-'}",
        f"等级：{_level_label(alert.get('level') or '')}",
        f"类型：{alert.get('alert_type') or '-'}",
        f"内容：{_short(alert.get('message') or '', 120)}",
    ]
    if alert.get("risk_reason"):
        lines.append(f"原因：{_short(alert['risk_reason'], 80)}")
    if alert.get("suggestion"):
        lines.append(f"建议：{_short(alert['suggestion'], 80)}")
    lines.append(f"处置链接：{alert.get('dashboard_url') or ''}")
    lines.append("可回复：关闭 {id} 原因 / 已读 {id}".format(id=alert["id"]))
    return "\n".join(lines)


def _preview_close_alert(openid: str, alert_id: int, reason: str, channel: str) -> str:
    operator_id = _operator_id_for_openid(openid, channel)
    if not operator_id:
        return "当前 OpenID 未绑定到链易配账号，无法准备关闭动作。"
    return _preview_action_text(
        action="close_alert",
        alert_id=alert_id,
        requested_by=f"{channel}:{openid}",
        parameters={"operator_id": operator_id, "reason": reason},
    )


def _preview_mark_alert_read(openid: str, alert_id: int, channel: str) -> str:
    operator_id = _operator_id_for_openid(openid, channel)
    if not operator_id:
        return "当前微信账号未绑定到链易配账号，无法准备写操作。"
    return _preview_action_text(
        action="mark_alert_read",
        alert_id=alert_id,
        requested_by=f"{channel}:{openid}",
        parameters={"operator_id": operator_id, "note": "微信标记已读"},
    )


def _preview_assign_alert(openid: str, alert_id: int, assigned_to: int, channel: str) -> str:
    assigned_by = _operator_id_for_openid(openid, channel)
    if not assigned_by:
        return "当前 OpenID 未绑定到链易配账号，无法准备派发动作。"
    return _preview_action_text(
        action="assign_alert",
        alert_id=alert_id,
        requested_by=f"{channel}:{openid}",
        parameters={"assigned_to": assigned_to, "assigned_by": assigned_by},
    )


def _preview_action_text(
    *,
    action: str,
    alert_id: int,
    requested_by: str,
    parameters: dict,
) -> str:
    try:
        result = preview_action(
            action=action,
            alert_id=alert_id,
            requested_by=requested_by,
            parameters=parameters,
        )
    except HermesActionError as exc:
        return f"动作预览失败：{exc.message}"
    return (
        "已生成待确认动作：\n"
        f"{result['summary']}\n"
        f"有效期至：{result['expires_at']}\n"
        f"确认请回复：{CONFIRMATION_PHRASE}"
    )


def _execute_latest_pending(openid: str, channel: str) -> str:
    requested_by = f"{channel}:{normalize_wechat_openid(openid)}"
    pending = (
        HermesPendingAction.query.filter_by(requested_by=requested_by, status="pending")
        .order_by(HermesPendingAction.created_at.desc())
        .first()
    )
    if not pending:
        return "没有找到待确认动作。请先发送“关闭 预警ID”或“已读 预警ID”。"
    try:
        result = execute_action(
            pending_action_id=pending.id,
            confirmation=CONFIRMATION_PHRASE,
        )
        db.session.commit()
    except HermesActionError as exc:
        return f"执行失败：{exc.message}"
    action = (result.get("result") or {}).get("action") or pending.action
    alert_id = (result.get("result") or {}).get("alert_id") or pending.alert_id
    return f"已执行：{_action_label(action)}，预警 #{alert_id}。"


def _operator_id_for_openid(openid: str, channel: str = "service_account") -> Optional[int]:
    clean = normalize_wechat_openid(openid)
    if clean:
        field = "wechat_work_userid" if channel == "work_wechat" else "wechat_service_openid"
        bound = Enterprise.query.filter(getattr(Enterprise, field) == clean).first()
        if bound:
            return bound.id
    return None


def _level_label(level: str) -> str:
    return {"red": "红色预警", "yellow": "黄色预警", "blue": "蓝色预警"}.get(level, level or "预警")


def _action_label(action: str) -> str:
    return {
        "assign_alert": "派发预警",
        "close_alert": "关闭预警",
        "mark_alert_read": "标记已读",
    }.get(action, action)


def _short(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def _clip_reply(text: str) -> str:
    return _short(text, 1200)


def _cdata(text: str) -> str:
    return "<![CDATA[" + str(text or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"
