"""
核心数据模型（业务核心表 + JSON 拍平策略）

说明：
- MatchFeedback 独立成表，供 Bandit/RL 等高频查询匹配反馈日志。
- 信用分变更历史存于 Enterprise.credit_score_events（JSON 列表），不再使用 credit_score_history 表。
- 其他附属数据迁入 Enterprise / Product / Inquiry / Transaction / Alert 的 JSON 字段。
- 信用分规则、预警阈值等请在 config.py 中维护（不再使用 credit_rules / alert_thresholds 表）。

当前核心业务表：enterprises, products, inquiries, quotes, transactions, match_feedbacks,
recruitment_tasks, alerts, price_indices, messages；Hermes 写操作确认单独落表。
"""
from datetime import datetime
import hashlib
import secrets
import time

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


# ---------------------------------------------------------------------------
# 1. Enterprise
# ---------------------------------------------------------------------------
class Enterprise(db.Model, UserMixin):
    __tablename__ = "enterprises"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    address = db.Column(db.String(200))
    longitude = db.Column(db.Float)
    latitude = db.Column(db.Float)
    company_images = db.Column(db.JSON)
    contact = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    credit_score = db.Column(db.Float, default=70.0)
    capacity = db.Column(db.Integer, default=50)
    current_orders = db.Column(db.Integer, default=0)
    max_capacity = db.Column(db.Integer)
    last_order_update = db.Column(db.DateTime)
    capacity_calendar_visibility = db.Column(db.String(20), default="private")
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), nullable=False, default="enterprise")

    registered_capital = db.Column(db.Float)
    business_scope = db.Column(db.Text)
    province = db.Column(db.String(20))
    city = db.Column(db.String(200))

    patent_category = db.Column(db.String(100))
    patent_count = db.Column(db.Integer)
    tech_keywords = db.Column(db.String(500))
    rd_investment = db.Column(db.Float)
    industry_code = db.Column(db.String(50))

    is_green_factory = db.Column(db.Boolean, default=False)
    green_certification = db.Column(db.JSON)
    clean_energy_usage = db.Column(db.Float, default=0.0)
    carbon_emission_level = db.Column(db.String(10))
    environment_protection_patents = db.Column(db.Integer, default=0)
    green_supplier_rank = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # —— 企业审核相关字段 —— 
    # 审核状态: pending(待审核)/approved(已通过)/rejected(已驳回)
    verification_status = db.Column(db.String(20), default="pending")
    # 是否通过审核（兼容旧字段）
    is_verified = db.Column(db.Boolean, default=False)
    # 审核人ID（管理员）
    verified_by = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=True)
    # 审核时间
    verified_at = db.Column(db.DateTime, nullable=True)
    # 驳回原因
    rejection_reason = db.Column(db.Text, nullable=True)
    # 注册时间（用于排序）
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 企业经营状态（存续/注销/吊销）- 来自工商API
    business_status = db.Column(db.String(20), nullable=True)
    # 工商数据更新时间
    biz_data_updated_at = db.Column(db.DateTime, nullable=True)

    daily_quote_count = db.Column(db.Integer, default=0)
    daily_quote_limit = db.Column(db.Integer, default=3)
    last_quote_reset_date = db.Column(db.Date)
    is_lead_enterprise = db.Column(db.Boolean, default=False)
    data_freshness_score = db.Column(db.Float, default=100.0)
    last_data_update = db.Column(db.DateTime)
    is_dormant = db.Column(db.Boolean, default=False)
    current_mode = db.Column(db.String(10), default="buyer")

    wechat_bound = db.Column(db.Boolean, default=False)
    wechat_work_userid = db.Column(db.String(100))
    wechat_work_openid = db.Column(db.String(100))
    wechat_service_openid = db.Column(db.String(100))
    wechat_bound_at = db.Column(db.DateTime)
    wechat_push_preference = db.Column(db.String(20), default="all")

    # —— JSON 拍平（替代 quality_labels / data_authorizations / case_library / enterprise_patents 等）——
    # qualifications: list[{label_type, label_name, issuer_id, certificate_no, valid_from, valid_until, status, ...}]
    qualifications = db.Column(db.JSON)
    # data_auth: dict[data_type -> {authorized, authorized_at, revoked_at, last_sync_at, sync_status, error_message}]
    data_auth = db.Column(db.JSON)
    # cooperation_cases: list[{buyer_name_masked, product_category, cooperation_time, amount_range, is_public, ...}]
    cooperation_cases = db.Column(db.JSON)
    # patents: list[{patent_no, title, patent_type, ipc_code, apply_date}]  替代 enterprise_patents
    patents = db.Column(db.JSON)
    # extras: 吸收 financing_applications、lead_onboarding、supplier_display、saas_orders、reports、match_interactions 等
    extras = db.Column(db.JSON)
    # 信用分变更流水（替代 credit_score_history 表）：list[{id, old_score, new_score, change_value, change_type, reason, created_at}]
    credit_score_events = db.Column(db.JSON)

    products = db.relationship(
        "Product",
        backref="enterprise",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash or not password:
            return False
        try:
            return check_password_hash(self.password_hash, password)
        except (AttributeError, ValueError, TypeError):
            return False

    def __repr__(self):
        return f"<Enterprise {self.name}>"


# ---------------------------------------------------------------------------
# 2. Product（吸收产品级风险信息）
# ---------------------------------------------------------------------------
class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    industry_code = db.Column(db.String(50))
    enterprise_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path = db.Column(db.String(255))
    embedding = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 替代 product_import_risks：{import_ratio, source_countries, hs_code, data_source, updated_at}
    import_risk = db.Column(db.JSON)

    def __repr__(self):
        return f"<Product {self.name}>"


# ---------------------------------------------------------------------------
# 3. Inquiry（合并原 Demand；拼单字段；可空买卖双方以支持挂牌）
# ---------------------------------------------------------------------------
class Inquiry(db.Model):
    __tablename__ = "inquiries"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 发布方（原 Demand.enterprise_id / 询盘发起人）
    poster_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=False)
    # 原 Demand.type：supply / demand
    direction = db.Column(
        db.Enum("supply", "demand", name="inquiry_direction"),
        nullable=False,
        default="demand",
    )
    buyer_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=True)
    seller_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=True)

    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    unit = db.Column(db.String(10))
    description = db.Column(db.Text)
    content = db.Column(db.Text)

    status = db.Column(db.String(32), nullable=False, default="open")
    match_feedback_id = db.Column(
        db.Integer,
        db.ForeignKey("match_feedbacks.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 补充上下文：{dim_scores, match_score, session_id, ...}（JSON，不另建表）
    match_context = db.Column(db.JSON)

    is_group_buy = db.Column(db.Boolean, default=False)
    # 拼单成员 [{enterprise_id, quantity, joined_at}, ...]（JSON，不另建关联表）
    group_members = db.Column(db.JSON)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    poster = db.relationship("Enterprise", foreign_keys=[poster_id])
    buyer = db.relationship("Enterprise", foreign_keys=[buyer_id])
    seller = db.relationship("Enterprise", foreign_keys=[seller_id])
    product = db.relationship("Product", foreign_keys=[product_id])
    match_feedback = db.relationship(
        "MatchFeedback",
        foreign_keys=[match_feedback_id],
        backref=db.backref("inquiries", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<Inquiry {self.id} {self.direction}>"


# ---------------------------------------------------------------------------
# 4. Quote（保持不变）
# ---------------------------------------------------------------------------
class Quote(db.Model):
    __tablename__ = "quotes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inquiry_id = db.Column(
        db.Integer, db.ForeignKey("inquiries.id", ondelete="CASCADE"), nullable=False
    )
    supplier_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer)
    unit = db.Column(db.String(10))
    delivery_days = db.Column(db.Integer)
    remarks = db.Column(db.Text)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inquiry = db.relationship("Inquiry", backref=db.backref("quotes", lazy="dynamic"))
    supplier = db.relationship("Enterprise", foreign_keys=[supplier_id])

    def __repr__(self):
        return f"<Quote {self.product_name} ¥{self.price}>"


# ---------------------------------------------------------------------------
# 5. Transaction（撮合码、发票与履约 JSON、履约状态）
# ---------------------------------------------------------------------------
class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    # 业务主状态（成交/取消等）
    status = db.Column(db.String(20), default="completed")
    # 原 collaboration_codes.code
    match_code = db.Column(db.String(64), unique=True, nullable=True)
    # 发票 + 交付 + 质检 + SaaS 订单扩展等：{invoice_no, invoice_amount, invoice_date, delivery_date, on_time, quality_rating, verified, contract_id, amount_range, valid_until, order_no, customer_name, ...}
    invoice_info = db.Column(db.JSON)
    # 履约链路：pending / invoiced / delivered / verified / failed 等（替代 fulfillment_data 状态维度）
    fulfillment_status = db.Column(db.String(32), default="pending")

    inquiry_id = db.Column(db.Integer, db.ForeignKey("inquiries.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    buyer = db.relationship("Enterprise", foreign_keys=[buyer_id])
    seller = db.relationship("Enterprise", foreign_keys=[seller_id])
    inquiry = db.relationship("Inquiry", foreign_keys=[inquiry_id])

    def __repr__(self):
        return f"<Transaction {self.product_name}>"

    @staticmethod
    def generate_match_code(buyer_id: int, seller_id: int, contract_id: str = "") -> str:
        prefix = "LYP"
        ts = time.strftime("%y%m%d%H%M")
        raw = f"{buyer_id}-{seller_id}-{contract_id}-{time.time()}-{secrets.token_hex(4)}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:5].upper()
        return f"{prefix}{ts}{h}"


# ---------------------------------------------------------------------------
# 6. MatchFeedback（匹配反馈日志，供 Bandit / 强化学习）
# ---------------------------------------------------------------------------
class MatchFeedback(db.Model):
    __tablename__ = "match_feedbacks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("enterprises.id"), nullable=False)
    product_name = db.Column(db.String(100))
    clicked = db.Column(db.Boolean, default=False)
    contacted = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(32), nullable=True)
    blockchain_evidence_hash = db.Column(db.String(128), nullable=True)
    rl_reward_applied = db.Column(db.Boolean, default=False)
    dim_scores = db.Column(db.JSON)
    match_score = db.Column(db.Float)
    session_id = db.Column(db.String(64))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    buyer = db.relationship(
        "Enterprise",
        foreign_keys=[buyer_id],
        backref=db.backref("match_feedbacks_as_buyer", lazy="dynamic"),
    )
    supplier = db.relationship(
        "Enterprise",
        foreign_keys=[supplier_id],
        backref=db.backref("match_feedbacks_as_supplier", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<MatchFeedback {self.buyer_id}->{self.supplier_id}>"


# ---------------------------------------------------------------------------
# 7. RecruitmentTask（保持不变；须在 Alert 之前定义以便外键解析）
# ---------------------------------------------------------------------------
class RecruitmentTask(db.Model):
    __tablename__ = "recruitment_tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_name = db.Column(db.String(200), nullable=False)
    target_product = db.Column(db.String(100))
    target_enterprise_name = db.Column(db.String(100))
    target_enterprise_location = db.Column(db.String(100))
    assigned_to = db.Column(db.Integer, db.ForeignKey("enterprises.id"))
    assigned_by = db.Column(db.Integer, db.ForeignKey("enterprises.id"))
    priority = db.Column(db.String(10), default="normal")
    status = db.Column(db.String(20), default="pending")
    progress_notes = db.Column(db.Text)
    deadline = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    assignee = db.relationship("Enterprise", foreign_keys=[assigned_to])
    assigner = db.relationship("Enterprise", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<RecruitmentTask {self.task_name}>"


# ---------------------------------------------------------------------------
# 8. Alert（实例告警 + workflow_history 替代 alert_workflows）
# ---------------------------------------------------------------------------
class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    level = db.Column(db.String(20), default="yellow")
    dimension = db.Column(db.String(30), default="local")
    is_active = db.Column(db.Boolean, default=True)
    suggestion = db.Column(db.Text)
    alert_type = db.Column(db.String(50))
    severity_score = db.Column(db.Float)
    auto_pushed = db.Column(db.Boolean, default=False)
    linked_recruitment_task_id = db.Column(
        db.Integer, db.ForeignKey("recruitment_tasks.id", ondelete="SET NULL"), nullable=True
    )
    # list[{assigned_to, assigned_by, status, handling_notes, evidence_urls, completed_at, review_result, ...}]
    workflow_history = db.Column(db.JSON)
    # 结构化深度分析数据（链小易 AI 风险解读字段）
    # {
    #   risk_reason: str,
    #   impact_scope: str,
    #   ai_suggestions: [str, ...],
    #   data_source_info: {name: str, node_id: str, last_sync: str},
    #   historical_trend: [int, ...]  (近7天数值)
    # }
    analysis_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    linked_recruitment_task = db.relationship(
        "RecruitmentTask", foreign_keys=[linked_recruitment_task_id]
    )

    def __repr__(self):
        return f"<Alert {self.product_name} - {self.level}>"


# ---------------------------------------------------------------------------
# 8.1 HermesPendingAction（Hermes 写操作二次确认）
# ---------------------------------------------------------------------------
class HermesPendingAction(db.Model):
    __tablename__ = "hermes_pending_actions"

    id = db.Column(db.String(64), primary_key=True)
    action = db.Column(db.String(50), nullable=False)
    alert_id = db.Column(db.Integer, db.ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    requested_by = db.Column(db.String(120), nullable=False, default="hermes")
    parameters = db.Column(db.JSON)
    summary = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    executed_at = db.Column(db.DateTime)

    alert = db.relationship("Alert", foreign_keys=[alert_id])

    def to_payload(self) -> dict:
        return {
            "id": self.id,
            "action": self.action,
            "alert_id": self.alert_id,
            "requested_by": self.requested_by,
            "parameters": self.parameters or {},
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "summary": self.summary or "",
        }


# ---------------------------------------------------------------------------
# 9. PriceIndex（保持不变）
# ---------------------------------------------------------------------------
class PriceIndex(db.Model):
    __tablename__ = "price_indices"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_name = db.Column(db.String(100), unique=True, nullable=False)
    median_price = db.Column(db.Float)
    mean_price = db.Column(db.Float)
    std_dev = db.Column(db.Float)
    min_price = db.Column(db.Float)
    max_price = db.Column(db.Float)
    sample_count = db.Column(db.Integer, default=0)
    data_source = db.Column(db.String(30), default="realtime")
    last_updated = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<PriceIndex {self.product_name} median={self.median_price}>"


# ---------------------------------------------------------------------------
# 10. Message（保持不变）
# ---------------------------------------------------------------------------
class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sender_id = db.Column(
        db.Integer, db.ForeignKey("enterprises.id", ondelete="SET NULL"), nullable=True
    )
    recipient_id = db.Column(
        db.Integer, db.ForeignKey("enterprises.id", ondelete="CASCADE"), nullable=False
    )
    message_type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    link_url = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(10), default="normal")
    # mode: 消息所属视角模式
    #   procurement → 采购视角消息（买方发起询价 → 卖方收到的询盘通知）
    #   sales        → 销售视角消息（卖方提交报价 → 买方收到的报价通知）
    mode = db.Column(db.String(20), default="procurement")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)

    sender = db.relationship(
        "Enterprise",
        foreign_keys=[sender_id],
        backref=db.backref("sent_messages", lazy="dynamic"),
    )
    recipient = db.relationship(
        "Enterprise",
        foreign_keys=[recipient_id],
        backref=db.backref("messages", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<Message {self.message_type} to={self.recipient_id}>"


# =============================================================================
# 11. MatchRecord（匹配记录：管理匹配成功后的会话生命周期）
# =============================================================================
class MatchRecord(db.Model):
    """
    匹配记录：记录匹配成功后买卖双方的完整流程状态。

    状态流转：
      matched        → 已匹配，尚未发起询价
      inquiry_sent   → 买方已发起询价
      inquiry_accepted → 卖方已接收询价
      quoted         → 至少有一方已提交正式报价
      contracted     → 已签署合作意向/电子合同

    关联 MatchFeedback.id 用于 Bandit 学习追踪。
    """
    __tablename__ = "match_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    buyer_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_name = db.Column(db.String(100), nullable=False)
    match_score = db.Column(db.Float)
    # dim_scores: {product, distance, capacity, semantic, tech, history, gnn, credit, green}
    dim_scores = db.Column(db.JSON)
    # 关联的 MatchFeedback.id（用于 Bandit 学习）
    match_feedback_id = db.Column(
        db.Integer,
        db.ForeignKey("match_feedbacks.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = db.Column(
        db.String(32),
        nullable=False,
        default="matched",
    )
    session_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    buyer = db.relationship(
        "Enterprise",
        foreign_keys=[buyer_id],
        backref=db.backref("match_records_as_buyer", lazy="dynamic"),
    )
    seller = db.relationship(
        "Enterprise",
        foreign_keys=[seller_id],
        backref=db.backref("match_records_as_seller", lazy="dynamic"),
    )
    match_feedback = db.relationship(
        "MatchFeedback",
        foreign_keys=[match_feedback_id],
        backref=db.backref("match_record", uselist=False),
    )
    # 关联的询价会话（一对多）
    chats = db.relationship(
        "InquiryChat",
        backref="match_record",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<MatchRecord {self.id} buyer={self.buyer_id} seller={self.seller_id} status={self.status}>"


# =============================================================================
# 12. InquiryChat（询价会话：关联匹配记录，支持采购/销售模式切换）
# =============================================================================
class InquiryChat(db.Model):
    """
    询价会话：买卖双方围绕一个 MatchRecord 展开的意向沟通渠道。

    - mode: 指示当前会话视角
        procurement → 采购视角（买方的会话列表中展示）
        sales       → 销售视角（卖方的会话列表中展示）
    - is_anonymous: 买方发起时是否匿名（需求15）
    - status: active / closed / quoted
    """
    __tablename__ = "inquiry_chats"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    match_record_id = db.Column(
        db.Integer,
        db.ForeignKey("match_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    buyer_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 采购视角(procurement) / 销售视角(sales)
    mode = db.Column(
        db.String(20),
        nullable=False,
        default="procurement",
    )
    # 买方匿名：True 时卖方侧仅显示「匿名上市车企」等脱敏名称
    is_anonymous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    buyer = db.relationship(
        "Enterprise",
        foreign_keys=[buyer_id],
        backref=db.backref("inquiry_chats_as_buyer", lazy="dynamic"),
    )
    seller = db.relationship(
        "Enterprise",
        foreign_keys=[seller_id],
        backref=db.backref("inquiry_chats_as_seller", lazy="dynamic"),
    )
    # 会话中的聊天消息
    messages = db.relationship(
        "ChatMessage",
        backref="chat",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
    )

    def __repr__(self):
        return (
            f"<InquiryChat {self.id} buyer={self.buyer_id} seller={self.seller_id} "
            f"mode={self.mode} anonymous={self.is_anonymous}>"
        )


# =============================================================================
# 13. ChatMessage（聊天消息：支持文本、报价提案、系统消息、AI建议）
# =============================================================================
class ChatMessage(db.Model):
    """
    聊天消息：记录会话中的每条消息。

    message_type:
      text            → 普通文本消息
      quote_proposal  → 结构化报价提案（metadata 含 {price, quantity, unit, delivery_days}）
      system          → 系统消息（如「对方已提交报价」）
      ai_suggestion    → AI 助手建议（metadata 含分析数据）

    sender_id 为 None 时表示系统消息。
    """
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chat_id = db.Column(
        db.Integer,
        db.ForeignKey("inquiry_chats.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="SET NULL"),
        nullable=True,
    )
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(
        db.String(32),
        nullable=False,
        default="text",
    )
    # msg_metadata: {
    #   price?, quantity?, unit?, delivery_days?,   ← quote_proposal
    #   risk_level?, profit_rate?, match_score?,  ← ai_suggestion
    #   extra?                                   ← system
    # }
    msg_metadata = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship(
        "Enterprise",
        foreign_keys=[sender_id],
        backref=db.backref("chat_messages", lazy="dynamic"),
    )

    def __repr__(self):
        return (
            f"<ChatMessage {self.id} chat={self.chat_id} "
            f"type={self.message_type} sender={self.sender_id}>"
        )


# =============================================================================
# 14. FavoriteSupplier（收藏供应商）
# =============================================================================
class FavoriteSupplier(db.Model):
    """
    收藏供应商：记录采购商收藏的供应商。
    
    功能：快速询价、批量比较、价格提醒、商机订阅。
    """
    __tablename__ = "favorite_suppliers"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 收藏方（采购商）
    collector_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 被收藏的供应商
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 收藏时的产品需求
    product_name = db.Column(db.String(100))
    # 收藏时的匹配分数
    match_score = db.Column(db.Float)
    # 用户备注
    notes = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    collector = db.relationship(
        "Enterprise",
        foreign_keys=[collector_id],
        backref=db.backref("favorite_suppliers", lazy="dynamic"),
    )
    supplier = db.relationship(
        "Enterprise",
        foreign_keys=[supplier_id],
        backref=db.backref("favorited_by", lazy="dynamic"),
    )

    # 同一供应商只能被同一采购商收藏一次
    __table_args__ = (
        db.UniqueConstraint("collector_id", "supplier_id", name="uq_collector_supplier"),
    )

    def __repr__(self):
        return f"<FavoriteSupplier collector={self.collector_id} supplier={self.supplier_id}>"


# =============================================================================
# 15. IntentQuote（意向报价）
# =============================================================================
class IntentQuote(db.Model):
    """
    意向报价：采购商发起、供应商确认的轻量级报价意向。
    
    状态流转：
      draft      → 草稿（采购方填写中）
      pending    → 待确认（采购方已发送，等待供应商回应）
      accepted   → 已接受（双方达成意向）
      rejected   → 已拒绝
      expired    → 已过期
    """
    __tablename__ = "intent_quotes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 关联的询价会话
    chat_id = db.Column(
        db.Integer,
        db.ForeignKey("inquiry_chats.id", ondelete="CASCADE"),
        nullable=True,
    )
    # 采购方
    buyer_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 供应方
    seller_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 关联的匹配记录
    match_record_id = db.Column(
        db.Integer,
        db.ForeignKey("match_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 报价产品信息
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer)
    unit = db.Column(db.String(20))
    target_price = db.Column(db.Float)  # 目标单价（选填）
    budget_range = db.Column(db.String(50))  # 预算区间，如 "45-55"
    
    # AI辅助生成
    ai_suggested_price = db.Column(db.Float)  # AI参考报价
    ai_price_basis = db.Column(db.Text)  # 报价依据说明
    ai_delivery_estimate = db.Column(db.String(100))  # 交期估算

    # 状态
    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft",
    )
    
    # 双方确认
    buyer_confirmed = db.Column(db.Boolean, default=False)
    seller_confirmed = db.Column(db.Boolean, default=False)
    
    # 供应商回复
    seller_reply_price = db.Column(db.Float)  # 供应商回复的报价
    seller_reply_notes = db.Column(db.Text)  # 供应商回复的备注

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # 过期时间

    buyer = db.relationship(
        "Enterprise",
        foreign_keys=[buyer_id],
        backref=db.backref("intent_quotes_as_buyer", lazy="dynamic"),
    )
    seller = db.relationship(
        "Enterprise",
        foreign_keys=[seller_id],
        backref=db.backref("intent_quotes_as_seller", lazy="dynamic"),
    )
    chat = db.relationship("InquiryChat", foreign_keys=[chat_id])
    match_record = db.relationship("MatchRecord", foreign_keys=[match_record_id])

    def __repr__(self):
        return f"<IntentQuote {self.id} buyer={self.buyer_id} seller={self.seller_id} status={self.status}>"


# =============================================================================
# 16. BusinessCard（名片交换记录）
# =============================================================================
class BusinessCard(db.Model):
    """
    名片交换记录：记录买卖双方交换名片的歷史。
    
    仅在双方均同意意向报价后解锁。
    """
    __tablename__ = "business_cards"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # 交换发起方
    initiator_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 交换接收方
    recipient_id = db.Column(
        db.Integer,
        db.ForeignKey("enterprises.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 关联的意向报价（用于验证解锁条件）
    intent_quote_id = db.Column(
        db.Integer,
        db.ForeignKey("intent_quotes.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 交换状态
    status = db.Column(
        db.String(20),
        nullable=False,
        default="completed",
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    initiator = db.relationship(
        "Enterprise",
        foreign_keys=[initiator_id],
        backref=db.backref("cards_sent", lazy="dynamic"),
    )
    recipient = db.relationship(
        "Enterprise",
        foreign_keys=[recipient_id],
        backref=db.backref("cards_received", lazy="dynamic"),
    )
    intent_quote = db.relationship("IntentQuote", foreign_keys=[intent_quote_id])

    # 同一对企业之间只能有一条交换记录
    __table_args__ = (
        db.UniqueConstraint("initiator_id", "recipient_id", name="uq_card_pair"),
    )

    def __repr__(self):
        return f"<BusinessCard {self.initiator_id} -> {self.recipient_id}>"
