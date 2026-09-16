# 链易配

链易配是一个由 Flask 后端、React/Vite 前端和可选模型服务组成的产业链供需匹配系统。

## 快速入口

```bash
# 后端（推荐使用项目虚拟环境）
.venv/bin/python run.py

# 前端开发服务器
cd frontend
npm install
npm run dev

# 前端生产构建；产物会写入 app/static/frontend
npm run build

# 后端测试
cd ..
.venv/bin/python -m pytest
```

首次初始化数据库和演示数据，执行：

```bash
.venv/bin/python scripts/db/create_db.py
.venv/bin/python scripts/seed/seed_all_data.py
```

Windows 用户可使用根目录的 `启动.bat`。数据库、Neo4j、模型服务和演示账号的完整说明见 [`docs/启动说明.md`](docs/启动说明.md)。

## 目录地图

| 目录 | 作用 | 维护规则 |
| --- | --- | --- |
| `app/routes/` | Flask 路由和 API 入口 | 按 HTTP 能力维护 |
| `app/applications/` | 按领域划分的后端业务服务 | 新业务代码的唯一主目录 |
| `app/services/` | 基础设施服务和旧导入路径兼容层 | 兼容层不新增业务逻辑，详见目录内说明 |
| `app/templates/` | Flask 服务端模板 | 仅维护仍由 Flask 渲染的页面 |
| `frontend/src/` | React 前端源代码 | 前端功能只在这里修改 |
| `app/static/frontend/` | Flask 承载的前端构建产物 | 在 `frontend/` 中执行 `npm run build` 生成，不手工编辑 |
| `scripts/db/`、`scripts/migrate/`、`scripts/seed/`、`scripts/verify/` | 数据库、迁移、种子和验证脚本 | 按用途放置，详见 [`scripts/README.md`](scripts/README.md) |
| `migrations/` | Alembic 迁移文件 | 已发布迁移不要改写 |
| `deploy/baota/` | 宝塔/Nginx/Supervisor 部署模板 | 仅替换部署参数，不提交真实密钥 |
| `docs/` | 使用、架构、部署和历史报告 | 先从 [`docs/README.md`](docs/README.md) 找入口 |
| `data/` | 可版本化的示例数据 | 本地数据库和缓存不放入此处 |

## 后端服务的主路径

业务服务已经按领域迁移到 `app/applications/`。`app/services/` 中标记为“兼容层”的文件仍保留，是为了让旧路由、测试或外部脚本继续使用原导入路径；修改业务逻辑时应编辑对应的 `app/applications/<domain>/services/` 文件。

前端同样区分源码和产物：`frontend/src/` 是唯一源码位置，`app/static/frontend/` 只用于 Flask 运行时托管。两处出现相同图片或静态资源是构建部署链路的一部分，不要把它们当作无效重复文件删除。

更多目录约定：

- 后端领域说明：[`app/applications/README.md`](app/applications/README.md)
- 兼容层和基础服务：[`app/services/README.md`](app/services/README.md)
- 文档索引：[`docs/README.md`](docs/README.md)
- 设计规范：[`DESIGN.md`](DESIGN.md)
