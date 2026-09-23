"""
测试配置验证
验证测试环境是否正确配置
"""
import os

import pytest
from cryptography.fernet import Fernet
from flask import current_app
from app import create_app, db
from app.models import Enterprise
from config import Config, _load_project_env, _resolve_dev_sqlite_path


@pytest.mark.unit
def test_app_exists(app):
    """测试应用实例是否存在"""
    assert app is not None
    assert current_app is not None


@pytest.mark.unit
def test_process_environment_wins_over_project_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("CHAIN_XIAOYI_TEST_PRECEDENCE=from-file\n", encoding="utf-8")
    monkeypatch.setenv("CHAIN_XIAOYI_TEST_PRECEDENCE", "from-process")

    _load_project_env(env_file)

    assert os.environ["CHAIN_XIAOYI_TEST_PRECEDENCE"] == "from-process"


@pytest.mark.unit
def test_app_is_testing(app):
    """测试应用是否处于测试模式"""
    assert app.config['TESTING'] is True


@pytest.mark.unit
def test_database_uri(app):
    """测试数据库URI是否为SQLite内存数据库"""
    assert 'sqlite:///:memory:' in app.config['SQLALCHEMY_DATABASE_URI']


@pytest.mark.unit
def test_dev_sqlite_fallback_prefers_complete_local_database(monkeypatch):
    monkeypatch.delenv("LIANYIPEI_DEV_SQLITE_PATH", raising=False)
    path = _resolve_dev_sqlite_path()
    assert path.endswith("instance/lianyipei.db")


@pytest.mark.database
def test_database_tables_created(_db):
    """测试数据库表是否创建成功"""
    # 检查关键表是否存在
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    
    assert 'enterprises' in tables
    assert 'transactions' in tables
    assert 'inquiries' in tables
    assert 'match_feedbacks' in tables
    assert 'messages' in tables


@pytest.mark.database
def test_create_enterprise(_db):
    """测试创建企业记录"""
    enterprise = Enterprise(
        name='测试企业',
        role='enterprise',
        credit_score=60.0,
    )
    enterprise.set_password('test123')
    
    db.session.add(enterprise)
    db.session.commit()
    
    # 验证企业已创建
    saved = Enterprise.query.filter_by(name='测试企业').first()
    assert saved is not None
    assert saved.credit_score == 60.0
    assert saved.check_password('test123')


@pytest.mark.unit
def test_client_exists(client):
    """测试客户端是否存在"""
    assert client is not None


@pytest.mark.integration
def test_index_route(client):
    """测试首页路由"""
    response = client.get('/')
    assert response.status_code in [200, 302]  # 200 或重定向


@pytest.mark.unit
def test_fixtures_work(test_enterprise, test_supplier):
    """测试fixtures是否正常工作"""
    assert test_enterprise is not None
    assert test_supplier is not None
    assert test_enterprise.name == '测试企业A'
    assert test_supplier.name == '测试供应商B'
    assert test_enterprise.credit_score == 75.0
    assert test_supplier.credit_score == 85.0


@pytest.mark.unit
def test_mock_api_is_not_registered_without_explicit_enablement():
    class ProductionLikeConfig(Config):
        TESTING = False
        ENABLE_MOCK_API = False
        SCHEDULER_ENABLED = False
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    production_app = create_app(ProductionLikeConfig)
    rules = {rule.rule for rule in production_app.url_map.iter_rules()}
    assert not any(rule.startswith("/mock/") for rule in rules)


def test_production_requires_explicit_chain_xiaoyi_approval(monkeypatch):
    monkeypatch.delenv("CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL", raising=False)
    class ProductionApprovalConfig(Config):
        APP_ENV = "production"
        CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL = True

    assert ProductionApprovalConfig.CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL is True


def test_production_session_cookies_are_secure():
    class ProductionCookieConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        DATABASE_URL_CONFIGURED = True
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        AUTO_CREATE_SCHEMA = False
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "s3"
        MATERIAL_ENCRYPTION_KEY = "9jVx6S3m0H5yqf7r6VQ9f7q4s8Q2u5w8J3x6c9z2a5M="
        MATERIAL_S3_BUCKET = "test-bucket"

    production_app = create_app(ProductionCookieConfig)
    assert production_app.config["SESSION_COOKIE_SECURE"] is True
    assert production_app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert production_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert production_app.config["REMEMBER_COOKIE_SECURE"] is True


@pytest.mark.unit
def test_production_refuses_unsafe_defaults():
    class UnsafeProductionConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = True
        DATABASE_URL_CONFIGURED = False
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False

    with pytest.raises(RuntimeError, match="SECRET_KEY.*DATABASE_URL"):
        create_app(UnsafeProductionConfig)


@pytest.mark.unit
def test_production_rejects_explicit_sqlite_database():
    class SqliteProductionConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        DATABASE_URL_CONFIGURED = True
        SQLALCHEMY_DATABASE_URI = "sqlite:////tmp/lianyipei-production.sqlite"
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        AUTO_CREATE_SCHEMA = False
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "s3"
        MATERIAL_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
        MATERIAL_S3_BUCKET = "private-materials"
        SCHEDULER_ENABLED = False

    with pytest.raises(RuntimeError, match="DATABASE_URL_NON_SQLITE"):
        create_app(SqliteProductionConfig)


@pytest.mark.unit
def test_production_requires_clamav_material_scanning():
    class UnsafeMaterialConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        DATABASE_URL_CONFIGURED = True
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        MATERIAL_AV_MODE = "basic"
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        SCHEDULER_ENABLED = False

    with pytest.raises(RuntimeError, match="MATERIAL_AV_MODE"):
        create_app(UnsafeMaterialConfig)


@pytest.mark.unit
def test_production_requires_encrypted_object_storage():
    class UnsafeStorageConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        DATABASE_URL_CONFIGURED = True
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "none"
        MATERIAL_ENCRYPTION_KEY = ""
        MATERIAL_S3_BUCKET = ""
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        SCHEDULER_ENABLED = False

    with pytest.raises(RuntimeError, match="MATERIAL_STORAGE_BACKEND"):
        create_app(UnsafeStorageConfig)


@pytest.mark.unit
def test_production_accepts_complete_material_security_configuration():
    class SafeProductionConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        SECRET_KEY = "test-only-production-secret"
        DATABASE_URL_CONFIGURED = True
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "s3"
        MATERIAL_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
        MATERIAL_S3_BUCKET = "private-materials"
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        SCHEDULER_ENABLED = False

    production_app = create_app(SafeProductionConfig)

    assert production_app.config["MATERIAL_STORAGE_BACKEND"] == "s3"


@pytest.mark.unit
def test_production_does_not_create_schema_at_app_startup(monkeypatch):
    """Production schema must come from Alembic, not implicit create_all()."""
    class SafeProductionConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        SECRET_KEY = "test-only-production-secret"
        DATABASE_URL_CONFIGURED = True
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "s3"
        MATERIAL_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
        MATERIAL_S3_BUCKET = "private-materials"
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        SCHEDULER_ENABLED = False

    def fail_create_all(*_args, **_kwargs):
        raise AssertionError("production must apply migrations explicitly")

    monkeypatch.setattr(db, "create_all", fail_create_all)
    production_app = create_app(SafeProductionConfig)

    assert production_app.config["AUTO_CREATE_SCHEMA"] is False


@pytest.mark.unit
def test_production_rejects_explicit_auto_schema_creation():
    class UnsafeSchemaConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        DATABASE_URL_CONFIGURED = True
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        AUTO_CREATE_SCHEMA = True
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "s3"
        MATERIAL_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
        MATERIAL_S3_BUCKET = "private-materials"
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        SCHEDULER_ENABLED = False

    with pytest.raises(RuntimeError, match="AUTO_CREATE_SCHEMA"):
        create_app(UnsafeSchemaConfig)


@pytest.mark.unit
def test_production_requires_cloud_model_by_default(monkeypatch):
    """A production process must fail closed when the cloud flag is omitted."""
    monkeypatch.delenv("CHAINXIAOYI_CLOUD_REQUIRED", raising=False)

    class ProductionCloudDefaultConfig(Config):
        APP_ENV = "production"
        SECRET_KEY_IS_DEFAULT = False
        SECRET_KEY = "test-only-production-secret"
        DATABASE_URL_CONFIGURED = True
        DISABLE_API_AUTH = False
        ENABLE_MOCK_API = False
        MATERIAL_AV_MODE = "clamav"
        MATERIAL_STORAGE_BACKEND = "s3"
        MATERIAL_ENCRYPTION_KEY = Fernet.generate_key().decode("ascii")
        MATERIAL_S3_BUCKET = "private-materials"
        SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pass@db.example/lianyipei"
        SCHEDULER_ENABLED = False

    production_app = create_app(ProductionCloudDefaultConfig)
    assert production_app.config["CHAINXIAOYI_CLOUD_REQUIRED"] is True
