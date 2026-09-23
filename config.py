import os
import secrets
from datetime import datetime
from urllib.parse import urlparse

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))


def _load_project_env(path):
    """Load local defaults without overriding injected deployment secrets.

    Container/Supervisor environments are the production source of truth. A
    checked-out ``.env`` is still useful for local development, but must only
    fill values that are absent from the process environment.
    """
    load_dotenv(path, override=False)


_load_project_env(os.path.join(basedir, ".env"))


def _resolve_dev_sqlite_path() -> str:
    """Choose the local SQLite dataset used by the development fallback.

    The repository contains both the complete imported dataset and a small
    demo database.  The complete database must win whenever it is present;
    otherwise a fresh checkout would silently make every search look empty.
    An explicit path remains available for tests and local experiments.
    """
    configured = (os.environ.get("LIANYIPEI_DEV_SQLITE_PATH") or "").strip()
    if configured:
        return configured if os.path.isabs(configured) else os.path.join(basedir, configured)

    complete_path = os.path.join(basedir, "instance", "lianyipei.db")
    if os.path.exists(complete_path):
        return complete_path
    return os.path.join(basedir, "instance", "lianyipei-dev.sqlite")

# Ollama 原生 API 根地址（无 /v1 后缀），与 app.services.ollama_client 一致
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


def _is_localhost_llm_port(url: str, port: int) -> bool:
    """是否指向本机某端口的 HTTP(S) 地址（用于识别遗留的 model_service :5001）。"""
    if not (url or "").strip():
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.hostname not in ("localhost", "127.0.0.1"):
            return False
        return parsed.port == port
    except Exception:
        return False


def normalize_ollama_environ() -> None:
    """未配置时默认本机 Ollama；若仍指向本机 :5001（旧 model_service），改为默认 Ollama 地址。"""
    ob = (os.environ.get("OLLAMA_BASE_URL") or "").strip()
    if ob and _is_localhost_llm_port(ob, 5001):
        os.environ["OLLAMA_BASE_URL"] = DEFAULT_OLLAMA_BASE_URL
    elif not ob:
        for key in ("LLMBASEURL", "LLM_BASE_URL"):
            val = (os.environ.get(key) or "").strip()
            if val and _is_localhost_llm_port(val, 5001):
                os.environ["OLLAMA_BASE_URL"] = DEFAULT_OLLAMA_BASE_URL
                break
        if not (os.environ.get("OLLAMA_BASE_URL") or "").strip():
            os.environ["OLLAMA_BASE_URL"] = DEFAULT_OLLAMA_BASE_URL


normalize_ollama_environ()


# 预警阈值（原 alert_thresholds 表已删除，由业务代码读取此配置）
# dimension -> 阈值；与 app.services.alerter / alert_engine 中 dimension 命名保持一致
DEFAULT_ALERT_THRESHOLDS = {
    # 本地最少供应商家数（alerter.check_local_supplier_count）
    "local": 3,
    "green": 0.60,
    "import_risk": 0.40,
    "import": 0.6,
    "interprovincial": 0.7,
    "credit": 65.0,
    "capacity_utilization_low": 0.30,
    "supplier_count_min": 3,
    "business_risk_credit_min": 50.0,
    "credit_drop_7days": 15.0,
    "red_threshold": 0.7,
    "yellow_threshold": 0.4,
}

# 信用分规则增量（原 credit_rules 表，供 credit_engine 读取）
DEFAULT_CREDIT_RULES = {
    "fulfillment_on_time": 5.0,
    "fulfillment_late": -3.0,
    "data_auth": 10.0,
    "report_verified": -10.0,
    "report_false": -5.0,
    "consecutive_bonus": 5.0,
    "activity_inquiry": 2.0,
    "activity_quote": 1.0,
    "data_update": 2.0,
    "first_warning": 0.0,
}

# 撮合 / 对外协作 API 密钥（逗号分隔，原 api_keys 表）
# 例：COLLAB_API_KEYS=key1,key2
def _collab_api_keys_list():
    raw = os.environ.get("COLLAB_API_KEYS") or ""
    return [x.strip() for x in raw.split(",") if x.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _trusted_origins(app_env: str) -> list[str]:
    """Return explicit browser origins allowed to write to the SPA APIs.

    Development gets only loopback Vite origins because the dev server is a
    separate browser origin. Production has no implicit dev origins; the
    public HTTPS origin must be configured by the deployment environment.
    """
    raw = os.environ.get("TRUSTED_ORIGINS")
    if raw is not None:
        return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    if app_env != "production":
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    return []


# 管理后台创建的密钥（进程内；重启后丢失，生产请写入 COLLAB_API_KEYS）
_RUNTIME_COLLAB_API_KEYS = []


def register_runtime_collab_api_key(key_name: str) -> tuple[int, str]:
    """生成并登记一枚新密钥，返回 (id, key_value)。"""
    key_value = secrets.token_urlsafe(32)
    new_id = max([x["id"] for x in _RUNTIME_COLLAB_API_KEYS], default=0) + 1
    _RUNTIME_COLLAB_API_KEYS.append(
        {
            "id": new_id,
            "key_name": key_name,
            "key_value": key_value,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "is_active": True,
        }
    )
    return new_id, key_value


def disable_runtime_collab_api_key(key_id: int) -> bool:
    for x in _RUNTIME_COLLAB_API_KEYS:
        if x["id"] == key_id:
            x["is_active"] = False
            return True
    return False


def get_collab_api_keys():
    """对外协作 / 撮合码验证 API 密钥列表（环境变量 + 运行时登记）。"""
    env_keys = _collab_api_keys_list()
    extra = [
        x["key_value"]
        for x in _RUNTIME_COLLAB_API_KEYS
        if x.get("is_active", True)
    ]
    return env_keys + extra


def build_external_interfaces() -> dict:
    """外部接口配置（原 external_interface_configs 表），可被运行时内存覆盖。"""
    return {
        "power_api": {
            "interface_type": "power_api",
            "interface_name": "电力数据接口",
            "base_url": (os.environ.get("POWER_API_BASE_URL") or "").rstrip("/"),
            "auth_type": os.environ.get("POWER_API_AUTH_TYPE") or "oauth2",
            "api_key": os.environ.get("POWER_API_KEY") or "",
            "client_id": os.environ.get("POWER_API_CLIENT_ID") or "",
            "client_secret": os.environ.get("POWER_API_CLIENT_SECRET") or "",
            "timeout_seconds": int(os.environ.get("POWER_API_TIMEOUT") or 10),
            "max_retries": int(os.environ.get("POWER_API_RETRIES") or 3),
            "field_mapping": None,
            "is_enabled": (os.environ.get("POWER_API_ENABLED", "false").lower() == "true"),
            "last_check_status": "unknown",
            "last_check_at": None,
            "last_check_error": None,
        },
        "tax_api": {
            "interface_type": "tax_api",
            "interface_name": "税务数据接口",
            "base_url": (os.environ.get("TAX_API_BASE_URL") or "").rstrip("/"),
            "auth_type": os.environ.get("TAX_API_AUTH_TYPE") or "api_key",
            "api_key": os.environ.get("TAX_API_KEY") or "",
            "client_id": os.environ.get("TAX_API_CLIENT_ID") or "",
            "client_secret": os.environ.get("TAX_API_CLIENT_SECRET") or "",
            "timeout_seconds": int(os.environ.get("TAX_API_TIMEOUT") or 10),
            "max_retries": int(os.environ.get("TAX_API_RETRIES") or 3),
            "field_mapping": None,
            "is_enabled": (os.environ.get("TAX_API_ENABLED", "false").lower() == "true"),
            "last_check_status": "unknown",
            "last_check_at": None,
            "last_check_error": None,
        },
        "industrial_commerce_api": {
            "interface_type": "industrial_commerce_api",
            "interface_name": "工商数据接口",
            "base_url": (os.environ.get("INDUSTRIAL_COMMERCE_API_BASE_URL") or "").rstrip("/"),
            "auth_type": os.environ.get("INDUSTRIAL_COMMERCE_AUTH_TYPE") or "api_key",
            "api_key": os.environ.get("INDUSTRIAL_COMMERCE_API_KEY") or "",
            "client_id": os.environ.get("INDUSTRIAL_COMMERCE_CLIENT_ID") or "",
            "client_secret": os.environ.get("INDUSTRIAL_COMMERCE_CLIENT_SECRET") or "",
            "timeout_seconds": int(os.environ.get("INDUSTRIAL_COMMERCE_TIMEOUT") or 15),
            "max_retries": int(os.environ.get("INDUSTRIAL_COMMERCE_RETRIES") or 3),
            "field_mapping": None,
            "is_enabled": (os.environ.get("INDUSTRIAL_COMMERCE_ENABLED", "false").lower() == "true"),
            "last_check_status": "unknown",
            "last_check_at": None,
            "last_check_error": None,
        },
    }


EXTERNAL_INTERFACES = build_external_interfaces()


class Config:
    APP_ENV = (os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "development").strip().lower()
    TRUSTED_ORIGINS = _trusted_origins(APP_ENV)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-12345'
    SECRET_KEY_IS_DEFAULT = not bool(os.environ.get("SECRET_KEY"))
    # Session cookies must not be sent over plain HTTP in production. SameSite
    # Lax keeps normal same-origin SPA navigation working while blocking the
    # common cross-site form-post cookie flow; HttpOnly prevents script access.
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = APP_ENV == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    # Production schema changes must be applied by the checked-in Alembic
    # migrations. Implicit ``create_all`` is retained only for local demos and
    # tests, where it keeps the bundled SQLite fixture convenient.
    AUTO_CREATE_SCHEMA = _env_bool("AUTO_CREATE_SCHEMA", APP_ENV != "production")
    # Production must label public records as production data by default. A
    # missing flag must never make real database rows look like demo content.
    PUBLIC_DATA_MODE = (
        os.environ.get('PUBLIC_DATA_MODE')
        or ('production' if APP_ENV == 'production' else 'demo')
    ).strip().lower()
    ENABLE_MOCK_API = _env_bool("ENABLE_MOCK_API", False)

    # 本地联调：顶层 /api/… 可通过 request_loader 自动登录，生产默认关闭。
    DISABLE_API_AUTH = _env_bool("DISABLE_API_AUTH", False)
    DEV_API_LOGIN_ENTERPRISE_ID = int(os.environ.get("DEV_API_LOGIN_ENTERPRISE_ID") or 123)

    # 生产部署时建议仅在一个独立进程启用调度器，避免 Gunicorn 多 worker 重复跑任务。
    # LIANYIPEI_SCHEDULER_ENABLED 是进程级覆盖项，供 Supervisor 将 Web 与调度器拆开运行。
    # 之所以单独提供覆盖项，是为了让 Web 与独立调度器可以分别声明进程
    # 行为；它优先于普通 SCHEDULER_ENABLED，但两者都不会覆盖已注入的环境变量。
    SCHEDULER_ENABLED = _env_bool(
        "LIANYIPEI_SCHEDULER_ENABLED",
        _env_bool("SCHEDULER_ENABLED", True),
    )
    CHAIN_XIAOYI_QUEUE_LEASE_SECONDS = _env_int("CHAIN_XIAOYI_QUEUE_LEASE_SECONDS", 900, 60, 86_400)
    # Supplier quote windows default to three days and can be overridden per
    # RFQ.  The worker expires unanswered records after this deadline.
    CHAIN_XIAOYI_RFQ_DEADLINE_HOURS = _env_int("CHAIN_XIAOYI_RFQ_DEADLINE_HOURS", 72, 1, 720)
    # A one-sentence RFQ preview may include only a bounded number of
    # authorized candidates; the buyer can still expand the list in the
    # review workspace before approving the send.
    CHAIN_XIAOYI_AUTO_RFQ_SUPPLIER_LIMIT = _env_int("CHAIN_XIAOYI_AUTO_RFQ_SUPPLIER_LIMIT", 5, 1, 20)
    # Public directory facts are shown with an explicit freshness state.  A
    # stale record remains discoverable for recall, but is never presented as
    # the latest verified fact.
    CHAINXIAOYI_DATA_MAX_AGE_DAYS = _env_int("CHAINXIAOYI_DATA_MAX_AGE_DAYS", 180, 1, 3650)
    # Production must never present deterministic rules as if a configured
    # model had executed. Operators can explicitly set ``false`` for a
    # controlled emergency window, but the safe default is fail-closed.
    _cloud_required_default = APP_ENV == "production"
    CHAINXIAOYI_CLOUD_REQUIRED = _env_bool("CHAINXIAOYI_CLOUD_REQUIRED", _cloud_required_default)
    # Production never treats a browser POST without an explicit confirmation
    # as approval to contact suppliers. Development keeps the legacy empty
    # body accepted for local smoke scripts; the UI always sends ``confirm``.
    CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL = _env_bool(
        "CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL",
        APP_ENV == "production",
    )
    SCHEDULER_LOCK_FILE = os.environ.get("SCHEDULER_LOCK_FILE") or "/tmp/lianyipei-scheduler.lock"
    # A file lock prevents duplicate schedulers on one host, while the Redis
    # heartbeat lets a web container observe a dedicated worker in a separate
    # PID namespace. The heartbeat expires automatically if the worker dies.
    WORKER_HEARTBEAT_KEY = os.environ.get("WORKER_HEARTBEAT_KEY") or "lianyipei:worker:heartbeat"
    WORKER_HEARTBEAT_TTL_SECONDS = _env_int("WORKER_HEARTBEAT_TTL_SECONDS", 30, 10, 300)

    # 为扩展注入的 /hybridaction/* JSONP 探测提供空响应；与业务无关，可减少本地 404
    BROWSER_EXTENSION_PROBE_NOOP = True

    # 本地开发可显式启用项目自带 SQLite，避免 MySQL 凭据失效时页面完全无法启动。
    # 仓库同时保留完整数据集和小型演示库时，优先使用完整数据集，避免搜索
    # 页面在未配置 DATABASE_URL 的新环境中静默显示为空。
    # 生产环境不允许静默回退，必须显式提供 DATABASE_URL。
    _configured_database_url = os.environ.get('DATABASE_URL')
    DATABASE_URL_CONFIGURED = bool(_configured_database_url)
    SQLALCHEMY_DATABASE_URI = _configured_database_url or (
        f"sqlite:///{_resolve_dev_sqlite_path()}"
        if _env_bool('LIANYIPEI_DEV_SQLITE_FALLBACK', False)
        else 'mysql+pymysql://root:password@localhost/lianyipei'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    NEO4J_URI = os.environ.get('NEO4J_URI') or 'bolt://localhost:7687'
    NEO4J_USER = os.environ.get('NEO4J_USER') or 'neo4j'
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD') or 'password'
    
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    MATERIAL_AV_MODE = (os.environ.get('MATERIAL_AV_MODE') or 'basic').strip().lower()
    CLAMAV_COMMAND = (os.environ.get('CLAMAV_COMMAND') or 'clamscan').strip()
    # In containerized production ClamAV normally runs as a separate clamd
    # service.  When set, material scans use the authenticated-free INSTREAM
    # protocol over this private network address instead of spawning a local
    # executable.  Keep the local command fallback for single-host installs.
    CLAMAV_HOST = (os.environ.get('CLAMAV_HOST') or '').strip()
    CLAMAV_PORT = _env_int('CLAMAV_PORT', 3310, 1, 65_535)
    CLAMAV_TIMEOUT_SECONDS = _env_int('CLAMAV_TIMEOUT_SECONDS', 30, 1, 120)
    MATERIAL_STORAGE_BACKEND = (os.environ.get('MATERIAL_STORAGE_BACKEND') or 'none').strip().lower()
    MATERIAL_STORAGE_ROOT = os.environ.get('MATERIAL_STORAGE_ROOT') or os.path.join(basedir, 'instance', 'materials')
    MATERIAL_ENCRYPTION_KEY = os.environ.get('MATERIAL_ENCRYPTION_KEY') or ''
    MATERIAL_S3_BUCKET = os.environ.get('MATERIAL_S3_BUCKET') or ''
    MATERIAL_S3_REGION = os.environ.get('MATERIAL_S3_REGION') or ''
    MATERIAL_S3_ENDPOINT_URL = os.environ.get('MATERIAL_S3_ENDPOINT_URL') or ''

    # 税务API配置（发票验证）
    TAX_API_URL = os.environ.get('TAX_API_URL') or ''
    TAX_API_KEY = os.environ.get('TAX_API_KEY') or ''
    ALLOW_MOCK_TAX_API = False

    # 电子合同默认禁用；生产必须配置真实供应商，服务层会失败关闭。
    ECONTRACT_PROVIDER = (os.environ.get('ECONTRACT_PROVIDER') or 'disabled').strip().lower()
    ECONTRACT_API_KEY = os.environ.get('ECONTRACT_API_KEY') or ''
    ECONTRACT_API_SECRET = os.environ.get('ECONTRACT_API_SECRET') or ''
    ECONTRACT_BASE_URL = (os.environ.get('ECONTRACT_BASE_URL') or '').strip().rstrip('/')

    SMTP_HOST = os.environ.get('SMTP_HOST') or ''
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME') or ''
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD') or ''
    SMTP_FROM_NAME = os.environ.get('SMTP_FROM_NAME') or '链易配'
    SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL') or ''
    SMTP_USE_TLS = _env_bool('SMTP_USE_TLS', True)

    # Provider delivery webhooks sign their JSON payload with this secret.
    # Keep it separate from WeChat callback credentials so rotating one
    # integration cannot invalidate the others.
    RFQ_DELIVERY_CALLBACK_SECRET = os.environ.get('RFQ_DELIVERY_CALLBACK_SECRET') or ''
    # Provider adapters use a separate secret when they submit normalized
    # supplier quote content.  Never reuse the delivery-status secret.
    RFQ_QUOTE_CALLBACK_SECRET = os.environ.get('RFQ_QUOTE_CALLBACK_SECRET') or ''
    # Signed inbound email gateway events; keep separate from both RFQ
    # delivery and normalized quote callback secrets.
    RFQ_EMAIL_INBOUND_SECRET = os.environ.get('RFQ_EMAIL_INBOUND_SECRET') or ''
    FULFILLMENT_CALLBACK_SECRET = os.environ.get('FULFILLMENT_CALLBACK_SECRET') or ''
    INBOUND_EMAIL_ENABLED = _env_bool('INBOUND_EMAIL_ENABLED', False)
    INBOUND_IMAP_HOST = os.environ.get('INBOUND_IMAP_HOST') or ''
    INBOUND_IMAP_PORT = _env_int('INBOUND_IMAP_PORT', 993, 1, 65_535)
    INBOUND_IMAP_USERNAME = os.environ.get('INBOUND_IMAP_USERNAME') or ''
    INBOUND_IMAP_PASSWORD = os.environ.get('INBOUND_IMAP_PASSWORD') or ''
    INBOUND_IMAP_FOLDER = os.environ.get('INBOUND_IMAP_FOLDER') or 'INBOX'
    INBOUND_EMAIL_CALLBACK_URL = os.environ.get('INBOUND_EMAIL_CALLBACK_URL') or ''
    INBOUND_EMAIL_BATCH_SIZE = _env_int('INBOUND_EMAIL_BATCH_SIZE', 20, 1, 100)
    INBOUND_EMAIL_TIMEOUT_SECONDS = _env_int('INBOUND_EMAIL_TIMEOUT_SECONDS', 20, 5, 120)

    # 高德地图：三密钥拆分（.env 中配置，勿提交明文）
    # 前端 JS API 2.0
    AMAP_JS_KEY = os.environ.get('AMAP_JS_KEY') or ''
    AMAP_SECURITY_JS_CODE = os.environ.get('AMAP_SECURITY_JS_CODE') or ''
    # 后端 Web 服务（地理编码、距离等 REST）
    AMAP_SERVICE_KEY = os.environ.get('AMAP_SERVICE_KEY') or ''
    # 兼容旧环境变量：未配置 SERVICE 时回退到 AMAP_KEY
    AMAP_KEY = os.environ.get('AMAP_KEY') or ''

    OLLAMA_BASE_URL = (os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")

    # 微信推送配置
    # 企业微信
    WORK_WECHAT_CORPID = os.environ.get('WORK_WECHAT_CORPID') or ''
    WORK_WECHAT_CORPSECRET = os.environ.get('WORK_WECHAT_CORPSECRET') or ''
    WORK_WECHAT_AGENTID = os.environ.get('WORK_WECHAT_AGENTID') or ''
    WORK_WECHAT_CALLBACK_TOKEN = os.environ.get('WORK_WECHAT_CALLBACK_TOKEN') or ''
    WORK_WECHAT_ENCODING_AES_KEY = os.environ.get('WORK_WECHAT_ENCODING_AES_KEY') or ''
    WORK_WECHAT_TIMEOUT_SECONDS = _env_int('WORK_WECHAT_TIMEOUT_SECONDS', 15, 3, 60)
    
    # 微信服务号
    WECHAT_SERVICE_APPID = os.environ.get('WECHAT_SERVICE_APPID') or ''
    WECHAT_SERVICE_SECRET = os.environ.get('WECHAT_SERVICE_SECRET') or ''
    WECHAT_TEMPLATE_ID = os.environ.get('WECHAT_TEMPLATE_ID') or ''  # 模板消息ID
    # 模板 data 字段名，须与公众号后台模板详情中 {{xxx.DATA}} 的 xxx 一致；主文案,时间 两个键，逗号分隔
    WECHAT_TEMPLATE_DATA_KEYS = os.environ.get('WECHAT_TEMPLATE_DATA_KEYS') or 'thing1,time2'
    # 服务号/测试号回调 Token，需与微信公众平台后台填写的 Token 一致
    WECHAT_CALLBACK_TOKEN = os.environ.get('WECHAT_CALLBACK_TOKEN') or ''

    # Hermes 本机网关 / 链易配内部控制接口
    HERMES_API_SERVER_URL = (os.environ.get("HERMES_API_SERVER_URL") or "http://127.0.0.1:8642/v1").rstrip("/")
    HERMES_API_SERVER_KEY = os.environ.get("HERMES_API_SERVER_KEY") or ""
    HERMES_WEIXIN_TARGET = os.environ.get("HERMES_WEIXIN_TARGET") or "weixin"
    HERMES_LIANYIPEI_TOKEN = os.environ.get("HERMES_LIANYIPEI_TOKEN") or ""
    HERMES_LIANYIPEI_BASE_URL = (os.environ.get("HERMES_LIANYIPEI_BASE_URL") or "").rstrip("/")
    HERMES_ACTION_CONFIRM_TTL_SECONDS = int(os.environ.get("HERMES_ACTION_CONFIRM_TTL_SECONDS") or 300)
    HERMES_ALLOWED_REMOTE_ADDRS = os.environ.get("HERMES_ALLOWED_REMOTE_ADDRS") or "127.0.0.1,::1,localhost"
    HERMES_TRUST_PROXY_HEADERS = _env_bool("HERMES_TRUST_PROXY_HEADERS", False)
    HERMES_API_TIMEOUT_SECONDS = float(os.environ.get("HERMES_API_TIMEOUT_SECONDS") or 30)

    DEFAULT_ALERT_THRESHOLDS = DEFAULT_ALERT_THRESHOLDS
    DEFAULT_CREDIT_RULES = DEFAULT_CREDIT_RULES
    EXTERNAL_INTERFACES = EXTERNAL_INTERFACES
