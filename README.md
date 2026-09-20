# 链易配

链易配是面向制造业采购方、制造企业、园区与政府的产业链供需协同平台。平台将企业画像、产品能力、产能、信用、地理与履约信号连接起来，帮助用户筛选可核验的制造企业，并通过链小易 AI 完成需求理解、工厂匹配、询价与后续协同。

当前产品由 Flask 后端、React/Vite 前端和可选的模型服务组成。本文描述当前版本的页面入口、本地运行方式和验证命令；生产部署请以 [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md) 与 [`docs/PRODUCTION_AUDIT_2026-09-18.md`](docs/PRODUCTION_AUDIT_2026-09-18.md) 为准。

## 页面入口

| 地址 | 页面 | 用途 |
| --- | --- | --- |
| `/` | 首次入口 | 自动跳转到品牌首页 `/indisea/` |
| `/indisea/` | Indisea 品牌首页 | 展示平台定位、协同能力、数据边界与公共导航 |
| `/aisearch/` | AI 搜索主页 | 公共找厂首页、热门搜索、AI 找厂入口和服务区 |
| `/search` | 筛选工厂 | 按地区、城市、行业、经营状态、注册资本和企业标签筛选工厂 |
| `/aia` | 链小易 · AI 找工厂 | 输入自然语言需求、上传采购材料并查看匹配结果 |
| `/agent-market` | AI 能力市场 | 查看面向销售、采购、计划和产业情报的岗位型 AI |
| `/industry-news` | 行业资讯 | 浏览行业资讯并从资讯进入相关业务能力 |
| `/factory/:id` | 企业详情 | 查看公开企业能力摘要和数据来源边界 |

兼容地址 `/indesea/` 会自动重定向到正确的 `/indisea/`。

### 找厂主流程

```text
访问 /
    ↓
/indisea/  品牌首页
    ├── 筛选工厂 → /search
    │       └── 提交筛选条件 → /aia?q=...
    └── AI 找工厂 → /aisearch/
            └── 输入需求 → /aia?q=...
```

`/search` 默认以工厂/企业为筛选对象，支持切换到产品、供应信息和采购需求。筛选页会把关键词与地区、行业、企业标签等条件整理成自然语言参数，再交给 `/aia` 的链小易流程处理。

## 功能概览

- 公共 Indisea 品牌首页：平台定位、制造能力连接流程、场景、数据边界和公共导航。
- 工厂筛选：关键词、地区、城市、行业、经营状态、注册资本、可出口、决策人联系方式、专精特新和绿色工厂等条件。
- AI 找工厂：自然语言需求解析、数据库匹配、九维匹配解释、候选工厂证据与数据新鲜度提示。
- 采购材料处理：支持 CSV、Excel、PDF、Word 等材料，识别采购项、提示字段冲突并分别匹配工厂。
- 协同闭环：询价预览、人工审批、供应商报价筛选、订单草稿和合同/付款确认。
- 企业工作台：经营看板、订单、履约、产能、资产、报价池、风险与设置等功能。
- 政府与运营端：产业链、招商、质量标签、风险告警、数字大屏、新闻和审核能力。

平台公开页面仅展示脱敏摘要；联系方式、完整企业能力和对外协同操作受登录、授权和权限控制。演示数据、模型降级结果和未知字段会在页面中明确标识，不以缺失事实代替真实数据。

## 本地启动

### 1. 启动后端

项目推荐使用虚拟环境：

```bash
.venv/bin/python run.py
```

后端默认使用项目配置的本地端口，常见地址为 `http://localhost:5050`。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器地址：`http://localhost:3000`。Vite 会将 `/api`、`/auth` 等请求代理到本地 Flask 后端；如后端不在 `5050`，可通过 `VITE_FLASK_PROXY_TARGET` 或 `FLASK_PROXY_TARGET` 配置代理地址。

Windows 用户也可以使用根目录的 [`启动.bat`](启动.bat)。数据库、Neo4j、Redis、模型服务和演示账号的补充说明见 [`docs/启动说明.md`](docs/启动说明.md)。

### 3. 初始化本地演示数据

仅用于本地开发和演示；生产环境不要执行这些脚本：

```bash
.venv/bin/python scripts/db/create_db.py
.venv/bin/python scripts/seed/seed_all_data.py
```

链小易文件采购闭环演示见 [`docs/CHAIN_XIAOYI_CORE_DEMO.md`](docs/CHAIN_XIAOYI_CORE_DEMO.md)。云端模型密钥应通过运行环境注入 `DEEPSEEK_API_KEY`，不要提交到代码、日志或示例配置中。

## 前端命令

在 `frontend/` 目录执行：

```bash
npm run dev                         # Vite 开发服务器，端口 3000
npm run lint                        # TypeScript 类型检查
npm run build                       # 生产构建，输出到 app/static/frontend
npm run test:e2e                    # Playwright 端到端测试
npx tsx scripts/verify-indisea.ts   # Indisea 页面结构和资源校验
```

生产构建会更新 Flask 托管的 `app/static/frontend/` 产物。该目录是构建输出，不要手工编辑；前端源码只维护在 `frontend/src/`。

## 目录结构

| 目录 | 作用 |
| --- | --- |
| `app/routes/` | Flask 路由和 API 编排 |
| `app/applications/` | 按领域组织的后端业务服务 |
| `app/services/` | 基础设施服务与兼容导入层 |
| `frontend/src/` | React 页面、组件、路由和样式源码 |
| `frontend/src/indisea/` | Indisea 品牌首页及其动画、导航和内容模块 |
| `frontend/src/pages/PublicHome.tsx` | `/aisearch/` AI 搜索主页 |
| `frontend/src/pages/PublicSearch.tsx` | `/search` 筛选工厂页 |
| `frontend/src/pages/PublicAia.tsx` | `/aia` 链小易 AI 找工厂页 |
| `app/static/frontend/` | 前端生产构建产物，由 Vite 生成 |
| `scripts/db/`、`scripts/seed/`、`scripts/verify/` | 数据库、种子和验证脚本 |
| `migrations/` | Alembic 数据库迁移 |
| `deploy/baota/` | 宝塔、Nginx 和 Supervisor 部署模板 |
| `docs/` | 部署、架构、运行和验收文档 |

更多目录约定见 [`app/applications/README.md`](app/applications/README.md)、[`app/services/README.md`](app/services/README.md)、[`scripts/README.md`](scripts/README.md) 和 [`docs/README.md`](docs/README.md)。

## 生产部署提醒

本地 Flask/Vite 开发服务器、固定演示账号、种子数据和本地模型降级路径都不能直接作为公网生产方案。生产环境至少应完成：

1. 使用 Alembic 完成数据库迁移，再启动 Web 服务。
2. 使用 Gunicorn/Worker、Nginx 或等效反向代理，并启用 HTTPS。
3. 配置 MySQL、Redis、对象存储、ClamAV、密钥和模型服务等生产依赖。
4. 关闭生产环境的免登录、Mock 和本地开发开关。
5. 执行 readiness、接口、权限、材料上传和 Worker 验收。

详细规格、配置门禁和验收记录请阅读 [`docs/PRODUCTION_DEPLOYMENT.md`](docs/PRODUCTION_DEPLOYMENT.md)、[`docs/BAOTA_SERVER_DEPLOYMENT_SPEC.md`](docs/BAOTA_SERVER_DEPLOYMENT_SPEC.md) 和 [`docs/PRODUCTION_AUDIT_2026-09-18.md`](docs/PRODUCTION_AUDIT_2026-09-18.md)。
