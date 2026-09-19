import logging

from flask import Flask, current_app, flash, jsonify, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user
from flask_login.signals import user_unauthorized
from flask_login.utils import login_url as make_login_url
from flask_migrate import Migrate

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
_logger = logging.getLogger(__name__)


def _path_is_top_level_api(path: str) -> bool:
    return path == "/api" or path.startswith("/api/")


def _path_is_dashboard_json_api(path: str) -> bool:
    """政府/管理大屏 fetch 用的 JSON 接口，未登录时返回 401 JSON，避免 SPA 收到 HTML 误判为网络错误。"""
    p = path or ""
    return p.startswith("/dashboard/api/")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Config subclasses commonly override APP_ENV without redeclaring every
    # derived safety flag. Recompute the cloud-model fail-closed default for
    # that case while preserving an explicit CHAINXIAOYI_CLOUD_REQUIRED=false
    # emergency override on the subclass itself.
    if "CHAINXIAOYI_CLOUD_REQUIRED" not in getattr(config_class, "__dict__", {}):
        app.config["CHAINXIAOYI_CLOUD_REQUIRED"] = str(app.config.get("APP_ENV") or "development").lower() == "production"
    if "AUTO_CREATE_SCHEMA" not in getattr(config_class, "__dict__", {}):
        app.config["AUTO_CREATE_SCHEMA"] = str(app.config.get("APP_ENV") or "development").lower() != "production"

    if app.config.get("APP_ENV") == "production":
        unsafe = []
        if app.config.get("SECRET_KEY_IS_DEFAULT"):
            unsafe.append("SECRET_KEY")
        if not app.config.get("DATABASE_URL_CONFIGURED"):
            unsafe.append("DATABASE_URL")
        if app.config.get("DISABLE_API_AUTH"):
            unsafe.append("DISABLE_API_AUTH")
        if app.config.get("ENABLE_MOCK_API"):
            unsafe.append("ENABLE_MOCK_API")
        if app.config.get("AUTO_CREATE_SCHEMA"):
            unsafe.append("AUTO_CREATE_SCHEMA")
        if app.config.get("MATERIAL_AV_MODE") != "clamav":
            unsafe.append("MATERIAL_AV_MODE")
        if app.config.get("MATERIAL_STORAGE_BACKEND") != "s3":
            unsafe.append("MATERIAL_STORAGE_BACKEND")
        if not app.config.get("MATERIAL_ENCRYPTION_KEY"):
            unsafe.append("MATERIAL_ENCRYPTION_KEY")
        else:
            try:
                from cryptography.fernet import Fernet

                Fernet(str(app.config.get("MATERIAL_ENCRYPTION_KEY")).encode("ascii"))
            except (ValueError, TypeError):
                unsafe.append("MATERIAL_ENCRYPTION_KEY")
        if not app.config.get("MATERIAL_S3_BUCKET"):
            unsafe.append("MATERIAL_S3_BUCKET")
        if unsafe:
            raise RuntimeError("生产环境安全配置不完整或不安全：" + ", ".join(unsafe))

    # 开发模式下把业务 logger 打到终端（否则默认 root=WARNING，看不到 [WeChatPush] 等排查信息）
    if app.debug:
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        if not root.handlers:
            _h = logging.StreamHandler()
            _h.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
            root.addHandler(_h)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "请先登录访问此页面"

    if app.config.get("DISABLE_API_AUTH"):

        def _dev_login_enterprise():
            from app.models import Enterprise as DevLoginEnterprise

            eid = app.config.get("DEV_API_LOGIN_ENTERPRISE_ID")
            user = DevLoginEnterprise.query.get(eid) if eid is not None else None
            if user is None:
                user = DevLoginEnterprise.query.order_by(
                    DevLoginEnterprise.id.asc()
                ).first()
            return user

        @login_manager.request_loader
        def _dev_request_user(req):
            path = req.path or ""
            # 会话探测必须反映真实 Cookie 状态，否则开发自动登录会让
            # React 把未登录访客误判成管理员并重定向到后台。
            if path == "/api/session" or not _path_is_top_level_api(path):
                return None
            user = _dev_login_enterprise()
            if user is None:
                _logger.warning(
                    "DISABLE_API_AUTH：enterprises 表无数据，/api 无法用 request_loader 登录"
                )
            return user

        @app.before_request
        def _dev_api_force_login_session():
            """与 request_loader 互补：保证本请求内 g._login_user 已就绪（不依赖 Cookie）。"""
            # 保留业务 API 的本地免登录联调，但 /api/session 只能检查真实会话。
            if request.path == "/api/session" or not _path_is_top_level_api(request.path):
                return None
            from flask_login import current_user

            if current_user.is_authenticated:
                return None
            user = _dev_login_enterprise()
            if user is None:
                return None
            login_user(user, remember=False)
            return None

        @login_manager.unauthorized_handler
        def _dev_unauthorized():
            if _path_is_top_level_api(request.path):
                return (
                    jsonify(
                        error=(
                            "本地 DISABLE_API_AUTH 已开启但仍未通过登录校验："
                            "请确认 enterprises 表存在 id=123 或任意一条企业记录"
                        )
                    ),
                    401,
                )
            if _path_is_dashboard_json_api(request.path):
                return jsonify({"error": "请先登录"}), 401
            user_unauthorized.send(current_app._get_current_object())
            if login_manager.login_message:
                flash(
                    login_manager.login_message,
                    category=login_manager.login_message_category,
                )
            return redirect(
                make_login_url(login_manager.login_view, next_url=request.url)
            )

    else:

        @login_manager.unauthorized_handler
        def _unauthorized():
            """SPA / fetch 调顶层 /api/* 时返回 401 JSON，便于前端拦截；页面访问仍走登录重定向。"""
            if _path_is_top_level_api(request.path):
                return jsonify({"error": "请先登录"}), 401
            if _path_is_dashboard_json_api(request.path):
                return jsonify({"error": "请先登录"}), 401
            user_unauthorized.send(current_app._get_current_object())
            if login_manager.login_message:
                flash(
                    login_manager.login_message,
                    category=login_manager.login_message_category,
                )
            return redirect(
                make_login_url(login_manager.login_view, next_url=request.url)
            )

    # 初始化定时任务调度器
    from app.services.scheduler import init_scheduler
    init_scheduler(app)
    
    from app.routes.auth import auth as auth_bp
    from app.routes.enterprise import enterprise as enterprise_bp
    from app.routes.demand import demand as demand_bp
    from app.routes.match import match as match_bp
    from app.routes.dashboard import dashboard as dashboard_bp
    from app.routes.main import main as main_bp
    from app.routes.api import api_bp
    from app.routes.credit import credit_bp
    from app.routes.collab import collab_bp
    from app.routes.admin_panel import admin_panel_bp
    from app.routes.contract import bp as contract_bp
    from app.routes.fulfillment import fulfillment_bp
    from app.routes.alerts import alerts_bp
    from app.routes.recruitment import recruitment_bp
    from app.routes.quality_labels import quality_labels_bp
    from app.routes.lead_enterprise import bp as lead_enterprise_bp
    from app.routes.data_authorization import bp as data_authorization_bp
    from app.routes.external_interfaces import bp as external_interfaces_bp
    from app.routes.orders import bp as orders_bp
    from app.routes.messages import bp as messages_bp
    from app.routes.inquiry_chat import inquiry_chat_bp
    from app.routes.wechat import bp as wechat_bp
    from app.routes.favorite import favorite_bp
    from app.routes.intent_quote import intent_quote_bp
    from app.routes.hermes import bp as hermes_bp
    from app.routes.rag import rag_bp
    from app.routes.chain_xiaoyi import chain_xiaoyi_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(enterprise_bp, url_prefix='/enterprise')
    app.register_blueprint(demand_bp, url_prefix='/demand')
    app.register_blueprint(match_bp, url_prefix='/match')
    # dashboard 蓝图内路由已含 /dashboard/... 前缀，便于 SPA 通配与字面路径一致
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(main_bp)
    # Mock endpoints include simulated companies and contract responses. Keep
    # them completely absent from production unless explicitly enabled.
    if app.testing or app.config.get("ENABLE_MOCK_API"):
        from app.routes.mock_api import mock_api as mock_bp
        app.register_blueprint(mock_bp, url_prefix='/mock')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(credit_bp)
    app.register_blueprint(collab_bp)
    app.register_blueprint(admin_panel_bp, url_prefix='/admin')
    app.register_blueprint(contract_bp)
    app.register_blueprint(fulfillment_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(recruitment_bp)
    app.register_blueprint(quality_labels_bp)
    app.register_blueprint(lead_enterprise_bp)
    app.register_blueprint(data_authorization_bp)
    app.register_blueprint(external_interfaces_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(messages_bp)
    app.register_blueprint(inquiry_chat_bp)
    app.register_blueprint(wechat_bp)
    app.register_blueprint(favorite_bp)
    app.register_blueprint(intent_quote_bp)
    app.register_blueprint(hermes_bp)
    app.register_blueprint(rag_bp)
    app.register_blueprint(chain_xiaoyi_bp)

    from app.routes.react_admin_shell import bp as react_admin_shell_bp

    app.register_blueprint(react_admin_shell_bp)

    if app.config.get("BROWSER_EXTENSION_PROBE_NOOP"):
        from app.routes.browser_extension_noop import bp as browser_noop_bp

        app.register_blueprint(browser_noop_bp)

    from app.errors import register_error_handlers
    register_error_handlers(app)

    with app.app_context():
        if app.config.get("AUTO_CREATE_SCHEMA"):
            db.create_all()
            # Development compatibility shim: production schema changes must
            # be applied through Alembic, while local demos may still need
            # additive columns when using an old SQLite fixture.
            try:
                from app.services.schema_migrator import ensure_schema

                ensure_schema(db)
            except Exception as e:
                _logger.warning("ensure_schema failed (DB may be missing columns): %s", e, exc_info=True)
        else:
            _logger.info("AUTO_CREATE_SCHEMA disabled; waiting for Alembic migrations")
    
    return app

from app.models import Enterprise
@login_manager.user_loader
def load_user(user_id):
    return Enterprise.query.get(int(user_id))
