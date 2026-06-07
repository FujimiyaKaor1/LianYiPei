"""
测试配置验证
验证测试环境是否正确配置
"""
import pytest
from flask import current_app
from app import db
from app.models import Enterprise


@pytest.mark.unit
def test_app_exists(app):
    """测试应用实例是否存在"""
    assert app is not None
    assert current_app is not None


@pytest.mark.unit
def test_app_is_testing(app):
    """测试应用是否处于测试模式"""
    assert app.config['TESTING'] is True


@pytest.mark.unit
def test_database_uri(app):
    """测试数据库URI是否为SQLite内存数据库"""
    assert 'sqlite:///:memory:' in app.config['SQLALCHEMY_DATABASE_URI']


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
