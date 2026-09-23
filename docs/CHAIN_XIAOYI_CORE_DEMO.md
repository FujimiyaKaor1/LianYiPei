# 链小易核心一条龙演示

这份演示只使用明确标记为 `is_demo=true` 的广东电子/五金样例企业；演示记录不会进入生产推荐。生产环境必须使用企业自主认领和公开可核验数据。

## 启动

```bash
cd /Users/fujimiyakaori/Documents/ChatGPT/lypdemo
source .venv/bin/activate
export LIANYIPEI_DEV_SQLITE_FALLBACK=1
export APP_ENV=development
python scripts/seed/seed_guangdong_agent_demo.py
flask --app wsgi:app run --host 127.0.0.1 --port 5051
```

打开 [http://127.0.0.1:5051/aia](http://127.0.0.1:5051/aia)，用脚本输出的演示采购方账号登录。

## 演示路径

1. 上传含 `product`、`quantity`、`specification`、`delivery_days` 列的 CSV/XLSX，或直接输入：`找广东能做精密连接器、2000件、30天交付的工厂`。Word/PDF 的固定字段先走确定性解析；如果是自然语言段落且字段缺失，链小易才调用 DeepSeek 补充，并且只接受正文中可逐字核验的引用证据。
2. 链小易生成字段证据和采购任务，自动召回广东候选企业；未认领或未授权企业不会进入询价选择。
3. 也可以直接在一句话中说“帮我找广东连接器工厂，采购100件，并准备询价”。链小易会自动选择前5家已认领且授权触达的候选，生成询价预览；不会在聊天消息中直接外发。
4. 检查供应商范围、披露内容和触达渠道，点击一次确认后进入后台队列。
   每条询价默认有 72 小时供应商回复窗口（可在 API 预览中用 `quote_deadline_at` 覆盖，最长 30 天）；后台每分钟关闭未回复的记录并标记为 `timed_out`，不会让任务永久停在“已发送”。
   后台真正发送前会再次读取供应商当前的认领和触达授权；审批后撤销授权会失败关闭，不会按旧候选快照继续发送。
5. 供应商可在站内、企业微信或邮件适配器回复结构化报价。外部适配器调用签名回调：

   ```text
   POST /api/chain-xiaoyi/quote-callback/<provider>
   X-Lianyipei-Signature: sha256=<HMAC(raw-json, RFQ_QUOTE_CALLBACK_SECRET)>
   ```

   报价 JSON 至少包含 `event_id`、`quote_id`、`supplier_id`、`confirmed`、`reply_price`。首次 `confirmed=false` 只生成预览，改为 `true` 才入账。

   如果使用邮件网关，可直接把纯文本入站到：

   ```text
   POST /api/chain-xiaoyi/email-quote-inbound
   X-Lianyipei-Signature: sha256=<HMAC(raw-json, RFQ_EMAIL_INBOUND_SECRET)>
   {"event_id":"mail-1","from_email":"供应商已授权邮箱","text":"确认报价 #123 单价12.8元 含税13% 交期25天"}
   ```

   系统会按授权邮箱反查供应商，不接受未认领或未授权发件人。

6. 在报价汇总中输入一句话，例如“只看含税价最低且 30 天内能交付的一家”，系统只基于供应商实际回复筛选。
   也可以直接在链小易会话中说：“只看含税价最低且 30 天内能交付的一家，并生成订单草稿”。系统会复用当前询价任务生成可审阅草稿，不会在聊天里越过正式订单确认。
7. 生成订单草稿；正式订单、合同和付款仍保留独立人工确认。
8. 订单生成后，可用签名的 ERP/支付/物流回调写入 `payment_succeeded`、`shipment_dispatched`、`delivery_confirmed` 等事实事件；回调不会代替合同或付款确认。

询价进度会区分 `sent`、`delivered`、`read`、`replied`、`rejected`、`timed_out` 和 `failed`。供应商拒绝属于已回复的终态但不会进入报价推荐；截止后的迟到回调或报价不会重新打开任务。
采购方仍可从任务待办中对 `timed_out` 任务点击重新触达；系统复用原询价记录、重置新的回复窗口，不会重复创建报价或订单。

## DeepSeek

不要把密钥写入仓库或 `.env`。在部署平台的密钥管理系统中注入 `DEEPSEEK_API_KEY` 后，链小易默认启用视觉模型 `deepseek-v4-flash-vision-exp`；如需使用已批准的其他模型，可通过部署环境的 `DEEPSEEK_MODEL` 覆盖；如需紧急停用，设置 `CHAINXIAOYI_CLOUD_ENABLED=false`。模型只参与意图抽取、材料理解和证据解释，企业事实、分数、排序和报价始终来自数据库与供应商回执。当前客户端会透传 `text`/`image_url` 多模态消息块；扫描件原图是否送入模型仍由材料解析链路的授权和大小限制控制。

生产模板同时设置 `CHAINXIAOYI_CLOUD_REQUIRED=true`：DeepSeek 鉴权、网络或响应失败时接口会返回 `503 model_unavailable` 并停止本次 Agent 执行，不会把规则降级结果伪装成云模型结果。开发环境未设置该开关时，才会按规则引擎继续演示。

## 验证

```bash
./.venv/bin/pytest -q
cd frontend && npm run lint && npm run build
```

也可以用一次命令跑完整的真实模型演示。密钥只从当前进程环境读取，不写入仓库或 `.env`：

```bash
export DEEPSEEK_API_KEY='由密钥管理系统注入'
export CHAINXIAOYI_CLOUD_ENABLED=true
./.venv/bin/python scripts/verify/chain_xiaoyi_demo.py --json
```

如果不希望把密钥写进当前 shell 环境，也可以让演示进程从隐藏输入读取；密钥只存在于该短生命周期进程，不会写入 `.env`、命令行参数或演示报告：

```bash
./.venv/bin/python scripts/verify/chain_xiaoyi_demo.py --api-key-stdin --json --confirm-order --simulate-fulfillment
```

如果要验证“文件即任务”，可直接把 CSV/XLSX/PDF/DOCX 作为参数传入。脚本会调用真实上传解析接口，保留字段证据，再进入同一条询价、报价、订单和履约链路：

```bash
./.venv/bin/python scripts/verify/chain_xiaoyi_demo.py \
  --material ./examples/chain_xiaoyi/采购需求.csv \
  --json --confirm-order --simulate-fulfillment
```

如果服务已经由 Flask/Gunicorn 监听，可再执行真实 HTTP smoke（不使用 Flask test client）。它会检查监听服务确实启用 DeepSeek、登录专用验收采购方、创建会话并发送一条自然语言采购请求；规则模式会直接失败，避免误报：

```bash
LIVE_SMOKE_BUYER_NAME='专用验收采购账号' \
LIVE_SMOKE_BUYER_PASSWORD='由密钥管理系统临时注入' \
./.venv/bin/python scripts/verify/live_chain_xiaoyi_smoke.py \
  --base-url http://127.0.0.1:5112
```

该 smoke 不再内置或创建演示账号；生产/预生产必须使用一次性或专用的低权限采购账号，密码应通过环境变量或密钥管理系统注入，不要写入命令行历史。若要使用虚构企业和固定演示账号，只能运行本地演示种子与演示脚本，不能把它们带入生产库。

该命令用于单个采购项的核心演示；多行 Excel 采购单在网页工作台中使用批量候选、批量询价和批量订单草稿流程。

脚本会用明确标记的演示企业完成“DeepSeek 意图抽取 → 数据库找厂 → 站内询价审批 → 签名报价回收 → 一句话报价筛选 → 报价汇总 → 订单草稿”。增加 `--confirm-order` 会继续执行人工确认后的正式订单步骤；再增加 `--simulate-fulfillment` 会在正式订单后执行合同/付款确认，并通过签名 ERP 回调模拟发货和交付，最终将任务推进到 `fulfillment_completed`。该参数仅用于本地演示，不代表生产环境自动替用户确认合同或付款。

完整演示命令：

```bash
./.venv/bin/python scripts/verify/chain_xiaoyi_demo.py --json --confirm-order --simulate-fulfillment
```
