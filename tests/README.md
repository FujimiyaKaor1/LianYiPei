# 测试指南

## 概述

本项目使用 pytest 作为测试框架，支持单元测试、集成测试和属性测试（基于 hypothesis）。

## 安装测试依赖

```bash
pip install -r requirements.txt
```

主要测试依赖：
- `pytest` - 测试框架
- `pytest-flask` - Flask 应用测试支持
- `pytest-cov` - 代码覆盖率
- `hypothesis` - 属性测试框架

## 运行测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试文件

```bash
pytest tests/test_credit_engine.py
```

### 运行特定测试类

```bash
pytest tests/test_credit_engine.py::TestCreditScoreCalculation
```

### 运行特定测试函数

```bash
pytest tests/test_credit_engine.py::TestCreditScoreCalculation::test_calculate_base_score
```

### 按标记运行测试

```bash
# 只运行单元测试
pytest -m unit

# 只运行信用分相关测试
pytest -m credit

# 只运行API测试
pytest -m api

# 只运行数据库测试
pytest -m database

# 只运行属性测试
pytest -m property
```

### 查看详细输出

```bash
pytest -v
```

### 查看测试覆盖率

```bash
pytest --cov=app --cov-report=html
```

覆盖率报告会生成在 `htmlcov/index.html`

### 只运行失败的测试

```bash
pytest --lf
```

### 停在第一个失败的测试

```bash
pytest -x
```

## 测试标记

项目定义了以下测试标记：

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.property` - 属性测试（基于hypothesis）
- `@pytest.mark.slow` - 慢速测试
- `@pytest.mark.credit` - 信用分相关测试
- `@pytest.mark.api` - API接口测试
- `@pytest.mark.scheduler` - 定时任务测试
- `@pytest.mark.database` - 数据库相关测试

## 测试结构

```
tests/
├── __init__.py              # 测试包初始化
├── conftest.py              # pytest配置和fixtures
├── test_config.py           # 配置验证测试
├── test_credit_engine.py    # 信用分引擎测试
├── test_api.py              # API接口测试
├── test_scheduler.py        # 定时任务测试
├── property/                # 属性测试
│   ├── __init__.py
│   ├── strategies.py        # Hypothesis策略
│   └── test_credit_properties.py
└── README.md                # 本文件
```

## Fixtures

### 应用和数据库

- `app` - Flask应用实例（会话级别）
- `_db` - 测试数据库（函数级别，每个测试都会重新创建）
- `client` - 测试客户端
- `runner` - CLI测试运行器

### 测试数据

- `test_enterprise` - 测试企业（信用分75）
- `test_supplier` - 测试供应商（信用分85）
- `test_admin` - 测试管理员
- `test_government` - 测试政府用户
- `test_credit_history` - 测试信用分历史记录
- `test_fulfillment` - 测试履约数据
- `test_quote` - 测试报价
- `test_message` - 测试消息
- `test_api_key` - 测试API密钥

### 认证

- `auth_headers` - 认证头（用于API测试）

## 编写测试

### 单元测试示例

```python
import pytest
from app.services.credit_engine import calculate_credit_score

@pytest.mark.unit
@pytest.mark.credit
def test_calculate_credit_score(_db, test_enterprise):
    """测试信用分计算"""
    score = calculate_credit_score(test_enterprise.id)
    assert 0.0 <= score <= 100.0
```

### 集成测试示例

```python
import pytest

@pytest.mark.integration
@pytest.mark.api
def test_get_credit_score(client, test_enterprise):
    """测试获取信用分API"""
    response = client.get(f'/api/credit/score/{test_enterprise.id}')
    assert response.status_code == 200
    data = response.get_json()
    assert 'credit_score' in data
```

### 属性测试示例

```python
import pytest
from hypothesis import given
from hypothesis import strategies as st

@pytest.mark.property
@given(score_change=st.floats(min_value=-50, max_value=50))
def test_credit_score_range_property(_db, test_enterprise, score_change):
    """属性测试：信用分始终在0-100之间"""
    from app.services.credit_engine import update_credit_score
    
    result = update_credit_score(
        test_enterprise.id,
        'custom',
        change_value=score_change,
        reason='属性测试'
    )
    
    assert 0.0 <= result['new_score'] <= 100.0
```

## 测试数据库

测试使用 SQLite 内存数据库（`:memory:`），每个测试函数都会：

1. 创建新的数据库
2. 创建所有表
3. 插入默认信用分规则
4. 运行测试
5. 清理数据库

这确保了测试之间的隔离性。

## 持续集成

在CI/CD流程中运行测试：

```bash
# 运行所有测试并生成覆盖率报告
pytest --cov=app --cov-report=xml --cov-report=term

# 检查覆盖率是否达到要求（例如80%）
pytest --cov=app --cov-fail-under=80
```

## 调试测试

### 使用pdb调试

```python
def test_something():
    import pdb; pdb.set_trace()
    # 测试代码
```

### 查看打印输出

```bash
pytest -s
```

### 查看详细的失败信息

```bash
pytest -vv
```

## 最佳实践

1. **测试隔离**: 每个测试应该独立，不依赖其他测试的执行顺序
2. **使用fixtures**: 复用测试数据和设置
3. **清晰的测试名称**: 测试函数名应该清楚地描述测试内容
4. **一个测试一个断言**: 尽量每个测试只验证一个行为
5. **使用标记**: 合理使用标记来组织测试
6. **测试边界条件**: 测试正常情况、边界情况和异常情况
7. **保持测试快速**: 单元测试应该快速执行

## 故障排查

### 导入错误

确保项目根目录在 Python 路径中：

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### 数据库错误

检查测试配置是否正确使用内存数据库：

```python
# tests/conftest.py
class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
```

### Fixture未找到

确保 `conftest.py` 在正确的位置，pytest会自动发现它。

## 参考资源

- [pytest 文档](https://docs.pytest.org/)
- [pytest-flask 文档](https://pytest-flask.readthedocs.io/)
- [hypothesis 文档](https://hypothesis.readthedocs.io/)
