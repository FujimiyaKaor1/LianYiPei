"""
询价会话 API 路由（InquiryChat Blueprint）
============================================

提供询价控制台的完整 REST API，支持：
  - 会话创建/获取/列表
  - 聊天消息发送/历史查询（含匿名脱敏）
  - 采购/销售模式切换
  - AI 商机评估数据获取
  - 正式结构化报价提交（含信用分卡点）

URL 前缀：/api/inquiry-chat/*
关联需求：4（信用分卡点）、15（匿名逻辑）、16（价格指数触发）
"""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.authz import role_required
from app.models import Enterprise
from app.services.inquiry_chat_service import InquiryChatService

inquiry_chat_bp = Blueprint("inquiry_chat", __name__, url_prefix="/api/inquiry-chat")

_svc = InquiryChatService()


# ── 辅助 ───────────────────────────────────────────────────────────────────

def _current_enterprise_id() -> int | None:
    """从 Flask-Login 当前用户获取企业 ID"""
    if current_user.is_authenticated:
        return current_user.id
    return None


def _require_login():
    eid = _current_enterprise_id()
    if not eid:
        return jsonify({"error": "请先登录"}), 401
    return None


# ── 会话管理 ────────────────────────────────────────────────────────────────

@inquiry_chat_bp.route("/create", methods=["POST"])
@role_required("enterprise")
def api_create_or_get_chat():
    """
    POST /api/inquiry-chat/create

    创建或获取已有询价会话。

    请求体：
    {
        "buyer_id": int,          # 买方企业 ID（必填）
        "seller_id": int,          # 卖方企业 ID（必填）
        "match_record_id": int,     # 匹配记录 ID（必填）
        "is_anonymous": bool,       # 是否匿名询价（默认 False，需求15）
        "product_name": str,        # 产品名称（用于新建 MatchRecord 时）
        "match_score": float,      # 匹配度（可选）
        "dim_scores": dict,        # 各维度得分（可选）
        "match_feedback_id": int,  # MatchFeedback ID（可选）
    }

    返回：
    {
        "success": true,
        "chat_id": int,
        "is_new": bool,
        "chat": { ... }
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}

    buyer_id = data.get("buyer_id")
    seller_id = data.get("seller_id")
    match_record_id = data.get("match_record_id")
    is_anonymous = bool(data.get("is_anonymous", False))
    product_name = data.get("product_name", "未知产品")
    match_score = data.get("match_score")
    dim_scores = data.get("dim_scores")
    match_feedback_id = data.get("match_feedback_id")

    if not buyer_id or not seller_id or not match_record_id:
        return jsonify({"error": "缺少必填参数：buyer_id, seller_id, match_record_id"}), 400

    current_id = _current_enterprise_id()
    if buyer_id != current_id and seller_id != current_id:
        return jsonify({"error": "无权操作此会话"}), 403

    # 匿名询价权限校验（需求15）：信用分<80限制使用匿名
    if is_anonymous:
        from app.models import Enterprise
        ent = Enterprise.query.get(current_id)
        if ent and (ent.credit_score or 60) < 80:
            return jsonify({
                "error": "信用分低于80分，无法使用匿名询价功能",
                "credit_score": ent.credit_score or 60,
            }), 403

    # 先确保 MatchRecord 存在
    record = _svc.get_or_create_match_record(
        buyer_id=buyer_id,
        seller_id=seller_id,
        product_name=product_name,
        match_score=match_score,
        dim_scores=dim_scores,
        match_feedback_id=match_feedback_id,
    )

    # 创建/获取会话
    chat, is_new = _svc.create_or_get_chat(
        buyer_id=buyer_id,
        seller_id=seller_id,
        match_record_id=record.id,
        is_anonymous=is_anonymous,
    )

    # 若新会话，发送初始系统消息
    if is_new:
        record.status = "inquiry_sent"
        record.updated_at = datetime.utcnow()
        from app import db
        db.session.commit()

        _svc.send_message(
            chat_id=chat.id,
            sender_id=None,
            content="会话已建立，等待双方沟通。",
            message_type="system",
            msg_metadata={"event": "chat_created"},
        )

    # 更新会话的 mode（根据当前用户角色）
    if current_id == buyer_id:
        chat.mode = "procurement"
    else:
        chat.mode = "sales"
    from app import db
    db.session.commit()

    return jsonify({
        "success": True,
        "chat_id": chat.id,
        "is_new": is_new,
        "chat": _svc.serialize_chat(chat, current_id),
    })


@inquiry_chat_bp.route("/list", methods=["GET"])
@role_required("enterprise")
def api_get_chat_list():
    """
    GET /api/inquiry-chat/list?role=buyer&status=active

    获取当前企业的会话列表。

    参数（Query）：
      role: "buyer" | "seller"（默认自动推断）
      status: 筛选状态（可选，默认返回所有）
      limit: 返回数量（默认50）

    返回：
    {
        "success": true,
        "total": int,
        "chats": [{...}, ...]
    }
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    role = request.args.get("role", "").strip().lower()
    status = request.args.get("status", "").strip() or None
    limit = request.args.get("limit", 50, type=int)

    # 前端「采购模式 / 销售模式」与列表筛选角色对齐：procurement→买方会话，sales→卖方会话
    if role in ("procurement", "buyer"):
        role = "buyer"
    elif role in ("sales", "seller"):
        role = "seller"
    else:
        role = "buyer"

    chats = _svc.get_chat_list(
        enterprise_id=current_id,
        role=role,
        status=status,
        limit=limit,
    )

    return jsonify({
        "success": True,
        "total": len(chats),
        "chats": [_svc.serialize_chat(chat, current_id) for chat in chats],
    })


@inquiry_chat_bp.route("/<int:chat_id>", methods=["GET"])
@role_required("enterprise")
def api_get_chat(chat_id: int):
    """GET /api/inquiry-chat/<id> — 获取单个会话详情"""
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权访问此会话"}), 403

    return jsonify({
        "success": True,
        "chat": _svc.serialize_chat(chat, current_id),
    })


@inquiry_chat_bp.route("/<int:chat_id>/mode", methods=["PUT"])
@role_required("enterprise")
def api_switch_mode(chat_id: int):
    """
    PUT /api/inquiry-chat/<id>/mode

    切换采购/销售模式。

    请求体：{"mode": "procurement" | "sales"}
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    new_mode = data.get("mode", "").strip()

    if new_mode not in ("procurement", "sales"):
        return jsonify({"error": "mode 必须是 'procurement' 或 'sales'"}), 400

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权操作此会话"}), 403

    updated = _svc.switch_mode(chat_id, new_mode)
    if not updated:
        return jsonify({"error": "切换模式失败"}), 500

    return jsonify({
        "success": True,
        "mode": updated.mode,
        "chat": _svc.serialize_chat(updated, current_id),
    })


# ── 消息管理 ────────────────────────────────────────────────────────────────

@inquiry_chat_bp.route("/<int:chat_id>/message", methods=["POST"])
@role_required("enterprise")
def api_send_message(chat_id: int):
    """
    POST /api/inquiry-chat/<id>/message

    发送聊天消息。

    请求体：
    {
        "content": str,           # 消息内容（必填）
        "message_type": str,       # text / quote_proposal / ai_suggestion（默认 text）
        "msg_metadata": dict,         # 扩展数据（可选，对应 ChatMessage.msg_metadata）
    }

    返回：
    {
        "success": true,
        "message_id": int,
        "message": { ... }
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    content = (data.get("content") or "").strip()
    message_type = data.get("message_type", "text").strip()
    msg_metadata = data.get("msg_metadata")

    if not content:
        return jsonify({"error": "消息内容不能为空"}), 400

    if message_type not in ("text", "quote_proposal", "ai_suggestion"):
        message_type = "text"

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权在此会话发送消息"}), 403

    if chat.status == "closed":
        return jsonify({"error": "会话已关闭，无法发送消息"}), 400

    if message_type == "text":
        allowed, reason = _svc.can_send_text_message(chat_id=chat_id, sender_id=current_id)
        if not allowed:
            return jsonify({"error": reason or "已达到发送上限"}), 429

    # 更新 MatchRecord 状态
    record = _svc.get_match_record_by_id(chat.match_record_id)
    if record and record.status == "matched":
        _svc.update_match_status(record.id, "inquiry_sent")

    msg = _svc.send_message(
        chat_id=chat_id,
        sender_id=current_id,
        content=content,
        message_type=message_type,
        msg_metadata=msg_metadata,
    )

    if not msg:
        return jsonify({"error": "发送消息失败"}), 500

    return jsonify({
        "success": True,
        "message_id": msg.id,
        "message": {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "sender_name": current_user.name,
            "is_mine": True,
            "content": msg.content,
            "message_type": msg.message_type,
            "msg_metadata": msg.msg_metadata,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        },
    })


@inquiry_chat_bp.route("/<int:chat_id>/history", methods=["GET"])
@role_required("enterprise")
def api_get_history(chat_id: int):
    """
    GET /api/inquiry-chat/<id>/history

    获取聊天记录（含匿名脱敏）。

    参数（Query）：
      limit: 返回数量（默认 50）
      offset: 分页偏移（默认 0）
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权访问此会话"}), 403

    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    history = _svc.get_chat_history(
        chat_id=chat_id,
        current_user_id=current_id,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "success": True,
        "chat_id": chat_id,
        "is_anonymous": chat.is_anonymous,
        "messages": history,
    })


# ── 商机评估 ────────────────────────────────────────────────────────────────

@inquiry_chat_bp.route("/<int:chat_id>/insights", methods=["GET"])
@role_required("enterprise")
def api_get_insights(chat_id: int):
    """
    GET /api/inquiry-chat/<id>/insights

    获取 AI 商机评估数据（匹配度、预计利润率、客户风险评估）。

    返回：
    {
        "success": true,
        "match_record_id": int,
        "match_score": int,         # 0-100
        "profit_rate": float,       # 预计利润率 %
        "risk_level": str,          # 低风险 / 中风险 / 高风险
        "risk_detail": str,
        "credit_score": float,
        "level": str,              # AAA / AA+ / A / 一般
    }
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权访问此会话"}), 403

    insights = _svc.get_business_insights(
        match_record_id=chat.match_record_id,
        current_enterprise_id=current_id,
    )

    return jsonify({
        "success": True,
        "match_record_id": chat.match_record_id,
        **insights,
    })


# ── 正式报价 ────────────────────────────────────────────────────────────────

@inquiry_chat_bp.route("/<int:chat_id>/quote", methods=["POST"])
@role_required("enterprise")
def api_submit_quote(chat_id: int):
    """
    POST /api/inquiry-chat/<id>/quote

    提交正式结构化报价（触发信用分卡点和价格指数计算）。

    请求体：
    {
        "price": float,        # 单价（必填）
        "quantity": int,        # 数量（必填）
        "unit": str,            # 单位（必填，如"件"、"套"）
        "delivery_days": int,   # 预计交期天数（必填）
        "remarks": str,         # 补充说明（可选）
    }

    返回：
    {
        "success": true,
        "quote_id": int,
        "remaining_quotes_today": int | "unlimited",
    }

    错误返回（信用分限制，需求4）：
    {
        "error": "今日报价次数已达上限（3次），提升信用分可解锁更多次数",
        "credit_limit_reached": true
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}

    price = data.get("price")
    quantity = data.get("quantity")
    unit = (data.get("unit") or "").strip() or "件"
    delivery_days = data.get("delivery_days")
    remarks = (data.get("remarks") or "").strip()

    missing = []
    if price is None:
        missing.append("price")
    if quantity is None:
        missing.append("quantity")
    if delivery_days is None:
        missing.append("delivery_days")

    if missing:
        return jsonify({"error": f"缺少必填字段：{', '.join(missing)}"}), 400

    try:
        price = float(price)
        quantity = int(quantity)
        delivery_days = int(delivery_days)
    except (TypeError, ValueError):
        return jsonify({"error": "price/quantity/delivery_days 必须是有效数字"}), 400

    if price <= 0:
        return jsonify({"error": "报价金额必须大于0"}), 400
    if quantity <= 0:
        return jsonify({"error": "数量必须大于0"}), 400
    if delivery_days <= 0:
        return jsonify({"error": "交期天数必须大于0"}), 400

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权提交此会话的报价"}), 403

    # 提交报价（内部调用 can_submit_quote 校验 + QuotePoolManager.add_quote）
    quote, error = _svc.submit_formal_quote(
        chat_id=chat_id,
        sender_id=current_id,
        price=price,
        quantity=quantity,
        unit=unit,
        delivery_days=delivery_days,
        remarks=remarks,
    )

    if error:
        # 判断是否是信用分限制导致的错误
        is_credit_limit = "上限" in error or "信用分" in error
        from app.models import Enterprise

        ent = Enterprise.query.get(current_id)
        privileges = {}
        if ent:
            from app.services.credit_engine import check_credit_privileges
            privileges = check_credit_privileges(current_id)

        return jsonify({
            "error": error,
            "credit_limit_reached": is_credit_limit,
            "credit_score": float(ent.credit_score or 60) if ent else 60,
            "daily_quote_limit": privileges.get("daily_quote_limit", 3),
        }), 429 if is_credit_limit else 400

    # 获取剩余报价次数
    from app.services.credit_engine import check_credit_privileges

    privileges = check_credit_privileges(current_id)
    remaining = privileges.get("daily_quote_limit", "unlimited")

    return jsonify({
        "success": True,
        "quote_id": quote.id,
        "remaining_quotes_today": remaining,
        "total_price": round(price * quantity, 2),
    })


# ── MatchRecord 状态管理 ───────────────────────────────────────────────────

@inquiry_chat_bp.route("/<int:chat_id>/match-status", methods=["PUT"])
@role_required("enterprise")
def api_update_match_status(chat_id: int):
    """
    PUT /api/inquiry-chat/<id>/match-status

    更新关联的 MatchRecord 状态。

    请求体：{"status": "inquiry_sent" | "inquiry_accepted" | "quoted" | "quote_acknowledged" | "contracted"}
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip()

    valid = {"inquiry_sent", "inquiry_accepted", "quoted", "quote_acknowledged", "contracted"}
    if new_status not in valid:
        return jsonify({"error": f"无效状态，可选值：{valid}"}), 400

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权操作"}), 403

    ok = _svc.update_match_status(chat.match_record_id, new_status)
    if not ok:
        return jsonify({"error": "更新状态失败"}), 500

    return jsonify({
        "success": True,
        "match_record_id": chat.match_record_id,
        "status": new_status,
    })


@inquiry_chat_bp.route("/<int:chat_id>/seller-accept-quote", methods=["POST"])
@role_required("enterprise")
def api_seller_accept_quote(chat_id: int):
    """
    卖方在「已报价」后点击「同意意向报价」，解锁名片交换。
    将 MatchRecord.status 从 quoted → quote_acknowledged。
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)
    if not chat:
        return jsonify({"error": "会话不存在"}), 404
    if current_id != chat.seller_id:
        return jsonify({"error": "仅卖方可确认同意意向报价"}), 403
    if chat.status != "quoted":
        return jsonify({"error": "当前会话尚未进入已报价状态，无法确认"}), 400

    record = _svc.get_match_record_by_id(chat.match_record_id)
    if not record:
        return jsonify({"error": "匹配记录不存在"}), 404
    if record.status != "quoted":
        return jsonify({
            "error": "已确认过或状态已变更",
            "match_record_status": record.status,
        }), 400

    record.status = "quote_acknowledged"
    record.updated_at = datetime.utcnow()
    chat.updated_at = datetime.utcnow()
    from app import db
    db.session.commit()

    _svc.send_message(
        chat_id=chat_id,
        sender_id=None,
        content="卖方已同意本意向报价，双方可交换名片推进合作。",
        message_type="system",
        msg_metadata={"event": "seller_accepted_quote"},
    )

    return jsonify({
        "success": True,
        "match_record_status": record.status,
        "chat": _svc.serialize_chat(chat, current_id),
    })


@inquiry_chat_bp.route("/<int:chat_id>/exchange-card", methods=["POST"])
@role_required("enterprise")
def api_exchange_card(chat_id: int):
    """
    POST /api/inquiry-chat/<id>/exchange-card

    交换名片：双方均同意后，获取对方企业信息（含地理位置）。
    仅在会话状态为 quoted（已报价）时允许交换名片。

    请求体：{}（空对象即可）

    返回：
    {
        "success": true,
        "card": {
            "id": int,
            "name": str,
            "address": str,
            "longitude": float | None,
            "latitude": float | None,
            "contact": str,
            "phone": str,
            "main_business": str,
            "credit_score": int,
            "is_green_factory": bool,
            "tags": list[str],
        }
    }
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    chat = _svc.get_chat_by_id(chat_id)

    if not chat:
        return jsonify({"error": "会话不存在"}), 404

    if chat.buyer_id != current_id and chat.seller_id != current_id:
        return jsonify({"error": "无权访问此会话"}), 403

    # 仅在 quoted 及之后阶段允许交换名片
    if chat.status not in ("quoted", "contracted"):
        return jsonify({
            "error": "请先完成报价后再交换名片",
            "current_status": chat.status,
        }), 403

    record = _svc.get_match_record_by_id(chat.match_record_id)
    if not record or record.status not in ("quote_acknowledged", "contracted"):
        return jsonify({
            "error": "请卖方先在会话中点击「同意意向报价」后再交换名片",
            "match_record_status": record.status if record else None,
        }), 403

    # 判断当前用户是买方还是卖方，获取对方 ID
    if current_id == chat.buyer_id:
        counterparty_id = chat.seller_id
    else:
        counterparty_id = chat.buyer_id

    counterparty = Enterprise.query.get(counterparty_id)
    if not counterparty:
        return jsonify({"error": "对方企业信息不存在"}), 404

    # 记录名片交换历史（使用新模型）
    from app.models import BusinessCard
    existing_card = BusinessCard.query.filter(
        ((BusinessCard.initiator_id == current_id) & (BusinessCard.recipient_id == counterparty_id)) |
        ((BusinessCard.initiator_id == counterparty_id) & (BusinessCard.recipient_id == current_id))
    ).first()

    if not existing_card:
        new_card = BusinessCard(
            initiator_id=current_id,
            recipient_id=counterparty_id,
            status="completed",
        )
        db.session.add(new_card)

    # 构造名片信息（record 已在上方校验）
    tags = []
    if counterparty.is_green_factory:
        tags.append("政府绿标")
    if counterparty.qualifications:
        quals = counterparty.qualifications if isinstance(counterparty.qualifications, list) else []
        for q in quals:
            if isinstance(q, dict) and q.get("status") == "有效":
                title = q.get("title", "")
                if title:
                    tags.append(title[:20])
    tags = tags[:5]

    main_business = ""
    if counterparty.business_scope:
        scope = counterparty.business_scope
        main_business = scope[:80] + ("…" if len(scope) > 80 else "")

    # 更新 MatchRecord 状态为 contracted（双方达成合作）
    if record.status not in ("contracted",):
        record.status = "contracted"
        record.updated_at = datetime.utcnow()

    if chat.status != "contracted":
        chat.status = "contracted"
        chat.updated_at = datetime.utcnow()

    from app import db
    db.session.commit()

    # 发送系统消息（双方可见）
    from app.services.inquiry_chat_service import InquiryChatService
    InquiryChatService().send_message(
        chat_id=chat_id,
        sender_id=None,
        content=f"双方已完成名片交换，正式达成合作！可前往签约页签署电子合同。",
        message_type="system",
        msg_metadata={"event": "card_exchanged"},
    )

    return jsonify({
        "success": True,
        "card": {
            "id": counterparty.id,
            "name": counterparty.name,
            "address": counterparty.address or f"{counterparty.province or ''}{counterparty.city or ''}",
            "longitude": counterparty.longitude,
            "latitude": counterparty.latitude,
            "contact": counterparty.contact or "",
            "phone": counterparty.phone or "",
            "main_business": main_business,
            "credit_score": int(counterparty.credit_score or 70),
            "is_green_factory": counterparty.is_green_factory,
            "tags": tags,
        }
    })
