# 链易配本地拉起与功能验证文档

验证日期：2026-06-12  
验证环境：macOS，本地 MySQL，Flask 后端 + Vite/React 前端

## 1. 项目怎么拉起

### 后端

```bash
cd /Users/fujimiyakaori/Desktop/717273/链易配
venv/bin/python run.py
```

实际结果：

- 5000 端口被 macOS `ControlCenter` 占用时，`run.py` 会自动切到 5050。
- 本次后端运行地址为 `http://127.0.0.1:5050`。
- 后端启动时会初始化 Flask、SQLAlchemy、Flask-Login、Migrate 和 APScheduler。

### 前端

```bash
cd /Users/fujimiyakaori/Desktop/717273/链易配/frontend
VITE_FLASK_PROXY_TARGET=http://127.0.0.1:5050 npm run dev
```

实际结果：

- 前端运行地址为 `http://127.0.0.1:3000`。
- Vite 代理把 `/api`、`/auth`、`/dashboard/api`、`/admin/api` 等请求转发到 Flask 后端。

## 2. 可用账号

本地验证可用：

| 角色 | 账号 | 密码 | 入口 |
|---|---|---|---|
| 企业端 | `test_ent` | `123456` | `/` |
| 企业端 | `成都星河新能源汽车有限公司` | `123456` | `/` |
| 企业端 | `广州洪飞贸易有限公司` | `admin` | `/` |
| 政府端 | `成都市产业链协同专班` | `123456` | `/gov` |
| 管理端 | `链易配运营中心` | `123456` | `/admin/dashboard` |

注意：README 中旧账号 `admin / admin123` 本次验证不可登录。

## 3. 主要功能有什么用

### 企业端

| 模块 | 页面 | 用途 |
|---|---|---|
| 经营驾驶舱 | `/dashboard` | 查看企业信用、风险、订单、报价、履约等经营概览 |
| 企业名录 | `/enterprise-directory` | 按地区、行业、信用等筛选合作企业 |
| 供需匹配 | `/matching` | 基于产品、距离、信用、产能等条件寻找供应商 |
| 销售控制台 | `/sales-console` | 管理询价、报价、销售线索和消息 |
| 风险监测 | `/risk` | 查看供应链预警和 AI 风险解释 |
| 订单工作流 | `/orders` | 创建订单、推进状态，并联动产能日历 |
| 集采拼单 | `/group-purchase` | 汇总采购需求，提高议价能力 |
| 报价池 | `/quote-pool` | 查看报价、价格指数和报价状态 |
| 履约看板 | `/fulfillment` | 查看交付、质检、付款、信用趋势 |
| 产能日历 | `/capacity-calendar` | 查看订单占用和产能利用情况 |
| 资产/设置 | `/assets`、`/settings` | 管理企业资料、通知和微信绑定 |

### 政府端

| 模块 | 页面 | 用途 |
|---|---|---|
| 监管首页 | `/gov` | 汇总产业监管指标和工作入口 |
| 数字大屏 | `/gov/screen` | 投屏式展示企业、预警、图谱、招商态势 |
| 预警中心 | `/gov/alerts` | 查看并处置产业链风险 |
| 产业链图谱 | `/gov/supply-chain` | 展示企业、产品、供应关系网络 |
| 招商决策 | `/gov/recruitment` | 识别供应缺口并生成招商任务 |
| 质量标签 | `/gov/labels` | 查询、颁发、同步企业质量标签 |

### 管理端

| 模块 | 页面 | 用途 |
|---|---|---|
| 管理首页 | `/admin/dashboard` | 平台运营总览 |
| 控制台大屏 | `/admin/dashboard/overview` | 平台统计和预警概览 |
| 入驻审核 | `/admin/dashboard/onboarding` | 查看企业审核状态 |
| 规则配置 | `/admin/dashboard/rules` | 配置信用规则和预警阈值 |
| 风控中心 | `/admin/dashboard/risk` | 查看企业异常和风控状态 |
| API 管理 | `/admin/dashboard/api-management` | 管理外部接口和 API Key |
| 审计日志 | `/admin/dashboard/audit` | 查看平台操作日志 |

## 4. 主要实现方式

### 后端

- `run.py` 创建 Flask 应用并启动服务，自动选择 5000 / 5050 / 5100 端口。
- `app/__init__.py` 注册蓝图，包括认证、企业、撮合、合同、履约、预警、招商、管理后台等。
- `config.py` 读取 `.env`，本地当前开启 `DISABLE_API_AUTH=True`，顶层 `/api/*` 可自动注入企业用户，方便联调。
- 数据层使用 SQLAlchemy + MySQL：
  - 企业、产品、询价、报价、交易等为核心表。
  - SaaS 订单存储在 `Enterprise.extras["saas_orders"]`。
  - 发票、合同、履约回流聚合在 `Transaction.invoice_info` 和 `Transaction.fulfillment_status`。
- 调度任务由 APScheduler 管理，用于报价计数重置、信用分重算、预警检查、招商任务等。
- 大模型相关路径已迁移到 MiMo 兼容调用，保留部分旧 DeepSeek 命名兼容层。

### 前端

- 前端是 React + Vite SPA，入口为 `frontend/src/App.tsx`。
- 企业端、政府端、管理端使用 React Router 分区。
- `frontend/src/services/api.ts` 统一封装前端 API 调用。
- 生产构建输出到 `app/static/frontend`，由 Flask 的 `spa.html` 承载。

## 5. 本次发现并修复的问题

### 5.1 订单状态更新 403

现象：企业创建订单成功后，更新 `/orders/:id/update-status` 返回 403。  
原因：SaaS 订单保存在每个企业自己的 `extras["saas_orders"]` 中，订单 id 是企业内部局部编号。旧代码按全库扫描第一个 `id=1`，会误命中其他企业订单。  
修复：

- `app/applications/fulfillment/services/order_service.py` 增加按 `enterprise_id` 范围查找订单。
- 保存 JSON 字段时显式 `flag_modified(ent, "extras")`，确保状态更新写回数据库。
- `app/routes/orders.py` 的详情、编辑、状态更新、删除入口改为按当前企业范围查找。
- 新增 `tests/test_order_workflow.py` 回归测试。

### 5.2 发票兼容层测试失效

现象：旧路径 `app.services.invoice_validator` 的测试无法 patch `call_tax_api`，属性测试也无法导入 `_mock_tax_api_validation`。  
原因：文件已迁移到 `app/applications/fulfillment/services/invoice_service.py`，旧兼容层只做 `import *`，没有保留旧 patch 语义。  
修复：

- `app/services/invoice_validator.py` 显式导出旧路径所需对象。
- `validate_invoice()` 兼容旧 patch 路径。
- 发票普通单测 + 属性测试通过。

### 5.3 企业看板路由错位

现象：点击“企业看板”实际进入销售控制台，`/dashboard` 也渲染销售控制台内容。  
原因：导航把“企业看板”指向 `/sales-console`，同时 `App.tsx` 把 `/dashboard` 路由配置成了 `SalesConsole`。  
修复：

- `frontend/src/App.tsx` 将 `/dashboard` 改为渲染 `Dashboard`。
- `frontend/src/components/Sidebar.tsx` 将“企业看板”指向 `/dashboard`，销售功能单独保留为“销售控制台”。
- `frontend/src/pages/Dashboard.tsx` 接入信用、预警、订单、报价和匹配数据，改为企业经营驾驶舱。

## 6. 验证结果

### 自动化测试

| 项目 | 结果 |
|---|---|
| 后端本地测试集 | 62 项收集，退出码 0 |
| 合同/订单/发票重点回归 | 20 passed |
| 前端类型检查 | `npm run lint` 通过 |
| 前端生产构建 | `npm run build` 通过 |
| 浏览器页面巡检 | 30/30 通过 |

说明：

- `tests/test_scheduler.py` 会打印“调度器未初始化”和 pytest 返回值警告，但本地测试退出码为 0。
- `tests/test_neo4j.py` 是外部 Neo4j 连接脚本，不作为本地普通 pytest 用例。
- 构建存在 Vite 大 chunk 提示：`main.js` 超过 500 kB，这是性能优化建议，不影响本次运行。

### API 巡检

| 类型 | 结果 |
|---|---|
| 企业端常用读接口 | 通过 |
| 政府端带 Cookie 角色接口 | 17/17 通过 |
| 管理端带 Cookie 角色接口 | 通过 |
| 订单创建 + 状态更新 | 通过 |
| 收藏添加/检查/备注/取消 | 通过 |
| 意向报价创建 + 发送 | 通过 |
| 发票兼容层单测 | 通过 |
| 企业看板路由与动作入口 | 通过 |

### 浏览器页面巡检

企业端 17 个页面、政府端 6 个页面、管理端 7 个页面均能打开并渲染，无 500、无业务 404、无“网络请求失败”。

## 7. 当前限制和注意事项

1. 本地 Neo4j 未启动，图谱接口会记录连接失败日志，但接口会返回降级数据，政府图谱和数字大屏页面可正常渲染。
2. 本地 Ollama `http://localhost:11434` 未启动，匹配时自然语言意图解析会失败并降级到规则匹配，接口仍返回 200。
3. 本次没有额外发起真实付费大模型压力测试；MiMo 客户端路径通过单元测试和应用集成路径验证。
4. 当前 `.env` 开启 `DISABLE_API_AUTH=True`，适合本地联调；生产部署必须关闭。
5. 本次写流程产生了少量“自动巡检”订单、意向报价、发票履约记录，可按关键字清理。

## 8. 最终结论

项目已成功本地拉起：

- 前端：`http://127.0.0.1:3000`
- 后端：`http://127.0.0.1:5050`

企业端、政府端、管理端主要页面和核心接口均已验证可用。已修复订单状态更新、企业看板路由错位、发票兼容层三处会影响功能体验或测试稳定性的问题。当前剩余限制主要来自本地未启动 Neo4j/Ollama，以及生产环境必须关闭的本地免登录配置。
