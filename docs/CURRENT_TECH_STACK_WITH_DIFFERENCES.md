# 链易配当前实际使用技术说明及与原 Word 文档差异标注

对照文件：`/Users/fujimiyakaori/Desktop/链易配（修改）(1).docx`

当前项目：`/Users/fujimiyakaori/Desktop/717273/链易配`

更新时间：2026-06-12

## 1. 总体说明

当前项目已经不是原 Word 文档中描述的“Vue3 + Element Plus + DeepSeek + 完整合同/发票闭环”版本，而是一个实际可运行的 Flask 后端 + React/Vite 前端项目。

当前项目的核心技术主线是：

- 前端：React + Vite + TypeScript + Tailwind CSS
- 后端：Python Flask + Flask Blueprint + SQLAlchemy
- 数据库：MySQL 为主，Neo4j 用于产业链图谱，Redis 为可选缓存
- AI 能力：本地 Ollama/Qwen 负责轻量意图解析和问答，云端 MiMo-V2.5-Pro 负责深度推理/解释类任务
- 匹配算法：规则评分 + 语义扩写 + 可选 XGBoost 精排 + HAN/BPR/FAISS 图嵌入能力
- 多端：企业端、政府端、管理员端

以下所有“差异标注”均以当前代码为准，而不是以 Word 文档的设计描述为准。

## 2. 前端技术

### 2.1 当前实际使用

当前前端是 React SPA，入口在 `frontend/src/App.tsx`。

主要技术：

- React 19：页面组件和状态渲染
- React Router：企业端、政府端、管理端路由分区
- Vite：开发服务器和生产构建
- TypeScript：类型检查，`npm run lint` 实际执行 `tsc --noEmit`
- Tailwind CSS：样式系统
- lucide-react：图标库
- motion：动效
- Recharts：业务图表
- ECharts / echarts-for-react：政府数字大屏等图表能力

主要入口：

- 企业端：`/dashboard`、`/sales-console`、`/matching`、`/quote-pool`、`/orders`、`/fulfillment`
- 政府端：`/gov`、`/gov/screen`、`/gov/alerts`、`/gov/supply-chain`、`/gov/recruitment`、`/gov/labels`
- 管理端：`/admin/dashboard`

### 2.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 前端采用 `Vue3 + Element Plus + ECharts` | 当前主前端是 `React + Vite + TypeScript + Tailwind CSS` | 需要改，不能继续写 Vue3 / Element Plus |
| 早期章节还提到 `Bootstrap5` 响应式布局 | 当前主企业端/政府端是 React SPA；Bootstrap/Jinja 只作为部分历史模板存在 | 可以写“历史兼容模板仍存在”，但主前端不要写 Bootstrap |
| 政府端是普通后台界面 | 当前新增了独立 `/gov/screen` 投屏式数字大屏 | 应补充“政府数字大屏”当前实现 |
| 企业首页/控制台描述较笼统 | 当前 `/dashboard` 已修复为企业经营驾驶舱，聚合信用、风险、订单、报价、匹配 | 应以当前企业看板为准 |

## 3. 后端技术

### 3.1 当前实际使用

当前后端使用 Python Flask，入口为 `run.py`，应用工厂在 `app/__init__.py`。

主要技术：

- Flask 2.3.3：Web 框架
- Flask Blueprint：按业务模块拆分路由
- Flask-Login：登录态和角色控制
- Flask-SQLAlchemy / SQLAlchemy：ORM 数据访问
- Flask-Migrate：数据库迁移支持
- APScheduler：定时任务，如信用分重算、预警检查、报价计数重置
- gunicorn：生产部署服务
- requests：外部接口调用
- pandas / openpyxl：表格导入导出和数据处理
- pytest / pytest-flask / hypothesis：测试

主要业务路由：

- 认证与会话：`/auth/*`、`/api/session`
- 企业匹配：`/api/matching/search`、`/api/match/ai`
- 询价与报价：`/api/inquiry-chat/*`、`/api/intent-quote/*`、`/api/quotes`
- 订单履约：`/api/orders`、`/orders/:id/update-status`、`/api/fulfillment`
- 政府监管：`/dashboard/api/*`、`/api/recruitment/*`、`/api/alert-workflows/*`
- 管理后台：`/admin/*`、`/admin/api/*`

### 3.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 只笼统写 Flask 后端 | 当前已经是多 Blueprint + 多业务 service 分层 | 可以补充具体工程结构 |
| 合作闭环重点写电子合同、发票验证、撮合码 | 当前 React 企业端已经删除“电子合同 / 发票管理 / 物流距离”独立功能入口 | 文档中如果继续写这些为前端核心功能，会和项目不一致 |
| 电子合同、发票验证是企业端显式功能 | 后端仍有历史兼容服务和旧 Jinja 路由痕迹，但当前主 React 企业端不暴露 | 应写成“历史兼容/底层遗留能力”，不要写成当前主功能 |
| 性能测试结论较宏观 | 当前更适合写已验证命令：`npm run lint`、`npm run build`、pytest、Playwright 页面断言 | 建议用真实验证口径替代泛泛结论 |

## 4. 数据库与存储

### 4.1 当前实际使用

当前项目以 MySQL 为主数据库。

主要技术：

- MySQL：企业、产品、询价、报价、交易、预警、用户等结构化数据
- SQLAlchemy：模型定义和 ORM 操作
- JSON 字段：部分业务扩展数据保存在 JSON 字段中，例如订单扩展、履约回流、企业补充信息
- Neo4j：产业链图谱、上下游关系、政府端图谱分析
- Redis：可选缓存，用于偏好向量、bandit 权重、定时任务缓存等

当前 `.env.example` 中明确：

- `DATABASE_URL` 为必填 MySQL 连接
- `NEO4J_URI` 为产业链图谱功能需要
- `REDIS_URL` 为可选缓存

### 4.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| MySQL + Neo4j + Redis 是完整体系 | 当前 MySQL 是必填，Neo4j/Redis 更接近可选增强能力 | 应标注“Neo4j/Redis 未启动时有降级或可选路径” |
| 文档说 Neo4j 参与完整图谱推理 | 当前政府图谱和招商分析依赖 Neo4j，但部分接口有 MySQL 降级数据 | 不能写成所有场景强依赖 Neo4j |
| 文档说 Redis 支撑高并发缓存 | 当前 Redis 在部分服务里使用，但项目可在无 Redis 情况下退化 | 应写“可选缓存/性能增强” |

## 5. AI 与大模型技术

### 5.1 当前实际使用

当前项目采用“本地模型 + 云端模型”的组合。

本地模型：

- Ollama
- Qwen 系列模型，如 `qwen2:7b`、`qwen2.5:3b`
- 用于 BizMind 问答、意图解析、查询扩写、SQL/Cypher 生成等轻量任务

云端模型：

- Xiaomi MiMo-V2.5-Pro
- OpenAI 兼容接口
- 默认网关：`https://token-plan-cn.xiaomimimo.com/v1`
- 用于云端深度推理、长文档降级、AI 匹配理由等

相关代码：

- `app/services/ollama_client.py`
- `app/services/llm_service.py`
- `app/services/mimo_client.py`
- `app/services/rag_service.py`
- `frontend/src/components/AISidebar.tsx`

### 5.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 云端大模型是 DeepSeek | 当前云端模型已迁移为 MiMo-V2.5-Pro | 必须改为 MiMo |
| DeepSeek 负责 Top5 深度评估和解释 | 当前代码中部分旧命名仍叫 DeepSeek，但实际云端路径走 MiMo | 可以说明“保留 DeepSeek 命名兼容层，实际调用 MiMo” |
| 本地模型是 Qwen2.5 | 当前配置默认 `qwen2:7b`，也支持 `qwen2.5:3b/7b` | 可写“Qwen 系列，按 Ollama 本地模型配置决定” |
| 文档没有提 MiMo 网关 | 当前 `.env.example` 已有 `MIMO_API_KEY`、`MIMO_MODEL`、`MIMO_BASE_URL` | 需要新增 MiMo 配置说明 |

## 6. 智能匹配与推荐算法

### 6.1 当前实际使用

当前项目的匹配逻辑主要位于：

- `app/applications/matching/services/matcher.py`
- `app/applications/matching/services/match_llm.py`
- `app/applications/matching/services/ranking_model.py`
- `app/services/gnn_model.py`
- `app/applications/matching/services/recommender.py`

主要技术：

- 查询扩写：通过本地 Ollama/Qwen 对用户需求做语义纠错和扩展
- 规则召回：基于产品、行业、地区、企业画像等进行候选召回
- 九维评分：产品、距离、信用、产能、历史合作、语义、技术、绿色低碳、GNN 相似度等维度
- 距离计算：geopy + 高德地图服务可选增强
- 语义相似度：`sentence-transformers/all-MiniLM-L6-v2`
- XGBoost：可选排序模型
- HAN + BPR：图神经网络训练企业嵌入
- FAISS：企业嵌入索引存储与检索
- Redis：偏好向量缓存

### 6.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| FALCON 五阶段漏斗作为完整核心算法 | 代码里存在对应模块和能力，但实际运行依赖模型文件、数据、Neo4j、可选依赖是否齐全 | 应写成“已实现支撑能力 / 可选增强”，不要全部写成每次在线必跑 |
| DeepSeek 生成可解释推荐理由 | 当前应改成 MiMo 生成或 MiMo 兼容路径生成 | 替换模型名称 |
| HAN/BPR/FAISS 是完整线上流程 | 当前有 `gnn_model.py` 训练与写入能力，在线匹配可读取嵌入；没有数据或索引时会退化 | 需要标注“有降级机制” |
| BGE-M3 与 all-MiniLM 对比 | 当前代码实际使用 `all-MiniLM-L6-v2` | 这一点可保留，但应写成当前工程选型 |

## 7. 企业端功能技术

### 7.1 当前实际功能

当前企业端主要功能：

- 企业看板：信用、风险、订单、报价、匹配推荐聚合
- 销售控制台：询价消息、报价、意向报价、名片交换
- 企业名录筛选：按企业条件筛选合作对象
- 供需匹配：自然语言需求、智能推荐、匿名询价
- 集采拼单：联合采购
- 报价池：报价提交、报价列表、价格指数
- 风险监测：企业风险预警
- 履约看板：订单履约状态、履约评分
- 产能日历：订单和产能占用
- 订单工作流：订单创建、状态更新、导出
- 资产管理：企业资料、数据授权接口、数字资产展示
- 设置：用户配置

### 7.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 企业端包括电子合同、发票管理、物流距离 | 当前 React 企业端已删除这三个独立页面和路由 | 必须标注“已移除” |
| 企业端有收藏管理独立模块 | 当前 `/favorites` 会重定向到销售控制台；收藏 API 和服务仍存在 | 不建议写成独立页面模块 |
| 匿名询价是需求功能 | 当前匹配页和询价聊天中有匿名询价逻辑 | 可以保留 |
| 数据授权是独立模块 | 当前主路由把 `/data-auth` 重定向到 `/settings`，资产页也展示数据授权接口 | 应写成资产/设置中的能力，而不是独立入口 |

## 8. 政府端功能技术

### 8.1 当前实际功能

当前政府端主要功能：

- 监管首页：产业指标、风险概览
- 数字大屏：`/gov/screen`，投屏式可视化页面
- 质量标签：绿标、验厂标签管理
- 预警中心：风险预警查看与处理
- 产业链图谱：企业、产品、上下游关系可视化
- 招商决策：产业链缺口、招商建议、任务管理

### 8.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 政府端包含政策模拟器 | 当前未作为主前端页面暴露 | 应删除或写成规划功能 |
| 政府端包含区域对比分析 | 当前主路由未暴露独立区域对比页面 | 应删除或写成规划功能 |
| 政府端包含数据导出审批 | 当前未作为主前端页面暴露 | 应删除或写成规划功能 |
| 政府端大屏描述较普通 | 当前已有专门 `/gov/screen` 数字大屏 | 应强化当前实现 |

## 9. 管理端功能技术

### 9.1 当前实际功能

当前管理端路径为 `/admin/dashboard`，主要页面包括：

- 管理首页
- 平台统计概览
- 企业审核 / 认证
- 规则配置
- 风险中心
- API 管理
- 审计日志

### 9.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 管理端包含完整用户、权限、角色、备份、清理、安全监控等 14 个模块 | 当前主前端只暴露部分核心管理页 | 应压缩管理端描述 |
| 撮合码规则配置是后台功能 | 当前没有作为主前端管理页面明确暴露 | 建议写成后续规划或后端底层能力 |
| 演示模式一键生成数据 | 当前存在模拟/测试数据能力，但不是完整后台按钮式演示模式 | 不建议夸大 |

## 10. 部署与运行技术

### 10.1 当前实际使用

本地运行：

- 后端：`run.py` 启动 Flask，端口可从 5000 回退到 5050
- 前端：`frontend/ npm run dev`，默认端口 3000
- Vite 代理：将 `/api`、`/auth`、`/dashboard/api`、`/admin/api` 等请求转发给 Flask

生产部署建议：

- Nginx 反向代理
- Gunicorn 运行 Flask
- MySQL 为主数据库
- Neo4j/Redis/Ollama/MiMo 按需配置
- 前端生产构建输出到 `app/static/frontend`，由 Flask 承载 SPA

### 10.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 混合部署描述偏概念化 | 当前已有 Flask + Vite 本地运行方式和 Flask 托管生产构建路径 | 应写具体命令和端口 |
| 云端 DeepSeek API | 当前云端 MiMo API | 替换 |
| 只写 Flask 内置服务器 | 当前 `requirements.txt` 已加入 gunicorn | 生产部署应写 gunicorn |

## 11. 测试与验证技术

### 11.1 当前实际使用

当前项目可使用以下验证方式：

- TypeScript 检查：`cd frontend && npm run lint`
- 前端构建：`cd frontend && npm run build`
- Python 编译检查：`venv/bin/python -m py_compile ...`
- 后端测试：`venv/bin/python -m pytest -q`
- 页面验证：Playwright
- 政府大屏验证：`npm run verify:gov-screen`

### 11.2 与原 Word 文档不同之处

| 原 Word 文档写法 | 当前项目实际情况 | 差异标注 |
|---|---|---|
| 文档列了大量 Apifox 性能测试和准确率指标 | 当前仓库更可靠的是本地构建、pytest、Playwright 验证证据 | 若要写指标，必须重新实测 |
| 文档提到区块链存证测试 | 当前主项目未看到区块链上链作为企业端主功能入口 | 建议删除或标注为规划/概念验证 |
| 文档说功能全部稳定运行 | 当前应按实际已验证页面和接口列出 | 使用 `docs/RUNTIME_FUNCTION_VERIFICATION.md` 的实测口径 |

## 12. 建议替换进 Word 文档的技术栈表

| 层级 | 当前建议写法 |
|---|---|
| 前端层 | React 19、Vite、TypeScript、Tailwind CSS、React Router、lucide-react、motion、Recharts、ECharts |
| 后端层 | Python Flask、Flask Blueprint、Flask-Login、Flask-SQLAlchemy、Flask-Migrate、APScheduler、Gunicorn |
| 数据层 | MySQL、SQLAlchemy ORM、Neo4j 图数据库、Redis 可选缓存、JSON 扩展字段 |
| AI 层 | Ollama/Qwen 本地模型、MiMo-V2.5-Pro 云端模型、LangChain、RAG 长文档降级 |
| 匹配算法层 | 语义扩写、九维规则评分、距离衰减、all-MiniLM-L6-v2 语义相似度、XGBoost 可选精排、HAN+BPR 图嵌入、FAISS 向量索引 |
| 企业端 | 企业看板、销售控制台、企业名录、供需匹配、集采拼单、报价池、风险监测、履约看板、产能日历、订单工作流、资产管理、设置 |
| 政府端 | 监管首页、数字大屏、质量标签、预警中心、产业链图谱、招商决策 |
| 管理端 | 管理首页、统计概览、企业审核、规则配置、风险中心、API 管理、审计日志 |
| 测试验证 | TypeScript 检查、Vite 构建、pytest、Playwright 页面验证、政府大屏专项验证 |

## 13. 最重要的修改提醒

如果要把原 Word 文档改成和当前项目一致，优先改这 6 处：

1. 把 `Vue3 + Element Plus` 改成 `React + Vite + TypeScript + Tailwind CSS`。
2. 把云端 `DeepSeek` 改成 `MiMo-V2.5-Pro`，并说明部分旧命名是兼容层。
3. 删除或弱化“电子合同、发票管理、物流距离”作为企业端主功能的表述。
4. 把企业首页/控制台改成当前 `/dashboard` 企业经营驾驶舱。
5. 政府端补充 `/gov/screen` 数字大屏，删除未落地的政策模拟器、区域对比、导出审批等独立页面描述。
6. 测试结果不要继续沿用文档中的泛化性能结论，应使用当前构建、pytest、Playwright 的实测结果。
