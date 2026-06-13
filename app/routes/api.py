"""
REST API：地图相关（/api/map/*）
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime

_logger = logging.getLogger(__name__)

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from flask_login import current_user, login_required
from sqlalchemy import and_, or_
from langchain_core.messages import HumanMessage, SystemMessage

from app.authz import role_required, user_effective_role, user_session_role
from app.models import Enterprise
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
    参数：province（省/直辖市/自治区名）、industry（预置行业 key）、q（关键词）、
    min_credit、page、per_page；limit 作为旧参数兼容 per_page；
    include_self=1 可用于政府大屏等全量监管视图。
    """
    province = (request.args.get("province") or "").strip()
    industry_key = (request.args.get("industry") or "").strip()
    q = (request.args.get("q") or "").strip()
    min_credit = request.args.get("min_credit", type=float)
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

    if min_credit is not None and min_credit > 0:
        query = query.filter(Enterprise.credit_score >= min_credit)

    total = query.count()
    pages = (total + per_page - 1) // per_page if total else 0
    rows = (
        query.order_by(Enterprise.credit_score.desc(), Enterprise.id.desc())
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
                }
                for ent in rows
            ],
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
