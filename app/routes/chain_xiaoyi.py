"""Chain XiaoYi API: session, message, file preview and approval boundaries."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app import db
from app.models_chain_xiaoyi import ChainXiaoYiApproval, ChainXiaoYiMessage, ChainXiaoYiSession, ChainXiaoYiTask
from app.services.chain_xiaoyi import ChainXiaoYiOrchestrator
from app.services.chain_xiaoyi.model_router import get_model_status

chain_xiaoyi_bp = Blueprint("chain_xiaoyi", __name__)


def _owner_id() -> int | None:
    return int(current_user.id) if current_user.is_authenticated else None


def _session(session_id: int):
    item = ChainXiaoYiSession.query.get(session_id)
    if not item or not ChainXiaoYiOrchestrator.session_allowed(item, _owner_id(), request.headers.get("X-Chain-Xiaoyi-Token")):
        return None
    return item


def _session_payload(item: ChainXiaoYiSession) -> dict:
    return {"id": item.id, "token": item.access_token if item.owner_id is None else None, "title": item.title, "surface": item.surface, "status": item.status}


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions")
def create_session():
    data = request.get_json(silent=True) or {}
    surface = str(data.get("surface") or "public")[:40]
    item = ChainXiaoYiOrchestrator.create_session(_owner_id(), surface)
    return jsonify({"success": True, "session": _session_payload(item), "model_status": get_model_status().to_dict()}), 201


@chain_xiaoyi_bp.get("/api/chain-xiaoyi/sessions/<int:session_id>")
def get_session(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    messages = item.messages.order_by(ChainXiaoYiMessage.created_at.asc()).all()
    return jsonify({"success": True, "session": _session_payload(item), "messages": [{"id": message.id, "role": message.role, "content": message.content, "metadata": message.metadata_json or {}, "created_at": message.created_at.isoformat()} for message in messages]})


@chain_xiaoyi_bp.post("/api/chain-xiaoyi/sessions/<int:session_id>/messages")
def send_message(session_id: int):
    item = _session(session_id)
    if not item:
        return jsonify({"error": "会话不存在或无权访问"}), 404
    data = request.get_json(silent=True) or {}
    try:
        result = ChainXiaoYiOrchestrator.handle_message(item, str(data.get("content") or data.get("message") or ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    task = result["task"]
    return jsonify({"success": True, "reply": result["reply"], "intent": result["intent"], "model_status": result["model_status"], "task": {"id": task.id, "type": task.task_type, "status": task.status, "requires_approval": task.requires_approval}})


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
