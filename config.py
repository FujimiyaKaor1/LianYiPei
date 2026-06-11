import os
import secrets
from datetime import datetime
from urllib.parse import urlparse

from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
# 必须用 override：否则系统/IDE 里残留的 WECHAT_* 会优先于 .env，易出现「token 是 A 公众号、模板 ID 是 B 测试号」→ 40037
load_dotenv(os.path.join(basedir, ".env"), override=True)

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
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-12345'

    # 本地联调：顶层 /api/… 可通过 request_loader 自动登录，生产默认关闭。
    DISABLE_API_AUTH = _env_bool("DISABLE_API_AUTH", False)
    DEV_API_LOGIN_ENTERPRISE_ID = int(os.environ.get("DEV_API_LOGIN_ENTERPRISE_ID") or 123)

    # 生产部署时建议仅在一个独立进程启用调度器，避免 Gunicorn 多 worker 重复跑任务。
    SCHEDULER_ENABLED = _env_bool("SCHEDULER_ENABLED", True)
    SCHEDULER_LOCK_FILE = os.environ.get("SCHEDULER_LOCK_FILE") or "/tmp/lianyipei-scheduler.lock"

    # 为扩展注入的 /hybridaction/* JSONP 探测提供空响应；与业务无关，可减少本地 404
    BROWSER_EXTENSION_PROBE_NOOP = True

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:password@localhost/lianyipei'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    NEO4J_URI = os.environ.get('NEO4J_URI') or 'bolt://localhost:7687'
    NEO4J_USER = os.environ.get('NEO4J_USER') or 'neo4j'
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD') or 'password'
    
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://localhost:6379/0'
    
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # 税务API配置（发票验证）
    TAX_API_URL = os.environ.get('TAX_API_URL') or ''
    TAX_API_KEY = os.environ.get('TAX_API_KEY') or ''

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
    
    # 微信服务号
    WECHAT_SERVICE_APPID = os.environ.get('WECHAT_SERVICE_APPID') or ''
    WECHAT_SERVICE_SECRET = os.environ.get('WECHAT_SERVICE_SECRET') or ''
    WECHAT_TEMPLATE_ID = os.environ.get('WECHAT_TEMPLATE_ID') or ''  # 模板消息ID
    # 模板 data 字段名，须与公众号后台模板详情中 {{xxx.DATA}} 的 xxx 一致；主文案,时间 两个键，逗号分隔
    WECHAT_TEMPLATE_DATA_KEYS = os.environ.get('WECHAT_TEMPLATE_DATA_KEYS') or 'thing1,time2'

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
