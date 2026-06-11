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
```

前端使用 Vite 构建到 `app/static/frontend`，由 Flask/Nginx 托管静态资源，不需要线上长期运行 Vite dev server。

## 关键生产环境变量

```bash
SECRET_KEY=use-a-long-random-secret
DATABASE_URL=mysql+pymysql://user:password@mysql-host/lianyipei
NEO4J_URI=bolt://neo4j-host:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=change-me
REDIS_URL=redis://redis-host:6379/0

DISABLE_API_AUTH=0
SCHEDULER_ENABLED=1
SCHEDULER_LOCK_FILE=/tmp/lianyipei-scheduler.lock
```

生产默认已改为 `DISABLE_API_AUTH=0`。只有本地联调才应开启。

## Gunicorn 示例

```bash
venv/bin/gunicorn 'app:create_app()' \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 120
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
