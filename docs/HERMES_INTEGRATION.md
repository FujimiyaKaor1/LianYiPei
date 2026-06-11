# Hermes 微信智能告警与远程确认操作

本文档说明链易配与本机 Hermes 的集成方式。目标是让红色预警先交给 Hermes 总结，再通过 Hermes 微信号通知，并允许用户在 Hermes 中查询和准备处置动作。

## 已实现能力

- 红色预警触发时，链易配会先尝试调用本机 Hermes API Server。
- Hermes 不可用或未配置时，链易配继续走原有微信模板消息、短信日志和站内消息，不阻断告警。
- Hermes 可通过内部 API 查询预警列表和预警详情。
- Hermes 可创建待确认动作，并在用户回复 `确认执行` 后执行。
- 当前开放的动作：
  - `assign_alert`：派发预警处置任务。
  - `close_alert`：关闭预警并写入处置记录。
  - `mark_alert_read`：标记该预警已被 Hermes 处理/读取。

## 链易配环境变量

在链易配项目 `.env` 中配置：

```bash
HERMES_API_SERVER_URL=http://127.0.0.1:8642/v1
HERMES_API_SERVER_KEY=change-me
HERMES_WEIXIN_TARGET=weixin

HERMES_LIANYIPEI_BASE_URL=http://127.0.0.1:5100
HERMES_LIANYIPEI_TOKEN=change-me-strong-token
HERMES_ACTION_CONFIRM_TTL_SECONDS=300
HERMES_ALLOWED_REMOTE_ADDRS=127.0.0.1,::1,localhost
HERMES_TRUST_PROXY_HEADERS=0
```

`HERMES_API_SERVER_KEY` 必须与 Hermes `API_SERVER_KEY` 一致。  
`HERMES_LIANYIPEI_TOKEN` 必须与 Hermes 插件侧配置一致。

## Hermes 配置

在 `~/.hermes/.env` 中配置：

```bash
API_SERVER_ENABLED=true
API_SERVER_KEY=change-me
HERMES_LIANYIPEI_BASE_URL=http://127.0.0.1:5100
HERMES_LIANYIPEI_TOKEN=change-me-strong-token
```

在 `~/.hermes/config.yaml` 中启用插件：

```yaml
plugins:
  enabled:
    - chainyipei
```

插件目录：

```text
~/.hermes/plugins/chainyipei/
```

## 内部 API

Hermes 使用独立 Bearer token 访问以下接口：

```text
GET  /api/hermes/alerts
GET  /api/hermes/alerts/<id>
POST /api/hermes/actions/preview
POST /api/hermes/actions/execute
```

所有接口默认只允许本机地址访问。若未来放到反向代理后面，只有在可信代理已正确清洗请求头时，才开启：

```bash
HERMES_TRUST_PROXY_HEADERS=1
```

## 操作确认规则

写操作必须先调用 `preview`，获得 `pending_action_id` 和摘要。  
用户必须回复完全一致的确认短语：

```text
确认执行
```

默认 300 秒过期，由 `HERMES_ACTION_CONFIRM_TTL_SECONDS` 控制。

## 验收方式

1. 启动链易配后端。
2. 启动 Hermes gateway，并确认 Weixin 与 API Server 已启用。
3. 手动生成红色预警。
4. 微信收到 Hermes 总结后的预警摘要。
5. 在微信中让 Hermes 查询该预警详情。
6. 让 Hermes 准备派发或关闭动作，确认只在回复 `确认执行` 后生效。
