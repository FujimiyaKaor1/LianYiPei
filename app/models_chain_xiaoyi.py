"""Persistent state for the Chain XiaoYi orchestration layer.

The tables deliberately stay separate from InquiryChat: Chain XiaoYi is a
cross-surface assistant, while InquiryChat represents a buyer/seller business
conversation.
"""
from datetime import datetime
import secrets

from app import db


class ChainXiaoYiSession(db.Model):
    __tablename__ = "chain_xiaoyi_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=True)
    access_token = db.Column(db.String(96), nullable=False, unique=True, index=True)
    title = db.Column(db.String(160), nullable=False, default="新的链小易会话")
    surface = db.Column(db.String(40), nullable=False, default="public")
    status = db.Column(db.String(24), nullable=False, default="active")
    context = db.Column(db.JSON, nullable=True)
    anonymous_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = db.relationship("Enterprise", foreign_keys=[owner_id])
    messages = db.relationship("ChainXiaoYiMessage", backref="session", lazy="dynamic", cascade="all, delete-orphan")
    tasks = db.relationship("ChainXiaoYiTask", backref="session", lazy="dynamic", cascade="all, delete-orphan")

    @staticmethod
    def issue_token() -> str:
        return secrets.token_urlsafe(48)


class ChainXiaoYiGuestTrial(db.Model):
    """Privacy-preserving guest quota record; raw browser tokens/IPs are never stored."""
    __tablename__ = "chain_xiaoyi_guest_trials"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    browser_token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    ip_hmac_hash = db.Column(db.String(64), nullable=False, index=True)
    match_count = db.Column(db.Integer, nullable=False, default=0)
    minute_count = db.Column(db.Integer, nullable=False, default=0)
    minute_started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ChainXiaoYiMessage(db.Model):
    __tablename__ = "chain_xiaoyi_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chain_xiaoyi_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ChainXiaoYiTask(db.Model):
    __tablename__ = "chain_xiaoyi_tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chain_xiaoyi_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    task_type = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="created")
    requires_approval = db.Column(db.Boolean, nullable=False, default=False)
    input_json = db.Column(db.JSON, nullable=True)
    output_json = db.Column(db.JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ChainXiaoYiRun(db.Model):
    __tablename__ = "chain_xiaoyi_runs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey("chain_xiaoyi_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = db.Column(db.String(32), nullable=False, default="rules")
    skill = db.Column(db.String(60), nullable=False)
    status = db.Column(db.String(24), nullable=False, default="succeeded")
    latency_ms = db.Column(db.Integer, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ChainXiaoYiApproval(db.Model):
    __tablename__ = "chain_xiaoyi_approvals"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey("chain_xiaoyi_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    decision = db.Column(db.String(20), nullable=False, default="pending")
    decided_by = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime, nullable=True)


class ChainXiaoYiFileImport(db.Model):
    __tablename__ = "chain_xiaoyi_file_imports"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chain_xiaoyi_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120), nullable=True)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(24), nullable=False, default="preview")
    detected_kind = db.Column(db.String(60), nullable=True)
    preview_json = db.Column(db.JSON, nullable=True)
    errors_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ChainXiaoYiEvent(db.Model):
    __tablename__ = "chain_xiaoyi_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chain_xiaoyi_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type = db.Column(db.String(60), nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
