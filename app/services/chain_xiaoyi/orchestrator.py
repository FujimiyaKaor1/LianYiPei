from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app import db
from app.models import Enterprise, Inquiry
from app.applications.matching.services.matcher import DEFAULT_WEIGHTS, match_suppliers
from app.services.deepseek_client import create_deepseek_chat_model_from_env
from app.services.ollama_client import invoke_ollama
from app.models_chain_xiaoyi import (
    ChainXiaoYiApproval,
    ChainXiaoYiEvent,
    ChainXiaoYiFileImport,
    ChainXiaoYiMessage,
    ChainXiaoYiRun,
    ChainXiaoYiSession,
    ChainXiaoYiTask,
)
from .model_router import get_model_status
from .rules import merge_procurement_intent, parse_procurement_intent, preview_tabular_file


INTENT_KEYS = {
    "product", "synonyms", "processes", "region", "quantity", "unit",
    "delivery_days", "industry", "certifications", "is_export",
    "is_little_giant", "is_green_factory", "min_credit",
    "min_registered_capital", "min_capacity", "max_distance", "preferences",
}


def _normalize_intent(value: dict) -> dict:
    clean: dict = {}
    string_keys = {"product", "region", "unit", "industry"}
    list_keys = {"synonyms", "processes", "certifications"}
    boolean_keys = {"is_export", "is_little_giant", "is_green_factory"}
    numeric_keys = {"quantity", "delivery_days", "min_credit", "min_registered_capital", "min_capacity", "max_distance"}
    for key in string_keys:
        if isinstance(value.get(key), str) and value[key].strip():
            clean[key] = value[key].strip()[:120]
    for key in list_keys:
        if isinstance(value.get(key), list):
            clean[key] = [str(item).strip()[:80] for item in value[key][:20] if str(item).strip()]
    for key in boolean_keys:
        if isinstance(value.get(key), bool):
            clean[key] = value[key]
    for key in numeric_keys:
        try:
            number = float(value[key])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= number <= 1_000_000_000:
            clean[key] = int(number) if number.is_integer() else number
    preferences = value.get("preferences")
    if isinstance(preferences, dict):
        clean["preferences"] = {str(key)[:40]: float(weight) for key, weight in list(preferences.items())[:20] if isinstance(weight, (int, float)) and float(weight) >= 0}
    return clean


def _json_object(text: str) -> dict:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()
    try:
        value = json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        value = json.loads(raw[start:end + 1]) if start >= 0 < end else {}
    return value if isinstance(value, dict) else {}


def parse_intent(text: str) -> tuple[dict, str]:
    """Parse controlled intent with DeepSeek; deterministic rules are always available."""
    prompt = (
        "只输出JSON对象。提取采购找厂条件，允许字段：" + ",".join(sorted(INTENT_KEYS)) +
        "。明确限制写字段；优先/最好/尽量写入preferences对象。不得输出SQL、企业事实或候选结果。"
    )
    providers: list[tuple[str, Callable[[], str]]] = []
    if (os.getenv("DEEPSEEK_API_KEY") or "").strip() and os.getenv("CHAINXIAOYI_CLOUD_ENABLED", "").lower() in {"1", "true", "yes", "on"}:
        providers.append(("deepseek", lambda: str(create_deepseek_chat_model_from_env().invoke([SystemMessage(content=prompt), HumanMessage(content=text[:2000])]).content)))
    if os.getenv("CHAINXIAOYI_LOCAL_ENABLED", "").lower() in {"1", "true", "yes", "on"} and (os.getenv("CHAINXIAOYI_LOCAL_MODEL") or os.getenv("BIZMIND_OLLAMA_MODEL") or "").strip():
        providers.append(("local", lambda: invoke_ollama(prompt, text[:2000])))
    for provider, invoke in providers:
        try:
            parsed = _json_object(invoke())
            clean = _normalize_intent({key: value for key, value in parsed.items() if key in INTENT_KEYS})
            if not clean.get("product"):
                clean["product"] = parse_procurement_intent(text).get("product")
            clean.update({"raw_text": text[:500], "confidence": provider})
            return clean, provider
        except Exception:
            continue
    return parse_procurement_intent(text), "rules"


def _deterministic_reason(row: dict) -> str:
    reasons = [str(value) for value in (row.get("reasons") or []) if value]
    return "、".join(reasons[:3]) + "，综合九维数据库评分推荐。" if reasons else "基于数据库九维能力与当前需求的综合评分推荐。"


def explain_matches(intent: dict, rows: list[dict]) -> tuple[dict[int, str], str]:
    """Generate grounded prose only. IDs, order and all scores remain algorithm-owned."""
    fallback = {int(row["id"]): _deterministic_reason(row) for row in rows}
    if not rows:
        return fallback, "rules"
    facts = [{
        "id": row.get("id"), "name": row.get("name"), "score": row.get("score"),
        "reasons": row.get("reasons") or [], "dimensions": row.get("dimensions") or {},
        "province": row.get("province"), "city": row.get("city"),
    } for row in rows[:10]]
    system_prompt = "只输出JSON对象，键为候选企业ID，值为{\"reason\":\"不超过80字\",\"evidence_fields\":[\"reasons\",\"dimensions\"]}。evidence_fields只能取name、score、reasons、dimensions、province、city；只能引用输入事实，不得新增事实、修改分数或排序。"
    user_prompt = json.dumps({"intent": intent, "candidates": facts}, ensure_ascii=False)
    providers: list[tuple[str, Callable[[], str]]] = []
    if (os.getenv("DEEPSEEK_API_KEY") or "").strip() and os.getenv("CHAINXIAOYI_CLOUD_ENABLED", "").lower() in {"1", "true", "yes", "on"}:
        providers.append(("deepseek", lambda: str(create_deepseek_chat_model_from_env().invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]).content)))
    if os.getenv("CHAINXIAOYI_LOCAL_ENABLED", "").lower() in {"1", "true", "yes", "on"} and (os.getenv("CHAINXIAOYI_LOCAL_MODEL") or os.getenv("BIZMIND_OLLAMA_MODEL") or "").strip():
        providers.append(("local", lambda: invoke_ollama(system_prompt, user_prompt)))
    for provider, invoke in providers:
        try:
            parsed = _json_object(invoke())
            allowed = set(fallback)
            allowed_fields = {"name", "score", "reasons", "dimensions", "province", "city"}
            reasons: dict[int, str] = {}
            for key, value in parsed.items():
                if not str(key).isdigit() or int(key) not in allowed or not isinstance(value, dict):
                    continue
                reason = value.get("reason")
                fields = value.get("evidence_fields")
                if isinstance(reason, str) and reason.strip() and len(reason) <= 80 and isinstance(fields, list) and fields and all(field in allowed_fields for field in fields):
                    reasons[int(key)] = reason.strip()
            if reasons:
                return {**fallback, **reasons}, provider
        except Exception:
            continue
    return fallback, "rules"


def _best_database_product(text: str, parsed_product: str) -> str:
    from app.models import Product
    products = Product.query.with_entities(Product.name, Product.category).all()
    normalized = (parsed_product or "").strip()
    text_lower = text.lower()
    direct_hits = [name for name, category in products if normalized and normalized.lower() in f"{name or ''} {category or ''}".lower()]
    if len(direct_hits) >= 2:
        return normalized
    exact = [
        name for name, _category in products
        if name and (name.lower() == normalized.lower() or (len(normalized) >= 4 and name.lower() in text_lower))
    ]
    if exact:
        return max(exact, key=len)
    # Natural-language modifiers such as "工业/高精度/供应商" should not block
    # recall of the database's canonical product name or category.
    candidates: list[tuple[int, str]] = []
    matched_tokens: list[str] = []
    for name, category in products:
        haystack = f"{name or ''} {category or ''}".lower()
        if normalized and (normalized.lower() in haystack or haystack in normalized.lower()):
            candidates.append((len(name or ''), name))
            continue
        raw_tokens = set(__import__('re').findall(r"[\u4e00-\u9fff]{2,}", normalized))
        raw_tokens.update(normalized[index:index + 2] for index in range(max(0, len(normalized) - 1)))
        raw_tokens.difference_update({"工业", "精密", "高端", "制造", "生产", "采购", "华东", "华南", "华北", "华中", "西南", "西北", "东北"})
        for token in raw_tokens:
            if token in haystack:
                matched_tokens.append(token)
                break
    # Prefer the shortest shared token for broad category requests (e.g. 电机)
    # so the matcher recalls every compatible database product, not one arbitrary SKU.
    if matched_tokens:
        return min(matched_tokens, key=len)
    return max(candidates, key=lambda item: item[0])[1] if candidates else normalized


def _match(intent: dict, owner_id: int | None) -> tuple[dict, str]:
    product = _best_database_product(str(intent.get("raw_text") or ""), str(intent.get("product") or ""))
    filters = {
        "region": intent.get("region"), "min_credit": intent.get("min_credit"),
        "min_capacity": intent.get("min_capacity"), "max_distance": intent.get("max_distance"),
        "min_registered_capital": intent.get("min_registered_capital"),
        "green_only": intent.get("is_green_factory") is True,
        "export_only": intent.get("is_export") is True,
        "little_giant_only": intent.get("is_little_giant") is True,
        "certifications": intent.get("certifications") or [],
    }
    try:
        quantity = int(float(intent.get("quantity") or 100))
    except (TypeError, ValueError):
        quantity = 100
    custom_weights = dict(DEFAULT_WEIGHTS)
    preferences = intent.get("preferences") if isinstance(intent.get("preferences"), dict) else {}
    for key, multiplier in preferences.items():
        if key in custom_weights and isinstance(multiplier, (int, float)):
            custom_weights[key] *= max(0.1, min(float(multiplier), 5.0))
    total_weight = sum(custom_weights.values()) or 1.0
    custom_weights = {key: value / total_weight for key, value in custom_weights.items()}
    rows = match_suppliers(product, demand_quantity=quantity, demand_ent_id=owner_id, filters=filters, custom_weights=custom_weights)
    reason_map, provider = explain_matches(intent, rows)
    sanitized = []
    for row in rows:
        dimensions = row.get("dimensions") or {}
        sanitized.append({
            "id": int(row["id"]), "name": str(row.get("name") or ""),
            "province": str(row.get("province") or ""), "city": str(row.get("city") or ""),
            "business_scope": str(row.get("business_scope") or "数据未公开"),
            "score": round(float(row.get("score") or 0), 2),
            "confidence_index": round(float(row.get("confidence_index") or row.get("score") or 0), 2),
            "dimensions": dimensions, "trusted_labels": list(row.get("quality_label_types") or []),
            "reason": reason_map.get(int(row["id"]), _deterministic_reason(row)),
            "data_updated_at": row.get("data_updated_at"),
            "degraded": provider != "deepseek",
        })
    return {"total": len(sanitized), "results": sanitized, "degraded": provider != "deepseek", "explanation_provider": provider}, provider


class ChainXiaoYiOrchestrator:
    """Single entry point for all assistant actions.

    Model providers are intentionally a later seam. Rule execution is useful,
    testable, and truthful while DeepSeek/local models are not configured.
    """

    @staticmethod
    def create_session(owner_id: int | None, surface: str = "public") -> ChainXiaoYiSession:
        raw_token = ChainXiaoYiSession.issue_token()
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session = ChainXiaoYiSession(owner_id=owner_id, access_token=token_hash, surface=surface, anonymous_expires_at=datetime.utcnow() + timedelta(hours=24) if owner_id is None else None)
        session._raw_access_token = raw_token
        db.session.add(session)
        db.session.commit()
        return session

    @staticmethod
    def session_allowed(session: ChainXiaoYiSession, owner_id: int | None, token: str | None) -> bool:
        if owner_id is not None and session.owner_id == owner_id:
            return True
        if session.owner_id is None and session.anonymous_expires_at and session.anonymous_expires_at < datetime.utcnow():
            return False
        return bool(token and hashlib.sha256(token.encode("utf-8")).hexdigest() == session.access_token and session.owner_id is None)

    @staticmethod
    def handle_message(session: ChainXiaoYiSession, content: str) -> dict:
        started = time.monotonic()
        text = (content or "").strip()
        if not text:
            raise ValueError("消息不能为空")
        if len(text) > 2000:
            raise ValueError("消息不能超过 2000 个字符")
        user_message = ChainXiaoYiMessage(session_id=session.id, role="user", content=text)
        db.session.add(user_message)
        incoming, intent_provider = parse_intent(text)
        intent = merge_procurement_intent(session.context, incoming, text)
        session.context = intent
        if session.title == "新的链小易会话" and intent.get("product"):
            session.title = f"找{str(intent['product'])[:140]}"
        status = get_model_status()
        match_result, explanation_provider = _match(intent, session.owner_id)
        task_type = "demand_intake" if any(word in text for word in ("找", "采购", "需要", "工厂", "供应商", "报价")) else "general_assistant"
        task = ChainXiaoYiTask(
            session_id=session.id,
            task_type=task_type,
            status="succeeded",
            requires_approval=False,
            input_json={"message": text},
            output_json={"intent": intent, "provider": intent_provider, "match_result": match_result},
        )
        db.session.add(task)
        db.session.flush()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        active_provider = "deepseek" if "deepseek" in {intent_provider, explanation_provider} else "local" if "local" in {intent_provider, explanation_provider} else "rules"
        db.session.add(ChainXiaoYiRun(task_id=task.id, provider=active_provider, skill=task_type, latency_ms=elapsed_ms, metadata_json={"intent_provider": intent_provider, "explanation_provider": explanation_provider}))
        count = match_result["total"]
        reply = f"已按数据库九维算法找到 {count} 家候选工厂。" if count else "暂未找到满足当前条件的工厂，可以放宽地区、资质或产能条件后再试。"
        db.session.add(ChainXiaoYiMessage(session_id=session.id, role="assistant", content=reply, metadata_json={"task_id": task.id, "intent": intent, "model_status": status.to_dict()}))
        db.session.add(ChainXiaoYiEvent(session_id=session.id, event_type="message_processed", payload={"task_id": task.id, "provider": status.active_provider}))
        session.updated_at = datetime.utcnow()
        db.session.commit()
        model_status = status.to_dict()
        model_status.update({"active_provider": active_provider, "is_configured": active_provider != "rules", "message": "DeepSeek 已完成本轮意图或解释" if active_provider == "deepseek" else "本地 Qwen 已完成本轮意图或解释" if active_provider == "local" else "本轮使用确定性规则与数据库匹配"})
        return {"reply": reply, "intent": intent, "task": task, "model_status": model_status, "match_result": match_result, "needs_clarification": not bool(intent.get("product")), "suggestions": ["限定地区", "补充交期", "说明资质要求"]}

    @staticmethod
    def create_inquiry_draft(session: ChainXiaoYiSession, intent: dict, owner_id: int) -> Inquiry:
        owner = Enterprise.query.filter(Enterprise.id == owner_id, Enterprise.role == "enterprise").first()
        if not owner:
            raise ValueError("只有企业账号可以创建采购需求草稿")
        product_name = str(intent.get("product") or "待补充产品")[:100]
        inquiry = Inquiry(
            poster_id=owner.id,
            buyer_id=owner.id,
            direction="demand",
            product_name=product_name,
            quantity=int(intent.get("quantity") or 0) or None,
            unit=str(intent.get("unit") or "件")[:10],
            description=str(intent.get("raw_text") or "")[:2000],
            content="链小易生成的采购需求草稿，待企业确认后发送。",
            status="draft",
            match_context={"chain_xiaoyi_session_id": session.id, "intent": intent, "source": "chain_xiaoyi"},
        )
        db.session.add(inquiry)
        db.session.add(ChainXiaoYiEvent(session_id=session.id, event_type="inquiry_draft_created", actor_id=owner.id, payload={"product_name": product_name}))
        db.session.commit()
        return inquiry

    @staticmethod
    def preview_file(session: ChainXiaoYiSession, filename: str, content_type: str, content: bytes) -> ChainXiaoYiFileImport:
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("文件大小不能超过 10MB")
        digest = hashlib.sha256(content).hexdigest()
        preview = preview_tabular_file(filename, content)
        item = ChainXiaoYiFileImport(session_id=session.id, filename=filename[:255], content_type=content_type[:120], sha256=digest, size_bytes=len(content), detected_kind=preview.get("kind"), preview_json=preview, errors_json=preview.get("errors", []), status="preview")
        db.session.add(item)
        db.session.add(ChainXiaoYiEvent(session_id=session.id, event_type="file_previewed", payload={"filename": filename[:255], "sha256": digest, "kind": preview.get("kind")}))
        db.session.commit()
        return item
