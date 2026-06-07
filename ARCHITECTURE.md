# 链易配 - 项目架构文档

> 基于代码实际调用关系整理，未使用部分已标注或移除。

## 系统架构总览

```
┌───────────────────────────────────────────────────────────┐
│                    前端层（服务端渲染）                      │
│     Jinja2 模板 + Bootstrap 5 + JavaScript + 图表库        │
├───────────────────────────────────────────────────────────┤
│                     控制层（Flask 路由）                     │
│   认证路由 | 企业管理路由 | 供需路由 | 匹配路由 | 大屏路由    │
├───────────────────────────────────────────────────────────┤
│                      业务逻辑层                             │
│  ├─ 企业画像服务                                            │
│  ├─ 智能匹配引擎                                            │
│  ├─ 知识图谱服务                                            │
│  ├─ 供需管理（routes 内联）                                 │
│  ├─ 预警服务（含时序预测）                                  │
│  ├─ 数据统计（routes 内联）                                 │
│  ├─ LLM 自然语言查询                                        │
│  └─ CLIP 图文匹配                                           │
├───────────────────────────────────────────────────────────┤
│                      数据访问层                             │
│    SQLAlchemy(MySQL) | Neo4j | 向量嵌入(CLIP 可选)         │
└───────────────────────────────────────────────────────────┘
```

---

## 一、前端层（服务端渲染）

| 技术 | 用途 | 对应位置 |
|------|------|----------|
| Jinja2 | 模板引擎 | `app/templates/` |
| Bootstrap 5 | UI 框架 | `layout/base.html`（CDN） |
| Bootstrap Icons | 图标 | `layout/base.html`（CDN） |
| ECharts 5 | 图谱、折线图、饼图 | `dashboard/stats.html`, `dashboard/graph.html` |
| PyEcharts | 服务端柱状图 | `dashboard.py` → `_render_pyecharts_chart()` |
| AntV G2 | 柱状图 | `dashboard/stats.html`（CDN） |
| JavaScript | 表单、API 调用、图表交互 | 各模板 `{% block extra_js %}` |

### 模板文件（实际存在）

```
app/templates/
├── layout/base.html
├── index.html
├── auth/login.html, register.html
├── enterprise/profile.html, edit.html, products.html, add_product.html
├── demand/list.html, my_demands.html, create.html
├── match/index.html
├── dashboard/stats.html, graph.html, alerts.html, alert_denied.html
├── ai_query.html
└── clip_match.html
```

---

## 二、控制层（Flask 路由）

| 蓝图 | 前缀 | 功能 | 文件 |
|------|------|------|------|
| 认证 | `/auth` | 注册、登录、登出 | `routes/auth.py` |
| 企业管理 | `/enterprise` | 资料、产品管理 | `routes/enterprise.py` |
| 供需 | `/demand` | 发布、列表、关闭 | `routes/demand.py` |
| 匹配 | `/match` | 智能匹配 | `routes/match.py` |
| 大屏 | `/dashboard` | 统计、图谱、预警、报告 | `routes/dashboard.py` |
| 主路由 | `/` | 首页、智能问答、图文匹配 | `routes/main.py` |

### 路由与调用关系

| 路由 | 调用的服务 |
|------|------------|
| `/enterprise/profile` | `profile.build_enterprise_profile` |
| `/match/`, `/match/api` | `matcher.match_suppliers` |
| `/dashboard/stats` | `_render_pyecharts_chart`, `forecaster`（前端 fetch） |
| `/dashboard/graph` | 前端 fetch `get_full_graph` |
| `/dashboard/api/graph-data` | `graph_manager.get_full_graph` |
| `/dashboard/api/graph-pagerank` | `graph_algorithms.pagerank_products` |
| `/dashboard/api/graph-communities` | `graph_algorithms.community_detection` |
| `/dashboard/api/forecast` | `forecaster.forecast_supply_demand` |
| `/dashboard/api/run-alerts` | `alerter.run_all_checks` |
| `/dashboard/settings/thresholds` | `alerter.get_threshold` |
| `/dashboard/report` | `alerter.generate_chain_risk_report` |
| `/api/ai-query` | `llm_query.nl_query` |
| `/api/clip-match` | `clip_matcher.clip_available`, `match_image_to_products` |

---

## 三、业务逻辑层（按实际调用归类）

### 3.1 企业画像服务

| 模块 | 状态 | 说明 |
|------|------|------|
| `build_enterprise_profile` | ✅ 使用 | `enterprise/profile` 调用 |
| `update_credit_score` | ❌ 未使用 | 已导出，无路由调用 |
| `get_enterprise_summary` | ❌ 未使用 | 已导出，无路由调用 |

### 3.2 智能匹配引擎

| 模块 | 状态 | 说明 |
|------|------|------|
| `match_suppliers` | ✅ 使用 | `match` 路由调用 |
| `calculate_distance` | ✅ 使用 | `match_suppliers` 内部调用 |
| `find_nearby_suppliers` | ❌ 未使用 | 无路由调用 |

### 3.3 知识图谱服务

| 模块 | 状态 | 说明 |
|------|------|------|
| `get_full_graph` | ✅ 使用 | `dashboard/api/graph-data` |
| `create_relation` | ✅ 使用 | `import_relations_from_csv`（脚本） |
| `create_product_node` | ✅ 使用 | `create_relation` 内部 |
| `find_upstream`, `find_downstream` | ❌ 未使用 | 图谱页用前端过滤 |
| `get_graph`, `close_driver` | ❌ 未使用 | 无调用方 |

### 3.4 图算法（NetworkX）

| 模块 | 状态 | 说明 |
|------|------|------|
| `pagerank_products` | ✅ 使用 | `dashboard/api/graph-pagerank` |
| `community_detection` | ✅ 使用 | `dashboard/api/graph-communities` |
| `graph_stats` | ❌ 未使用 | 已导入但未调用 |
| `get_critical_paths` | ❌ 未使用 | 无路由调用 |

### 3.5 预警服务

| 模块 | 状态 | 说明 |
|------|------|------|
| `run_all_checks` | ✅ 使用 | 大屏刷新、定时任务 |
| `generate_chain_risk_report` | ✅ 使用 | 报告下载 |
| `get_threshold` | ✅ 使用 | 阈值设置页 |
| `get_active_alerts`, `get_alerts_by_level`, `get_alerts_by_dimension` | ❌ 未使用 | 路由直接用 `Alert.query` |

### 3.6 时序预测

| 模块 | 状态 | 说明 |
|------|------|------|
| `forecast_supply_demand` | ✅ 使用 | `dashboard/api/forecast` |

### 3.7 LLM 与 CLIP

| 模块 | 状态 | 说明 |
|------|------|------|
| `llm_query.nl_query` | ✅ 使用 | 智能问答 |
| `clip_matcher` | ✅ 使用 | 图文匹配（需安装 open-clip-torch） |

### 3.8 联邦学习

| 模块 | 状态 | 说明 |
|------|------|------|
| `scripts/fedlab_demo.py` | ⚪ 独立脚本 | 非应用内调用，演示用 |

---

## 四、数据访问层

| 存储 | 状态 | 用途 |
|------|------|------|
| **MySQL (SQLAlchemy)** | ✅ 使用 | 企业、产品、供需、交易、预警、进口依赖、专利 |
| **Neo4j** | ✅ 使用 | `neo4j` 驱动，`graph_manager` 访问图谱 |
| **Redis** | ❌ 未使用 | 仅 config 配置，应用内无调用（依赖已从 requirements 移除） |
| **py2neo** | ✅ 已移除 | requirements 已移除，代码统一使用 `neo4j` 官方驱动 |

### 数据模型（MySQL，实际使用）

| 表 | 使用情况 |
|----|----------|
| enterprises | ✅ |
| products | ✅ |
| demands | ✅ |
| transactions | ✅ 匹配引擎历史合作 |
| alerts | ✅ |
| alert_thresholds | ✅ |
| product_import_risks | ✅ 预警进口依赖 |
| enterprise_patents | ✅ 种子数据，企业画像未展示 |

---

## 五、项目目录与职责

```
链易配/
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── enterprise.py
│   │   ├── demand.py
│   │   ├── match.py
│   │   ├── dashboard.py
│   │   └── main.py
│   ├── services/
│   │   ├── profile.py       # 企业画像
│   │   ├── matcher.py       # 智能匹配
│   │   ├── graph_manager.py # 知识图谱
│   │   ├── graph_algorithms.py
│   │   ├── alerter.py
│   │   ├── forecaster.py
│   │   ├── llm_query.py
│   │   └── clip_matcher.py
│   ├── templates/
│   └── static/
├── scripts/
├── data/
├── config.py
└── run.py
```

---

## 六、未使用项汇总（可考虑清理）

| 类型 | 项 | 建议 |
|------|-----|------|
| 路由 | `/about` | ✅ 已删除（无模板会 404） |
| 服务 | `update_credit_score`, `get_enterprise_summary` | 可移出导出或删除 |
| 服务 | `find_nearby_suppliers`, `get_graph`, `close_driver` | 保留供扩展 |
| 服务 | `find_upstream`, `find_downstream` | 可作 API 供图谱页后端查询 |
| 服务 | `graph_stats`, `get_critical_paths` | 可移出导入或后续接入 |
| 服务 | `get_active_alerts`, `get_alerts_by_*` | 可替代直接 Query |
| 依赖 | py2neo | ✅ 已移除 |
| 依赖 | redis | ✅ 已移除（应用内未使用） |
| 配置 | REDIS_URL | 当前未用，可保留待用（如未来接缓存/任务队列） |
