# 链易配生产部署与阶段路线

## 推荐部署形态

生产环境不要使用 GitHub Pages 承载登录和 API。GitHub Pages 只能托管静态前端，无法提供 Flask 的 `/auth/*` 和 `/api/*`。

推荐结构：

```text
用户浏览器
  -> Nginx 80/443
  -> Gunicorn
  -> Flask app
  -> MySQL / Neo4j / Redis / Ollama
  -> 独立 Agent Scheduler/Worker（询价队列、超时、回调清理）
```

仓库同时提供一个可直接用于预生产验收的 Compose 拓扑：
`docker-compose.production.yml` 会启动 MySQL、Redis、MinIO 私有对象存储、
独立 ClamAV（clamd）以及 Web/迁移/Worker 进程。Web 进程通过内部网络使用
ClamAV 的 INSTREAM 协议扫描材料，不需要在 Web 容器里安装或暴露病毒扫描端口。
生产镜像同时内置 `poppler-utils`、`tesseract-ocr` 和 `tesseract-ocr-chi-sim`，扫描版 PDF 会走受限 OCR，不会因缺少 OCR 二进制而静默降级。
使用前请在部署平台注入 `MYSQL_*`、`DATABASE_URL`、`SECRET_KEY`、`DEEPSEEK_API_KEY`（除非明确执行紧急关闭）、
`MATERIAL_ENCRYPTION_KEY`、`S3_ACCESS_KEY` 和 `S3_SECRET_KEY`，再执行：

生产进程环境变量优先于工作区 `.env`；`.env` 只用于补充未注入的本地开发默认值，
不会覆盖密钥管理系统、Supervisor 或容器编排注入的凭证。

```bash
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml ps
```

Compose 中的 `migrate` 服务先执行 `flask db upgrade`，迁移成功后才启动 Web 和
Worker；材料扫描和私有对象存储未就绪时，业务上传会失败关闭，不会把未扫描的
采购文件交给解析器。MinIO 与 ClamAV 只加入私有网络，公网只映射 Web 端口，外层
仍应使用 Nginx/网关提供 HTTPS、限流和访问日志。

Nginx、Supervisor 或容器编排可使用两个不需要登录的探针：`GET /healthz` 只确认 Web 进程存活；`GET /readyz` 检查数据库连接和链小易关键表，未就绪时返回 `503`。它们不返回密钥、连接串或业务数据；Redis、ClamAV、S3、DeepSeek 等生产门禁继续使用管理员 readiness 和 `scripts/verify/production_smoke.py`。

前端使用 Vite 构建到 `app/static/frontend`，由 Flask/Nginx 托管静态资源，不需要线上长期运行 Vite dev server。

生产启动时 `AUTO_CREATE_SCHEMA` 必须为 `0`（默认在 `APP_ENV=production` 下关闭），并且生产进程会拒绝 `sqlite://` 数据库 URL，只允许显式配置生产数据库（推荐 MySQL）。部署顺序应为：备份数据库 → 在迁移进程执行 `FLASK_APP=wsgi:app flask db upgrade` → 验证 `GET /readyz` → 再启动 Gunicorn。Web 进程不会隐式 `create_all`，避免 Alembic 迁移记录与实际表结构漂移。

## 关键生产环境变量

```bash
SECRET_KEY=use-a-long-random-secret
DATABASE_URL=mysql+pymysql://user:password@mysql-host/lianyipei
NEO4J_URI=bolt://neo4j-host:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me
REDIS_URL=redis://redis-host:6379/0

# Browser origins allowed to create/update Chain XiaoYi sessions.
# Use the public HTTPS origin of the site, without a path; comma-separate
# multiple trusted frontends. Do not use localhost in production.
TRUSTED_ORIGINS=https://your-domain.example

DISABLE_API_AUTH=0
SCHEDULER_ENABLED=1
SCHEDULER_LOCK_FILE=/tmp/lianyipei-scheduler.lock
# Split Web/Worker deployments use Redis for cross-container Worker liveness.
WORKER_HEARTBEAT_KEY=lianyipei:worker:heartbeat
WORKER_HEARTBEAT_TTL_SECONDS=30

# 采购材料生产安全：ClamAV + 加密私有对象存储（不能使用 basic/none）
MATERIAL_AV_MODE=clamav
CLAMAV_COMMAND=clamscan
MATERIAL_STORAGE_BACKEND=s3
MATERIAL_ENCRYPTION_KEY=由密钥管理系统生成的Fernet密钥
MATERIAL_S3_BUCKET=lianyipei-private-materials
MATERIAL_S3_REGION=cn-south-1
MATERIAL_S3_ENDPOINT_URL=
```

生产默认已改为 `DISABLE_API_AUTH=0`。只有本地联调才应开启。

## 上线前就绪检查

管理员登录后可调用 `GET /api/admin/production-readiness` 查看部署是否满足生产门槛。接口只返回布尔状态、provider 名称和失败项，不会返回 API key、密码或完整连接串：

```bash
curl -b session.cookie https://your-domain.example/api/admin/production-readiness
```

配置完成后，在同一部署环境执行只读连通性验收：

```bash
./.venv/bin/python scripts/verify/production_smoke.py --json
```

该命令会检查数据库、Redis、ClamAV、S3 和后台 Worker；DeepSeek 默认只检查配置而不消耗配额，确认要做真实模型探针时再显式加 `--probe-deepseek`。输出只包含状态、耗时和脱敏错误类型，不会打印密钥或连接串。

`data.ready=false` 时，优先处理 `data.required_failures`。生产硬门槛包括非默认高强度 `SECRET_KEY`、正常登录鉴权、关闭 Mock 路由、显式数据库连接、关键 Agent 数据表/列、ClamAV、S3 私有材料存储、Fernet 加密密钥、显式询价审批、HTTPS `TRUSTED_ORIGINS`，以及实际可运行的后台 Worker。Web 进程可以关闭 `SCHEDULER_ENABLED`，但独立 Worker 必须发布有效的 Redis 心跳；仅设置 `LIANYIPEI_WORKER_ENABLED`、消息队列 URL 或调度器开关都不能伪造存活证据。仅设置调度器开关但没有任何进程持有调度器锁/心跳时会失败关闭。电子签、支付、SMTP、企业微信及工商/税务/电力接口会作为可选集成显示，未配置时业务必须保持失败关闭。该检查会只读检查当前数据库结构，但不会写入数据库或主动连接第三方系统；真实第三方连通性仍需在部署环境用供应商沙盒回调验收。独立 Worker 每 10 秒向 Redis 发布短期心跳，Web 可跨容器检测其存活；心跳过期后 readiness 会失败关闭。

只要密钥管理系统向进程注入 `DEEPSEEK_API_KEY`，链小易默认启用 DeepSeek；将 `CHAINXIAOYI_CLOUD_ENABLED=false` 可作为紧急关闭开关。Compose 允许在该紧急模式下不注入模型密钥；默认的 `CHAINXIAOYI_CLOUD_REQUIRED=true` 仍会让未配置真实密钥的实例 readiness 失败关闭。若确需关闭云模型，必须同时显式设置 `CHAINXIAOYI_CLOUD_ENABLED=false`，并确认主流程按文档允许的规则/人工降级运行；不能只删除密钥后把 required 保持为 true。模型启用时，运行时故障返回 `503 model_unavailable`，不会悄悄以规则模式冒充云模型。密钥不会被接口状态或审计接口返回。

DeepSeek 调用对连接超时、429 和 5xx 等临时错误使用有上限的指数退避重试，默认最多重试 2 次。可通过 `DEEPSEEK_MAX_RETRIES`（0–5）和 `DEEPSEEK_RETRY_BACKOFF_SECONDS`（0–10 秒）调节；鉴权错误等 4xx 不重试，避免放大配额消耗或掩盖密钥配置问题。

### RFQ 外部渠道状态回写

邮件或企业微信供应商适配器可以向以下接口回报传输状态：

```text
POST /api/chain-xiaoyi/delivery-callback/<email|wechat|work_wechat>
X-Lianyipei-Signature: sha256=<HMAC-SHA256(raw-json, RFQ_DELIVERY_CALLBACK_SECRET)>
```

JSON 至少包含 `event_id`、`status`（`queued`、`sent`、`delivered`、`read` 或 `failed`）以及 `outbound_id` 或 `provider_message_id`。事件会使用 `external_callback_receipts` 去重，状态只会单调推进，过期的 delivered 回调不能覆盖 read/replied；失败原因会进入外发审计记录。该接口不会创建询价、修改报价或绕过人工审批。

询价草稿的 `channels` 支持 `work_wechat`。服务端通过企业微信应用消息接口获取并缓存 `access_token`，仅向已认领且明确授权的企业 `wechat_work_userid` 发送消息；未认领、未授权或未绑定 UserID 时会记录 `skipped`，不会猜测联系人。回执中的 `provider_message_id` 会写入外发审计，可继续由 `delivery-callback/work_wechat` 回写传输状态。

### RFQ 供应商报价回写

邮件、企业微信或中间适配器完成供应商身份校验并把消息解析成结构化 JSON 后，可调用：

```text
POST /api/chain-xiaoyi/quote-callback/<email|wechat|work_wechat>
X-Lianyipei-Signature: sha256=<HMAC-SHA256(raw-json, RFQ_QUOTE_CALLBACK_SECRET)>
```

请求至少包含 `event_id`、`quote_id`、`confirmed` 和 `reply_price`；商业条款放在 `reply_details`。`confirmed=false` 只返回待确认预览，不会改变报价状态；只有明确确认的签名事件才会把待报价置为 `accepted`。事件使用同一幂等回执表去重，重复回调不会重复入账。

### 邮件报价入站

邮件网关解析 MIME 后，将发件人授权邮箱和纯文本正文通过签名请求转发到：

```text
POST /api/chain-xiaoyi/email-quote-inbound
X-Lianyipei-Signature: sha256=<HMAC-SHA256(raw-json, RFQ_EMAIL_INBOUND_SECRET)>
```

请求至少包含 `event_id`、`from_email` 和 `text`。正文使用“报价 #询价ID 单价…”生成预览；供应商明确使用“确认报价 #询价ID …”后才会入账。系统会校验企业认领状态、邮箱授权和询价供应商归属，并按 `event_id` 幂等处理。

仓库提供 `scripts/workers/email_quote_poller.py` 和
`deploy/baota/supervisor-lianyipei-email-worker.conf`。Worker 通过 IMAP over
SSL 读取 `UNSEEN` 邮件，提取纯文本后签名转发；只有接口返回 2xx 才标记邮件为已读，解析失败或应用不可用时会保留邮件等待下一轮重试。生产启用时必须同时配置 IMAP 凭据、`RFQ_EMAIL_INBOUND_SECRET` 和 HTTPS 回调地址。

可先用 `python scripts/workers/email_quote_poller.py --once` 做一次配置验收；未配置完整时会失败关闭并返回原因，不会连接或删除邮件。

### 订单与履约状态回写

ERP、支付、物流、质检或电子合同适配器可使用独立密钥回写有限的事实事件：

```text
POST /api/chain-xiaoyi/fulfillment-event-callback/<erp|payment|econtract|logistics|quality|tax>
X-Lianyipei-Signature: sha256=<HMAC-SHA256(raw-json, FULFILLMENT_CALLBACK_SECRET)>
```

请求包含 `event_id`、`enterprise_id`、`order_id`、`event_type`。支持成功事件 `contract_signed`、`payment_succeeded`、`invoice_validated`、`shipment_dispatched`、`quality_passed`、`delivery_confirmed`，以及异常事件 `contract_failed`、`payment_failed`、`invoice_rejected`、`shipment_delayed`、`quality_failed`、`delivery_failed`。事件按 `event_id` 幂等，订单状态只单调推进；合同和付款确认仍必须由采购方单独确认，外部回调不能绕过该门槛。回调会把事实写入链小易任务审计；延期或失败会将关联任务标记为 `fulfillment_exception`，供采购员恢复处理。

电子合同创建/签署请求还会携带稳定的 `Idempotency-Key`；适配器重试时应原样转发该 header，并在供应商侧按该键去重。

## 企业微信/公众号报价回收验收

供应商账号必须先绑定对应的公众号 OpenID 或企业微信 UserID。询价发出后，供应商可发送：

```text
报价 询价ID 单价12.8元 含税13% MOQ500 交期25天 模具费1200元 运费0元 付款30%预付 有效期30天
```

系统只返回结构化预览，不会在此时形成商业承诺。供应商核对后将开头改为 `确认报价` 再发送，报价才会入库并进入链小易报价汇总。回调必须通过微信验签/企业微信 AES 验签解密；同一消息 ID 只处理一次。完成回执保留 30 天，遗留处理中回执在 24 小时后释放，每日由独立调度进程清理。

## 多行采购材料批量询价验收

对接外部工作台时可使用统一资源路径：`POST/GET /api/chain-xiaoyi/materials`、`POST/GET /api/chain-xiaoyi/procurement-tasks`，字段修正、候选重算、询价预览、审批、发送和进度分别位于同一采购任务资源下。旧的 `/sessions/<id>/files` 与 `/tasks/<id>/...` 路径继续兼容，避免前端升级时中断已有会话。

Excel/CSV 中的每个有效采购行会独立保留产品、规格、数量、交期等单元格证据，并分别执行数据库候选召回。工作台允许逐采购项复核候选，但对外发送采用一个材料父任务的统一预览：展示每个采购项、供应商范围、渠道和正文，采购方一次确认后才原子化地把所有子询价放入后台队列。

每个 `采购行 × 供应商` 使用来源 RFQ 任务键保证幂等；重试不会重复生成报价，相同产品但不同规格也不会错误合并。全部子任务发送完成后父任务自动转为 `completed`，任一终态失败则转为 `partial_failure`，可从待办中心恢复审计上下文。

候选结果同时返回 `data_freshness`（`fresh`、`stale` 或 `unknown`）、更新时间和配置的最大数据年龄；过期或缺少时间戳的企业仍可用于人工召回，但不会被界面或导出标记为“最新事实”，需要重新核验后再作为可信能力使用。

报价回收后，父任务还提供 `GET /api/chain-xiaoyi/tasks/<id>/batch-quote-summary` 和 `POST /api/chain-xiaoyi/tasks/<id>/batch-quote-query`，采购方可以用一句话对每个采购项分别筛选已回收报价。`POST /api/chain-xiaoyi/tasks/<id>/batch-order-drafts` 只生成可审阅草稿；只有明确 `confirm=true` 调用 `.../batch-order-drafts/confirm` 才会一次创建正式订单。合同与付款仍保留逐单独立确认，批量操作具备事务回滚和幂等返回。

## Gunicorn 示例

```bash
venv/bin/gunicorn 'app:create_app()' \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 120
```

也可使用仓库提供的入口 `wsgi:app`。生产 Web 进程必须使用 Gunicorn/uWSGI，不能使用 `python run.py` 的 Flask 开发服务器：

```bash
venv/bin/gunicorn wsgi:app --bind 127.0.0.1:8000 --workers 2 --timeout 120
```

APScheduler 已增加进程锁，避免多 worker 重复启动同一组定时任务。更稳的生产方式是把定时任务拆成独立进程，Web worker 设置：

```bash
SCHEDULER_ENABLED=0
```

再单独启动一个启用调度器的进程。

## 阶段路线

- Phase 1：生产部署基础
  - Nginx + Gunicorn + Flask。
  - MySQL / Neo4j 接入。
  - 关闭联调免登录。
  - 密钥全部使用环境变量。

- Phase 2：核心业务闭环
  - 发布需求、AI 匹配、意向报价、合同/撮合码、履约记录、信用分更新。
  - 政府端风险监控、预警处置、审核归档。
  - 管理端规则配置、接口配置、日志审计、演示数据。

- Phase 3：Hermes 微信智能告警
  - 红色预警交给 Hermes 总结。
  - 微信中查询预警和准备处置动作。
  - 写操作必须确认后执行。

- Phase 4：移动端
  - 先做响应式 Web/PWA 或 H5 封装。
  - 确有微信生态需求后再做 Taro/uni-app 小程序。
  - 原生 App 放到最后。
