# 链易配 - 产业链供需智能匹配平台

基于 Flask + MySQL + Neo4j 构建的产业链供需智能匹配平台，助力县域经济高质量发展。

## 功能特性

- **企业画像**: 自动生成企业标签和信用评分
- **供需发布**: 企业可发布供应/需求信息
- **智能匹配**: 多维度加权算法精准匹配供需双方
- **产业链图谱**: Neo4j知识图谱可视化展示产业链关系
- **供应链预警**: 三级预警机制监测供应链风险
- **政府大屏**: 关键指标可视化展示

## 技术栈

- **后端**: Flask 2.3+
- **数据库**: MySQL 8.0, Neo4j 4.4+
- **缓存**: Redis 6.0+ (可选)
- **前端**: Bootstrap 5.1, ECharts

## 快速开始

### 1. 环境准备

确保已安装以下软件：
- Python 3.9+
- MySQL 8.0
- Neo4j 4.4+ (可选，用于产业链图谱功能)
- Redis 6.0+ (可选，用于缓存)

### 2. 安装依赖

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，修改数据库连接信息：

```
SECRET_KEY=your-secret-key
DATABASE_URL=mysql+pymysql://root:password@localhost/lianyipei
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### 4. 创建数据库

```sql
CREATE DATABASE lianyipei CHARACTER SET utf8mb4;
```

### 5. 初始化数据库

```bash
python scripts/db/init_db.py
```

### 6. 生成测试数据

```bash
python scripts/seed/generate_test_data.py
```

### 6.1 生成完整演示数据

```bash
python scripts/seed/seed_demo_full_flow.py
```

### 7. 导入产业链关系 (需要Neo4j)

```bash
python scripts/seed/import_graph.py
```

### 8. 启动服务

```bash
python run.py
```

访问 http://localhost:5000

## 测试账号

- **企业用户**: 企业名称 / 123456
- **管理员**: admin / admin123

## 项目文档

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **架构文档**（前端层、控制层、业务层、数据层） |
| [DATA_GUIDE.md](DATA_GUIDE.md) | 数据使用说明 |
| [TECH_STACK.md](TECH_STACK.md) | 技术栈实现说明 |
| [docs/HERMES_INTEGRATION.md](docs/HERMES_INTEGRATION.md) | Hermes 微信智能告警与确认后远程操作 |
| [docs/PRODUCTION_DEPLOYMENT.md](docs/PRODUCTION_DEPLOYMENT.md) | 云服务器 / ECS 生产部署建议 |
| [启动说明.md](启动说明.md) | 启动与排错指南 |

## 项目结构（按架构分层）

详见 [ARCHITECTURE.md](ARCHITECTURE.md)，简要结构如下：

```
app/
├── templates/       # 前端层：Jinja2 + Bootstrap 5 + ECharts/PyEcharts/AntV
├── routes/          # 控制层：认证、企业、供需、匹配、大屏
├── services/        # 业务层：企业画像、匹配、图谱、预警、时序、LLM、CLIP
└── models.py        # 数据层：SQLAlchemy 模型
```

## API接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/match` | POST | 智能匹配 |
| `/api/alerts` | GET | 获取预警列表 |
| `/api/graph-data` | GET | 获取图谱数据 |
| `/api/stats` | GET | 获取统计数据 |

## 匹配算法

匹配度分数由以下因素加权计算：

| 因子 | 权重 | 说明 |
|------|------|------|
| 产品匹配度 | 40分 | 是否生产该产品 |
| 地理位置 | 20分 | 距离越近分数越高 |
| 信用评分 | 15分 | 企业信用分归一化 |
| 产能匹配 | 10分 | 供应商产能与需求量匹配 |
| 历史合作 | 15分 | 是否曾有交易记录 |

## 预警等级

| 等级 | 风险维度 | 触发条件 |
|------|----------|----------|
| 红色 | 国际进口依赖 | 进口来源国单一且占比>60% |
| 橙色 | 省外采购依赖 | 省外采购占比>70% |
| 黄色 | 本地供应短缺 | 本地供应商数量<3家 |

## 许可证

MIT License
