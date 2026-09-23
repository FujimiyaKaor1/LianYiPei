# 生产上线审计报告（2026-09-18）

> 复核更新：2026-09-22。以下结论以本次复核的当前工作树和运行环境为准。

## 结论

当前项目的代码质量和生产拓扑验收结果良好，但**仍不能在没有真实第三方凭据/沙盒验收的前提下直接判定为公网生产就绪**。

目标服务器和供应商验收请直接使用：[外部生产验收模板](PRODUCTION_EXTERNAL_ACCEPTANCE_TEMPLATE.md)。
文档索引也已将该模板列为生产部署入口；`RUNTIME_FUNCTION_VERIFICATION.md` 和 `启动说明.md` 仅保留为历史本地记录。

历史隔离验收已证明：生产 Docker 镜像、完整 Compose 拓扑、MySQL Alembic 迁移、Redis、MinIO/S3、ClamAV、Web/Worker、真实登录和容器探针可以通过。当前工作区可复核的项目级证据包括后端核心测试、前端类型检查、前端生产构建和 Python 编译；历史隔离拓扑不等同于当前目标服务器已连接。

不能确认：真实生产 MySQL/S3 凭据、真实 DeepSeek 配额、Neo4j、邮件/企业微信/电子合同等外部服务尚未在目标服务器或供应商沙盒完成验收。因此目前的状态为：**预生产核心拓扑 READY，公网生产外部集成 NOT READY**。

本次复核的工作区证据：当前进程使用 SQLite，`SELECT 1` 已成功；未发现可供本项目使用的目标生产服务器连接。`scripts/verify/production_smoke.py --json` 在开发配置下报告 database/redis/worker 可用，但 ClamAV、S3 未配置且 DeepSeek 探针跳过；该结果只能作为本地开发状态，不能作为生产 readiness。生产 Compose 在注入必需变量后可通过配置渲染校验，但本次没有使用真实凭据启动目标服务器。

2026-09-22 复核补充：Docker daemon 不可连接，因此本次没有重新启动 MySQL、Redis、MinIO、ClamAV、Web 和 Worker 隔离拓扑；之前记录的隔离 Compose 结果仍属于历史证据，不能替代目标服务器验收。当前可复核的新证据为本地 Flask + SQLite HTTP 探针全部通过、后端 `369 passed`、前端桌面/移动端 E2E `22 passed`。E2E 的业务 API 使用受控响应，不能证明真实第三方网络链路。另已验证生产进程使用 SQLite URL 会被 `DATABASE_URL_NON_SQLITE` 门禁拒绝。

## 已执行且通过的检查

| 检查项 | 结果 | 证据 |
|---|---|---|
| Python 依赖一致性 | 通过 | `.venv/bin/python -m pip check` |
| Python 本地依赖漏洞扫描 | 通过 | `.venv/bin/python -m pip_audit --local --progress-spinner off --timeout 5`：No known vulnerabilities found |
| Node 生产依赖安全扫描 | 通过 | `npm audit --omit=dev --audit-level=high`：0 vulnerabilities |
| 后端全量测试 | 通过 | 当前工作树 `369 passed in 111.13s` |
| 前端 Playwright E2E | 通过 | 桌面/移动端共 `22 passed`；业务 API 在测试中使用受控响应，不能替代目标服务器真实链路验收 |
| Python 语法/字节码编译 | 通过 | `python -m compileall -q app scripts wsgi.py run.py` |
| 前端 TypeScript 检查 | 通过 | `cd frontend && npm run lint` |
| 前端生产构建 | 通过 | `cd frontend && npm run build` |
| Compose 配置渲染 | 通过 | 默认云模型门禁和 `CHAINXIAOYI_CLOUD_ENABLED=false` 无 key 的紧急关闭矩阵均执行 `docker compose ... config` |
| 宝塔备份脚本语法 | 通过 | `bash -n deploy/baota/backup-lianyipei.sh`；数据库 URL 字段按行解析，支持 URL 编码特殊字符 |
| 上传入口安全回归 | 通过 | 发票、RAG PDF、CLIP 图片均经过统一格式/大小/恶意文件检查；CLIP 接口要求登录 |
| 企业资产/收藏事实性回归 | 通过 | 无资质、无授权、无团队、无匹配记录时返回空/未知，不再生成演示证书、ERP 连接、团队成员或伪匹配度 |
| 报价建议事实性回归 | 通过 | 冷启动无持久化报价样本时返回“无法估算”；缺失产能时不生成虚构交期或产能状态；前端明确展示数据库规则来源 |
| 政府监管大屏失败关闭 | 通过 | 接口失败或返回空数据时不再展示硬编码企业、预警、招商任务、历史趋势或健康指数；仅显示真实返回值和离线状态 |
| 生产数据标识门禁 | 通过 | 生产默认 `PUBLIC_DATA_MODE=production`，readiness 会拒绝以 demo 标签运行的生产实例 |
| 金融功能事实性回归 | 通过 | 未接入金融机构时不生成合作银行、默认匹配分或授信金额；融资申请返回 503，且不修改信用分 |
| 企业资产/名片缺失字段回归 | 通过 | 缺少资质状态、授权状态、主营业务或信用分时显示未核验/未连接/未登记/未公开，不再补成有效事实 |
| 收藏、履约信用展示真实性 | 通过 | 收藏、名片、履约凭证页面不再以 60/70/78 等默认值伪造信用分；上传凭证后只刷新后端真实信用历史，不在前端本地制造加分记录 |
| 新企业信用/产能冷启动真实性 | 通过 | 新建企业不再自动写入 70 分信用或 50 单产能；履约、信用、名录、招商和画像页面对缺失事实显示未公开/未知 |
| 履约回流接口权限边界 | 通过 | `/fulfillment/api/backflow` 仅允许管理员/内部合同流程，普通企业会返回 403，避免伪造发票触发信用变更 |
| 生产 Docker 镜像 | 通过 | `docker build --target runtime -t lianyipei-audit-runtime:local .`；Compose 的 MySQL、Redis、MinIO、mc、ClamAV 均锁定到本轮已验证 digest |
| 容器 `/healthz` | 通过 | 返回 HTTP 200 和 `{"status":"ok"}` |
| 容器 `/readyz` 门禁 | 通过 | 未迁移时返回 HTTP 503，`agent_schema=missing` |
| 隔离 Compose 生产拓扑 | 通过 | 本轮 `lianyipei-audit4` 中 MySQL、Redis、MinIO、ClamAV、迁移、Web、Worker 全部运行；验证后已清理容器、卷和网络 |
| MySQL 真实迁移 | 通过 | 本轮从空库执行到 `h3d4e5f6a7b8`；迁移容器正常退出，MySQL `alembic_version` 实际值已核对 |
| 生产 smoke | 通过核心依赖 | 本轮容器内 database/redis/clamav/s3/worker 均 `ok`，`/healthz` 与 `/readyz` 返回 200；管理员 readiness 明确列出 `deepseek` 为唯一 required failure，普通企业访问 readiness 返回 403；占位 key 不会冒充可用模型 |
| 真实 HTTP 登录与权限 | 通过 | 当前隔离 Compose 中 admin 与 enterprise 登录均返回 `ok:true`；管理员 readiness 可读，企业账号访问返回 403 |
| 公共首页/搜索与企业 API | 通过 | HTTP 200；未授权角色返回 302/403 |
| 生产安全启动门禁 | 通过 | 生产模式缺少必需配置、使用 SQLite 数据库或尝试隐式 `create_all` 时拒绝启动 |
| 会话 Cookie 安全属性 | 通过 | 生产配置显式启用 Secure、HttpOnly、SameSite=Lax 会话/Remember Cookie |
| 密钥扫描 | 未发现提交到仓库的常见 API 私钥格式 | 对源码和配置模板做只读扫描 |

## 当前明确的阻断项

### 1. 目标服务器的真实生产数据库连接仍需验收

开发工作区的 `.env` 仍启用了 SQLite 回退；不过本次已在隔离 Compose 生产拓扑中使用 MySQL 8.4 完成从空库到最新迁移的真实验证，并通过 `/readyz`。这证明了仓库的生产迁移链路可用，但不替代目标服务器自己的连接、备份和恢复验收。

生产必须注入 URL 编码后的 MySQL 连接串，并在目标环境执行迁移：

```bash
FLASK_APP=wsgi:app .venv/bin/flask db upgrade
FLASK_APP=wsgi:app .venv/bin/flask db current
```

随后必须确认 `GET /readyz` 返回 200，并检查 `GET /api/admin/production-readiness` 的 `required_failures` 为空。

### 2. Redis、MinIO/S3 和 ClamAV 已通过隔离生产拓扑，目标环境仍需复核

本次已启动隔离的 `lianyipei-audit4` Compose 项目，Redis、MinIO/S3、ClamAV、MySQL、Web 和独立 Worker 均通过真实网络探针；Worker 心跳停止后的失败关闭也已验证。目标服务器仍必须用自己的凭据和持久卷重复执行该检查。

生产 Compose 已定义 MySQL、Redis、MinIO、ClamAV、迁移、Web 和独立 Worker，但必须在目标服务器真实启动并检查：

```bash
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
.venv/bin/python scripts/verify/production_smoke.py --json
```

生产 smoke 的 `ready` 必须为 `true`；不能只看 Web 容器是 running。

### 3. DeepSeek 和外部回调未做真实验收

当前仅通过了模型客户端的单元测试和多模态请求构造测试；生产 smoke 已确认密钥配置门槛，但没有消耗真实配额做 DeepSeek 请求，也没有用供应商沙盒验证邮件、企业微信、电子合同、支付、物流或税务回调。

注入真实 `DEEPSEEK_API_KEY` 后，按需执行一次低额度探针：

```bash
.venv/bin/python scripts/verify/production_smoke.py --json --probe-deepseek
```

邮件、企业微信、电子合同、支付、物流和税务功能只能在对应供应商沙盒/测试租户中完成真实回调后，才能标记为生产可用。未配置的可选集成应继续失败关闭，不能用模拟数据代替。

### 4. Neo4j 未纳入当前验收

图谱相关页面有降级路径，但本次没有运行 Neo4j。若生产需要政府图谱、数字大屏关系数据或图算法能力，必须在目标环境验证 `NEO4J_URI`、账号、密码和查询权限；否则这些功能只能按“降级可展示，图谱能力未证明可用”处理。

### 5. 前端存在构建体积警告

Vite 构建成功，但 `charts.js`、`vendor.js` 等 chunk 超过 500 kB。小额度规模使用通常可以上线，但首次加载和弱网体验会受影响，建议上线后再做动态分包，不属于当前硬阻断。

## 与文档描述的一致性

- 生产默认关闭免登录和 Mock 路由：代码启动门禁与 readiness 检查均已覆盖。
- 生产禁止隐式建表：`AUTO_CREATE_SCHEMA=0` 时 `/readyz` 在迁移前返回 503，符合文档的“先迁移后启动”顺序。
- 材料上传生产要求 ClamAV、S3 私有存储和 Fernet 密钥：代码启动门禁与 readiness 检查均会拒绝缺失配置。
- 链小易询价、回调幂等、明确审批、订单草稿与履约事件：已有测试覆盖，且后端全量测试通过。
- “外部事实接口未配置时失败关闭”：已有测试覆盖；本次未对真实供应商接口做网络验收。
- 文档中的本地 Demo 账号、SQLite 回退、规则模型降级只适用于开发/演示，不应复制到公网生产环境。

## 正式上线前的最小验收顺序

1. 准备独立的生产 MySQL、Redis、MinIO/S3、ClamAV，以及可选的 Neo4j；创建备份和恢复点。
2. 通过密钥管理系统注入 `SECRET_KEY`、`DATABASE_URL`、`DEEPSEEK_API_KEY`、`MATERIAL_ENCRYPTION_KEY`、S3 凭据和回调密钥；不要把真实值写入仓库 `.env`。
3. 确认 `APP_ENV=production`、`AUTO_CREATE_SCHEMA=0`、`DISABLE_API_AUTH=0`、`ENABLE_MOCK_API=false`、`CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL=true`。
4. 执行 Alembic 迁移，检查 `/readyz` 和生产 readiness。
5. 启动独立 Worker，确认队列能领取任务并持有调度器锁；Web 进程不承担重复调度。
6. 在预生产用测试账号完成：登录、企业名录、供需匹配、采购材料上传/扫描/解析、询价预览、审批发送、报价回收、订单草稿确认、履约回写和审计查询。
7. 对每个已启用外部渠道完成供应商沙盒回调、签名校验、幂等重放和失败重试验收。
8. 通过 Nginx/网关启用 HTTPS、限流、访问日志和备份监控后，才切换少量真实流量。

## 最终判定

**代码和核心生产拓扑层面：可进入预生产，并已在隔离 Compose 中跑通。**

**公网部署层面：尚未达到完全放量的证据标准。** 当前剩余风险集中在真实 DeepSeek 调用、Neo4j（若启用图谱能力）和外部供应商回调。完成本报告“正式上线前的最小验收顺序”后，再依据 `/readyz`、production smoke、真实模型探针和外部沙盒结果决定小额度放量。

## 本轮修复的真实问题

- 修复 ClamAV `PONG\0` 被探针误判为不可用的问题。
- 修复生产 smoke 在未执行计费模型探针时错误返回 `ready=false` 的问题；现在会检查密钥存在性，真实网络调用仍由 `--probe-deepseek` 显式触发。
- 新增迁移 `h3d4e5f6a7b8`，将 `enterprises.password_hash` 从 128 扩展为 255 字符；此前 MySQL 上创建 Werkzeug scrypt 密码会报 `Data too long`。
- 修复 `scripts/db/ensure_test_accounts.py` 的容器路径问题，并使初始化的管理员/测试企业明确为已审核状态。
- 修正宝塔部署说明：Redis、S3 凭据和生产 ClamAV/S3 门槛不再被描述为可选；生产初始化改为只执行 Alembic，避免误执行清库或演示种子脚本。
- 固定 Compose 中已验收的 MinIO/`mc` 镜像 digest，避免生产部署无意拉取变化的 `latest`；备份脚本不再用空白分隔解析数据库凭据。
- 进一步固定 Compose 中本轮已验证的 MySQL、Redis 和 ClamAV 镜像 digest，避免固定版本标签在后续重新拉取时发生内容漂移。
- 明确宝塔 Nginx 文件是 `server` 片段，必须由宝塔 SSL 配置生成 HTTPS、跳转、限流和安全响应头后才能接公网。
- 修复发票、RAG 和 CLIP 上传入口绕过统一材料安全策略的问题；生产扫描不可用时这些入口会失败关闭。
- 修复企业资产和收藏接口中的硬编码演示事实；认证、专利、外部授权、团队、信用拆分和匹配度现在只来自数据库/企业 extras/真实匹配反馈。
- 修复分容器部署中 Web 看不到 Worker `/tmp` 调度锁导致 smoke 误报 Worker 未运行的问题；Worker 现在通过 Redis 发布短期心跳，Web 跨 PID namespace 检测该心跳并在过期时失败关闭。
- 修复报价参考在价格冷启动和产能字段缺失时使用 50/100 等默认值的问题；现在只基于已持久化报价样本和已登记企业字段计算，缺失事实明确返回无法估算。
- 修复政府监管大屏在接口异常时展示硬编码演示企业、预警、招商缺口、任务、趋势和健康指数的问题；现在对应数据源失败时显示“暂无数据”，不再形成虚假监管事实。
- 修复生产环境缺少 `PUBLIC_DATA_MODE` 时将真实数据库记录标成演示数据的问题；生产配置默认和 Compose/宝塔模板均明确使用 `production`，readiness 增加失败关闭门禁。
- 修复链易贷把企业 ID 映射成合作银行、无匹配反馈使用默认 75 分、提交申请自动增加信用分的问题；当前明确标记为未接入，金融申请失败关闭。
- 修复企业资产和名片接口对不完整数据库记录的默认事实：缺失资质状态、授权状态、行业和信用分现在分别显示未核验、未连接、未登记和未公开。
- 修复收藏、名片和履约凭证页面中的默认信用分与本地“加 10 分”演示逻辑；信用数据缺失时显示未公开，凭证上传后只读取后端持久化结果。
- 修复剩余的信用/产能冷启动默认值：新企业不再自动获得 70 分信用或 50 单产能；信用 API、履约看板、招商候选、企业画像和匹配指标不会把缺失信用证据渲染为 60/70 分。
- 收紧履约回流入口：普通企业不能直接调用内部 `/fulfillment/api/backflow` 伪造履约数据；正式合同流程继续通过合同权限和发票验真后调用服务层。
- 增加测试账号脚本的生产拒绝门禁：`ensure_test_accounts.py` 在 `APP_ENV=production` 下不会创建或重置 `admin/admin`、`test_ent/123456`，避免误把固定弱口令带入正式库。
- 收紧 Worker readiness：`LIANYIPEI_WORKER_ENABLED`、消息队列 URL 或调度器开关本身不再被当作存活证据，避免误配 Web 容器造成假阳性；测试环境不会继承本机 Redis worker 心跳，生产仍验证真实 Redis 心跳、调度器或锁文件；本轮最终全量测试为 `369 passed in 111.13s`。
- 收紧生产数据库门禁：`APP_ENV=production` 下显式 SQLite URL 会被拒绝，避免把本地数据库误部署为正式数据库；readiness 也将 SQLite 标记为不满足生产数据库要求。
- 修正前端 E2E 的首页入口：当前产品约定 `/` 跳转品牌首页 `/indisea/`，AI 搜索公共首页为 `/aisearch/`；测试已改为验证实际文档路由，桌面和移动端共 22 项通过。
- 修复生产 Cookie 安全配置在配置子类覆盖 `APP_ENV` 时不会重新计算的问题；应用工厂现在按最终生效的生产环境强制启用 Secure、HttpOnly、SameSite=Lax，并新增回归测试。
- 修正宝塔生产文档中仍推荐调用 `db.create_all()` 历史脚本的问题；生产迁移现在只保留 Alembic 命令，避免绕过 `AUTO_CREATE_SCHEMA=0` 门禁。
- 收紧真实 HTTP DeepSeek smoke：移除内置演示账号，改为由部署方注入专用低权限验收账号，避免生产验收依赖固定弱口令或把演示账号带入正式库。
- 收紧历史开发入口：`setup_and_start.py`、建库/测试账号/演示种子脚本在 `APP_ENV=production` 下拒绝执行，并在脚本说明中明确生产只能使用 Alembic、Gunicorn/Worker 和生产 smoke。
- 在 README、启动说明和运行验证记录中增加“本地/历史文档，不是生产验收”的显式警告，避免固定演示账号、旧路径或开发服务器被误用于公网部署。
- 修正生产 Compose 的 DeepSeek 紧急关闭路径：云模型开关和 required 标志可由部署环境覆盖，关闭云模型时不再被强制要求提供虚假 API key；默认仍保持 required=true 的失败关闭门禁。
