"""
pytest 配置和 fixtures
提供测试所需的通用fixtures，包括应用实例、数据库、测试客户端等
"""
import os
import pytest
import tempfile
from datetime import datetime, date

from app import create_app, db
from app.models import (
    Enterprise,
    Message,
    Quote,
    Transaction,
)
from config import Config


class TestConfig(Config):
    """测试环境配置"""
    TESTING = True
    WTF_CSRF_ENABLED = False

    # 覆盖 Config 中硬编码的联调免登录，避免干扰鉴权相关用例
    DISABLE_API_AUTH = False
    DEV_API_LOGIN_ENTERPRISE_ID = None
    BROWSER_EXTENSION_PROBE_NOOP = False

    # 使用SQLite内存数据库进行测试
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # 强制走 invoice_validator 的模拟税务校验，避免 Hypothesis 大量用例触发真实 HTTP
    TAX_API_URL = ""
    TAX_API_KEY = ""
    
    # 禁用调度器（测试时不需要后台任务）
    SCHEDULER_ENABLED = False
    
    # 加快密码哈希（测试时不需要高安全性）
    BCRYPT_LOG_ROUNDS = 4


@pytest.fixture(scope='session')
def app():
    """
    创建测试应用实例（会话级别，整个测试会话只创建一次）
    """
    app = create_app(TestConfig)
    
    # 禁用调度器
    app.config['SCHEDULER_ENABLED'] = False
    
    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def _db(app):
    """
    创建测试数据库（函数级别，每个测试函数都会重新创建）
    """
    with app.app_context():
        db.create_all()

        yield db
        
        # 清理数据库
        db.session.remove()
        db.drop_all()


@pytest.fixture(scope='function')
def client(app, _db):
    """
    创建测试客户端（函数级别）
    """
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """
    创建CLI测试运行器（函数级别）
    """
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def auth_headers(client, test_enterprise):
    """
    返回认证头（用于API测试）
    """
    # 登录获取session
    with client:
        client.post('/auth/login', data={
            'username': test_enterprise.name,
            'password': 'test123456'
        })
        return {}


# ── 测试数据 fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def test_enterprise(_db):
    """创建测试企业"""
    enterprise = Enterprise(
        name='测试企业A',
        address='四川省成都市高新区',
        contact='张三',
        phone='13800138000',
        role='enterprise',
        credit_score=75.0,
        capacity=100,
        max_capacity=200,
        industry_code='C35',
        tech_keywords='电子元器件,芯片',
        business_scope='电子产品制造',
        daily_quote_count=0,
        daily_quote_limit=3,
        last_quote_reset_date=date.today(),
    )
    enterprise.set_password('test123456')
    db.session.add(enterprise)
    db.session.commit()
    return enterprise


@pytest.fixture(scope='function')
def test_supplier(_db):
    """创建测试供应商"""
    supplier = Enterprise(
        name='测试供应商B',
        address='四川省成都市武侯区',
        contact='李四',
        phone='13800138001',
        role='enterprise',
        credit_score=85.0,
        capacity=50,
        max_capacity=150,
        industry_code='C36',
        tech_keywords='原材料,金属加工',
        business_scope='金属制品制造',
    )
    supplier.set_password('test123456')
    db.session.add(supplier)
    db.session.commit()
    return supplier


@pytest.fixture(scope='function')
def test_admin(_db):
    """创建测试管理员"""
    admin = Enterprise(
        name='测试管理员',
        role='admin',
        credit_score=100.0,
    )
    admin.set_password('admin123456')
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture(scope='function')
def test_government(_db):
    """创建测试政府用户"""
    gov = Enterprise(
        name='成都市经信局',
        role='government',
        credit_score=100.0,
    )
    gov.set_password('gov123456')
    db.session.add(gov)
    db.session.commit()
    return gov


@pytest.fixture(scope='function')
def test_enterprises(_db):
    """创建测试买卖双方企业"""
    buyer = Enterprise(
        name='测试买方企业',
        address='四川省成都市高新区',
        contact='买方联系人',
        phone='13800138000',
        role='enterprise',
        credit_score=75.0,
    )
    buyer.set_password('test123456')
    db.session.add(buyer)
    
    seller = Enterprise(
        name='测试卖方企业',
        address='四川省成都市武侯区',
        contact='卖方联系人',
        phone='13800138001',
        role='enterprise',
        credit_score=85.0,
    )
    seller.set_password('test123456')
    db.session.add(seller)
    
    db.session.commit()
    
    return {
        'buyer': buyer,
        'seller': seller
    }


@pytest.fixture(scope='function')
def db_session(_db):
    """返回数据库会话"""
    return db.session


@pytest.fixture(scope='function')
def test_credit_history(_db, test_enterprise):
    """创建测试信用分变更历史（Enterprise.credit_score_events JSON）"""
    test_enterprise.credit_score_events = [
        {
            "id": "test-h1",
            "old_score": 70.0,
            "new_score": 75.0,
            "change_value": 5.0,
            "change_type": "fulfillment_on_time",
            "reason": "按时履约",
            "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
    ]
    db.session.add(test_enterprise)
    db.session.commit()
    return test_enterprise.credit_score_events[0]


@pytest.fixture(scope='function')
def test_fulfillment(_db, test_enterprise, test_supplier):
    """创建测试履约数据（Transaction + invoice_info）"""
    fulfillment = Transaction(
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name='测试产品',
        status='completed',
        match_code='LYP2401150001ABC',
        invoice_info={
            'invoice_no': '12345678',
            'invoice_amount': 50000.0,
            'on_time': True,
            'quality_rating': 5,
            'verified': True,
        },
        fulfillment_status='verified',
    )
    db.session.add(fulfillment)
    db.session.commit()
    return fulfillment


@pytest.fixture(scope='function')
def test_quote(_db, test_supplier, test_enterprise):
    """创建测试报价（依赖询价单）"""
    from app.models import Inquiry

    inq = Inquiry(
        poster_id=test_enterprise.id,
        direction='demand',
        product_name='电阻',
        status='open',
    )
    db.session.add(inq)
    db.session.flush()
    quote = Quote(
        inquiry_id=inq.id,
        supplier_id=test_supplier.id,
        product_name='电阻',
        price=0.5,
        quantity=10000,
        unit='个',
        delivery_days=7,
        status='active',
    )
    db.session.add(quote)
    db.session.commit()
    return quote


@pytest.fixture(scope='function')
def test_message(_db, test_enterprise):
    """创建测试消息"""
    message = Message(
        recipient_id=test_enterprise.id,
        message_type='system',
        title='测试消息',
        content='这是一条测试消息',
        is_read=False,
        priority='normal',
    )
    db.session.add(message)
    db.session.commit()
    return message


# ── Hypothesis 策略 ────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def hypothesis_settings():
    """
    Hypothesis 配置
    用于属性测试
    """
    from hypothesis import settings, Verbosity
    
    return settings(
        max_examples=100,  # 每个测试运行100个例子
        verbosity=Verbosity.verbose,
        deadline=None,  # 禁用超时检查
    )
