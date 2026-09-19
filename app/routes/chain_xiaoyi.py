"""Chain XiaoYi API: secure conversational factory-finding sessions."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
from io import BytesIO
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user
from openpyxl import Workbook

from app import db
from app.models import Enterprise
from app.models_chain_xiaoyi import ChainXiaoYiApproval, ChainXiaoYiCandidateSnapshot, ChainXiaoYiEvent, ChainXiaoYiFileImport, ChainXiaoYiGuestTrial, ChainXiaoYiMessage, ChainXiaoYiOutboundRecord, ChainXiaoYiRun, ChainXiaoYiSession, ChainXiaoYiTask
from app.services.chain_xiaoyi import ChainXiaoYiOrchestrator
from app.services.chain_xiaoyi.model_router import get_model_status
from app.services.material_security import (
    InvalidMaterial,
    MaterialInfected,
    MaterialScanUnavailable,
    scan_material,
)
from app.services.material_storage import MaterialStorageUnavailable, store_material
from app.services.production_readiness import build_readiness_report
from app.services.rfq_delivery_callbacks import DeliveryCallbackError, apply_delivery_event, normalize_provider
from app.services.rfq_quote_callbacks import QuoteCallbackError, apply_quote_event, normalize_quote_provider
from app.services.email_quote_intake import EmailQuoteInboundError, normalize_email_quote
from app.services.fulfillment_event_callbacks import FulfillmentEventError, apply_fulfillment_event, normalize_fulfillment_provider
from app.authz import role_required, user_effective_role

chain_xiaoyi_bp = Blueprint("chain_xiaoyi", __name__)
GUEST_COOKIE = "chain_xiaoyi_guest"
_AUDIT_REDACTED_KEYS = {"phone", "contact", "email", "address", "api_key", "token", "secret", "password", "access_token"}


def _redact_audit(value):
    """Defence-in-depth redaction for persisted metadata returned by audit APIs."""
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key).lower() in _AUDIT_REDACTED_KEYS else _redact_audit(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_audit(item) for item in value]
    return value


@chain_xiaoyi_bp.get("/api/admin/production-readiness")
@role_required("admin")
def production_readiness():
    """Return a redacted production readiness report for administrators."""
    return jsonify({"success": True, "data": build_readiness_report()})


@chain_xiaoyi_bp.get("/api/data-evidence/<string:entity_type>/<int:entity_id>")
def data_evidence(entity_type: str, entity_id: int):
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看数据证据", "code": "login_required"}), 401
    if entity_type != "enterprise":
        return jsonify({"error": "暂不支持该实体类型"}), 404
    enterprise = Enterprise.query.get(entity_id)
    if not enterprise:
        return jsonify({"error": "企业不存在"}), 404
    extras = dict(enterprise.extras or {})
    trust = extras.get("trust_profile") if isinstance(extras.get("trust_profile"), dict) else {}
    sources = []
    for raw in trust.get("sources") or []:
        if not isinstance(raw, dict):
            continue
        sources.append({key: _redact_audit(value) for key, value in raw.items() if str(key).lower() not in _AUDIT_REDACTED_KEYS})
    raw_fields = extras.get("data_evidence") if isinstance(extras.get("data_evidence"), dict) else {}
    fields = {key: _redact_audit(value) for key, value in raw_fields.items() if str(key).lower() not in _AUDIT_REDACTED_KEYS}
    updated_at = enterprise.last_data_update or enterprise.biz_data_updated_at
    return jsonify({
        "success": True,
        "entity": {"type": "enterprise", "id": enterprise.id, "name": enterprise.name},
        "claim_status": trust.get("claim_status", "unclaimed"),
        "contact_authorized": trust.get("contact_authorized") is True,
        "is_demo": bool(extras.get("is_demo")),
        "updated_at": updated_at.isoformat() if updated_at else None,
        "sources": sources,
        "fields": fields,
        "uncertain_fields": list(extras.get("unverified_fields") or []),
    })


def _enterprise_trust_profile(enterprise: Enterprise) -> tuple[dict, dict]:
    """Return mutable enterprise extras and trust metadata for claim APIs."""
    extras = dict(enterprise.extras or {}) if isinstance(enterprise.extras, dict) else {}
    trust = dict(extras.get("trust_profile") or {}) if isinstance(extras.get("trust_profile"), dict) else {}
    sources = trust.get("sources") if isinstance(trust.get("sources"), list) else []
    trust["sources"] = [dict(row) for row in sources if isinstance(row, dict)][-20:]
    return extras, trust


def _claim_response(enterprise: Enterprise, *, idempotent: bool = False) -> dict:
    extras, trust = _enterprise_trust_profile(enterprise)
    channels = extras.get("communication_authorizations")
    if not isinstance(channels, dict):
        channels = trust.get("communication_authorizations") if isinstance(trust.get("communication_authorizations"), dict) else {}
    return {
        "success": True,
        "idempotent": idempotent,
        "enterprise": {"id": enterprise.id, "name": enterprise.name},
        "claim_status": trust.get("claim_status", "unclaimed"),
        "contact_authorized": trust.get("contact_authorized") is True,
        "channels": sorted(str(key) for key, value in channels.items() if value is True),
        "authorization": trust.get("authorization") or "none",
    }


@chain_xiaoyi_bp.post("/api/enterprises/claim")
def claim_enterprise_directory_record():
    """Let an authenticated enterprise claim its public directory record.

    Claiming never grants contact permission.  A second, explicit
    ``contact-authorization`` request is required before RFQ delivery can use
    any contact channel.  Administrators may repair/claim a record on behalf
    of an enterprise, while ordinary accounts can only claim their own row.
    """
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "请登录后认领企业档案", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    raw_id = data.get("enterprise_id", current_user.id)
    try:
        enterprise_id = int(raw_id)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "enterprise_id 必须是有效数字"}), 400
    enterprise = Enterprise.query.filter_by(id=enterprise_id, role="enterprise").first()
    if not enterprise:
        return jsonify({"success": False, "error": "企业档案不存在"}), 404
    is_admin = user_effective_role(current_user) == "admin"
    if not is_admin and enterprise.id != int(current_user.id):
        return jsonify({"success": False, "error": "只能认领当前登录企业档案"}), 403

    extras, trust = _enterprise_trust_profile(enterprise)
    existing_claimant = trust.get("claimed_by")
    if trust.get("claim_status") == "claimed":
        try:
            same_claimant = existing_claimant in (None, int(current_user.id))
        except (TypeError, ValueError):
            same_claimant = False
        if not same_claimant:
            return jsonify({"success": False, "error": "企业档案已被其他主体认领", "code": "claim_conflict"}), 409
        return jsonify(_claim_response(enterprise, idempotent=True)), 200

    now = datetime.utcnow().isoformat()
    trust.update({
        "claim_status": "claimed",
        "claimed_by": int(current_user.id),
        "claimed_at": now,
        "contact_authorized": False,
        "authorization": "claim_only",
        "communication_authorizations": {},
    })
    trust["sources"].append({
        "name": "企业自主认领",
        "source_type": "enterprise_claim",
        "collected_at": now,
        "updated_at": now,
        "is_mock": False,
        "authorization": "claim_only",
    })
    extras["trust_profile"] = trust
    extras["communication_authorizations"] = {}
    enterprise.extras = extras
    db.session.add(ChainXiaoYiEvent(
        event_type="enterprise_claimed",
        actor_id=int(current_user.id),
        payload={"enterprise_id": enterprise.id, "claim_status": "claimed"},
    ))
    db.session.commit()
    return jsonify(_claim_response(enterprise)), 200


@chain_xiaoyi_bp.post("/api/enterprises/<int:enterprise_id>/contact-authorization")
def update_enterprise_contact_authorization(enterprise_id: int):
    """Grant or revoke explicit RFQ contact consent for a claimed enterprise."""
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "请登录后管理触达授权", "code": "login_required"}), 401
    enterprise = Enterprise.query.filter_by(id=enterprise_id, role="enterprise").first()
    if not enterprise:
        return jsonify({"success": False, "error": "企业档案不存在"}), 404
    is_admin = user_effective_role(current_user) == "admin"
    if not is_admin and enterprise.id != int(current_user.id):
        return jsonify({"success": False, "error": "只能管理当前登录企业的触达授权"}), 403
    data = request.get_json(silent=True) or {}
    authorized = data.get("authorized")
    if not isinstance(authorized, bool):
        return jsonify({"success": False, "error": "authorized 必须是布尔值"}), 400
    requested_channels = data.get("channels")
    if requested_channels is None:
        channels = ["site"] if authorized else []
    elif not isinstance(requested_channels, list):
        return jsonify({"success": False, "error": "channels 必须是数组"}), 400
    else:
        allowed_channels = {"site", "email", "wechat", "work_wechat"}
        channels = list(dict.fromkeys(str(item).strip().lower() for item in requested_channels if str(item).strip()))
        invalid = [item for item in channels if item not in allowed_channels]
        if invalid:
            return jsonify({"success": False, "error": "包含不支持的触达渠道", "invalid_channels": invalid}), 400
        if not authorized:
            channels = []

    extras, trust = _enterprise_trust_profile(enterprise)
    if trust.get("claim_status") != "claimed":
        return jsonify({"success": False, "error": "请先完成企业档案认领", "code": "claim_required"}), 409
    now = datetime.utcnow().isoformat()
    channel_map = {channel: True for channel in channels}
    trust["contact_authorized"] = authorized
    trust["authorization"] = "contact_channels" if authorized else "revoked"
    trust["communication_authorizations"] = channel_map
    trust["authorization_updated_at"] = now
    trust["authorization_actor_id"] = int(current_user.id)
    trust["sources"].append({
        "name": "企业触达授权" if authorized else "企业撤销触达授权",
        "source_type": "enterprise_contact_authorization",
        "collected_at": now,
        "updated_at": now,
        "is_mock": False,
        "authorization": ",".join(channels) if channels else "revoked",
    })
    extras["trust_profile"] = trust
    # The delivery adapter reads this top-level map so channel permissions are
    # enforced independently of the global consent flag.
    extras["communication_authorizations"] = channel_map
    enterprise.extras = extras
    db.session.add(ChainXiaoYiEvent(
        event_type="enterprise_contact_authorization_changed",
        actor_id=int(current_user.id),
        payload={"enterprise_id": enterprise.id, "authorized": authorized, "channels": channels},
    ))
    db.session.commit()
    return jsonify(_claim_response(enterprise)), 200


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/delivery-callback/<string:provider>")
def delivery_callback(provider: str):
    """Accept a signed transport-status callback from an RFQ provider.

    This endpoint never accepts credentials, quote values, or arbitrary
    business actions. It only advances an existing outbound record's delivery
    state and is safe to expose without a user session.
    """
    try:
        provider = normalize_provider(provider)
    except DeliveryCallbackError as exc:
        return jsonify({"success": False, "error": str(exc)}), exc.status_code

    raw = request.get_data(cache=True) or b""
    if len(raw) > 64 * 1024:
        return jsonify({"success": False, "error": "payload_too_large"}), 413
    secret = str(current_app.config.get("RFQ_DELIVERY_CALLBACK_SECRET") or os.getenv("RFQ_DELIVERY_CALLBACK_SECRET") or "").strip()
    if not secret:
        return jsonify({"success": False, "error": "delivery_callback_unavailable"}), 503
    provided = str(request.headers.get("X-Lianyipei-Signature") or "").strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not provided or not hmac.compare_digest(expected, provided):
        return jsonify({"success": False, "error": "invalid_callback_signature"}), 403

    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"success": False, "error": "invalid_json"}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "callback_body_must_be_object"}), 400

    from app.services.callback_receipts import callback_event_key, claim_callback, complete_callback, release_callback

    event_key = callback_event_key(payload, raw)
    receipt, claimed = claim_callback(f"rfq_delivery:{provider}", event_key)
    if not claimed:
        if receipt.status == "completed" and receipt.response_body:
            try:
                cached = json.loads(receipt.response_body)
            except (TypeError, json.JSONDecodeError):
                cached = {"success": True, "status": "processed"}
            cached["idempotent"] = True
            return jsonify(cached), 200
        return jsonify({"success": True, "status": "processing", "idempotent": True}), 202

    try:
        result = apply_delivery_event(provider, payload)
    except DeliveryCallbackError as exc:
        release_callback(receipt)
        return jsonify({"success": False, "error": str(exc)}), exc.status_code
    except Exception:
        release_callback(receipt)
        current_app.logger.exception("RFQ delivery callback processing failed")
        return jsonify({"success": False, "error": "delivery_callback_failed"}), 500

    response_body = {"success": True, **result}
    complete_callback(receipt, json.dumps(response_body, ensure_ascii=False, separators=(",", ":")))
    return jsonify(response_body), 200


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/quote-callback/<string:provider>")
def quote_callback(provider: str):
    """Accept a signed, provider-normalized supplier quote response.

    Transport adapters may parse email/WeCom messages outside this process,
    but only this HMAC-protected endpoint can persist a commercial quote.  The
    callback secret is deliberately separate from delivery-status secrets.
    """
    try:
        provider = normalize_quote_provider(provider)
    except QuoteCallbackError as exc:
        return jsonify({"success": False, "error": str(exc)}), exc.status_code

    raw = request.get_data(cache=True) or b""
    if len(raw) > 64 * 1024:
        return jsonify({"success": False, "error": "payload_too_large"}), 413
    secret = str(
        current_app.config.get("RFQ_QUOTE_CALLBACK_SECRET")
        or os.getenv("RFQ_QUOTE_CALLBACK_SECRET")
        or ""
    ).strip()
    if not secret:
        return jsonify({"success": False, "error": "quote_callback_unavailable"}), 503
    provided = str(request.headers.get("X-Lianyipei-Signature") or "").strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not provided or not hmac.compare_digest(expected, provided):
        return jsonify({"success": False, "error": "invalid_callback_signature"}), 403
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"success": False, "error": "invalid_json"}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "callback_body_must_be_object"}), 400

    from app.services.callback_receipts import callback_event_key, claim_callback, complete_callback, release_callback

    event_key = callback_event_key(payload, raw)
    receipt, claimed = claim_callback(f"rfq_quote:{provider}", event_key)
    if not claimed:
        if receipt.status == "completed" and receipt.response_body:
            try:
                cached = json.loads(receipt.response_body)
            except (TypeError, json.JSONDecodeError):
                cached = {"success": True, "status": "processed"}
            cached["idempotent"] = True
            return jsonify(cached), 200
        return jsonify({"success": True, "status": "processing", "idempotent": True}), 202

    try:
        result = apply_quote_event(provider, payload)
    except QuoteCallbackError as exc:
        release_callback(receipt)
        return jsonify({"success": False, "error": str(exc)}), exc.status_code
    except Exception:
        release_callback(receipt)
        current_app.logger.exception("RFQ quote callback processing failed")
        return jsonify({"success": False, "error": "quote_callback_failed"}), 500

    response_body = {"success": True, **result}
    complete_callback(receipt, json.dumps(response_body, ensure_ascii=False, separators=(",", ":")))
    return jsonify(response_body), 200


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/email-quote-inbound")
def email_quote_inbound():
    """Receive a signed, normalized inbound supplier email.

    An email gateway may parse MIME/attachments outside the app and POST only
    ``event_id``, ``from_email`` and plain text here.  The endpoint performs
    sender authorization and deterministic quote extraction, then reuses the
    same preview/confirmation semantics as other quote callbacks.
    """
    raw = request.get_data(cache=True) or b""
    if len(raw) > 128 * 1024:
        return jsonify({"success": False, "error": "payload_too_large"}), 413
    secret = str(
        current_app.config.get("RFQ_EMAIL_INBOUND_SECRET")
        or os.getenv("RFQ_EMAIL_INBOUND_SECRET")
        or ""
    ).strip()
    if not secret:
        return jsonify({"success": False, "error": "email_inbound_unavailable"}), 503
    provided = str(request.headers.get("X-Lianyipei-Signature") or "").strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not provided or not hmac.compare_digest(expected, provided):
        return jsonify({"success": False, "error": "invalid_callback_signature"}), 403
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"success": False, "error": "invalid_json"}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "callback_body_must_be_object"}), 400

    from app.services.callback_receipts import callback_event_key, claim_callback, complete_callback, release_callback

    event_key = callback_event_key(payload, raw)
    receipt, claimed = claim_callback("rfq_email_inbound", event_key)
    if not claimed:
        if receipt.status == "completed" and receipt.response_body:
            try:
                cached = json.loads(receipt.response_body)
            except (TypeError, json.JSONDecodeError):
                cached = {"success": True, "status": "processed"}
            cached["idempotent"] = True
            return jsonify(cached), 200
        return jsonify({"success": True, "status": "processing", "idempotent": True}), 202

    try:
        normalized = normalize_email_quote(payload)
        if not normalized["confirmed"]:
            response_body = {
                "success": True,
                "quote_id": normalized["quote_id"],
                "product_name": normalized["product_name"],
                "reply_price": normalized["reply_price"],
                "reply_details": normalized["reply_details"],
                "confirmed": False,
                "needs_confirmation": True,
                "provider": "email",
            }
        else:
            result = apply_quote_event("email", normalized)
            response_body = {"success": True, **result}
    except EmailQuoteInboundError as exc:
        release_callback(receipt)
        return jsonify({"success": False, "error": str(exc)}), exc.status_code
    except QuoteCallbackError as exc:
        release_callback(receipt)
        return jsonify({"success": False, "error": str(exc)}), exc.status_code
    except Exception:
        release_callback(receipt)
        current_app.logger.exception("Inbound email quote processing failed")
        return jsonify({"success": False, "error": "email_quote_inbound_failed"}), 500

    complete_callback(receipt, json.dumps(response_body, ensure_ascii=False, separators=(",", ":")))
    return jsonify(response_body), 200


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/fulfillment-event-callback/<string:provider>")
def fulfillment_event_callback(provider: str):
    """Apply signed ERP/payment/logistics lifecycle events to an order.

    The callback records provider facts and advances only monotonic order
    states. It never sets the independent contract/payment confirmation flags.
    """
    try:
        provider = normalize_fulfillment_provider(provider)
    except FulfillmentEventError as exc:
        return jsonify({"success": False, "error": str(exc)}), exc.status_code
    raw = request.get_data(cache=True) or b""
    if len(raw) > 64 * 1024:
        return jsonify({"success": False, "error": "payload_too_large"}), 413
    secret = str(
        current_app.config.get("FULFILLMENT_CALLBACK_SECRET")
        or os.getenv("FULFILLMENT_CALLBACK_SECRET")
        or ""
    ).strip()
    if not secret:
        return jsonify({"success": False, "error": "fulfillment_callback_unavailable"}), 503
    provided = str(request.headers.get("X-Lianyipei-Signature") or "").strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not provided or not hmac.compare_digest(expected, provided):
        return jsonify({"success": False, "error": "invalid_callback_signature"}), 403
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"success": False, "error": "invalid_json"}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "callback_body_must_be_object"}), 400

    from app.services.callback_receipts import callback_event_key, claim_callback, complete_callback, release_callback

    receipt, claimed = claim_callback(f"fulfillment:{provider}", callback_event_key(payload, raw))
    if not claimed:
        if receipt.status == "completed" and receipt.response_body:
            try:
                cached = json.loads(receipt.response_body)
            except (TypeError, json.JSONDecodeError):
                cached = {"success": True, "status": "processed"}
            cached["idempotent"] = True
            return jsonify(cached), 200
        return jsonify({"success": True, "status": "processing", "idempotent": True}), 202
    try:
        result = apply_fulfillment_event(provider, payload)
    except FulfillmentEventError as exc:
        release_callback(receipt)
        return jsonify({"success": False, "error": str(exc)}), exc.status_code
    except Exception:
        release_callback(receipt)
        current_app.logger.exception("Fulfillment callback processing failed")
        return jsonify({"success": False, "error": "fulfillment_callback_failed"}), 500
    response_body = {"success": True, **result}
    complete_callback(receipt, json.dumps(response_body, ensure_ascii=False, separators=(",", ":")))
    return jsonify(response_body), 200


@chain_xiaoyi_bp.before_request
def verify_write_origin():
    """Reject explicit cross-site browser writes; SameSite cookies cover missing-Origin clients."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"} or current_app.testing:
        return None
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.host:
        return jsonify({"error": "请求来源校验失败"}), 403
    return None


def _owner_id() -> int | None:
    return int(current_user.id) if current_user.is_authenticated else None


def _session(session_id: int):
    item = ChainXiaoYiSession.query.get(session_id)
    token = request.cookies.get(GUEST_COOKIE) or request.headers.get("X-Chain-Xiaoyi-Token")
    if not item or not ChainXiaoYiOrchestrator.session_allowed(item, _owner_id(), token):
        return None
    return item


def _session_payload(item: ChainXiaoYiSession) -> dict:
    return {"id": item.id, "title": item.title, "surface": item.surface, "status": item.status, "intent": item.context or {}, "updated_at": item.updated_at.isoformat()}


def _ip_hash() -> str:
    # Trust Flask's remote_addr only; production proxy configuration must normalize it.
    raw_ip = request.remote_addr or "unknown"
    secret = str(current_app.config.get("SECRET_KEY") or os.getenv("SECRET_KEY") or "local-development")
    return hmac.new(secret.encode(), raw_ip.encode(), hashlib.sha256).hexdigest()


def _set_guest_cookie(response, token: str):
    response.set_cookie(GUEST_COOKIE, token, max_age=30 * 24 * 3600, httponly=True, secure=not current_app.testing, samesite="Lax", path="/")
    return response


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/sessions")
def list_sessions():
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看历史会话", "code": "login_required"}), 401
    items = ChainXiaoYiSession.query.filter_by(owner_id=int(current_user.id), status="active").order_by(ChainXiaoYiSession.updated_at.desc()).all()
    sessions = []
    for item in items:
        latest = item.tasks.order_by(ChainXiaoYiTask.created_at.desc()).first()
        snapshot = (latest.output_json or {}).get("match_result", {}) if latest else {}
        payload = _session_payload(item)
        payload["match_count"] = int(snapshot.get("total") or 0)
        sessions.append(payload)
    return jsonify({"success": True, "sessions": sessions})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions")
def create_session():
    data = request.get_json(silent=True) or {}
    surface = str(data.get("surface") or "public")[:40]
    raw_cookie = request.cookies.get(GUEST_COOKIE) if not current_user.is_authenticated else None
    if raw_cookie:
        token_hash = hashlib.sha256(raw_cookie.encode("utf-8")).hexdigest()
        existing = ChainXiaoYiSession.query.filter_by(access_token=token_hash, owner_id=None, status="active").first()
        if existing and (not existing.anonymous_expires_at or existing.anonymous_expires_at >= datetime.utcnow()):
            response = jsonify({"success": True, "session": _session_payload(existing), "model_status": get_model_status().to_dict()})
            _set_guest_cookie(response, raw_cookie)
            return response, 200
        prior_trial = ChainXiaoYiGuestTrial.query.filter_by(browser_token_hash=token_hash).first()
        if prior_trial and prior_trial.match_count >= 1 and prior_trial.expires_at >= datetime.utcnow():
            return jsonify({"error": "游客试用已使用，请登录后继续", "code": "login_required"}), 401
    item = ChainXiaoYiOrchestrator.create_session(_owner_id(), surface)
    response = jsonify({"success": True, "session": _session_payload(item), "model_status": get_model_status().to_dict()})
    if item.owner_id is None:
        raw_token = item._raw_access_token
        now = datetime.utcnow()
        db.session.add(ChainXiaoYiGuestTrial(browser_token_hash=item.access_token, ip_hmac_hash=_ip_hash(), expires_at=now + timedelta(days=30)))
        db.session.commit()
        _set_guest_cookie(response, raw_token)
    return response, 201


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/sessions/<int:session_id>")
def get_session(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    messages = item.messages.order_by(ChainXiaoYiMessage.created_at.asc()).all()
    latest = item.tasks.order_by(ChainXiaoYiTask.created_at.desc()).first()
    return jsonify({"success": True, "session": _session_payload(item), "intent": item.context or {}, "match_result": ((latest.output_json or {}).get("match_result") if latest else None), "messages": [{"id": message.id, "role": message.role, "content": message.content, "metadata": message.metadata_json or {}, "created_at": message.created_at.isoformat()} for message in messages]})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/messages")
def send_message(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    if current_user.is_authenticated:
        recent_count = ChainXiaoYiMessage.query.join(ChainXiaoYiSession).filter(
            ChainXiaoYiSession.owner_id == int(current_user.id),
            ChainXiaoYiMessage.role == "user",
            ChainXiaoYiMessage.created_at >= datetime.utcnow() - timedelta(minutes=1),
        ).count()
        if recent_count >= 5:
            return jsonify({"error": "请求过于频繁，请稍后再试", "code": "rate_limited"}), 429
    if not current_user.is_authenticated and item.messages.filter_by(role="user").count() >= 1:
        return jsonify({"error": "游客可完成一次匹配，请登录后继续追问", "code": "login_required"}), 401
    if not current_user.is_authenticated:
        trial = ChainXiaoYiGuestTrial.query.filter_by(browser_token_hash=item.access_token).first()
        now = datetime.utcnow()
        if trial:
            day_count = ChainXiaoYiGuestTrial.query.filter(ChainXiaoYiGuestTrial.ip_hmac_hash == trial.ip_hmac_hash, ChainXiaoYiGuestTrial.used_at >= now - timedelta(days=1)).count()
            if day_count >= 10:
                return jsonify({"error": "匿名匹配次数已达今日上限", "code": "rate_limited"}), 429
            if trial.minute_started_at < now - timedelta(minutes=1):
                trial.minute_started_at, trial.minute_count = now, 0
            if trial.minute_count >= 5:
                return jsonify({"error": "请求过于频繁，请稍后再试", "code": "rate_limited"}), 429
            trial.minute_count += 1
            trial.match_count += 1
            trial.used_at = now
    data = request.get_json(silent=True) or {}
    try:
        result = ChainXiaoYiOrchestrator.handle_message(item, str(data.get("content") or data.get("message") or ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        # Production deployments with CHAINXIAOYI_CLOUD_REQUIRED=true must
        # fail closed when DeepSeek is unavailable instead of presenting a
        # rules-only result as if the requested model had run.
        db.session.rollback()
        current_app.logger.warning("Chain XiaoYi model unavailable: %s", str(exc)[:200])
        return jsonify({"error": "智能模型暂时不可用，请稍后重试", "code": "model_unavailable"}), 503
    task = result["task"]
    return jsonify({"success": True, "reply": result["reply"], "intent": result["intent"], "needs_clarification": result["needs_clarification"], "suggestions": result["suggestions"], "model_status": result["model_status"], "match_result": result["match_result"], "workflow": result.get("workflow"), "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval}})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/claim")
def claim_session(session_id: int):
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后认领会话", "code": "login_required"}), 401
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或认领令牌无效"}), 404
    if item.owner_id is not None:
        return jsonify({"error": "该会话已被认领"}), 409
    item.owner_id = int(current_user.id)
    item.access_token = hashlib.sha256(ChainXiaoYiSession.issue_token().encode()).hexdigest()
    item.anonymous_expires_at = None
    db.session.commit()
    return jsonify({"success": True, "session": _session_payload(item)})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/archive")
def archive_session(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    if not current_user.is_authenticated or item.owner_id != int(current_user.id):
        return jsonify({"error": "请登录后归档会话", "code": "login_required"}), 401
    item.status = "archived"
    db.session.commit()
    return jsonify({"success": True, "session": _session_payload(item)})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/sessions/<int:session_id>/export.xlsx")
def export_session(session_id: int):
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后导出", "code": "login_required"}), 401
    item = _session(session_id)
    if not item or item.owner_id != int(current_user.id):
        return jsonify({"error": "会话不存在或无权访问"}), 404
    task = item.tasks.order_by(ChainXiaoYiTask.created_at.desc()).first()
    results = ((task.output_json or {}).get("match_result") or {}).get("results", []) if task else []
    book = Workbook()
    sheet = book.active
    sheet.title = "匹配结果"
    sheet.append(["企业名称", "省市", "经营范围", "综合算法分", "九维分数", "可信标签", "推荐理由", "数据更新时间", "数据新鲜度"])
    for row in results:
        dims = row.get("dimensions") or {}
        dim_text = "；".join(f"{key}:{value.get('score', '数据未公开') if isinstance(value, dict) else value}" for key, value in dims.items())
        freshness = row.get("data_freshness") if isinstance(row.get("data_freshness"), dict) else {}
        freshness_text = str(freshness.get("status") or "unknown")
        if freshness.get("age_days") is not None:
            freshness_text += f"（{freshness['age_days']}天）"
        sheet.append([row.get("name"), f"{row.get('province', '')}{row.get('city', '')}", row.get("business_scope") or "数据未公开", row.get("score"), dim_text, "、".join(row.get("trusted_labels") or []), row.get("reason"), row.get("data_updated_at") or "数据未公开", freshness_text])
    output = BytesIO()
    book.save(output)
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name=f"chain-xiaoyi-{item.id}.xlsx")


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/demand-draft")
def create_demand_draft(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后创建需求草稿"}), 401
    data = request.get_json(silent=True) or {}
    intent = data.get("intent") if isinstance(data.get("intent"), dict) else {}
    try:
        inquiry = ChainXiaoYiOrchestrator.create_inquiry_draft(item, intent, int(current_user.id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True, "inquiry": {"id": inquiry.id, "status": inquiry.status, "product_name": inquiry.product_name, "quantity": inquiry.quantity, "unit": inquiry.unit}}), 201


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/files")
def preview_file(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后上传采购材料", "code": "login_required"}), 401
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "请选择文件"}), 400
    try:
        filename = uploaded.filename.strip()
        allowed = {".csv", ".xlsx", ".pdf", ".docx"}
        suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix not in allowed:
            return jsonify({"error": "仅支持 CSV、XLSX、PDF 和 DOCX 文件", "code": "invalid_material"}), 400
        content = uploaded.read(10 * 1024 * 1024 + 1)
        security_scan = scan_material(filename, content)
        storage_key = store_material(
            content=content,
            sha256=security_scan["sha256"],
            owner_id=int(current_user.id),
            session_id=item.id,
        )
        result = ChainXiaoYiOrchestrator.preview_file(
            item,
            filename,
            uploaded.mimetype or "application/octet-stream",
            content,
            security_scan=security_scan,
            storage_key=storage_key,
        )
    except MaterialInfected as exc:
        return jsonify({"error": str(exc), "code": "material_infected"}), 422
    except MaterialScanUnavailable as exc:
        return jsonify({"error": str(exc), "code": "material_scan_unavailable"}), 503
    except MaterialStorageUnavailable as exc:
        return jsonify({"error": str(exc), "code": "material_storage_unavailable"}), 503
    except InvalidMaterial as exc:
        return jsonify({"error": str(exc), "code": "invalid_material"}), 400
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    draft = ChainXiaoYiOrchestrator.procurement_draft(result)
    result.preview_json = {**(result.preview_json or {}), "procurement_draft": draft}
    task = item.tasks.filter_by(task_type="procurement_intake").order_by(ChainXiaoYiTask.created_at.desc()).first()
    material_added = False
    if task is None:
        aggregate = ChainXiaoYiOrchestrator.merge_material_draft(None, draft, result)
        task = ChainXiaoYiTask(session_id=item.id, task_type="procurement_intake", status="needs_clarification" if aggregate.get("clarifying_questions") else "draft", requires_approval=False, input_json={"file_id": result.id, "file_ids": [result.id]}, output_json={"draft": aggregate})
        db.session.add(task)
        db.session.flush()
        material_added = True
    else:
        known_ids = list((task.input_json or {}).get("file_ids") or [])
        if not known_ids and (task.input_json or {}).get("file_id"):
            known_ids = [(task.input_json or {}).get("file_id")]
        aggregate = (task.output_json or {}).get("draft") or {}
        if result.id not in known_ids:
            aggregate = ChainXiaoYiOrchestrator.merge_material_draft(aggregate, draft, result)
            task.input_json = {**(task.input_json or {}), "file_ids": aggregate["file_ids"]}
            task.output_json = {**(task.output_json or {}), "draft": aggregate}
            task.status = "needs_clarification" if aggregate.get("clarifying_questions") else "draft"
            material_added = True
    if material_added:
        providers = aggregate.get("extraction_providers") or [draft.get("extraction_provider") or "rules"]
        provider = "deepseek" if "deepseek" in providers else "local" if "local" in providers else "rules"
        db.session.add(
            ChainXiaoYiRun(
                task_id=task.id,
                provider=provider,
                skill="material_extraction",
                status="succeeded",
                metadata_json={
                    "trace_schema": "chain_xiaoyi.run.v1",
                    "rules_version": "chain_xiaoyi.match.v2",
                    "model_version": get_model_status().cloud_model if provider == "deepseek" else "deterministic-rules",
                    "provider": provider,
                    "file_id": result.id,
                    "detected_kind": result.detected_kind,
                },
            )
        )
    result.status = "parsed" if not aggregate.get("clarifying_questions") else "needs_clarification"
    db.session.commit()
    return jsonify({"success": True, "file": {"id": result.id, "filename": result.filename, "sha256": result.sha256, "size_bytes": result.size_bytes, "status": result.status, "detected_kind": result.detected_kind, "retained": bool(result.storage_key), "scan_status": result.scan_status, "preview": result.preview_json, "errors": result.errors_json or []}, "draft": aggregate, "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval}})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/materials")
def upload_material_canonical():
    """Canonical material endpoint for API clients and external workspaces.

    The session-scoped route remains supported for the web UI.  API clients
    send ``session_id`` as a multipart field and receive the exact same
    evidenced draft response, so both surfaces share one parser and one audit
    trail.
    """
    raw_session_id = request.form.get("session_id") or request.args.get("session_id")
    try:
        session_id = int(raw_session_id)
    except (TypeError, ValueError):
        return jsonify({"error": "session_id 必须是有效数字"}), 400
    return preview_file(session_id)


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/materials/<int:material_id>")
def get_material(material_id: int):
    item = ChainXiaoYiFileImport.query.get(material_id)
    if not item or not _session(item.session_id):
        return jsonify({"error": "材料不存在或无权访问"}), 404
    session = ChainXiaoYiSession.query.get(item.session_id)
    task = session.tasks.filter_by(task_type="procurement_intake").order_by(ChainXiaoYiTask.created_at.desc()).first() if session else None
    return jsonify({
        "success": True,
        "material": {
            "id": item.id,
            "session_id": item.session_id,
            "filename": item.filename,
            "content_type": item.content_type,
            "sha256": item.sha256,
            "size_bytes": item.size_bytes,
            "status": item.status,
            "detected_kind": item.detected_kind,
            "scan_status": item.scan_status,
            "retained": bool(item.storage_key),
            "preview": item.preview_json or {},
            "errors": item.errors_json or [],
            "created_at": item.created_at.isoformat(),
        },
        "draft": ChainXiaoYiOrchestrator.procurement_draft(item),
        "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval} if task else None,
    })


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/procurement-tasks")
def create_procurement_task_canonical():
    """Create a durable procurement intake task without a form wizard.

    ``material_ids`` merges already parsed materials; ``fields`` is an
    optional small set of human/API corrections.  Both paths preserve the
    same evidence schema and stop in ``needs_clarification`` when required
    values are missing.
    """
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后创建采购任务", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "session_id 必须是有效数字"}), 400
    session = _session(session_id)
    if not session or session.owner_id != int(current_user.id):
        return jsonify({"error": "会话不存在或无权访问"}), 404
    fields = data.get("fields")
    if fields is not None and not isinstance(fields, dict):
        return jsonify({"error": "fields 必须是对象"}), 400

    draft: dict = {
        "fields": {}, "items": [], "file_ids": [], "conflicts": [],
        "missing_required": ["product", "quantity"],
        "clarifying_questions": ["请确认需要采购的产品名称", "请补充采购数量"],
        "schema_version": "procurement.v2",
    }
    material_ids = []
    raw_material_ids = data.get("material_ids") or []
    if not isinstance(raw_material_ids, list):
        return jsonify({"error": "material_ids 必须是数组"}), 400
    for raw_id in raw_material_ids[:20]:
        try:
            material_id = int(raw_id)
        except (TypeError, ValueError):
            return jsonify({"error": "material_ids 包含无效 ID"}), 400
        material = ChainXiaoYiFileImport.query.filter_by(id=material_id, session_id=session.id).first()
        if not material:
            return jsonify({"error": "材料不存在或不属于当前会话"}), 404
        draft = ChainXiaoYiOrchestrator.merge_material_draft(
            draft if draft.get("file_ids") else None,
            ChainXiaoYiOrchestrator.procurement_draft(material),
            material,
        )
        material_ids.append(material_id)

    # The upload endpoint already creates a material task.  Reusing it makes
    # the canonical resource safe for client retries and prevents one upload
    # from producing duplicate procurement workflows.
    existing_task = None
    if material_ids:
        for candidate in session.tasks.filter_by(task_type="procurement_intake").order_by(ChainXiaoYiTask.created_at.asc()).all():
            candidate_ids = set((candidate.input_json or {}).get("file_ids") or [])
            if set(material_ids).issubset(candidate_ids):
                existing_task = candidate
                break
    if existing_task is not None and fields is None:
        return jsonify({
            "success": True,
            "idempotent": True,
            "task": {"id": existing_task.id, "type": existing_task.task_type, "status": existing_task.status, "requires_approval": existing_task.requires_approval},
            "draft": (existing_task.output_json or {}).get("draft") or {},
        }), 200

    task = ChainXiaoYiTask(
        session_id=session.id,
        task_type="procurement_intake",
        status="needs_clarification" if draft.get("clarifying_questions") else "draft",
        requires_approval=False,
        input_json={"file_ids": material_ids},
        output_json={"draft": draft},
    )
    db.session.add(task)
    db.session.flush()
    if fields is not None:
        try:
            draft = ChainXiaoYiOrchestrator.update_procurement_fields(task, fields, int(current_user.id))
        except (PermissionError, ValueError) as exc:
            db.session.rollback()
            return jsonify({"error": str(exc)}), 400
    else:
        db.session.add(ChainXiaoYiEvent(session_id=session.id, event_type="procurement_task_created", actor_id=int(current_user.id), payload={"task_id": task.id, "file_ids": material_ids}))
        db.session.commit()
    return jsonify({
        "success": True,
        "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval},
        "draft": draft,
    }), 201


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/rfq-draft")
def create_rfq_draft(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后创建询价任务", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        task = ChainXiaoYiOrchestrator.create_rfq_draft(
            item,
            data.get("intent") if isinstance(data.get("intent"), dict) else {},
            data.get("supplier_ids") or [],
            str(data.get("message") or "")[:2000],
            int(current_user.id),
            data.get("channels") if isinstance(data.get("channels"), list) else None,
            data.get("quote_deadline_at") or data.get("deadline_at"),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True, "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval, "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None}, "preview": _rfq_preview(task)}), 201


def _rfq_preview(task: ChainXiaoYiTask) -> dict:
    """Build the buyer-facing approval card without exposing private contacts."""
    if not task or task.task_type != "rfq":
        return {}
    source = dict(task.input_json or {})
    snapshots = ChainXiaoYiCandidateSnapshot.query.filter_by(task_id=task.id).order_by(ChainXiaoYiCandidateSnapshot.id.asc()).all()
    suppliers = []
    for snapshot in snapshots:
        payload = dict(snapshot.payload or {})
        trust = payload.get("trust_profile") if isinstance(payload.get("trust_profile"), dict) else {}
        suppliers.append({
            "id": snapshot.supplier_id,
            "name": str(payload.get("name") or "")[:200],
            "province": str(payload.get("province") or "")[:40] or None,
            "city": str(payload.get("city") or "")[:40] or None,
            "data_updated_at": payload.get("data_updated_at"),
            "claim_status": trust.get("claim_status", "unclaimed"),
            "contact_authorized": trust.get("contact_authorized") is True,
            "authorization_scope": trust.get("authorization") or ("claimed_contact" if trust.get("contact_authorized") is True else "none"),
            "trusted_labels": [str(value)[:80] for value in (trust.get("trusted_labels") or [])[:10]],
        })
    intent = source.get("intent") if isinstance(source.get("intent"), dict) else {}
    disclosed = {key: value for key, value in intent.items() if key not in {"raw_text", "confidence"} and value not in (None, "", [])}
    return {
        "task_id": task.id,
        "status": task.status,
        "supplier_count": len(suppliers),
        "suppliers": suppliers,
        "content": str(source.get("message") or "")[:2000],
        "disclosed_fields": disclosed,
        "channels": list(source.get("channels") or []),
        "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None,
        "requires_approval": bool(task.requires_approval),
        "external_send": False,
    }


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>/rfq-preview")
def get_rfq_preview(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看询价预览", "code": "login_required"}), 401
    if task.task_type != "rfq":
        return jsonify({"error": "该任务不是询价任务"}), 409
    return jsonify({"success": True, "preview": _rfq_preview(task)})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks")
def list_tasks():
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看任务", "code": "login_required"}), 401
    query = ChainXiaoYiTask.query.join(ChainXiaoYiSession).filter(ChainXiaoYiSession.owner_id == int(current_user.id))
    requested_filter = str(request.args.get("filter") or "").strip()
    if requested_filter == "needs_action":
        query = query.filter(ChainXiaoYiTask.status.in_(["needs_clarification", "awaiting_approval", "approved", "queued", "running", "partial_failure", "sent", "timed_out", "fulfillment_exception"]))
    elif requested_filter:
        query = query.filter(ChainXiaoYiTask.status == requested_filter)
    limit = max(1, min(request.args.get("limit", 50, type=int), 100))
    tasks = query.order_by(ChainXiaoYiTask.updated_at.desc()).limit(limit).all()
    actions = {
        "needs_clarification": "resolve_fields",
        "awaiting_approval": "review_and_approve",
        "approved": "send_rfq",
        "queued": "processing",
        "running": "processing",
        "partial_failure": "retry_failed",
        "sent": "await_supplier_quotes",
        "timed_out": "review_no_response",
        "fulfillment_exception": "handle_fulfillment_exception",
        "fulfillment_in_progress": "monitor_fulfillment",
        "fulfillment_completed": "review_fulfillment",
        "completed": "review_quotes",
        "cancelled": "resume_task",
    }
    rows = []
    for task in tasks:
        intent = (task.input_json or {}).get("intent") or {}
        rows.append({
            "id": task.id,
            "session_id": task.session_id,
            "type": task.task_type,
            "status": task.status,
            "requires_approval": task.requires_approval,
            "product": intent.get("product"),
            "next_action": actions.get(task.status),
            "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        })
    return jsonify({"success": True, "tasks": rows, "total": len(rows), "filter": requested_filter or None})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/procurement-tasks/<int:task_id>")
@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>")
def get_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    return jsonify({"success": True, "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval, "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None, "input": task.input_json or {}, "output": task.output_json or {}, "error": task.error_message}})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>/audit")
def task_audit(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    session = _session(task.session_id) if task else None
    if not task or not session:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated or session.owner_id != int(current_user.id):
        return jsonify({"error": "请登录后查看任务审计", "code": "login_required"}), 401
    approvals = ChainXiaoYiApproval.query.filter_by(task_id=task.id).order_by(ChainXiaoYiApproval.created_at.asc()).all()
    runs = ChainXiaoYiRun.query.filter_by(task_id=task.id).order_by(ChainXiaoYiRun.created_at.asc()).all()
    candidates = ChainXiaoYiCandidateSnapshot.query.filter_by(task_id=task.id).order_by(ChainXiaoYiCandidateSnapshot.id.asc()).all()
    outbound = ChainXiaoYiOutboundRecord.query.filter_by(task_id=task.id).order_by(ChainXiaoYiOutboundRecord.id.asc()).all()
    events = [event for event in ChainXiaoYiEvent.query.filter_by(session_id=task.session_id).order_by(ChainXiaoYiEvent.created_at.asc()).all() if isinstance(event.payload, dict) and event.payload.get("task_id") == task.id]
    candidate_rows = []
    for row in candidates:
        payload = row.payload or {}
        trust = payload.get("trust_profile") if isinstance(payload.get("trust_profile"), dict) else {}
        candidate_rows.append({"supplier_id": row.supplier_id, "name": payload.get("name"), "province": payload.get("province"), "city": payload.get("city"), "data_updated_at": payload.get("data_updated_at"), "trust_profile": {"claim_status": trust.get("claim_status"), "contact_authorized": trust.get("contact_authorized") is True, "sources": _redact_audit(trust.get("sources") or [])}, "captured_at": row.created_at.isoformat()})
    return jsonify(_redact_audit({
        "success": True,
        "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval, "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None, "input": task.input_json or {}, "output": task.output_json or {}, "error": task.error_message, "created_at": task.created_at.isoformat(), "updated_at": task.updated_at.isoformat()},
        "runs": [{"provider": row.provider, "skill": row.skill, "status": row.status, "latency_ms": row.latency_ms, "metadata": row.metadata_json or {}, "created_at": row.created_at.isoformat()} for row in runs],
        "approvals": [{"decision": row.decision, "decided_by": row.decided_by, "comment": row.comment, "created_at": row.created_at.isoformat(), "decided_at": row.decided_at.isoformat() if row.decided_at else None} for row in approvals],
        "candidates": candidate_rows,
        "outbound": [{"supplier_id": row.supplier_id, "intent_quote_id": row.intent_quote_id, "status": row.status, "channel": row.channel, "channel_status": row.channel_status_json or {}, "error": row.error_message, "created_at": row.created_at.isoformat(), "sent_at": row.sent_at.isoformat() if row.sent_at else None, "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None, "read_at": row.read_at.isoformat() if row.read_at else None, "replied_at": row.replied_at.isoformat() if row.replied_at else None, "rejected_at": row.rejected_at.isoformat() if row.rejected_at else None, "timed_out_at": row.timed_out_at.isoformat() if row.timed_out_at else None} for row in outbound],
        "events": [{"type": row.event_type, "actor_id": row.actor_id, "payload": row.payload or {}, "created_at": row.created_at.isoformat()} for row in events],
    }))


@chain_xiaoyi_bp.patch("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/fields")
@chain_xiaoyi_bp.patch("/api/chain-xiaoyi/tasks/<int:task_id>/fields")
def update_task_fields(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后修正采购字段", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    if not isinstance(data.get("fields"), dict):
        return jsonify({"error": "fields 必须是对象"}), 400
    try:
        draft = ChainXiaoYiOrchestrator.update_procurement_fields(task, data["fields"], int(current_user.id))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True, "draft": draft, "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval}})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/recompute")
@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/recompute")
def recompute_task_candidates(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后重算候选", "code": "login_required"}), 401
    try:
        item_matches = ChainXiaoYiOrchestrator.recompute_procurement_candidates(
            task,
            int(current_user.id),
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "success": True,
            "task": {
                "id": task.id,
                "type": task.task_type,
                "status": task.status,
                "requires_approval": task.requires_approval,
            },
            "item_matches": item_matches,
        }
    )


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/rfq-preview")
@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/rfq-batch-preview")
def create_batch_rfq_preview(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后生成批量询价预览", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        children, idempotent = ChainXiaoYiOrchestrator.create_batch_rfq_preview(
            task,
            int(current_user.id),
            data.get("selections"),
            str(data.get("message") or ""),
            data.get("channels") if isinstance(data.get("channels"), list) else None,
            data.get("quote_deadline_at") or data.get("deadline_at"),
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "success": True,
            "idempotent": idempotent,
            "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval, "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None},
            "rfq_tasks": [{"id": child.id, "type": child.task_type, "status": child.status, "requires_approval": child.requires_approval} for child in children],
            "preview": (task.output_json or {}).get("batch_rfq") or {},
        }
    ), (200 if idempotent else 201)


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/auto-plan")
@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/auto-plan")
def auto_plan_procurement_task(task_id: int):
    """Move a complete material task directly to one approval card.

    The endpoint only creates an approval-ready preview.  It deliberately
    does not call ``send`` or any external delivery adapter; the existing
    approve endpoint remains the sole outbound confirmation boundary.
    """
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后自动规划询价", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        children, idempotent, item_matches = ChainXiaoYiOrchestrator.auto_plan_procurement(
            task,
            int(current_user.id),
            str(data.get("message") or "")[:1200],
            data.get("channels") if isinstance(data.get("channels"), list) else None,
            data.get("quote_deadline_at") or data.get("deadline_at"),
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "success": True,
            "idempotent": idempotent,
            "task": {
                "id": task.id,
                "type": task.task_type,
                "status": task.status,
                "requires_approval": task.requires_approval,
                "quote_deadline_at": task.quote_deadline_at.isoformat() if task.quote_deadline_at else None,
            },
            "item_matches": item_matches,
            "rfq_tasks": [
                {"id": child.id, "type": child.task_type, "status": child.status, "requires_approval": child.requires_approval}
                for child in children
            ],
            "preview": (task.output_json or {}).get("batch_rfq") or {},
        }
    ), (200 if idempotent else 201)


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/approve")
@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/rfq-batch-approve")
def approve_batch_rfq(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后审批批量询价", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify({"error": "对外发送前必须明确确认", "code": "confirmation_required"}), 400
    try:
        queued, idempotent = ChainXiaoYiOrchestrator.approve_batch_rfq(
            task,
            int(current_user.id),
            str(data.get("comment") or ""),
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "success": True,
            "queued": queued,
            "idempotent": idempotent,
            "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval},
        }
    ), (200 if idempotent else 202)


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/approve")
def approve_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后确认任务"}), 401
    if not task.requires_approval:
        return jsonify({"error": "该任务不需要审批"}), 400
    if task.status in {"approved", "queued", "running", "sent", "partial_failure", "completed"}:
        return jsonify({"success": True, "status": task.status, "idempotent": True})
    if task.status in {"cancelled", "timed_out"}:
        return jsonify({"error": "当前任务状态不可审批，请先恢复或重新生成询价预览", "code": "invalid_task_state"}), 409
    data = request.get_json(silent=True) or {}
    production = str(current_app.config.get("APP_ENV") or "development").lower() == "production"
    if (current_app.config.get("CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL") or production) and data.get("confirm") is not True:
        return jsonify({"error": "对外发送前必须明确确认", "code": "confirmation_required"}), 400
    task.status = "approved" if task.task_type == "rfq" else "running"
    db.session.add(ChainXiaoYiApproval(task_id=task.id, decision="approved", decided_by=current_user.id, decided_at=datetime.utcnow(), comment=str(data.get("comment") or "")[:500]))
    db.session.commit()
    return jsonify({"success": True, "status": task.status})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/send")
def send_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后发送询价", "code": "login_required"}), 401
    if task.status == "sent":
        return jsonify({"success": True, "sent": 0, "failed": 0, "idempotent": True})
    try:
        result = ChainXiaoYiOrchestrator.send_rfq(task, int(current_user.id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, **result, "idempotent": False})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/send")
def send_procurement_task(task_id: int):
    """Start a prepared material task without synchronously doing provider I/O.

    Approval creates queued child RFQs.  This endpoint is intentionally a
    durable hand-off: the worker/scheduler drains those children and the
    caller polls ``/progress``.  Direct RFQ tasks continue to use ``/tasks``.
    """
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后发送询价", "code": "login_required"}), 401
    if task.task_type != "procurement_intake":
        return send_task(task_id)
    if task.status not in {"running", "queued", "partial_failure", "completed"}:
        return jsonify({"error": "采购任务尚未审批或当前状态不可发送"}), 409
    batch = (task.output_json or {}).get("batch_rfq") or {}
    child_ids = [int(value) for value in batch.get("task_ids") or [] if str(value).isdigit()]
    children = ChainXiaoYiTask.query.filter(ChainXiaoYiTask.id.in_(child_ids)).all() if child_ids else []
    queued = sum(1 for child in children if child.status in {"queued", "running"})
    return jsonify({"success": True, "status": task.status, "queued": queued, "task_id": task.id, "child_task_ids": child_ids, "idempotent": task.status in {"queued", "completed"}})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/send-async")
def send_task_async(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后发送询价", "code": "login_required"}), 401
    try:
        idempotent = ChainXiaoYiOrchestrator.enqueue_rfq(task, int(current_user.id))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, "status": task.status, "idempotent": idempotent}), (200 if idempotent else 202)


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>/quote-summary")
def quote_summary(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看报价", "code": "login_required"}), 401
    try:
        summary = ChainXiaoYiOrchestrator.quote_summary(task, int(current_user.id))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, **summary})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/quote-query")
def quote_query(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后筛选报价", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        result = ChainXiaoYiOrchestrator.query_quotes(task, int(current_user.id), str(data.get("query") or ""))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.add(ChainXiaoYiEvent(session_id=task.session_id, event_type="quote_query_applied", actor_id=int(current_user.id), payload={"task_id": task.id, "criteria": result["criteria"], "result_count": len(result["quotes"]) }))
    db.session.commit()
    return jsonify({"success": True, **result})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>/batch-quote-summary")
def batch_quote_summary(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看批量报价", "code": "login_required"}), 401
    try:
        summary = ChainXiaoYiOrchestrator.batch_quote_summary(task, int(current_user.id))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, **summary})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/batch-quote-query")
def batch_quote_query(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后筛选批量报价", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        result = ChainXiaoYiOrchestrator.query_batch_quotes(task, int(current_user.id), str(data.get("query") or ""))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.add(
        ChainXiaoYiEvent(
            session_id=task.session_id,
            event_type="batch_quote_query_applied",
            actor_id=int(current_user.id),
            payload={
                "task_id": task.id,
                "query": result["query"],
                "item_count": result["item_count"],
                "selection_count": len(result["selections"]),
                "missing_items": result["missing_items"],
            },
        )
    )
    db.session.commit()
    return jsonify({"success": True, **result})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/batch-order-drafts")
def create_batch_order_drafts(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后生成批量订单草稿", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        orders, idempotent, selection = ChainXiaoYiOrchestrator.create_batch_order_drafts(
            task,
            int(current_user.id),
            str(data.get("query") or ""),
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "success": True,
            "idempotent": idempotent,
            "orders": orders,
            "selection": selection,
            "requires_formal_order_confirmation": True,
        }
    ), (200 if idempotent else 201)


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/batch-order-drafts/confirm")
def confirm_batch_order_drafts(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后确认批量订单", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify({"error": "创建正式订单前必须明确确认", "code": "confirmation_required"}), 400
    try:
        orders, idempotent = ChainXiaoYiOrchestrator.confirm_batch_order_drafts(
            task,
            int(current_user.id),
            str(data.get("query") or ""),
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify(
        {
            "success": True,
            "idempotent": idempotent,
            "orders": orders,
            "requires_contract_confirmation": True,
            "requires_payment_confirmation": True,
        }
    ), (200 if idempotent else 201)


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/procurement-tasks/<int:task_id>/progress")
@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>/progress")
def task_progress(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后查看任务进度", "code": "login_required"}), 401
    try:
        progress = (
            ChainXiaoYiOrchestrator.batch_task_progress(task, int(current_user.id))
            if task.task_type == "procurement_intake"
            else ChainXiaoYiOrchestrator.task_progress(task, int(current_user.id))
        )
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    return jsonify({"success": True, **progress})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/order-draft")
def create_order_draft(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后创建订单草稿", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        supplier_id = int(data.get("supplier_id"))
        order, idempotent = ChainXiaoYiOrchestrator.create_order_draft(task, supplier_id, int(current_user.id))
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 409
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    return jsonify({"success": True, "order": order, "idempotent": idempotent}), (200 if idempotent else 201)


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/order-draft/confirm")
def confirm_order_draft(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后确认订单", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    if data.get("confirm") is not True:
        return jsonify({"error": "创建正式订单前必须明确确认", "code": "confirmation_required"}), 400
    try:
        supplier_id = int(data.get("supplier_id"))
        order, idempotent = ChainXiaoYiOrchestrator.confirm_order_draft(task, supplier_id, int(current_user.id))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, "order": order, "idempotent": idempotent}), (200 if idempotent else 201)


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/retry")
def retry_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后重试任务", "code": "login_required"}), 401
    if task.task_type != "rfq" or task.status not in {"partial_failure", "sent", "timed_out"}:
        return jsonify({"error": "当前任务没有可重试的失败外发记录"}), 409
    try:
        result = ChainXiaoYiOrchestrator.send_rfq(task, int(current_user.id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, **result, "progress": ChainXiaoYiOrchestrator.task_progress(task, int(current_user.id))})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/reject")
def reject_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后拒绝任务"}), 401
    task.status = "cancelled"
    db.session.add(ChainXiaoYiApproval(task_id=task.id, decision="rejected", decided_by=current_user.id, decided_at=datetime.utcnow(), comment=str((request.get_json(silent=True) or {}).get("comment") or "")[:500]))
    db.session.commit()
    return jsonify({"success": True, "status": task.status})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/cancel")
def cancel_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后取消任务", "code": "login_required"}), 401
    data = request.get_json(silent=True) or {}
    try:
        ChainXiaoYiOrchestrator.cancel_task(task, int(current_user.id), str(data.get("reason") or "")[:500])
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, "status": task.status})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/resume")
def resume_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后恢复任务", "code": "login_required"}), 401
    try:
        ChainXiaoYiOrchestrator.resume_task(task, int(current_user.id))
    except PermissionError:
        return jsonify({"error": "任务不存在或无权访问"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    return jsonify({"success": True, "status": task.status})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/model-status")
def model_status():
    return jsonify({"success": True, **get_model_status().to_dict()})
