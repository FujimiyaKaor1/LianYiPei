# 链易配：新加坡宝塔服务器完整部署规格

本文是面向“企业采购端 + 供应商端 + 平台/园区管理端 + Agent 增量能力”的单机部署方案。它适合比赛网络初评、现场演示和小规模试运行，不是面向大规模生产的高可用集群方案。

## 1. 先给结论

推荐使用一台新加坡云服务器，宝塔只负责网站和进程管理，业务服务按下表运行：

```text
浏览器
  -> HTTPS / Nginx（公网 443）
  -> Gunicorn Web（127.0.0.1:8000）
  -> Flask：采购、供应商、管理端、Agent、上传、API
       -> MySQL 8（业务主数据）
       -> Neo4j 5（产业链图谱）
       -> Ollama（可选，本机 Agent 模型）
       -> 文件目录 uploads（附件、交付证明等）

Supervisor 单独启动 scheduler：预警、信用、价格、产能、清理等定时任务
```

云端负责“共享、远程演示和数据留存”，比赛现场保留本地 SQLite/本地运行包作为兜底。管理端不接入 Agent；Agent 只服务采购端和供应商端，并且写操作必须经过用户确认。

## 2. 服务器规格

| 项目 | 最低可运行 | 推荐比赛配置 | 说明 |
|---|---:|---:|---|
| CPU | 4 vCPU | 8 vCPU | Flask、Neo4j、构建和查询并发更稳 |
| 内存 | 8 GB | 16 GB | 若同机 Ollama，推荐 16 GB |
| 系统盘 | 80 GB SSD | 120 GB SSD | 系统、代码、依赖、日志 |
| 数据/备份盘 | 100 GB | 200 GB | MySQL、Neo4j、上传和备份分开更安全 |
| 公网 IPv4 | 必须 | 必须 | 远程演示和 DNS |
| 带宽 | 5 Mbps | 10 Mbps | 演示视频/大文件另行放对象存储 |
| 系统 | Ubuntu 22.04/24.04 LTS、Debian 12 | Ubuntu 22.04/24.04 LTS | 与宝塔兼容性优先 |

如果使用 8 GB 服务器，不建议同机运行 Qwen 7B 或 `model_service` 的 Transformers 服务。Agent 可暂时关闭，或接入可信的外部 OpenAI 兼容模型；比赛主流程必须保留规则匹配和传统页面，不能把模型作为唯一依赖。

新加坡节点可以部署，但湖南本地访问延迟可能高于中国大陆节点。若比赛评委主要在大陆访问，优先选择网络质量稳定、可备案/合规使用的节点；如果域名和合规条件未准备好，可以直接使用 IP + HTTPS 或仅在演示环境使用 HTTP。

## 3. 宝塔面板安装项

宝塔软件商店安装：

- Nginx 1.24+；
- Python 项目管理器或系统 Python 3.11；
- Node.js 20 LTS（仅用于构建前端，不需要长期运行）；
- MySQL 8.0；
- Supervisor 管理器；
- Git；
- Certbot 或宝塔 SSL 模块；
- Redis 7（生产部署必须安装并通过 `production_smoke.py`；仅本地开发可以省略）。

Neo4j 5.x 建议按 Neo4j 官方 Debian/Ubuntu 包安装并设置为 systemd 服务。若宝塔应用商店没有合适版本，不要从面板随便安装旧版；可以使用 Docker 运行 Neo4j，但仍应绑定到 `127.0.0.1:7687`。

## 4. 目录与权限

推荐目录：

```text
/www/wwwroot/lianyipei/          # 项目代码
/www/wwwroot/lianyipei/.venv/    # Python 虚拟环境
/www/wwwroot/lianyipei/uploads/  # 上传文件，不进入 Git
/www/wwwroot/lianyipei/logs/     # Supervisor 日志
/www/backup/lianyipei/            # 数据备份
/var/run/lianyipei/              # 调度器锁
```

代码目录和 `.env` 归部署用户所有；`uploads`、`logs`、`/var/run/lianyipei` 必须允许运行 Web 和 scheduler 的用户写入。不要把 `uploads` 目录直接配置为可执行目录，不要把 `.env`、数据库备份、模型文件放在 Nginx 可公开访问的目录。

## 5. 初始化命令

以下命令在服务器 SSH 终端执行，路径按实际情况替换：

```bash
cd /www/wwwroot/lianyipei
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt

cd frontend
npm ci
npm run build
cd ..

mkdir -p uploads logs /var/run/lianyipei /www/backup/lianyipei
chown -R www:www uploads logs /var/run/lianyipei
```

前端构建结果必须出现在 `app/static/frontend`。线上不要运行 `npm run dev`，也不要把 3000 端口暴露到公网。

## 6. MySQL 配置

建议创建专用数据库和专用账号，不使用 root 运行应用：

```sql
CREATE DATABASE lianyipei CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lianyipei_app'@'127.0.0.1' IDENTIFIED BY '请替换为强密码';
GRANT ALL PRIVILEGES ON lianyipei.* TO 'lianyipei_app'@'127.0.0.1';
FLUSH PRIVILEGES;
```

然后在项目根目录复制 `deploy/baota/.env.production.example` 为 `.env` 并填写 `DATABASE_URL`。密码如含 `@`、`:`、`/`、`#`、`?`，必须做 URL 编码。

初始化/迁移建议：

```bash
source /www/wwwroot/lianyipei/.venv/bin/activate
cd /www/wwwroot/lianyipei
# 生产环境只执行 Alembic 迁移；不要执行 init_db.py、fresh_init.py 或演示种子脚本。
# 这些脚本可能清空数据库或写入演示数据。
FLASK_APP=wsgi:app flask db upgrade
FLASK_APP=wsgi:app flask db current
```

正式数据已经存在时，不要运行 `init_db.py`、`fresh_init.py`、
`scripts/migrate/migrate_db.py`、`scripts/migrate/migrate_new_tables.py` 或任何演示
种子脚本。前两个历史迁移脚本内部仍调用 `db.create_all()`，不符合生产的
`AUTO_CREATE_SCHEMA=0` 门禁，只能用于隔离的开发/历史环境。生产只允许先备份，
再按仓库中的 Alembic 迁移执行增量变更：

```bash
FLASK_APP=wsgi:app flask db upgrade
FLASK_APP=wsgi:app flask db current
```

完成后用现有 `scripts/verify/` 脚本验证订单、发票、数据授权、消息和调度器。
生产模式下 `AUTO_CREATE_SCHEMA=0`，`create_app()` 不会执行 `db.create_all()`；
迁移必须在启动 Web 前完成。

## 7. Neo4j 配置

Neo4j 用于产业链上下游图谱和只读图查询：

```text
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=强密码
```

不要开放 7474/7687 到公网；管理端图谱由 Flask 代理使用。初始化关系数据可以执行：

```bash
source /www/wwwroot/lianyipei/.venv/bin/activate
cd /www/wwwroot/lianyipei
python scripts/seed/import_graph.py
```

图谱可以从 `data/relations.csv` 重建，因此比赛阶段备份重点是 MySQL、`uploads` 和关系数据文件。若需要物理备份 Neo4j，应在维护窗口停止数据库后使用对应 Neo4j 5.x 版本的 `neo4j-admin database dump`，不要在数据库运行中直接复制 store 目录。

## 8. Agent / 大模型配置

当前仓库的 BizMind/智能查询路径默认通过 Ollama 原生接口，关键配置是 `OLLAMA_BASE_URL`、`OLLAMA_MODEL` 和 `BIZMIND_OLLAMA_MODEL`。

推荐优先级：

1. 16 GB 服务器：同机 Ollama，使用轻量中文模型，模型只监听 `127.0.0.1:11434`；
2. 8 GB 服务器：不部署大模型，使用外部模型服务的内网/受控地址；
3. 模型不可用时：保留传统匹配、固定规则查询和页面操作，前端显示“智能能力暂不可用”，不影响业务演示。

使用 Ollama 时，模型应先在服务器上下载并验证：

```bash
ollama pull qwen2.5:3b
ollama list
curl http://127.0.0.1:11434/api/tags
```

不建议当前比赛版把 `model_service/` 的 Transformers/Qwen 服务部署在同一台普通 CPU 宝塔服务器上：它会增加内存占用、下载时间和故障点。需要时把它放到独立 GPU 机器，并让主项目只访问其内网地址。

Agent 工具权限仍按产品设计执行：查询可自动执行；生成询价、报价、订单等草稿后必须预览；发送询价、提交报价、创建订单、修改状态必须由用户确认。

## 9. Web、调度器和 Nginx

将 `deploy/baota/supervisor-lianyipei.conf` 粘贴到宝塔 Supervisor 管理器，替换项目目录。Web 使用 2 个 Gunicorn worker；调度器使用独立单进程。根 `.env` 设置 `SCHEDULER_ENABLED=0`，模板中的 `LIANYIPEI_SCHEDULER_ENABLED` 负责为两个进程分别覆盖配置。

将 `deploy/baota/nginx-lianyipei.conf` 作为宝塔“网站配置文件”中的 `server` 片段使用，替换域名和项目绝对路径；它不是可直接作为 `/etc/nginx/nginx.conf` 的完整配置。必须同时在宝塔 SSL 模块中启用 HTTPS（80 端口只用于跳转/证书签发），并配置限流和安全响应头。Nginx 对 `/static/` 直接提供 Vite 构建产物，其余请求转发给 Flask。`/api/chat` 已单独关闭代理缓冲，否则 Agent 的 SSE 流式回复会被 Nginx 聚合后才显示。

部署后检查：

```bash
curl -I http://127.0.0.1:8000/
curl -I https://lianyipei.example.com/
ss -lntp | grep -E ':(80|443|8000|7687|11434)'
```

公网只应看到 80/443（SSH 和宝塔面板另行限制来源 IP）；8000、3306、6379、7474、7687、11434 不应开放公网。

## 10. 防火墙和安全基线

宝塔安全设置只放行：

- SSH 22：最好只允许团队固定 IP；修改默认端口不是安全替代品；
- 宝塔面板端口：只允许团队固定 IP；
- 80/443：按需要开放，80 仅用于跳转/证书签发；
- 不开放 MySQL 3306、Redis 6379、Neo4j 7474/7687、Ollama 11434、Flask 8000。

上线前必须：

- `SECRET_KEY` 使用随机值，关闭 `DISABLE_API_AUTH`；
- 删除示例默认账号或立刻改密码；
- 不在聊天、日志和仓库中写入 API Key/数据库密码；
- 限制上传类型和大小，定期清理异常文件；
- 开启 HTTPS、Secure/HttpOnly Cookie 和安全响应头；
- 只允许可信 CORS 来源；
- 管理端、数据授权、审计和写入接口做角色校验；
- 保留 Web、scheduler、Nginx、MySQL 的错误日志，但避免记录身份证、密码和完整 Token。

## 11. 定时任务

项目当前调度器包含 12 类任务，包括：每小时预警检查、信用分重算、预警升级、招商清单、价格指数、产能利用率、质量标签过期、授权数据同步、外部接口检测、旧消息清理等。

宝塔计划任务建议只做两件事：

- 每天 03:30 执行 `deploy/baota/backup-lianyipei.sh`；
- 每周一次检查 Supervisor 中 `lianyipei-web` 和 `lianyipei-scheduler` 状态。

不要再通过宝塔计划任务重复启动 `python run.py`，否则会造成重复调度或端口冲突。

## 12. 备份、恢复和回滚

`deploy/baota/backup-lianyipei.sh` 会备份 MySQL 和 `uploads`，默认保留 14 天。至少保留一份服务器之外的副本（对象存储、另一台机器或下载到本地）。

恢复演练至少做一次：

```bash
tar -xzf lianyipei_*.tar.gz -C /tmp/lianyipei-restore
mysql -u lianyipei_app -p lianyipei < /tmp/lianyipei-restore/mysql.sql
```

代码发布采用“先备份、再拉取、构建、迁移、重启、冒烟检查”的顺序；保留上一个 Git commit 或压缩包。数据库迁移必须向后兼容，避免先删除旧字段再发布旧代码。

## 13. 云端与比赛现场双轨方案

云端版用于：多人共享、远程答辩、管理端数据留存、完整图谱和预警；本地版用于：服务器故障、网络不稳、模型冷启动和评委现场演示。

现场前准备：

1. 本地预装 Python、依赖、Node 构建产物和 SQLite 数据；
2. 准备 3 个测试账号：采购企业、供应商、管理员；
3. 预置一条采购需求、三家供应商、报价、订单、履约和一条预警；
4. 模型不可用时用规则匹配完成主链路；
5. 云端只作为远程展示地址，不作为唯一演示入口；
6. 准备一份离线演示视频和 PPT，满足网络不稳定时的提交/答辩需要。

## 14. 当前不部署的组件

为控制比赛复杂度，以下组件不作为本次单机上线前置条件：

- Redis 集群、Kubernetes、多节点高可用、复杂 CI/CD；
- CLIP 图像匹配、联邦学习、在线 GNN/HAN-BPR；
- 真实工商、税务、电力接口；
- 微信/Hermes 自动处置链路；
- 生产级电子签章和真实支付；
- 同机 Transformers/Qwen GPU 模型服务。

这些能力可以作为“可插拔扩展”展示，但不应阻塞采购—匹配—询价—报价—订单—履约—预警的主闭环。

## 15. 上线验收清单

- [ ] 域名解析到服务器，HTTPS 可访问；
- [ ] 登录、注销、角色权限正常；
- [ ] 采购端发布需求并完成匹配；
- [ ] 供应商端查看画像、响应询价并提交报价；
- [ ] 采购端比较报价并确认订单；
- [ ] 订单履约、发票/交付证明上传可用；
- [ ] 管理端预警、处置、审计可用；
- [ ] Neo4j 图谱可查询；
- [ ] Agent 可用或明确降级到规则能力；
- [ ] Web 与 scheduler 两个 Supervisor 进程均为 RUNNING；
- [ ] MySQL、上传文件和日志备份成功；
- [ ] 公网扫描确认数据库、Neo4j、Ollama、8000 未暴露；
- [ ] 已验证本地离线兜底包。
