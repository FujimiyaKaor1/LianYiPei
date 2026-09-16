"""
REST API：地图相关（/api/map/*）
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_login import current_user, login_required
from sqlalchemy import String, and_, cast, false, func, or_
from langchain_core.messages import HumanMessage, SystemMessage

from app.authz import role_required, user_effective_role, user_session_role
from app.models import Enterprise, Inquiry, Product, Quote, Transaction, IndustryNewsArticle, IndustryNewsSource
from app.services.industry_news_service import ALLOWED_CATEGORIES
from app.services import map_service
from app.services import finance_service
from app.services.fulfillment_dashboard import get_active_fulfillments, get_dashboard_payload
from app.services.fulfillment_service import get_all_cases, toggle_case_visibility
from app.services.intent_parser import extract_weights_from_nl
from app.services.order_service import OrderService
from app.services.matcher import DEFAULT_WEIGHTS, match_suppliers
from app.services.mimo_client import create_mimo_chat_model_from_env
from app.routes.match import ai_match_view, api_inquiry_send, api_inquiry_sign

api_bp = Blueprint("api", __name__)

# POST /api/match/ai — Ollama 权重提取 + 供应商匹配（实现见 match.ai_match_view）
api_bp.add_url_rule("/match/ai", endpoint="match_ai", view_func=ai_match_view, methods=["POST"])

# 匹配闭环：询盘、签约（实现见 match 蓝图内视图）
api_bp.add_url_rule("/inquiry/send", endpoint="inquiry_send", view_func=api_inquiry_send, methods=["POST"])
api_bp.add_url_rule("/inquiry/sign", endpoint="inquiry_sign", view_func=api_inquiry_sign, methods=["POST"])


def _news_item(article):
    return {
        "id": article.id, "slug": article.slug, "title": article.title,
        "summary": article.summary or "", "category": article.category,
        "source_name": article.source_name, "source_url": article.source_url,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "fetched_at": article.fetched_at.isoformat() if article.fetched_at else None,
        "cover_image": article.cover_image_url, "tags": article.tags or [],
        "is_external": True, "is_demo": bool(article.is_demo),
    }


@api_bp.route("/public/industry-news", methods=["GET"])
def api_public_industry_news():
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 12, type=int), 1), 50)
    query = IndustryNewsArticle.query.filter(IndustryNewsArticle.is_published.is_(True))
    category = (request.args.get("category") or "").strip()
    keyword = (request.args.get("q") or "").strip()[:100]
    source = (request.args.get("source") or "").strip()[:120]
    if category and category in ALLOWED_CATEGORIES: query = query.filter(IndustryNewsArticle.category == category)
    if source: query = query.filter(IndustryNewsArticle.source_name == source)
    if keyword: query = query.filter(or_(IndustryNewsArticle.title.contains(keyword), IndustryNewsArticle.summary.contains(keyword)))
    total = query.count()
    items = query.order_by(IndustryNewsArticle.published_at.desc(), IndustryNewsArticle.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    latest = IndustryNewsArticle.query.filter(IndustryNewsArticle.is_published.is_(True)).order_by(IndustryNewsArticle.fetched_at.desc()).first()
    return jsonify({"items": [_news_item(item) for item in items], "total": total, "page": page, "per_page": per_page,
                    "pages": (total + per_page - 1) // per_page if total else 0, "has_more": page * per_page < total,
                    "updated_at": latest.fetched_at.isoformat() if latest and latest.fetched_at else None,
                    "source": "rss_allowlist", "sync_status": "idle"})


@api_bp.route("/public/industry-news/<string:slug>", methods=["GET"])
def api_public_industry_news_detail(slug):
    article = IndustryNewsArticle.query.filter_by(slug=slug, is_published=True).first()
    if not article: return jsonify({"error": "资讯不存在"}), 404
    related = IndustryNewsArticle.query.filter(IndustryNewsArticle.is_published.is_(True), IndustryNewsArticle.id != article.id, IndustryNewsArticle.category == article.category).order_by(IndustryNewsArticle.published_at.desc(), IndustryNewsArticle.id.desc()).limit(4).all()
    return jsonify({"article": _news_item(article) | {"content_excerpt": article.content_excerpt or ""}, "related": [_news_item(item) for item in related]})


@api_bp.route("/public/industry-news/categories", methods=["GET"])
def api_public_industry_news_categories():
    return jsonify({"categories": [{"key": category, "label": category, "count": IndustryNewsArticle.query.filter_by(category=category, is_published=True).count()} for category in ALLOWED_CATEGORIES]})


@api_bp.route("/public/industry-news/sources", methods=["GET"])
def api_public_industry_news_sources():
    rows = IndustryNewsSource.query.filter_by(enabled=True).all()
    return jsonify({"sources": [{"name": row.name, "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None, "status": row.last_sync_status or "idle"} for row in rows]})


def _order_date_to_str(value):
    if not value:
        return None
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%Y-%m-%d")
        except Exception:
            pass
    text = str(value).strip()
    return text[:10] if text else None


def _public_region_from_address(address: str | None) -> str:
    """Best-effort province/city redaction for anonymous public search results."""
    text = (address or "").strip()
    if not text:
        return ""

    province_match = re.search(r"([\u4e00-\u9fa5]{2,12}(?:省|自治区|特别行政区))", text)
    city_search_text = text[province_match.end() :] if province_match else text
    city_match = re.search(r"([\u4e00-\u9fa5]{2,12}市)", city_search_text)
    parts = []
    if province_match:
        parts.append(province_match.group(1))
    if city_match and city_match.group(1) not in parts:
        parts.append(city_match.group(1))
    if parts:
        return " ".join(parts)

    direct_city_match = re.match(r"([\u4e00-\u9fa5]{2,12}市)", text)
    if direct_city_match:
        return direct_city_match.group(1)

    return ""


def _join_public_region(province: str | None, city: str | None) -> str:
    province_text = (province or "").strip()
    city_text = (city or "").strip()
    if province_text and city_text.startswith(province_text):
        city_text = city_text[len(province_text) :].strip()
    parts = [province_text]
    if city_text and city_text not in parts:
        parts.append(city_text)
    return " ".join([p for p in parts if p])


def _enterprise_public_address(ent: Enterprise) -> str:
    region = _join_public_region(getattr(ent, "province", None), getattr(ent, "city", None))
    return region or _public_region_from_address(getattr(ent, "address", None))


def _matching_public_address(row: dict) -> str:
    region = _join_public_region(row.get("province"), row.get("city"))
    return region or _public_region_from_address(row.get("address"))


@api_bp.route("/orders", methods=["GET"])
@login_required
def api_orders_list():
    """前后端分离专用订单列表接口，稳定返回 JSON。"""
    page = request.args.get("page", 1, type=int)
    status = (request.args.get("status") or "").strip()
    result = OrderService.get_orders(
        enterprise_id=current_user.id,
        status=status if status else None,
        page=page,
        per_page=20,
    )
    orders_data = []
    for order in result["orders"]:
        order_date = _order_date_to_str(getattr(order, "order_date", None))
        delivery_date = _order_date_to_str(getattr(order, "delivery_date", None))
        actual_delivery_date = _order_date_to_str(getattr(order, "actual_delivery_date", None))
        orders_data.append(
            {
                "id": order.id,
                "order_no": order.order_no,
                "product_name": order.product_name,
                "quantity": order.quantity,
                "unit": order.unit,
                "customer_name": order.customer_name,
                "order_date": order_date,
                "delivery_date": delivery_date,
                "actual_delivery_date": actual_delivery_date,
                "status": order.status,
                "notes": getattr(order, "notes", "") or "",
            }
        )
    return jsonify(
        {
            "success": True,
            "orders": orders_data,
            "total": result["total"],
            "page": result["page"],
            "pages": result["pages"],
        }
    )


@api_bp.route("/orders/statistics", methods=["GET"])
@login_required
def api_orders_statistics():
    stats = OrderService.get_order_statistics(current_user.id)
    return jsonify({"success": True, "statistics": stats})


def _enterprise_inquiry_scope(enterprise_id: int):
    return Inquiry.query.filter(or_(
        Inquiry.poster_id == enterprise_id,
        Inquiry.buyer_id == enterprise_id,
        Inquiry.seller_id == enterprise_id,
    ))


def _json_orders_for_enterprise(enterprise_id: int) -> list[dict]:
    ent = Enterprise.query.get(enterprise_id)
    extras = ent.extras if ent and isinstance(ent.extras, dict) else {}
    rows = extras.get("saas_orders") if isinstance(extras.get("saas_orders"), list) else []
    return [row for row in rows if isinstance(row, dict)]


@api_bp.route("/enterprise/dashboard/summary", methods=["GET"])
@role_required("enterprise")
def api_enterprise_dashboard_summary():
    """企业经营摘要；所有查询均以当前登录企业为边界，不返回演示数字。"""
    enterprise_id = int(current_user.id)
    since = datetime.utcnow() - timedelta(days=30)
    inquiries = _enterprise_inquiry_scope(enterprise_id).filter(Inquiry.created_at >= since)
    inquiry_ids = [row.id for row in inquiries.with_entities(Inquiry.id).all()]
    quote_query = Quote.query.filter(Quote.created_at >= since)
    if inquiry_ids:
        quote_query = quote_query.filter(or_(Quote.supplier_id == enterprise_id, Quote.inquiry_id.in_(inquiry_ids)))
    else:
        quote_query = quote_query.filter(Quote.supplier_id == enterprise_id)
    orders = _json_orders_for_enterprise(enterprise_id)
    recent_orders = []
    for row in orders:
        raw = str(row.get("created_at") or row.get("order_date") or "")
        try:
            if datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None) >= since:
                recent_orders.append(row)
        except ValueError:
            continue
    completed = sum(1 for row in recent_orders if row.get("status") == "completed")
    finished_or_cancelled = sum(1 for row in recent_orders if row.get("status") in {"completed", "cancelled"})
    fulfillment_rate = round(completed / finished_or_cancelled * 100, 1) if finished_or_cancelled else 0
    open_inquiries = _enterprise_inquiry_scope(enterprise_id).filter(Inquiry.status.in_(["open", "active"])).count()
    pending_quotes = quote_query.filter(Quote.status == "active").count()
    todos = []
    if open_inquiries:
        todos.append({"key": "inquiries", "label": "待处理询盘", "count": open_inquiries, "path": "/sales-console"})
    if pending_quotes:
        todos.append({"key": "quotes", "label": "待查看报价", "count": pending_quotes, "path": "/matching?panel=quotes"})
    pending_shipments = sum(1 for row in orders if row.get("status") in {"pending", "in_progress"})
    if pending_shipments:
        todos.append({"key": "shipments", "label": "待发货 / 履约", "count": pending_shipments, "path": "/orders"})
    return jsonify({
        "success": True,
        "metrics": {
            "inquiries": inquiries.count(),
            "quotes": quote_query.count(),
            "orders": len(recent_orders),
            "fulfillment_rate": fulfillment_rate,
        },
        "todos": todos,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "source": "business_records",
        "is_demo": False,
    })


@api_bp.route("/enterprise/dashboard/trends", methods=["GET"])
@role_required("enterprise")
def api_enterprise_dashboard_trends():
    """近六个月趋势。没有业务记录的月份返回 0，而不是前端填充伪造数据。"""
    enterprise_id = int(current_user.id)
    now = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = []
    for index in range(5, -1, -1):
        month = now.month - index
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        start = now.replace(year=year, month=month)
        next_month = start.replace(year=year + 1, month=1) if month == 12 else start.replace(month=month + 1)
        months.append((start, next_month))
    inquiries = _enterprise_inquiry_scope(enterprise_id).all()
    quotes = Quote.query.filter(or_(Quote.supplier_id == enterprise_id, Quote.inquiry.has(or_(Inquiry.buyer_id == enterprise_id, Inquiry.poster_id == enterprise_id)))).all()
    orders = _json_orders_for_enterprise(enterprise_id)
    labels, inquiry_values, quote_values, order_values, fulfillment_values = [], [], [], [], []
    for start, end in months:
        labels.append(start.strftime("%Y-%m"))
        inquiry_values.append(sum(1 for row in inquiries if row.created_at and start <= row.created_at < end))
        quote_values.append(sum(1 for row in quotes if row.created_at and start <= row.created_at < end))
        month_orders = []
        for row in orders:
            raw = str(row.get("created_at") or row.get("order_date") or "")
            try:
                created = datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
                if start <= created < end:
                    month_orders.append(row)
            except ValueError:
                continue
        order_values.append(len(month_orders))
        done = sum(1 for row in month_orders if row.get("status") == "completed")
        closed = sum(1 for row in month_orders if row.get("status") in {"completed", "cancelled"})
        fulfillment_values.append(round(done / closed * 100, 1) if closed else 0)
    return jsonify({"success": True, "labels": labels, "inquiries": inquiry_values, "quotes": quote_values, "orders": order_values, "fulfillment": fulfillment_values, "updated_at": datetime.utcnow().isoformat() + "Z", "source": "business_records", "is_demo": False})


@api_bp.route("/enterprise/sales-summary", methods=["GET"])
@role_required("enterprise")
def api_enterprise_sales_summary():
    """销售/采购控制台的真实指标，按当前企业和视角隔离。"""
    enterprise_id = int(current_user.id)
    mode = request.args.get("mode", "sales")
    if mode not in {"sales", "procurement"}:
        return jsonify({"error": "mode 必须是 sales 或 procurement"}), 400

    days = request.args.get("range", "30d")
    try:
        window_days = max(1, min(int(days.rstrip("d")), 365)) if days.endswith("d") else 30
    except (AttributeError, ValueError):
        window_days = 30
    since = datetime.utcnow() - timedelta(days=window_days)

    if mode == "sales":
        role_filter = or_(
            Inquiry.seller_id == enterprise_id,
            and_(Inquiry.poster_id == enterprise_id, Inquiry.direction == "supply"),
        )
    else:
        role_filter = or_(
            Inquiry.buyer_id == enterprise_id,
            and_(Inquiry.poster_id == enterprise_id, Inquiry.direction == "demand"),
        )

    inquiries = Inquiry.query.filter(role_filter, Inquiry.created_at >= since).all()
    inquiry_ids = {row.id for row in inquiries}
    if mode == "sales":
        quote_query = Quote.query.filter(Quote.supplier_id == enterprise_id, Quote.created_at >= since)
    elif inquiry_ids:
        quote_query = Quote.query.filter(Quote.inquiry_id.in_(inquiry_ids), Quote.created_at >= since)
    else:
        quote_query = Quote.query.filter(false())
    quotes = quote_query.all()
    quoted_inquiry_ids = {row.inquiry_id for row in quotes}

    transactions = Transaction.query.filter(
        or_(Transaction.buyer_id == enterprise_id, Transaction.seller_id == enterprise_id),
        Transaction.created_at >= since,
    ).all()
    orders = _json_orders_for_enterprise(enterprise_id)
    pending_orders = sum(1 for row in orders if row.get("status") in {"pending", "in_progress"})
    pending_orders += sum(1 for row in transactions if row.status in {"pending", "in_progress"})
    contracted_count = sum(1 for row in transactions if row.status not in {"cancelled", "rejected"})
    conversion_rate = round(len(quoted_inquiry_ids) / len(inquiries) * 100, 1) if inquiries else 0

    return jsonify({
        "success": True,
        "mode": mode,
        "range": f"{window_days}d",
        "metrics": {
            "new_inquiries": len(inquiries),
            "quoted": len(quotes),
            "intent_conversion_rate": conversion_rate,
            "pending_fulfillment_orders": pending_orders,
        },
        "funnel": {
            "inquiries": len(inquiries),
            "quotes": len(quotes),
            "contracts": contracted_count,
            "fulfillment": pending_orders,
        },
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "source": "business_records",
        "is_demo": False,
    })


@api_bp.route("/orders", methods=["POST"])
@login_required
def api_orders_create():
    """创建订单（JSON）。"""
    payload = request.get_json(silent=True) or {}
    product_name = (payload.get("product_name") or "").strip()
    unit = (payload.get("unit") or "件").strip()
    customer_name = (payload.get("customer_name") or "").strip()
    notes = (payload.get("notes") or "").strip()
    quantity = payload.get("quantity")
    order_date_str = (payload.get("order_date") or "").strip()
    delivery_date_str = (payload.get("delivery_date") or "").strip()

    if not all([product_name, customer_name, unit, order_date_str]) or quantity in (None, ""):
        return jsonify({"success": False, "message": "缺少必填字段"}), 400

    try:
        quantity_int = int(quantity)
        if quantity_int <= 0:
            raise ValueError("quantity must > 0")
    except Exception:
        return jsonify({"success": False, "message": "quantity 必须为正整数"}), 400

    try:
        order_date = datetime.strptime(order_date_str[:10], "%Y-%m-%d").date()
        delivery_date = (
            datetime.strptime(delivery_date_str[:10], "%Y-%m-%d").date()
            if delivery_date_str
            else None
        )
    except Exception:
        return jsonify({"success": False, "message": "日期格式应为 YYYY-MM-DD"}), 400

    order = OrderService.create_order(
        enterprise_id=current_user.id,
        product_name=product_name,
        quantity=quantity_int,
        unit=unit,
        customer_name=customer_name,
        order_date=order_date,
        delivery_date=delivery_date,
        notes=notes,
    )
    return jsonify(
        {
            "success": True,
            "order": {
                "id": order.id,
                "order_no": order.order_no,
                "product_name": order.product_name,
                "quantity": order.quantity,
                "unit": order.unit,
                "customer_name": order.customer_name,
                "order_date": _order_date_to_str(order.order_date),
                "delivery_date": _order_date_to_str(order.delivery_date),
                "actual_delivery_date": _order_date_to_str(order.actual_delivery_date),
                "status": order.status,
                "notes": order.notes or "",
            },
        }
    )


# ── 履约看板 / 产能日历（SPA 经 Vite /api 代理）────────────────────────────


def _capacity_calendar_enriched(enterprise_id: int, year: int, month: int) -> dict:
    raw = OrderService.get_capacity_calendar(enterprise_id, year, month)
    days = raw.get("days") or {}
    merged = dict(days)
    for _k, v in list(days.items()):
        if isinstance(v, dict) and v.get("date"):
            merged[v["date"]] = v
    raw["days"] = merged
    return raw


@api_bp.route("/fulfillment", methods=["GET"])
@login_required
def api_fulfillment_dashboard():
    """看板聚合 + 进行中履约列表。"""
    eid = current_user.id
    payload = get_dashboard_payload(eid)
    payload["active_fulfillments"] = get_active_fulfillments(eid, limit=20)
    return jsonify(payload)


@api_bp.route("/fulfillment/cases", methods=["GET"])
@login_required
def api_fulfillment_cases_list():
    return jsonify({"success": True, "cases": get_all_cases(current_user.id)})


@api_bp.route("/fulfillment/cases/<int:case_id>/toggle", methods=["POST"])
@role_required("enterprise")
def api_fulfillment_cases_toggle(case_id: int):
    data = request.get_json() or {}
    is_public = bool(data.get("is_public", False))
    ok = toggle_case_visibility(case_id, current_user.id, is_public)
    if not ok:
        return jsonify({"success": False, "message": "案例不存在或无权限"}), 404
    return jsonify({"success": True, "is_public": is_public})


@api_bp.route("/capacity", methods=["GET"])
@login_required
def api_capacity_calendar():
    """
    SPA 产能日历：GET /api/capacity?year=2026&month=4
    始终返回 JSON（避免异常时 HTML 调试页导致前端解析失败、误报「网络请求失败」）。
    """
    try:
        year = request.args.get("year", type=int) or datetime.utcnow().year
        month = request.args.get("month", type=int) or datetime.utcnow().month
        if month < 1 or month > 12:
            return jsonify({"success": False, "message": "月份应在 1–12 之间"}), 400
        if year < 2000 or year > 2100:
            return jsonify({"success": False, "message": "年份无效"}), 400
        ent = Enterprise.query.get(current_user.id)
        if ent is None:
            return jsonify({"success": False, "message": "当前账号未关联企业记录"}), 404
        data = _capacity_calendar_enriched(ent.id, year, month)
        return jsonify({"success": True, "data": data})
    except Exception as e:
        _logger.exception("api_capacity_calendar failed")
        return jsonify({"success": False, "message": str(e) or "产能日历生成失败"}), 500


@api_bp.route("/calendar-visibility", methods=["POST"])
@login_required
def api_calendar_visibility():
    try:
        visibility = (request.get_json() or {}).get("visibility")
        OrderService.update_calendar_visibility(current_user.id, visibility)
        return jsonify({"success": True, "message": "设置成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400


@api_bp.route("/orders-by-date/<date_str>", methods=["GET"])
@login_required
def api_orders_by_date_api(date_str: str):
    try:
        target_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return jsonify({"success": False, "message": "日期格式应为 YYYY-MM-DD"}), 400
    orders = OrderService.get_orders_by_date(current_user.id, target_date)
    orders_data = []
    for order in orders:
        orders_data.append(
            {
                "id": order.id,
                "order_no": order.order_no,
                "product_name": order.product_name,
                "quantity": order.quantity,
                "unit": order.unit,
                "customer_name": order.customer_name,
                "status": order.status,
                "order_date": _order_date_to_str(getattr(order, "order_date", None)),
                "delivery_date": _order_date_to_str(getattr(order, "delivery_date", None)),
            }
        )
    return jsonify({"success": True, "orders": orders_data, "date": date_str[:10]})


def get_llm_instance(model_choice: str):
    """
    按前端传入 model_choice 返回 LLM 实例（工厂模式）。
    - mimo: Xiaomi MiMo-V2.5-Pro 云端模型
    - qwen: ChatOllama(本地 Ollama)
    """
    choice = (model_choice or "qwen").strip().lower()
    if choice in {"mimo", "deepseek"}:
        return create_mimo_chat_model_from_env()

    if choice == "qwen":
        from langchain_ollama import ChatOllama

        ollama_model = (
            (os.getenv("BIZMIND_OLLAMA_MODEL") or "").strip()
            or "bizmind"
        )
        ollama_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").strip().rstrip("/")
        return ChatOllama(
            model=ollama_model,
            base_url=ollama_base_url,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
            num_predict=int(os.getenv("LLM_MAX_TOKENS", "2048")),
            timeout=int(float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))),
        )

    raise ValueError("model_choice 仅支持 'mimo' 或 'qwen'")


def _extract_json_list(text: str):
    """从 LLM 文本中提取 JSON 数组。"""
    raw = (text or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        pass

    m = re.search(r"(\[[\s\S]*\])", raw)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _clamp_ai_score_bracket(raw: object) -> int | None:
    try:
        x = int(round(float(raw)))
    except (TypeError, ValueError):
        return None
    return max(80, min(99, x))


def _dedupe_ai_scores_sequential(pairs: list[tuple[int, int]]) -> dict[int, int]:
    """保证 ai_score 互异且在 80~99；优先保留模型给出的分，冲突则向低档让位。"""
    used: set[int] = set()
    out: dict[int, int] = {}
    for sid, s in pairs:
        x = max(80, min(99, int(s)))
        chosen: int | None = None
        for cand in range(x, 79, -1):
            if cand not in used:
                chosen = cand
                break
        if chosen is None:
            for cand in range(x + 1, 100):
                if cand not in used:
                    chosen = cand
                    break
        if chosen is None:
            continue
        used.add(chosen)
        out[sid] = chosen
    return out


def _build_mimo_match_reasons(
    keyword: str, top_results: list[dict]
) -> tuple[dict[int, str], dict[int, int], bool, str | None]:
    """使用 MiMo 对 TopN 候选生成 AI 理由 + Agent 专家分（ai_score）。"""
    candidates = top_results[:5]
    if not candidates:
        return {}, {}, True, "no_candidates"

    try:
        llm = get_llm_instance("mimo")
    except Exception as exc:
        current_app.logger.exception("matching.mimo.init_failed: %s", exc)
        return {}, {}, True, f"mimo_init_failed:{type(exc).__name__}"

    compact_rows = []
    for row in candidates:
        compact_rows.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "score": row.get("score"),
                "credit_score": row.get("credit_score"),
                "distance_km": row.get("distance_km"),
                "reasons": row.get("reasons") or [],
                "dimensions": {
                    "product": (row.get("dimensions") or {}).get("product"),
                    "semantic": (row.get("dimensions") or {}).get("semantic"),
                    "gnn": (row.get("dimensions") or {}).get("gnn"),
                    "capacity": (row.get("dimensions") or {}).get("capacity"),
                },
            }
        )

    sys_prompt = (
        "你是供应链匹配专家。请基于候选供应商信息与需求关键词，为每家输出一句简短匹配理由，并给出 Agent 专家评分。"
        "必须只输出 JSON 数组，不要输出任何数组以外的文字。"
        "数组每项格式为："
        '{"id": 123, "reason": "不超过40字的中文理由", "ai_score": 96}。'
        "要求：1) id 与输入一致；2) reason 简明专业；"
        "3) ai_score 为 80 到 99 之间的整数，表示综合匹配推荐度，数值越高越推荐；"
        "4) 不同候选的 ai_score 必须互不相同，严禁两家分数相同。"
    )
    user_prompt = (
        f"需求关键词：{keyword or '未提供'}\n"
        f"候选供应商：{json.dumps(compact_rows, ensure_ascii=False)}"
    )

    try:
        resp = llm.invoke(
            [SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)]
        )
        content = getattr(resp, "content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        parsed = _extract_json_list(str(content))
    except Exception as exc:
        current_app.logger.exception("matching.mimo.invoke_failed: %s", exc)
        return {}, {}, True, f"mimo_invoke_failed:{type(exc).__name__}"

    reason_map: dict[int, str] = {}
    score_pairs: list[tuple[int, int]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        sid = item.get("id")
        reason = (item.get("reason") or "").strip()
        if sid is None:
            continue
        try:
            sid_int = int(sid)
        except Exception:
            continue
        if reason:
            reason_map[sid_int] = reason[:80]
        ac_raw = _clamp_ai_score_bracket(item.get("ai_score"))
        if ac_raw is not None:
            score_pairs.append((sid_int, ac_raw))

    score_map = _dedupe_ai_scores_sequential(score_pairs) if score_pairs else {}

    if not reason_map and not score_map:
        return {}, {}, True, "mimo_empty_output"
    return reason_map, score_map, False, None


def _enterprise_images(ent: Enterprise):
    raw = ent.company_images
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(u) for u in raw if u]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def _credit_threshold(level: str) -> float | None:
    level_map = {
        "AAA": 90.0,
        "AA+": 85.0,
        "A": 80.0,
    }
    return level_map.get((level or "").strip().upper())


def _delivery_weight_adjustment(delivery_days: int | None, base: dict) -> dict:
    """根据期望交付天数动态微调权重，天数越短越强调距离与产能。"""
    weights = dict(base)
    if delivery_days is None:
        return weights

    if delivery_days <= 15:
        weights["distance"] = weights.get("distance", 0.0) + 0.10
        weights["capacity"] = weights.get("capacity", 0.0) + 0.08
    elif delivery_days <= 30:
        weights["distance"] = weights.get("distance", 0.0) + 0.05
        weights["capacity"] = weights.get("capacity", 0.0) + 0.04

    total = sum(weights.values()) or 1.0
    return {k: v / total for k, v in weights.items()}


def _normalize_weights(weights: dict) -> dict:
    total = sum(float(v) for v in weights.values()) or 1.0
    return {k: float(v) / total for k, v in weights.items()}


def _merge_search_weights(base_weights: dict, parsed_weights: dict | None) -> dict:
    merged = dict(base_weights)
    if isinstance(parsed_weights, dict):
        for key, value in parsed_weights.items():
            if key not in merged:
                continue
            if isinstance(value, (int, float)):
                merged[key] = float(value)
    return _normalize_weights(merged)


@api_bp.route("/map/location", methods=["GET"])
@login_required
def map_location():
    """
    查询企业经纬度及基本信息。
    Query: enterprise_id (int)
    """
    eid = request.args.get("enterprise_id", type=int)
    if not eid:
        return jsonify({"error": "缺少参数 enterprise_id"}), 400

    ent = Enterprise.query.get(eid)
    if not ent:
        return jsonify({"error": "企业不存在"}), 404

    lng, lat, source = map_service.resolve_enterprise_coords(
        ent.address,
        ent.longitude,
        ent.latitude,
        getattr(ent, "province", None),
    )

    return jsonify(
        {
            "id": ent.id,
            "name": ent.name,
            "address": ent.address or "",
            "longitude": lng,
            "latitude": lat,
            "contact": ent.contact or "",
            "phone": ent.phone or "",
            "company_images": _enterprise_images(ent),
            "coordinate_source": source,
        }
    )


@api_bp.route("/map/distance", methods=["POST"])
@login_required
def map_distance():
    """
    根据两点坐标计算距离（米）。
    JSON:
      {
        "supplier": {"longitude": 116.4, "latitude": 39.9},
        "buyer": {"longitude": 116.5, "latitude": 40.0},
        "mode": "straight" | "driving"   # 可选，默认 straight
      }
    """
    data = request.get_json(silent=True) or {}
    supplier = data.get("supplier") or data.get("coord1") or data.get("from")
    buyer = data.get("buyer") or data.get("coord2") or data.get("to")
    mode = (data.get("mode") or "straight").strip().lower()

    if not isinstance(supplier, dict) or not isinstance(buyer, dict):
        return jsonify({"error": "请提供 supplier / buyer 坐标对象"}), 400

    if mode not in ("straight", "driving"):
        mode = "straight"

    try:
        result = map_service.calculate_distance(supplier, buyer, mode=mode)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        current_app.logger.exception("map_distance")
        return jsonify({"error": "距离计算失败"}), 500

    return jsonify(result)


@api_bp.route("/session", methods=["GET"])
def api_session():
    """供 Vite/React 读取当前 Flask-Login 会话（需 fetch 携带 Cookie，开发环境通过代理同域）。"""
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False, "user": None})
    name = current_user.name or ""
    return jsonify(
        {
            "authenticated": True,
            "user": {
                "id": current_user.id,
                "name": name,
                "enterprise_name": name,
                "role": user_session_role(current_user),
            },
        }
    )


@api_bp.route("/user/me", methods=["GET"])
def api_user_me():
    """与 SPA 约定的「当前企业」信息；未登录返回 401。"""
    if not current_user.is_authenticated:
        return jsonify({"error": "未登录"}), 401
    name = current_user.name or ""
    return jsonify(
        {
            "id": current_user.id,
            "enterprise_name": name,
            "name": name,
            "role": user_session_role(current_user),
        }
    )


@api_bp.route("/logout", methods=["POST"])
def api_logout():
    """供前端 SPA 注销：清除服务端会话 Cookie。"""
    from flask_login import logout_user

    if current_user.is_authenticated:
        logout_user()
    return jsonify({"ok": True})


@api_bp.route("/chat", methods=["POST"])
def api_llm_chat():
    """
    POST /api/chat — BizMind 对话（SSE 流式）。
    请求 JSON: {"message": "..."}
    响应 text/event-stream：每条正文为规范 SSE（可含多行 data:），结束 `data: [DONE]` 空行结束。
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    model_choice = (data.get("model_choice") or "qwen").strip().lower()
    if not message:
        return jsonify({"error": "缺少 message"}), 400

    try:
        from app.services.llm_service import (
            BIZMIND_SYSTEM_PROMPT,
            plain_text_delta_from_stream_chunk,
            sse_event_from_error,
            sse_event_from_plain_text,
        )

        llm = get_llm_instance(model_choice)

        def generate():
            try:
                messages = [
                    SystemMessage(content=BIZMIND_SYSTEM_PROMPT),
                    HumanMessage(content=message),
                ]
                for chunk in llm.stream(messages):
                    delta = plain_text_delta_from_stream_chunk(chunk)
                    if not delta:
                        continue
                    event = sse_event_from_plain_text(delta)
                    if event:
                        yield event
            except Exception as exc:
                current_app.logger.exception("api_chat.stream")
                yield sse_event_from_error(exc)
            yield sse_event_from_plain_text("[DONE]")

        return Response(
            stream_with_context(generate()),
            content_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        import traceback

        print("\n" + "=" * 80)
        print("!!! /api/chat 外层异常（完整堆栈） !!!")
        print(f"异常类型: {type(e).__name__}")
        print(f"异常信息: {e}")
        traceback.print_exc()
        print("=" * 80 + "\n")
        current_app.logger.exception("api_chat")
        return jsonify({"error": f"模型调用失败：{e}"}), 502


@api_bp.route("/matching/search", methods=["GET"])
def api_matching_search():
    """
    GET /api/matching/search
    参数：
    - query: 搜索词（产品关键词/企业名）
    - tag: 工艺标签
    - sort: score | credit | distance
    - delivery_days: 期望交付天数（可选）
    - min_credit: 最低信用分或等级（AAA/AA+/A）
    """
    _logger.debug("matching/search enter query=%r tag=%r", request.args.get("query"), request.args.get("tag"))
    query = (request.args.get("query") or "").strip()
    tag = (request.args.get("tag") or "").strip()
    sort = (request.args.get("sort") or "score").strip().lower()
    algorithm = (request.args.get("algorithm") or "rule").strip().lower()
    model_choice = (request.args.get("model_choice") or "qwen").strip().lower()
    is_guest = not current_user.is_authenticated
    if algorithm not in {"rule", "deep_learning"}:
        algorithm = "rule"
    keyword = query or tag

    delivery_days = request.args.get("delivery_days", type=int)
    min_credit_raw = (request.args.get("min_credit") or "").strip()
    min_credit_num = request.args.get("min_credit", type=float)
    min_credit = (
        min_credit_num
        if min_credit_num is not None
        else _credit_threshold(min_credit_raw)
    )

    # 无输入时：按信用分返回 Top 10
    if not keyword:
        _logger.debug("matching/search empty keyword, return top enterprises by credit")
        enterprise_query = Enterprise.query
        if min_credit is not None:
            enterprise_query = enterprise_query.filter(Enterprise.credit_score >= min_credit)
        top_enterprises = enterprise_query.order_by(Enterprise.credit_score.desc()).limit(10).all()
        return jsonify(
            {
                "query": query,
                "tag": tag,
                "sort": sort,
                "algorithm": algorithm,
                "model_choice": model_choice,
                "count": len(top_enterprises),
                "suppliers": [
                    {
                        "id": ent.id,
                        "name": ent.name,
                        "address": _enterprise_public_address(ent) if is_guest else (ent.address or ""),
                        "credit_score": float(ent.credit_score or 0.0),
                        "score": float(ent.credit_score or 0.0),
                        "match": f"{int(round(float(ent.credit_score or 0.0)))}%",
                        "desc": ent.business_scope or "优质供应商",
                        "ai_match_reason": None,
                        "tags": ["信用优先"],
                    }
                    for ent in top_enterprises
                ],
            }
        )

    filters = {}
    if min_credit is not None:
        filters["min_credit"] = min_credit

    sort_by = "score"
    if sort in {"credit", "distance"}:
        sort_by = sort

    demand_ent_id = current_user.id if current_user.is_authenticated else None
    delivery_adjusted_weights = _delivery_weight_adjustment(delivery_days, DEFAULT_WEIGHTS)
    parsed_intent = {}
    parsed_weights = {}
    core_product = keyword
    if query:
        parsed_intent = extract_weights_from_nl(query) or {}
        candidate_product = parsed_intent.get("product")
        if isinstance(candidate_product, str) and candidate_product.strip():
            core_product = candidate_product.strip()
        elif candidate_product is not None and str(candidate_product).strip():
            core_product = str(candidate_product).strip()
        parsed_weights_raw = parsed_intent.get("weights")
        if isinstance(parsed_weights_raw, dict):
            for key, value in parsed_weights_raw.items():
                if key in DEFAULT_WEIGHTS and isinstance(value, (int, float)):
                    parsed_weights[key] = float(value)
    custom_weights = _merge_search_weights(delivery_adjusted_weights, parsed_weights)

    _logger.debug("matching/search calling match_suppliers")
    results = match_suppliers(
        demand_product=core_product,
        demand_location=None,
        demand_quantity=100,
        demand_ent_id=demand_ent_id,
        demand_industry_code=None,
        sort_by=sort_by,
        custom_weights=custom_weights,
        filters=filters or None,
        algorithm=algorithm,
    )
    _logger.debug("matching/search match_suppliers done count=%s", len(results))
    mimo_reasons: dict[int, str] = {}
    is_basic_match = False
    fallback_reason = None
    mimo_ai_scores: dict[int, int] = {}
    if algorithm == "deep_learning":
        mimo_reasons, mimo_ai_scores, is_basic_match, fallback_reason = _build_mimo_match_reasons(
            core_product, results[:5]
        )
        for row in results:
            sid = int(row.get("id") or 0)
            if sid in mimo_ai_scores:
                s = float(mimo_ai_scores[sid])
                row["score"] = s
                row["total_score"] = s
                row["confidence_index"] = round(s, 2)
                row["deep_learning_explain"] = (
                    f"{row.get('deep_learning_explain') or ''} · Agent评分{int(s)}"
                ).strip(" ·")
        if mimo_ai_scores:
            results.sort(
                key=lambda r: float(r.get("confidence_index") or r.get("score") or 0.0),
                reverse=True,
            )

    return jsonify(
        {
            "query": query,
            "core_product": core_product,
            "tag": tag,
            "sort": sort,
            "algorithm": algorithm,
            "model_choice": model_choice,
            "parsed_weights": parsed_weights,
            "custom_weights": custom_weights,
            "parsed_intent": parsed_intent,
            "is_basic_match": is_basic_match,
            "fallback_reason": fallback_reason,
            "count": len(results),
            "suppliers": [
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "address": _matching_public_address(row) if is_guest else (row.get("address") or ""),
                    "credit_score": row.get("credit_score"),
                    "score": row.get("confidence_index", row.get("score")),
                    "match": f"{int(round(float(row.get('confidence_index', row.get('score')) or 0)))}%",
                    "distance_km": row.get("distance_km"),
                    "desc": row.get("match_reason") or "智能匹配供应商",
                    "ai_match_reason": mimo_reasons.get(int(row.get("id") or 0))
                    or row.get("ai_match_reason"),
                    "tags": row.get("reasons") or [],
                    "deep_learning_score": row.get("deep_learning_score"),
                    "deep_learning_explain": row.get("deep_learning_explain"),
                    "confidence_index": row.get("confidence_index"),
                    "match_basis": row.get("match_basis") or ("semantic" if algorithm == "deep_learning" else "rule"),
                }
                for row in results
            ],
        }
    )


# 企业名录 / 工厂检索：按「省份」「服务行业」等维度筛选（与前端 enterprise-directory 对齐）
INDUSTRY_DIRECTORY_KEYWORDS: dict[str, list[str]] = {
    "agriculture": ["农", "林", "牧", "渔", "种植", "养殖", "林业"],
    "mining": ["采矿", "矿物", "煤炭", "石油", "天然气", "黑色金属", "有色金属"],
    "food": ["食品", "饮料", "酒", "乳制品", "屠宰", "农副产品"],
    "textile": ["纺织", "服装", "服饰", "印染", "化纤"],
    "wood": ["木材", "家具", "造纸", "印刷"],
    "chemical": ["化工", "化学", "塑料", "橡胶", "化肥"],
    "metal": ["金属制品", "冶炼", "压延", "钢铁", "铸造"],
    "machinery": ["机械", "设备制造", "通用设备", "专用设备", "机床"],
    "electronics": ["电子", "通信", "计算机", "仪器仪表", "半导体"],
    "automotive": ["汽车", "摩托车", "零部件", "新能源车"],
    "building": ["建筑", "建材", "装饰", "水泥", "玻璃"],
    "electric": ["电力", "电气", "光伏", "新能源", "电池"],
    "medicine": ["医药", "医疗", "生物", "器械"],
    "logistics": ["物流", "仓储", "运输", "供应链"],
    "retail": ["批发", "零售", "贸易", "商贸"],
    "service": ["软件", "信息", "咨询", "技术服务", "互联网"],
}


@api_bp.route("/enterprises/directory", methods=["GET"])
def api_enterprises_directory():
    """
    GET /api/enterprises/directory
    企业端名录多维筛选（参考产业目录类 B2B 检索）。
    参数：province、city、industry、tech_keyword、q、min_credit、min_capacity、
    max_capacity、capacity_status、is_export、is_little_giant、is_green_factory、
    business_status、sort、page、per_page；limit 作为旧参数兼容 per_page；
    include_self=1 可用于政府大屏等全量监管视图。
    """
    province = (request.args.get("province") or "").strip()
    city = (request.args.get("city") or "").strip()
    industry_key = (request.args.get("industry") or "").strip()
    q = (request.args.get("q") or "").strip()
    tech_keyword = (request.args.get("tech_keyword") or "").strip()
    min_credit = request.args.get("min_credit", type=float)
    min_capacity = request.args.get("min_capacity", type=float)
    max_capacity = request.args.get("max_capacity", type=float)
    capacity_status = (request.args.get("capacity_status") or "").strip()
    business_status = (request.args.get("business_status") or "").strip()
    sort = (request.args.get("sort") or "credit").strip()
    is_export = request.args.get("is_export") in {"1", "true", "yes"}
    is_little_giant = request.args.get("is_little_giant") in {"1", "true", "yes"}
    is_green_factory = request.args.get("is_green_factory") in {"1", "true", "yes"}
    page = request.args.get("page", default=1, type=int) or 1
    per_page = request.args.get("per_page", type=int)
    legacy_limit = request.args.get("limit", type=int)
    is_guest = not current_user.is_authenticated
    include_self = (request.args.get("include_self") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    } and not is_guest
    if per_page is None:
        per_page = legacy_limit if legacy_limit is not None else 80
    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 10000))

    query = Enterprise.query.filter(Enterprise.role == "enterprise")
    if (
        not include_self
        and current_user.is_authenticated
        and getattr(current_user, "id", None)
    ):
        query = query.filter(Enterprise.id != current_user.id)

    if province:
        query = query.filter(
            or_(
                Enterprise.province == province,
                and_(
                    or_(Enterprise.province.is_(None), Enterprise.province == ""),
                    Enterprise.address.contains(province),
                ),
            )
        )
    if city:
        query = query.filter(or_(Enterprise.city == city, Enterprise.address.contains(city)))

    keywords = INDUSTRY_DIRECTORY_KEYWORDS.get(industry_key)
    if keywords:
        query = query.filter(
            or_(*[Enterprise.business_scope.contains(k) for k in keywords])
        )

    if q:
        query = query.filter(
            or_(
                Enterprise.name.contains(q),
                Enterprise.business_scope.contains(q),
            )
        )

    if tech_keyword:
        query = query.filter(
            or_(Enterprise.tech_keywords.contains(tech_keyword), Enterprise.business_scope.contains(tech_keyword))
        )

    if min_capacity is not None:
        query = query.filter(func.coalesce(Enterprise.max_capacity, Enterprise.capacity) >= min_capacity)
    if max_capacity is not None:
        query = query.filter(func.coalesce(Enterprise.max_capacity, Enterprise.capacity) <= max_capacity)
    if capacity_status:
        if capacity_status == "ample":
            query = query.filter(func.coalesce(Enterprise.capacity, 0) > func.coalesce(Enterprise.current_orders, 0))
        elif capacity_status == "tight":
            query = query.filter(func.coalesce(Enterprise.capacity, 0) <= func.coalesce(Enterprise.current_orders, 0))
    if business_status:
        query = query.filter(Enterprise.business_status == business_status)
    if is_green_factory:
        query = query.filter(Enterprise.is_green_factory.is_(True))
    # 当前数据模型使用 is_lead_enterprise 表示重点/专精特新企业标记。
    if is_little_giant:
        query = query.filter(Enterprise.is_lead_enterprise.is_(True))
    if is_export:
        query = query.filter(Enterprise.extras.isnot(None)).filter(
            cast(Enterprise.extras, String).ilike('%"is_export": true%')
        )

    if min_credit is not None and min_credit > 0:
        query = query.filter(Enterprise.credit_score >= min_credit)

    total = query.count()
    pages = (total + per_page - 1) // per_page if total else 0
    order_by = {
        "name": (Enterprise.name.asc(), Enterprise.id.asc()),
        "updated": (Enterprise.last_data_update.desc(), Enterprise.id.desc()),
        "capacity": (func.coalesce(Enterprise.capacity, 0).desc(), Enterprise.id.desc()),
        "credit": (Enterprise.credit_score.desc(), Enterprise.id.desc()),
    }.get(sort, (Enterprise.credit_score.desc(), Enterprise.id.desc()))
    rows = (
        query.order_by(*order_by)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify(
        {
            "count": len(rows),
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "has_more": page < pages,
            "enterprises": [
                {
                    "id": ent.id,
                    "name": ent.name,
                    "address": _enterprise_public_address(ent) if is_guest else (ent.address or ""),
                    "province": ent.province or "",
                    "city": ent.city or "",
                    "credit_score": float(ent.credit_score or 0.0),
                    "business_scope": (ent.business_scope or "")[:280],
                    "industry_code": ent.industry_code or "",
                    "tech_keywords": ent.tech_keywords or "",
                    "capacity": float(ent.capacity or 0),
                    "max_capacity": float(ent.max_capacity or ent.capacity or 0),
                    "current_orders": int(ent.current_orders or 0),
                    "capacity_status": "ample" if (ent.capacity or 0) > (ent.current_orders or 0) else "tight",
                    "is_export": bool(isinstance(ent.extras, dict) and ent.extras.get("is_export") is True),
                    "is_little_giant": bool(ent.is_lead_enterprise),
                    "is_green_factory": bool(ent.is_green_factory),
                    "business_status": ent.business_status or "待核验",
                    "updated_at": (ent.last_data_update or ent.biz_data_updated_at or ent.created_at).isoformat() if (ent.last_data_update or ent.biz_data_updated_at or ent.created_at) else None,
                    "source": "企业档案",
                    "is_demo": False,
                    "latitude": ent.latitude,
                    "longitude": ent.longitude,
                }
                for ent in rows
            ],
        }
    )


PUBLIC_SEARCH_TYPES = {"all", "enterprise", "product", "supply", "demand"}
PUBLIC_INDUSTRY_LABELS = {
    "machinery": "机械制造",
    "electronics": "电子信息",
    "automotive": "汽车零部件",
    "electric": "新能源与电气",
    "metal": "金属加工",
    "chemical": "化工材料",
    "medicine": "医药健康",
    "logistics": "物流与供应链",
}


def _public_credit_level(score: float | None) -> str:
    value = float(score or 0)
    if value >= 90:
        return "AAA"
    if value >= 80:
        return "AA"
    if value >= 70:
        return "A"
    if value >= 60:
        return "BBB"
    return "待提升"


def _public_mode() -> str:
    return str(current_app.config.get("PUBLIC_DATA_MODE", "demo") or "demo").strip().lower()


def _public_is_demo() -> bool:
    return _public_mode() != "production"


def _enterprise_public_qualifications(ent: Enterprise) -> list[dict]:
    raw = ent.qualifications if isinstance(ent.qualifications, list) else []
    return [row for row in raw if isinstance(row, dict)]


def _enterprise_has_label(ent: Enterprise, *terms: str) -> bool:
    haystack = " ".join(
        str(value or "")
        for row in _enterprise_public_qualifications(ent)
        for value in (row.get("label_type"), row.get("label_name"), row.get("status"))
    ).lower()
    return any(term.lower() in haystack for term in terms)


def _enterprise_is_export_capable(ent: Enterprise) -> bool:
    extras = ent.extras if isinstance(ent.extras, dict) else {}
    explicit = any(
        bool(extras.get(key))
        for key in ("is_export", "is_foreign_trade", "export_capable", "foreign_trade")
    )
    text = f"{ent.business_scope or ''} {ent.tech_keywords or ''}"
    return explicit or any(term in text for term in ("出口", "外贸", "国际贸易", "跨境"))


def _enterprise_has_decision_maker(ent: Enterprise) -> bool:
    return bool((ent.contact or "").strip() or (ent.phone or "").strip())


def _enterprise_is_little_giant(ent: Enterprise) -> bool:
    extras = ent.extras if isinstance(ent.extras, dict) else {}
    return bool(extras.get("is_little_giant")) or _enterprise_has_label(
        ent, "little_giant", "专精特新", "小巨人"
    )


def _public_enterprise_signals(ent: Enterprise) -> dict:
    return {
        "credit_level": _public_credit_level(ent.credit_score),
        "data_updated_at": _public_data_updated_at(ent),
        "verification_status": ent.verification_status or ("approved" if ent.is_verified else "pending"),
        "status": ent.business_status or "待核验",
        "is_export": _enterprise_is_export_capable(ent),
        "has_decision_maker": _enterprise_has_decision_maker(ent),
        "is_little_giant": _enterprise_is_little_giant(ent),
        "is_green_factory": bool(ent.is_green_factory),
        "registered_capital": float(ent.registered_capital or 0),
        "source": "企业档案",
        "is_demo": _public_is_demo(),
    }


def _public_resource_fields(signals: dict) -> dict:
    """Common anonymous resource metadata kept at the resource top level."""
    return {
        "verification_status": signals.get("verification_status"),
        "source": signals.get("source"),
        "updated_at": signals.get("data_updated_at") or signals.get("created_at"),
        "is_demo": bool(signals.get("is_demo")),
    }


def _public_data_updated_at(entity) -> str | None:
    value = getattr(entity, "last_data_update", None) or getattr(entity, "updated_at", None)
    if value is None:
        value = getattr(entity, "created_at", None)
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


def _public_enterprise_item(ent: Enterprise) -> dict:
    region = _enterprise_public_address(ent) or "区域待补充"
    tags = []
    if ent.is_verified or ent.verification_status == "approved":
        tags.append("已审核")
    if (ent.capacity or 0) > (ent.current_orders or 0):
        tags.append("产能可用")
    if ent.is_green_factory:
        tags.append("绿色供应")
    if _enterprise_is_export_capable(ent):
        tags.append("支持出口")
    if _enterprise_is_little_giant(ent):
        tags.append("专精特新")
    if _enterprise_has_decision_maker(ent):
        tags.append("有决策人联系方式")
    if not tags:
        tags.append("平台企业")
    signals = _public_enterprise_signals(ent)
    return {
        "kind": "enterprise",
        "id": ent.id,
        "title": ent.name,
        "subtitle": f"{ent.business_scope or ent.industry_code or '产业配套企业'} · {region}",
        "tags": tags,
        "public_signals": signals,
        **_public_resource_fields(signals),
        "requires_login_for_action": True,
    }


def _public_product_item(product: Product) -> dict:
    ent = product.enterprise
    region = _enterprise_public_address(ent) if ent else "区域待补充"
    supplier_name = ent.name if ent else "平台企业"
    category = product.category or product.industry_code or "产业产品"
    signals = {
        "enterprise_id": ent.id if ent else None,
        "data_updated_at": _public_data_updated_at(product),
        "source": "企业产品档案",
        "is_demo": _public_is_demo(),
    }
    return {
        "kind": "product",
        "id": product.id,
        "title": product.name,
        "subtitle": f"{supplier_name} · {category} · {region}",
        "tags": [category],
        "public_signals": signals,
        **_public_resource_fields(signals),
        "requires_login_for_action": True,
    }


def _public_inquiry_item(inquiry: Inquiry) -> dict:
    ent = inquiry.poster
    product_name = inquiry.product.name if inquiry.product else (inquiry.product_name or "未命名产品")
    direction_label = "供应信息" if inquiry.direction == "supply" else "采购需求"
    quantity = f"{inquiry.quantity}{inquiry.unit or ''}" if inquiry.quantity else "数量待确认"
    region = _enterprise_public_address(ent) if ent else "区域待补充"
    signals = {
        "status": inquiry.status,
        "created_at": inquiry.created_at.isoformat() if inquiry.created_at else None,
        "source": "公开供需信息",
        "is_demo": _public_is_demo(),
    }
    return {
        "kind": inquiry.direction,
        "id": inquiry.id,
        "title": product_name,
        "subtitle": f"{ent.name if ent else '平台企业'} · {quantity} · {region}",
        "tags": [direction_label, "开放中"],
        "public_signals": signals,
        **_public_resource_fields(signals),
        "requires_login_for_action": True,
    }


def _public_industry_filter(model, industry_key: str):
    keywords = INDUSTRY_DIRECTORY_KEYWORDS.get(industry_key)
    if not keywords:
        return None
    if model is Enterprise:
        return or_(*[Enterprise.business_scope.contains(keyword) for keyword in keywords])
    if model is Product:
        return or_(*[
            Product.category.contains(keyword)
            | Product.description.contains(keyword)
            | Enterprise.business_scope.contains(keyword)
            for keyword in keywords
        ])
    return or_(*[
        Inquiry.product_name.contains(keyword)
        | Inquiry.description.contains(keyword)
        | Inquiry.content.contains(keyword)
        | Enterprise.business_scope.contains(keyword)
        for keyword in keywords
    ])


def _public_region_filter(model, province: str):
    if not province:
        return None
    return or_(
        Enterprise.province == province,
        and_(
            or_(Enterprise.province.is_(None), Enterprise.province == ""),
            Enterprise.address.contains(province),
        ),
    )


def _public_enterprise_constraints(
    query,
    province: str,
    city: str = "",
    is_export: bool = False,
    has_decision_maker: bool = False,
    is_little_giant: bool = False,
    is_green_factory: bool = False,
    company_status: str = "",
    min_registered_capital: float | None = None,
):
    region_filter = _public_region_filter(Enterprise, province)
    if region_filter is not None:
        query = query.filter(region_filter)
    if city:
        query = query.filter(
            or_(Enterprise.city == city, Enterprise.city.contains(city), Enterprise.address.contains(city))
        )
    if is_green_factory:
        query = query.filter(Enterprise.is_green_factory.is_(True))
    if company_status:
        query = query.filter(Enterprise.business_status == company_status)
    if min_registered_capital is not None:
        query = query.filter(Enterprise.registered_capital >= min_registered_capital)
    if has_decision_maker:
        query = query.filter(
            or_(
                and_(Enterprise.contact.isnot(None), Enterprise.contact != ""),
                and_(Enterprise.phone.isnot(None), Enterprise.phone != ""),
            )
        )
    # JSON 标签来自企业画像；CAST 保持 SQLite 测试库和 MySQL 生产库行为一致。
    qualifications_text = cast(Enterprise.qualifications, String)
    extras_text = cast(Enterprise.extras, String)
    if is_little_giant:
        query = query.filter(
            or_(
                qualifications_text.contains("little_giant"),
                qualifications_text.contains("专精特新"),
                qualifications_text.contains("小巨人"),
                extras_text.contains("is_little_giant"),
            )
        )
    if is_export:
        query = query.filter(
            or_(
                Enterprise.business_scope.contains("出口"),
                Enterprise.business_scope.contains("外贸"),
                Enterprise.business_scope.contains("国际贸易"),
                Enterprise.business_scope.contains("跨境"),
                extras_text.contains("is_export"),
                extras_text.contains("is_foreign_trade"),
            )
        )
    return query


def _public_enterprise_query(
    q: str,
    province: str,
    industry_key: str,
    **filters,
):
    query = Enterprise.query.filter(Enterprise.role == "enterprise")
    if q:
        # 平台搜索产品时同时返回其供应企业，避免结果只有产品而缺少可行动的主体。
        query = query.outerjoin(Product, Product.enterprise_id == Enterprise.id).distinct()
        query = query.filter(
            or_(
                Enterprise.name.contains(q),
                Enterprise.business_scope.contains(q),
                Enterprise.industry_code.contains(q),
                Product.name.contains(q),
                Product.description.contains(q),
                Product.category.contains(q),
            )
        )
    query = _public_enterprise_constraints(query, province, **filters)
    industry_filter = _public_industry_filter(Enterprise, industry_key)
    if industry_filter is not None:
        query = query.filter(industry_filter)
    return query


def _public_product_query(q: str, province: str, industry_key: str, **filters):
    query = Product.query.join(Enterprise, Product.enterprise_id == Enterprise.id).filter(
        Enterprise.role == "enterprise"
    )
    if q:
        query = query.filter(
            or_(
                Product.name.contains(q),
                Product.description.contains(q),
                Product.category.contains(q),
                Enterprise.name.contains(q),
                Enterprise.business_scope.contains(q),
            )
        )
    query = _public_enterprise_constraints(query, province, **filters)
    industry_filter = _public_industry_filter(Product, industry_key)
    if industry_filter is not None:
        query = query.filter(industry_filter)
    return query


def _public_inquiry_query(
    q: str,
    province: str,
    industry_key: str,
    direction: str | None = None,
    **filters,
):
    query = Inquiry.query.join(Enterprise, Inquiry.poster_id == Enterprise.id).filter(
        Enterprise.role == "enterprise",
        Inquiry.status.in_(("open", "active")),
    )
    if direction:
        query = query.filter(Inquiry.direction == direction)
    if q:
        query = query.filter(
            or_(
                Inquiry.product_name.contains(q),
                Inquiry.description.contains(q),
                Inquiry.content.contains(q),
                Enterprise.name.contains(q),
            )
        )
    query = _public_enterprise_constraints(query, province, **filters)
    industry_filter = _public_industry_filter(Inquiry, industry_key)
    if industry_filter is not None:
        query = query.filter(industry_filter)
    return query


def _public_regions() -> list[dict]:
    rows = (
        Enterprise.query.with_entities(Enterprise.province, func.count(Enterprise.id))
        .filter(Enterprise.role == "enterprise", Enterprise.province.isnot(None), Enterprise.province != "")
        .group_by(Enterprise.province)
        .order_by(func.count(Enterprise.id).desc())
        .limit(8)
        .all()
    )
    return [{"key": province, "label": province, "count": count} for province, count in rows]


def _public_industrial_belts() -> list[dict]:
    return [
        {"key": row["key"], "label": f'{row["label"]}产业带', "count": row["count"]}
        for row in _public_regions()
    ]


def _public_services() -> list[dict]:
    return [
        {"key": "onboarding", "title": "企业入驻", "summary": "完善企业、产品、产能和资质档案"},
        {"key": "verification", "title": "工厂能力认证", "summary": "用可验证数据建立制造能力名片"},
        {"key": "matching", "title": "AI 供需匹配", "summary": "从需求快速找到合适的供应商"},
        {"key": "graph", "title": "产业链图谱", "summary": "查看上下游关系、产业缺口和风险"},
        {"key": "open", "title": "开放 API / MCP", "summary": "将工厂数据接入业务系统和 Agent"},
        {"key": "government", "title": "政府与园区方案", "summary": "支撑招商、补链和产业治理"},
    ]


@api_bp.route("/public/home", methods=["GET"])
def api_public_home():
    """公共平台首页聚合数据，只返回匿名可见的资源摘要。"""
    enterprise_count = Enterprise.query.filter(Enterprise.role == "enterprise").count()
    product_count = Product.query.join(Enterprise, Product.enterprise_id == Enterprise.id).filter(
        Enterprise.role == "enterprise"
    ).count()
    active_supply_count = Inquiry.query.filter(
        Inquiry.direction == "supply", Inquiry.status.in_(("open", "active"))
    ).count()
    active_demand_count = Inquiry.query.filter(
        Inquiry.direction == "demand", Inquiry.status.in_(("open", "active"))
    ).count()
    completed_transaction_count = Transaction.query.filter(Transaction.status == "completed").count()
    verified_count = Enterprise.query.filter(
        Enterprise.role == "enterprise",
        or_(Enterprise.is_verified.is_(True), Enterprise.verification_status == "approved"),
    ).count()

    featured_enterprises = (
        Enterprise.query.filter(Enterprise.role == "enterprise")
        .order_by(Enterprise.credit_score.desc(), Enterprise.id.desc())
        .limit(6)
        .all()
    )
    featured_products = (
        Product.query.join(Enterprise, Product.enterprise_id == Enterprise.id)
        .filter(Enterprise.role == "enterprise")
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(8)
        .all()
    )
    recent_inquiries = (
        Inquiry.query.join(Enterprise, Inquiry.poster_id == Enterprise.id)
        .filter(Enterprise.role == "enterprise", Inquiry.status.in_(("open", "active")))
        .order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
        .limit(8)
        .all()
    )

    return jsonify(
        {
            "stats": {
                "enterprise_count": enterprise_count,
                "product_count": product_count,
                "active_supply_count": active_supply_count,
                "active_demand_count": active_demand_count,
                "completed_transaction_count": completed_transaction_count,
                # MySQL 产品节点是 Neo4j 不可用时的稳定降级口径；首页不因图数据库暂时不可用而阻塞。
                "graph_node_count": product_count,
                "verified_count": verified_count,
            },
            "featured_enterprises": [_public_enterprise_item(ent) for ent in featured_enterprises],
            "featured_products": [_public_product_item(product) for product in featured_products],
            "latest_inquiries": [_public_inquiry_item(inquiry) for inquiry in recent_inquiries],
            "industries": [
                {"key": key, "label": label} for key, label in PUBLIC_INDUSTRY_LABELS.items()
            ],
            "regions": _public_regions(),
            "industrial_belts": _public_industrial_belts(),
            "public_services": _public_services(),
            "data_freshness": {
                "mode": _public_mode(),
                "is_demo": _public_is_demo(),
                "label": "演示数据" if _public_is_demo() else "生产数据",
                "updated_at": datetime.utcnow().isoformat(),
            },
            "data_status": {
                "mode": _public_mode(),
                "message": "公开页面仅展示脱敏摘要；完整企业能力和联系方式需登录后查看。",
            },
        }
    )


@api_bp.route("/public/search", methods=["GET"])
def api_public_search():
    """公共统一资源搜索：企业、产品、供应信息和采购需求。"""
    q = (request.args.get("q") or "").strip()[:120]
    search_type = (request.args.get("type") or "all").strip().lower()
    province = (request.args.get("province") or "").strip()[:30]
    city = (request.args.get("city") or "").strip()[:50]
    industry_key = (request.args.get("industry") or "").strip().lower()
    sort = (request.args.get("sort") or "relevance").strip().lower()
    is_export = request.args.get("is_export", "").lower() in {"1", "true", "yes"}
    has_decision_maker = request.args.get("has_decision_maker", "").lower() in {"1", "true", "yes"}
    is_little_giant = request.args.get("is_little_giant", "").lower() in {"1", "true", "yes"}
    is_green_factory = request.args.get("is_green_factory", "").lower() in {"1", "true", "yes"}
    company_status = (request.args.get("company_status") or "").strip()[:20]
    min_registered_capital = request.args.get("min_registered_capital", type=float)
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(50, request.args.get("per_page", default=20, type=int) or 20))

    if search_type not in PUBLIC_SEARCH_TYPES:
        return jsonify({"error": "type 必须是 all、enterprise、product、supply 或 demand"}), 400

    filters = {
        "city": city,
        "is_export": is_export,
        "has_decision_maker": has_decision_maker,
        "is_little_giant": is_little_giant,
        "is_green_factory": is_green_factory,
        "company_status": company_status,
        "min_registered_capital": min_registered_capital,
    }
    sources = []
    if search_type in {"all", "enterprise"}:
        query = _public_enterprise_query(q, province, industry_key, **filters)
        total = query.count()
        sources.append(("enterprise", total, query))
    if search_type in {"all", "product"}:
        query = _public_product_query(q, province, industry_key, **filters)
        total = query.count()
        sources.append(("product", total, query))
    if search_type in {"all", "supply", "demand"}:
        direction = None if search_type == "all" else search_type
        query = _public_inquiry_query(q, province, industry_key, direction, **filters)
        total = query.count()
        sources.append(("inquiry", total, query))

    total = sum(source_total for _, source_total, _ in sources)
    start = (page - 1) * per_page
    end = start + per_page
    page_results = []
    cursor = 0
    for source_name, source_total, query in sources:
        segment_start = max(0, start - cursor)
        segment_end = min(source_total, end - cursor)
        if segment_start < segment_end:
            limit = segment_end - segment_start
            if source_name == "enterprise":
                rows = query.order_by(Enterprise.credit_score.desc(), Enterprise.id.desc()).offset(segment_start).limit(limit).all()
                page_results.extend(_public_enterprise_item(row) for row in rows)
            elif source_name == "product":
                rows = query.order_by(Product.created_at.desc(), Product.id.desc()).offset(segment_start).limit(limit).all()
                page_results.extend(_public_product_item(row) for row in rows)
            else:
                rows = query.order_by(Inquiry.created_at.desc(), Inquiry.id.desc()).offset(segment_start).limit(limit).all()
                page_results.extend(_public_inquiry_item(row) for row in rows)
        cursor += source_total
        if cursor >= end:
            break

    if sort == "name":
        page_results.sort(key=lambda item: item["title"])
    return jsonify(
        {
            "query": q,
            "type": search_type,
            "province": province,
            "city": city,
            "industry": industry_key,
            "sort": sort,
            "filters": filters,
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page if total else 0,
            "has_more": start + per_page < total,
            "results": page_results,
        }
    )


@api_bp.route("/public/enterprises/<int:enterprise_id>", methods=["GET"])
def api_public_enterprise_detail(enterprise_id: int):
    """公开企业详情：只返回脱敏企业画像和公开产品，不返回联系方式。"""
    ent = Enterprise.query.filter(
        Enterprise.id == enterprise_id, Enterprise.role == "enterprise"
    ).first()
    if not ent:
        return jsonify({"error": "企业不存在"}), 404

    public_item = _public_enterprise_item(ent)
    capacity = int(ent.capacity or 0)
    current_orders = int(ent.current_orders or 0)
    if capacity <= 0:
        capacity_summary = "产能待补充"
    elif capacity > current_orders:
        capacity_summary = "当前有可用产能"
    else:
        capacity_summary = "当前产能较紧张"
    products = Product.query.filter(Product.enterprise_id == ent.id).order_by(
        Product.created_at.desc(), Product.id.desc()
    ).limit(30).all()

    return jsonify(
        {
            "enterprise": {
                "id": ent.id,
                "name": ent.name,
                "region": _enterprise_public_address(ent) or "区域待补充",
                "business_scope": ent.business_scope or "",
                "industry_code": ent.industry_code or "",
                "business_status": ent.business_status or "待核验",
                "registered_capital": float(ent.registered_capital or 0),
                "credit_level": _public_credit_level(ent.credit_score),
                "capacity_summary": capacity_summary,
                "tags": public_item["tags"],
                "public_signals": public_item["public_signals"],
                "data_updated_at": _public_data_updated_at(ent),
            },
            "products": [_public_product_item(product) for product in products],
            "actions": {
                "requires_login": True,
                "available": ["contact", "inquiry", "favorite", "export"],
            },
        }
    )


@api_bp.route("/public/agent-market", methods=["GET"])
def api_public_agent_market():
    """公开 Agent 能力目录，能力数量按真实展示内容计算。"""
    groups = [
        {"title": "AI 销售员", "summary": "线索获取、客户跟进和报价成交", "demo": False, "agents": ["客户线索整理", "智能报价助手", "企微跟进助手"]},
        {"title": "AI 采购员", "summary": "供应商寻源、比价决策和绩效风控", "demo": True, "agents": ["全国快速询价", "供应商筛选", "供应商风险检查"]},
        {"title": "AI 计划员", "summary": "订单分解、生产计划和交期协调", "demo": False, "agents": ["订单计划助手", "产能排程建议", "交期风险提醒"]},
        {"title": "AI 生产员", "summary": "车间执行、质量记录和异常闭环", "demo": False, "agents": ["生产执行助手", "质量异常归因", "工艺知识助手"]},
        {"title": "AI 财法务", "summary": "合同审查、单据处理和资金风险", "demo": False, "agents": ["合同审查", "发票单据处理", "财务风险告警"]},
        {"title": "AI 出海专员", "summary": "海外获客、合规检查和出口协同", "demo": False, "agents": ["海外客户开发", "出口资质检查", "跨境合规助手"]},
        {"title": "AI 情报官", "summary": "产业监测、竞争分析和政策匹配", "demo": False, "agents": ["产业监测", "招商线索发现", "政策匹配助手"]},
    ]
    return jsonify(
        {
            "groups": groups,
            "layers": [
                {"key": "industry", "title": "产业数据底座", "description": "企业、产品、产能、信用和产业关系"},
                {"key": "enterprise", "title": "企业业务数据", "description": "订单、库存、BOM、客户和报价"},
                {"key": "agent", "title": "岗位型 AI Agent", "description": "输出名单、询价单、排产建议和风险告警"},
            ],
        }
    )


def _public_structured_intent(query: str, parsed: dict) -> dict:
    """Normalize model output and add safe deterministic fields for the public flow.

    The public page must remain useful when the local LLM is unavailable. These
    fields are intentionally limited to procurement constraints and never
    include contact or private enterprise data.
    """
    intent = dict(parsed) if isinstance(parsed, dict) else {}
    region_terms = (
        "华东", "华南", "华北", "华中", "西南", "西北", "东北",
        "广东", "浙江", "江苏", "山东", "福建", "安徽", "湖北", "四川",
    )
    region = next((term for term in region_terms if term in query), None)
    if region:
        intent["region"] = region

    quantity_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(万|千)?\s*(件|台|套|吨|公斤|个|pcs)",
        query,
        flags=re.IGNORECASE,
    )
    if quantity_match:
        quantity = float(quantity_match.group(1))
        multiplier = {"万": 10000, "千": 1000}.get(quantity_match.group(2) or "", 1)
        intent["quantity"] = int(quantity * multiplier) if (quantity * multiplier).is_integer() else quantity * multiplier
        intent["unit"] = quantity_match.group(3)

    delivery_match = re.search(
        r"(?:交期|交付|交货|周期)[^\d]{0,8}(\d+)\s*(?:天|日)?|"
        r"(\d+)\s*(?:天|日)\s*(?:内|交付|交货|交期)?",
        query,
    )
    if delivery_match:
        intent["delivery_days"] = int(delivery_match.group(1) or delivery_match.group(2))

    process_terms = ("注塑", "冲压", "铸造", "锻造", "CNC", "机加工", "表面处理", "焊接", "装配")
    processes = [term for term in process_terms if term.lower() in query.lower()]
    if processes:
        intent["processes"] = processes

    certification_terms = ("ISO 9001", "ISO9001", "IATF16949", "ISO", "3C", "CE", "FDA", "专精特新", "绿色工厂")
    certifications = [term for term in certification_terms if term.lower() in query.lower()]
    if certifications:
        intent["certifications"] = certifications

    if any(term in query for term in ("出口", "外贸", "跨境", "国际贸易")):
        intent["is_export"] = True

    return intent


@api_bp.route("/public/ai-find", methods=["POST"])
def api_public_ai_find():
    """公开 AI 找厂：复用现有匹配引擎，但对匿名返回做脱敏。"""
    data = request.get_json(silent=True) or {}
    query = str(data.get("query") or data.get("message") or "").strip()[:500]
    if not query:
        return jsonify({"error": "请输入产品、工艺、地区或采购要求"}), 400

    parsed = _public_structured_intent(query, extract_weights_from_nl(query) or {})
    product = str(parsed.get("product") or query).strip()[:200]
    try:
        quantity = max(1, min(int(data.get("quantity", 100)), 1_000_000))
    except (TypeError, ValueError):
        quantity = 100

    try:
        matched = match_suppliers(
            demand_product=product,
            demand_quantity=quantity,
            demand_ent_id=None,
            demand_industry_code=data.get("industry_code"),
            sort_by="score",
            filters=None,
        )
    except Exception:
        _logger.exception("public ai-find failed")
        matched = []

    candidates = []
    for row in (matched or [])[:10]:
        enterprise_id = int(row.get("enterprise_id") or row.get("id") or 0)
        ent = Enterprise.query.filter(
            Enterprise.id == enterprise_id, Enterprise.role == "enterprise"
        ).first()
        if not ent:
            continue
        item = _public_enterprise_item(ent)
        candidates.append(
            {
                "id": ent.id,
                "title": ent.name,
                "subtitle": item["subtitle"],
                "score": float(row.get("score") or row.get("confidence_index") or 0),
                "reason": row.get("ai_match_reason") or row.get("match") or "符合产品和企业能力条件",
                "tags": item["tags"],
                "public_signals": item["public_signals"],
                **_public_resource_fields(item["public_signals"]),
                "requires_login_for_action": True,
            }
        )
    return jsonify(
        {
            "query": query,
            "parsed_intent": parsed,
            "product": product,
            "results": candidates,
            "has_more": len(matched or []) > len(candidates),
        }
    )


@api_bp.route("/finance/loan-eligibility", methods=["GET"])
@role_required("enterprise")
def finance_loan_eligibility():
    """链易贷预授信：基于 credit_score + 最近匹配反馈中的 match_score。"""
    info = finance_service.calculate_loan_eligibility(current_user.id)
    if not info:
        return jsonify({"error": "企业不存在"}), 404
    return jsonify({"status": "success", **info})


@api_bp.route("/finance/apply-order-financing", methods=["POST"])
@role_required("enterprise")
def finance_apply_order_financing():
    """
    提交订单融资申请并提升 credit_score（金融活跃度）。
    JSON: bank_name, loan_amount_yuan, supplier_id (可选)
    """
    data = request.get_json(silent=True) or {}
    bank_name = (data.get("bank_name") or "").strip()
    loan_amount_yuan = data.get("loan_amount_yuan")
    supplier_id = data.get("supplier_id")
    if loan_amount_yuan is None:
        return jsonify({"error": "缺少 loan_amount_yuan"}), 400
    try:
        amount = float(loan_amount_yuan)
    except (TypeError, ValueError):
        return jsonify({"error": "loan_amount_yuan 无效"}), 400
    if amount <= 0:
        return jsonify({"error": "额度须大于 0"}), 400

    sid = None
    if supplier_id is not None:
        try:
            sid = int(supplier_id)
        except (TypeError, ValueError):
            return jsonify({"error": "supplier_id 无效"}), 400

    if not bank_name:
        preview = finance_service.calculate_loan_eligibility(current_user.id)
        bank_name = (preview or {}).get("bank_name") or "合作银行"

    try:
        result = finance_service.apply_order_financing(
            current_user.id,
            bank_name,
            amount,
            supplier_id=sid,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"status": "success", **result})


@api_bp.route("/favorites", methods=["GET"])
@login_required
def get_favorites():
    """获取企业的客商收藏夹列表。从 Enterprise.extras['favorites'] 中读取 ID 列表，并返回企业详情。"""
    ent = Enterprise.query.get(current_user.id)
    extras = dict(ent.extras or {})
    favorite_ids = extras.get('favorites', [])
    
    if not favorite_ids:
        return jsonify({"success": True, "favorites": []})
        
    suppliers = Enterprise.query.filter(Enterprise.id.in_(favorite_ids)).all()
    
    result = []
    for s in suppliers:
        # Mocking some metrics that might not be directly available for the UI
        result.append({
            "id": s.id,
            "name": s.name,
            "industry": s.industry_code or "未知行业",
            "location": s.city or s.province or "未知地区",
            "score": float(s.credit_score or 0.0),
            "match": f"{int(round(float(s.credit_score or 0.0)))}%", # Mock match rate relative to credit score
            "tags": s.business_scope.split(',')[:2] if s.business_scope else ["优质客商"]
        })
        
    return jsonify({"success": True, "favorites": result})


@api_bp.route("/favorites/<int:supplier_id>", methods=["POST"])
@login_required
def add_favorite(supplier_id):
    """添加某个客商到收藏夹"""
    ent = Enterprise.query.get(current_user.id)
    extras = dict(ent.extras or {})
    favorites = extras.get('favorites', [])
    
    if supplier_id not in favorites:
        favorites.append(supplier_id)
        extras['favorites'] = favorites
        ent.extras = extras
        from app import db
        db.session.commit()
        
    return jsonify({"success": True, "message": "已添加到收藏夹"})


@api_bp.route("/favorites/<int:supplier_id>", methods=["DELETE"])
@login_required
def remove_favorite(supplier_id):
    """从收藏夹中移除某个客商"""
    ent = Enterprise.query.get(current_user.id)
    extras = dict(ent.extras or {})
    favorites = extras.get('favorites', [])
    
    if supplier_id in favorites:
        favorites.remove(supplier_id)
        extras['favorites'] = favorites
        ent.extras = extras
        from app import db
        db.session.commit()
        
    return jsonify({"success": True, "message": "已取消收藏"})
def _asset_default_qualifications():
    return [
        {"title": "ISO 9001 质量管理体系", "date": "有效期至 2026.12", "status": "有效"},
        {"title": "高新技术企业证书", "date": "有效期至 2025.08", "status": "有效"},
        {"title": "安全生产标准化二级", "date": "有效期至 2027.03", "status": "有效"},
        {"title": "精密加工特种行业许可证", "date": "有效期至 2026.01", "status": "有效"},
    ]


def _asset_default_data_auth():
    return [
        {"name": "金蝶云星空 ERP", "status": "已连接", "data": "订单、库存、财务"},
        {"name": "钉钉数字化办公", "status": "已连接", "data": "组织架构、审批流"},
        {"name": "顺丰物流开放平台", "status": "未连接", "data": "实时轨迹、电子面单"},
    ]


def _normalize_asset_qualifications(raw):
    if not isinstance(raw, list) or not raw:
        return _asset_default_qualifications()

    normalized = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = (
            item.get("title")
            or item.get("label_name")
            or item.get("name")
            or item.get("certificate_no")
            or "企业资质"
        )
        valid_until = item.get("valid_until") or item.get("expire_at") or item.get("date")
        date_text = item.get("date") or (f"有效期至 {valid_until}" if valid_until else "长期有效")
        status_raw = str(item.get("status") or "").lower()
        status = "有效" if status_raw in {"valid", "active", "enabled", "有效"} else item.get("status") or "有效"
        normalized.append({"title": str(title), "date": str(date_text), "status": str(status)})
    return normalized or _asset_default_qualifications()


def _normalize_asset_data_auth(raw):
    if isinstance(raw, list):
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "name": str(item.get("name") or item.get("system") or "外部数据接口"),
                    "status": str(item.get("status") or "已连接"),
                    "data": str(item.get("data") or item.get("scope") or "授权数据"),
                }
            )
        return normalized or _asset_default_data_auth()

    if isinstance(raw, dict) and raw:
        labels = {
            "power": ("电力数据接口", "用电负荷、产能曲线"),
            "invoice": ("发票数据接口", "开票、交易流水"),
            "business": ("工商数据接口", "企业登记、经营状态"),
            "tax": ("税务数据接口", "纳税信用、税票信息"),
        }
        normalized = []
        for key, value in raw.items():
            item = value if isinstance(value, dict) else {}
            name, data_scope = labels.get(str(key), (f"{key} 数据接口", "授权数据"))
            authorized = bool(item.get("authorized")) or item.get("sync_status") == "success"
            normalized.append(
                {
                    "name": name,
                    "status": "已连接" if authorized else "未连接",
                    "data": data_scope,
                }
            )
        return normalized or _asset_default_data_auth()

    return _asset_default_data_auth()


@api_bp.route("/user/assets", methods=["GET"])
@login_required
def api_user_assets():
    """获取当前用户的数字资产画像（含资质、数据授权、信用拆解等），供 Assets 页面使用"""
    ent = Enterprise.query.get(current_user.id)
    if not ent:
        return jsonify({"error": "未找到企业信息"}), 404

    qualifications = _normalize_asset_qualifications(ent.qualifications)
    data_auth = _normalize_asset_data_auth(ent.data_auth)

    # 团队成员 (Mock数据，实际中可以从另一个表或extras读取)
    team_members = [
        {"name": "张建国", "role": "法定代表人 / CEO", "avatar": "张"},
        {"name": "李晓琳", "role": "财务总监", "avatar": "李"},
        {"name": "王志强", "role": "生产主管", "avatar": "王"}
    ]

    return jsonify({
        "success": True,
        "assets": {
            "id": ent.id,
            "name": ent.name,
            "is_certified": True,
            "location": f"{ent.province or '未知'} · {ent.city or '未知'}",
            "industry_tag": str(ent.business_scope).split(',')[0] if ent.business_scope else "精密制造",
            "tags": ["专精特新“小巨人”", "高新技术企业", "绿色工厂"] if ent.is_green_factory else ["优质客商", "信守承诺"],
            "credit_score": int(ent.credit_score or 0),
            "patent_count": ent.patent_count or 12,
            "qualifications": qualifications,
            "data_auth": data_auth,
            "team_members": team_members,
            "credit_breakdown": [
                {"label": "履约真实度", "score": 98},
                {"label": "交付准时率", "score": 92},
                {"label": "财务稳健性", "score": 85},
                {"label": "行业影响力", "score": 78}
            ]
        }
    })


@api_bp.route("/enterprise/<int:ent_id>/profile-mini", methods=["GET"])
@login_required
def api_enterprise_profile_mini(ent_id: int):
    """
    获取企业的名片信息（含地理位置坐标），用于名片交换功能。
    返回字段：id, name, address, longitude, latitude, contact, phone,
              business_scope, credit_score, is_green_factory, tags。
    """
    ent = Enterprise.query.get(ent_id)
    if not ent:
        return jsonify({"error": "企业不存在"}), 404

    # 资质标签
    tags = []
    if ent.is_green_factory:
        tags.append("政府绿标")
    if ent.qualifications:
        quals = ent.qualifications if isinstance(ent.qualifications, list) else []
        for q in quals:
            if isinstance(q, dict) and q.get("status") == "有效":
                title = q.get("title", "")
                if title:
                    tags.append(title[:20])
    if len(tags) > 5:
        tags = tags[:5]

    # 主营业务截取
    main_business = ""
    if ent.business_scope:
        scope = ent.business_scope
        main_business = scope[:80] + ("…" if len(scope) > 80 else "")

    return jsonify({
        "success": True,
        "enterprise": {
            "id": ent.id,
            "name": ent.name,
            "address": ent.address or f"{ent.province or ''}{ent.city or ''}",
            "longitude": ent.longitude,
            "latitude": ent.latitude,
            "contact": ent.contact or "",
            "phone": ent.phone or "",
            "main_business": main_business,
            "business_scope": ent.business_scope or "",
            "credit_score": int(ent.credit_score or 70),
            "is_green_factory": ent.is_green_factory,
            "tags": tags,
            "collaboration_code": None,
        }
    })


@api_bp.route("/user/settings", methods=["GET"])
@login_required
def get_user_settings():
    """获取企业设置资料"""
    ent = Enterprise.query.get(current_user.id)
    extras = dict(ent.extras or {})
    email = extras.get('email', f"admin@{ent.phone or 'company'}.com")
    
    return jsonify({
        "success": True,
        "settings": {
            "name": ent.name,
            "role": user_effective_role(ent),
            "email": email,
            "phone": ent.phone or "",
            "business_scope": ent.business_scope or ""
        }
    })

@api_bp.route("/user/settings", methods=["POST"])
@login_required
def update_user_settings():
    """更新企业设置资料"""
    data = request.get_json() or {}
    ent = Enterprise.query.get(current_user.id)
    
    if 'name' in data and data['name'].strip():
        ent.name = data['name'].strip()
    if 'phone' in data:
        ent.phone = data['phone'].strip()
    if 'business_scope' in data:
        ent.business_scope = data['business_scope'].strip()
        
    if 'email' in data:
        extras = dict(ent.extras or {})
        extras['email'] = data['email'].strip()
        ent.extras = extras
        
    from app import db
    db.session.commit()
    
    return jsonify({"success": True, "message": "设置已保存"})


# ═══════════════════════════════════════════════════════════════════════════════
# 销售控制台消息接口
# ═══════════════════════════════════════════════════════════════════════════════

@api_bp.route("/messages", methods=["GET"])
@login_required
def api_get_messages():
    """
    GET /api/messages
    获取当前用户的消息列表，支持分页和模式筛选。

    Query 参数：
    - page: 页码（默认 1）
    - per_page: 每页数量（默认 20）
    - mode: 模式筛选（procurement | sales | 空）
    - type: 消息类型（可选）
    - is_read: 是否已读（true | false）
    """
    try:
        page = request.args.get("page", 1, type=int) or 1
        per_page = request.args.get("per_page", 20, type=int) or 20
        mode = request.args.get("mode", "").strip() or None
        msg_type = request.args.get("type", "").strip() or None
        is_read_param = request.args.get("is_read", "").strip()

        # 分页参数
        page = max(1, page)
        per_page = max(1, min(per_page, 100))

        # 已读状态筛选
        is_read_filter = None
        if is_read_param == "true":
            is_read_filter = True
        elif is_read_param == "false":
            is_read_filter = False

        # 获取当前用户的企业信息
        ent = Enterprise.query.get(current_user.id)
        if not ent:
            return jsonify({
                "success": True,
                "total": 0,
                "unread_count": 0,
                "page": page,
                "per_page": per_page,
                "messages": []
            })

        # 构建消息查询
        from app.models import Message
        query = Message.query.filter(Message.recipient_id == current_user.id)

        if msg_type:
            query = query.filter(Message.message_type == msg_type)

        if is_read_filter is not None:
            query = query.filter(Message.is_read == is_read_filter)

        # 计算总数
        total = query.count()

        # 获取未读数
        unread_count = Message.query.filter(
            Message.recipient_id == current_user.id,
            Message.is_read == False
        ).count()

        # 分页查询
        messages = query.order_by(Message.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

        # 转换为前端期望的格式
        result_messages = []
        for msg in messages:
            # 根据 mode 筛选消息方向
            # procurement 模式：用户是买方，显示来自卖方的消息
            # sales 模式：用户是卖方，显示来自买方的消息
            sender_id = msg.sender_id
            if mode == "procurement":
                # 采购模式：当前用户是买方，需要显示来自卖方的消息
                if sender_id == current_user.id:
                    continue  # 跳过自己发的消息
            elif mode == "sales":
                # 销售模式：当前用户是卖方，需要显示来自买方的消息
                if sender_id == current_user.id:
                    continue

            # 尝试从 sender_id 获取企业名称
            sender_ent = Enterprise.query.get(sender_id) if sender_id else None
            sender_name = sender_ent.name if sender_ent else f"用户{sender_id}"

            result_messages.append({
                "id": msg.id,
                "title": msg.title or "",
                "content": msg.content or "",
                "message_type": msg.message_type or "system",
                "is_read": msg.is_read,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "created_at": msg.created_at.strftime("%Y-%m-%d %H:%M") if msg.created_at else "",
                "link_url": getattr(msg, 'link_url', None) or "",
            })

        return jsonify({
            "success": True,
            "total": total,
            "unread_count": unread_count,
            "page": page,
            "per_page": per_page,
            "messages": result_messages
        })

    except Exception as e:
        _logger.exception("api_get_messages error")
        return jsonify({
            "success": False,
            "error": str(e) or "获取消息列表失败"
        }), 500
