# 目标服务器外部生产验收模板

本文件用于目标服务器/供应商沙盒验收，不要把密码、API Key、私钥或完整连接串回传到聊天、工单或 Git。只回传脱敏后的命令结果和状态。

## A. 目标服务器信息

由运维人员填写：

```text
部署环境：预生产 / 生产
域名：
HTTPS 证书：已配置 / 未配置
代码版本（git rev-parse --short HEAD）：
APP_ENV=production：是 / 否
数据库类型：MySQL 8.x
是否有独立备份和恢复点：是 / 否
```

不要提交 `.env` 内容；只确认必需变量是否已由密钥管理系统注入。

## B. 生产启动与数据库验收

在目标服务器项目目录执行：

```bash
export APP_ENV=production
export AUTO_CREATE_SCHEMA=0
export DISABLE_API_AUTH=0
export ENABLE_MOCK_API=false
export CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL=true

FLASK_APP=wsgi:app .venv/bin/flask db upgrade
FLASK_APP=wsgi:app .venv/bin/flask db current
curl -fsS https://your-domain.example/healthz
curl -fsS https://your-domain.example/readyz
.venv/bin/python scripts/verify/production_smoke.py --json
```

验收必须满足：

- Alembic 当前版本为仓库最新迁移 `h3d4e5f6a7b8` 或更高版本；
- `/healthz` 返回 HTTP 200；
- `/readyz` 返回 HTTP 200；
- smoke JSON 的 `ready` 为 `true`；
- `required_failures` 为空；
- `database`、`redis`、`clamav`、`s3`、`worker` 均为 `ok`。

如果紧急关闭云模型，必须显式设置：

```bash
CHAINXIAOYI_CLOUD_ENABLED=false
CHAINXIAOYI_CLOUD_REQUIRED=false
```

此时必须确认业务页面明确显示规则/人工降级状态；不能把规则结果标记为 DeepSeek 结果。

## C. 真实模型验收（可选但启用云模型时必做）

只在确认允许消耗一次低额度配额时执行：

```bash
.venv/bin/python scripts/verify/production_smoke.py --json --probe-deepseek
```

启用云模型时，`checks.deepseek.ok` 必须为 `true`。不要把 API Key 或模型响应原文回传。

## D. 浏览器主链路验收

使用一个专用、低权限、临时采购账号执行，不要使用 `admin/admin`、`test_ent/123456` 或任何演示账号：

```bash
LIVE_SMOKE_BUYER_NAME='临时验收采购账号' \
LIVE_SMOKE_BUYER_PASSWORD='由密钥管理系统注入' \
.venv/bin/python scripts/verify/live_chain_xiaoyi_smoke.py \
  --base-url https://your-domain.example
```

然后人工确认以下闭环：

```text
登录 → 企业名录 → 供需匹配 → 材料上传/扫描 → 询价预览
→ 明确审批发送 → 报价回收 → 订单草稿 → 明确确认订单
→ 履约事件回写 → 管理员审计查询
```

每一步记录：HTTP 状态、页面结果、是否产生预期审计事件；不要上传真实客户敏感材料做首次验收。

## E. 外部供应商沙盒矩阵

对已启用的集成逐项填写；未启用的集成必须保持失败关闭，不能填“模拟成功”。

| 集成 | 沙盒/测试租户 | 签名校验 | 幂等重放 | 失败重试 | 结果 |
|---|---|---|---|---|---|
| 邮件/IMAP 报价 |  |  |  |  | 未验收 |
| 企业微信/公众号 |  |  |  |  | 未验收 |
| 电子合同 |  |  |  |  | 未验收 |
| 支付 |  |  |  |  | 未验收 |
| 物流 |  |  |  |  | 未验收 |
| 税务/发票 |  |  |  |  | 未验收 |
| Neo4j 图谱（如启用） |  | 不适用 | 不适用 | 查询权限 | 未验收 |

## F. 备份恢复与公网安全

至少完成一次隔离恢复演练，并保留结果：

```text
MySQL 备份生成成功：是 / 否
uploads/S3 对象备份成功：是 / 否
隔离环境恢复成功：是 / 否
恢复后 /readyz：200 / 失败
公网扫描确认 3306、6379、7474、7687、8000 未暴露：是 / 否
HTTP 自动跳转 HTTPS：是 / 否
Nginx 限流和安全响应头：是 / 否
```

只有 A-F 均有证据，且没有未解释的 `required_failures`，才可切换小额度真实流量。
