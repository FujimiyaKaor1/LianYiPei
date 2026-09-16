from __future__ import annotations

import hashlib
import time
from datetime import datetime

from app import db
from app.models import Enterprise, Inquiry
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
from .rules import parse_procurement_intent, preview_tabular_file


class ChainXiaoYiOrchestrator:
    """Single entry point for all assistant actions.

    Model providers are intentionally a later seam. Rule execution is useful,
    testable, and truthful while DeepSeek/local models are not configured.
    """

    @staticmethod
    def create_session(owner_id: int | None, surface: str = "public") -> ChainXiaoYiSession:
        session = ChainXiaoYiSession(owner_id=owner_id, access_token=ChainXiaoYiSession.issue_token(), surface=surface)
        db.session.add(session)
        db.session.commit()
        return session

    @staticmethod
    def session_allowed(session: ChainXiaoYiSession, owner_id: int | None, token: str | None) -> bool:
        if owner_id is not None and session.owner_id == owner_id:
            return True
        return bool(token and token == session.access_token and session.owner_id is None)

    @staticmethod
    def handle_message(session: ChainXiaoYiSession, content: str) -> dict:
        started = time.monotonic()
        text = (content or "").strip()[:2000]
        if not text:
            raise ValueError("消息不能为空")
        user_message = ChainXiaoYiMessage(session_id=session.id, role="user", content=text)
        db.session.add(user_message)
        intent = parse_procurement_intent(text)
        status = get_model_status()
        task_type = "demand_intake" if any(word in text for word in ("找", "采购", "需要", "工厂", "供应商", "报价")) else "general_assistant"
        task = ChainXiaoYiTask(
            session_id=session.id,
            task_type=task_type,
            status="succeeded",
            requires_approval=False,
            input_json={"message": text},
            output_json={"intent": intent, "provider": status.active_provider},
        )
        db.session.add(task)
        db.session.flush()
        elapsed_ms = int((time.monotonic() - started) * 1000)
        db.session.add(ChainXiaoYiRun(task_id=task.id, provider=status.active_provider, skill=task_type, latency_ms=elapsed_ms, metadata_json={"mode": "fallback" if status.active_provider == "rules" else "provider"}))
        reply = (
            f"我已先按基础规则理解你的需求：{intent.get('product') or '待补充产品'}。"
            "你可以继续补充数量、工艺、地区、交期或资质；确认后我会帮你进入找厂和询价流程。"
        )
        db.session.add(ChainXiaoYiMessage(session_id=session.id, role="assistant", content=reply, metadata_json={"task_id": task.id, "intent": intent, "model_status": status.to_dict()}))
        db.session.add(ChainXiaoYiEvent(session_id=session.id, event_type="message_processed", payload={"task_id": task.id, "provider": status.active_provider}))
        session.updated_at = datetime.utcnow()
        db.session.commit()
        return {"reply": reply, "intent": intent, "task": task, "model_status": status.to_dict()}

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
