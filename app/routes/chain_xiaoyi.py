"""Chain XiaoYi API: secure conversational factory-finding sessions."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import os
from io import BytesIO
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_login import current_user
from openpyxl import Workbook

from app import db
from app.models_chain_xiaoyi import ChainXiaoYiApproval, ChainXiaoYiGuestTrial, ChainXiaoYiMessage, ChainXiaoYiSession, ChainXiaoYiTask
from app.services.chain_xiaoyi import ChainXiaoYiOrchestrator
from app.services.chain_xiaoyi.model_router import get_model_status

chain_xiaoyi_bp = Blueprint("chain_xiaoyi", __name__)
GUEST_COOKIE = "chain_xiaoyi_guest"


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
    task = result["task"]
    return jsonify({"success": True, "reply": result["reply"], "intent": result["intent"], "needs_clarification": result["needs_clarification"], "suggestions": result["suggestions"], "model_status": result["model_status"], "match_result": result["match_result"], "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval}})


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
    sheet.append(["企业名称", "省市", "经营范围", "综合算法分", "九维分数", "可信标签", "推荐理由", "数据更新时间"])
    for row in results:
        dims = row.get("dimensions") or {}
        dim_text = "；".join(f"{key}:{value.get('score', '数据未公开') if isinstance(value, dict) else value}" for key, value in dims.items())
        sheet.append([row.get("name"), f"{row.get('province', '')}{row.get('city', '')}", row.get("business_scope") or "数据未公开", row.get("score"), dim_text, "、".join(row.get("trusted_labels") or []), row.get("reason"), row.get("data_updated_at") or "数据未公开"])
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
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "请选择文件"}), 400
    try:
        filename = uploaded.filename.strip()
        allowed = {".csv", ".xlsx", ".xls", ".pdf", ".doc", ".docx"}
        suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix not in allowed:
            return jsonify({"error": "仅支持 CSV、Excel、PDF 和 Word 文件"}), 400
        result = ChainXiaoYiOrchestrator.preview_file(item, filename, uploaded.mimetype or "application/octet-stream", uploaded.read())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True, "file": {"id": result.id, "filename": result.filename, "sha256": result.sha256, "size_bytes": result.size_bytes, "status": result.status, "detected_kind": result.detected_kind, "preview": result.preview_json, "errors": result.errors_json or []}})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/tasks/<int:task_id>")
def get_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    return jsonify({"success": True, "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval, "input": task.input_json or {}, "output": task.output_json or {}, "error": task.error_message}})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/approve")
def approve_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后确认任务"}), 401
    if not task.requires_approval:
        return jsonify({"error": "该任务不需要审批"}), 400
    task.status = "running"
    db.session.add(ChainXiaoYiApproval(task_id=task.id, decision="approved", decided_by=current_user.id, comment=str((request.get_json(silent=True) or {}).get("comment") or "")[:500]))
    db.session.commit()
    return jsonify({"success": True, "status": task.status})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/tasks/<int:task_id>/reject")
def reject_task(task_id: int):
    task = ChainXiaoYiTask.query.get(task_id)
    if not task or not _session(task.session_id):
        return jsonify({"error": "任务不存在或无权访问"}), 404
    if not current_user.is_authenticated:
        return jsonify({"error": "请登录后拒绝任务"}), 401
    task.status = "cancelled"
    db.session.add(ChainXiaoYiApproval(task_id=task.id, decision="rejected", decided_by=current_user.id, comment=str((request.get_json(silent=True) or {}).get("comment") or "")[:500]))
    db.session.commit()
    return jsonify({"success": True, "status": task.status})


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/model-status")
def model_status():
    return jsonify({"success": True, **get_model_status().to_dict()})
