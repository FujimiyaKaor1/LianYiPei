"""
意向报价 API 路由
=================

提供意向报价的完整 REST API。

URL 前缀：/api/intent-quote/*
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.authz import role_required
from app.services.intent_quote_service import intent_quote_service
from app.services.deepseek_profile_service import deepseek_profile_service

intent_quote_bp = Blueprint("intent_quote", __name__, url_prefix="/api/intent-quote")


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


# ── 意向报价 CRUD ─────────────────────────────────────────────────────────

@intent_quote_bp.route("/create", methods=["POST"])
@role_required("enterprise")
def api_create_intent_quote():
    """
    POST /api/intent-quote/create

    创建意向报价（草稿状态）。

    请求体：
    {
        "seller_id": int,            # 必填，供应方ID
        "product_name": str,        # 必填
        "chat_id": int,              # 可选，关联的会话ID
        "match_record_id": int,     # 可选，关联的匹配记录ID
        "quantity": int,            # 可选，数量
        "unit": str,                # 可选，单位
        "target_price": float,      # 可选，目标单价
        "budget_range": str,         # 可选，预算区间 "45-55"
    }

    返回：
    {
        "success": true,
        "quote_id": int,
        "status": "draft"
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    seller_id = data.get("seller_id")
    product_name = data.get("product_name")

    if not seller_id:
        return jsonify({"error": "缺少 seller_id"}), 400
    if not product_name:
        return jsonify({"error": "缺少 product_name"}), 400

    try:
        seller_id = int(seller_id)
    except (TypeError, ValueError):
        return jsonify({"error": "seller_id 无效"}), 400

    current_id = _current_enterprise_id()

    quote, error = intent_quote_service.create_intent_quote(
        buyer_id=current_id,
        seller_id=seller_id,
        product_name=product_name,
        chat_id=data.get("chat_id"),
        match_record_id=data.get("match_record_id"),
        quantity=data.get("quantity"),
        unit=data.get("unit"),
        target_price=data.get("target_price"),
        budget_range=data.get("budget_range"),
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "quote_id": quote.id,
        "status": quote.status,
    })


@intent_quote_bp.route("/<int:quote_id>", methods=["GET"])
@role_required("enterprise")
def api_get_intent_quote(quote_id: int):
    """
    GET /api/intent-quote/<id>

    获取意向报价详情。
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    quote = intent_quote_service.get_intent_quote_by_id(quote_id)

    if not quote:
        return jsonify({"error": "意向报价不存在"}), 404

    if quote.buyer_id != current_id and quote.seller_id != current_id:
        return jsonify({"error": "无权访问此意向报价"}), 403

    return jsonify({
        "success": True,
        "quote": intent_quote_service._serialize_quote(quote, current_id),
    })


@intent_quote_bp.route("/<int:quote_id>/send", methods=["POST"])
@role_required("enterprise")
def api_send_intent_quote(quote_id: int):
    """
    POST /api/intent-quote/<id>/send

    发送意向报价（从草稿改为待确认）。
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    quote, error = intent_quote_service.send_intent_quote(quote_id, current_id)

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "quote_id": quote.id,
        "status": quote.status,
    })


@intent_quote_bp.route("/<int:quote_id>/cancel", methods=["POST"])
@role_required("enterprise")
def api_cancel_intent_quote(quote_id: int):
    """
    POST /api/intent-quote/<id>/cancel

    取消意向报价。
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    success, error = intent_quote_service.cancel_intent_quote(quote_id, current_id)

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "message": "意向报价已取消",
    })


# ── 供应商回复 ─────────────────────────────────────────────────────────────

@intent_quote_bp.route("/<int:quote_id>/accept", methods=["POST"])
@role_required("enterprise")
def api_accept_intent_quote(quote_id: int):
    """
    POST /api/intent-quote/<id>/accept

    供应商接受意向报价。

    请求体：
    {
        "reply_price": float,      # 可选，供应商回复的报价
        "reply_notes": str,        # 可选，供应商回复的备注
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    current_id = _current_enterprise_id()

    quote, error = intent_quote_service.accept_intent_quote(
        quote_id=quote_id,
        seller_id=current_id,
        reply_price=data.get("reply_price"),
        reply_notes=data.get("reply_notes"),
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "quote_id": quote.id,
        "status": quote.status,
        "message": "已接受意向报价，可交换名片",
    })


@intent_quote_bp.route("/<int:quote_id>/reject", methods=["POST"])
@role_required("enterprise")
def api_reject_intent_quote(quote_id: int):
    """
    POST /api/intent-quote/<id>/reject

    供应商拒绝意向报价。

    请求体：
    {
        "reason": str,              # 可选，拒绝原因
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    current_id = _current_enterprise_id()

    quote, error = intent_quote_service.reject_intent_quote(
        quote_id=quote_id,
        seller_id=current_id,
        reason=data.get("reason"),
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "quote_id": quote.id,
        "status": quote.status,
    })


# ── 列表查询 ───────────────────────────────────────────────────────────────

@intent_quote_bp.route("/buyer/list", methods=["GET"])
@role_required("enterprise")
def api_get_buyer_quotes():
    """
    GET /api/intent-quote/buyer/list?status=pending&limit=50&offset=0

    获取采购方发起的意向报价列表。
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    quotes = intent_quote_service.get_buyer_quotes(
        buyer_id=current_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "success": True,
        "total": len(quotes),
        "quotes": quotes,
    })


@intent_quote_bp.route("/seller/list", methods=["GET"])
@role_required("enterprise")
def api_get_seller_quotes():
    """
    GET /api/intent-quote/seller/list?status=pending&limit=50&offset=0

    获取供应方收到的意向报价列表。
    """
    err = _require_login()
    if err:
        return err

    current_id = _current_enterprise_id()
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    quotes = intent_quote_service.get_seller_quotes(
        seller_id=current_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "success": True,
        "total": len(quotes),
        "quotes": quotes,
    })


# ── AI报价建议 ─────────────────────────────────────────────────────────────

@intent_quote_bp.route("/ai-suggestion", methods=["POST"])
@role_required("enterprise")
def api_get_ai_suggestion():
    """
    POST /api/intent-quote/ai-suggestion

    获取AI意向报价建议。

    请求体：
    {
        "seller_id": int,           # 必填
        "product_name": str,        # 必填
        "quantity": int,            # 可选
    }

    返回：
    {
        "success": true,
        "suggestion": {
            "suggested_price": float,
            "price_range": {"min": float, "max": float},
            "delivery_estimate": str,
            "basis": str,
            "capacity_available": bool,
        }
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    seller_id = data.get("seller_id")
    product_name = data.get("product_name")

    if not seller_id:
        return jsonify({"error": "缺少 seller_id"}), 400
    if not product_name:
        return jsonify({"error": "缺少 product_name"}), 400

    suggestion = intent_quote_service.generate_ai_price_suggestion(
        seller_id=int(seller_id),
        product_name=product_name,
        quantity=data.get("quantity"),
    )

    return jsonify({
        "success": True,
        "suggestion": suggestion,
    })


@intent_quote_bp.route("/<int:quote_id>/apply-ai-suggestion", methods=["POST"])
@role_required("enterprise")
def api_apply_ai_suggestion(quote_id: int):
    """
    POST /api/intent-quote/<id>/apply-ai-suggestion

    将AI报价建议应用到意向报价。

    请求体：
    {
        "suggested_price": float,
        "price_basis": str,
        "delivery_estimate": str,
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}

    success, error = intent_quote_service.apply_ai_suggestion(
        quote_id=quote_id,
        suggested_price=data.get("suggested_price"),
        price_basis=data.get("price_basis"),
        delivery_estimate=data.get("delivery_estimate"),
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "success": True,
        "message": "AI建议已应用",
    })


# ── 名片交换 ───────────────────────────────────────────────────────────────

@intent_quote_bp.route("/<int:quote_id>/card-eligible", methods=["GET"])
@role_required("enterprise")
def api_check_card_exchange(quote_id: int):
    """
    GET /api/intent-quote/<id>/card-eligible

    检查是否可以交换名片。
    """
    err = _require_login()
    if err:
        return err

    can_exchange, reason = intent_quote_service.can_exchange_card(quote_id)

    return jsonify({
        "success": True,
        "can_exchange": can_exchange,
        "reason": reason,
    })


# ── 企业画像（DeepSeek） ───────────────────────────────────────────────────

@intent_quote_bp.route("/enterprise-profile/<int:enterprise_id>", methods=["GET"])
@role_required("enterprise")
def api_enterprise_profile(enterprise_id: int):
    """
    GET /api/intent-quote/enterprise-profile/<id>

    获取企业公开画像（不含敏感信息）。

    返回：
    {
        "success": true,
        "profile": {...}
    }
    """
    err = _require_login()
    if err:
        return err

    profile = deepseek_profile_service.generate_public_profile(enterprise_id)

    if not profile:
        return jsonify({"error": "企业不存在"}), 404

    return jsonify({
        "success": True,
        "profile": profile,
    })


@intent_quote_bp.route("/business-insight", methods=["POST"])
@role_required("enterprise")
def api_business_insight():
    """
    POST /api/intent-quote/business-insight

    生成商机洞察消息（用于插入对话消息）。

    请求体：
    {
        "enterprise_id": int,       # 必填
        "product_name": str,        # 必填
    }

    返回：
    {
        "success": true,
        "insight": {...}
    }
    """
    err = _require_login()
    if err:
        return err

    data = request.get_json() or {}
    enterprise_id = data.get("enterprise_id")
    product_name = data.get("product_name")

    if not enterprise_id:
        return jsonify({"error": "缺少 enterprise_id"}), 400
    if not product_name:
        return jsonify({"error": "缺少 product_name"}), 400

    current_id = _current_enterprise_id()

    insight = deepseek_profile_service.generate_business_insight_message(
        enterprise_id=enterprise_id,
        product_name=product_name,
        buyer_id=current_id,
    )

    return jsonify({
        "success": True,
        "insight": insight,
    })


@intent_quote_bp.route("/recommendation/<int:enterprise_id>", methods=["GET"])
@role_required("enterprise")
def api_match_recommendation(enterprise_id: int):
    """
    GET /api/intent-quote/recommendation/<id>?product_name=xxx&match_score=0.85

    生成AI匹配推荐理由。
    """
    err = _require_login()
    if err:
        return err

    product_name = request.args.get("product_name", "未知产品")
    match_score = request.args.get("match_score", type=float)

    recommendation = deepseek_profile_service.generate_match_recommendation(
        enterprise_id=enterprise_id,
        product_name=product_name,
        match_score=match_score,
    )

    return jsonify({
        "success": True,
        "recommendation": recommendation,
    })
