# 运维与开发脚本

脚本按执行目的分组，均从项目根目录运行：

| 目录 | 用途 | 常用入口 |
| --- | --- | --- |
| `db/` | 创建数据库、检查和修复账号/字段 | `python scripts/db/create_db.py`、`python scripts/db/init_db.py` |
| `migrate/` | 执行数据库迁移 | `python scripts/migrate/migrate_db.py` |
| `seed/` | 初始化、导入和生成演示数据 | `python scripts/seed/seed_all_data.py`、`python scripts/seed/seed_demo_full_flow.py` |
| `verify/` | 按模块做运行验证 | `python scripts/verify/verify_tests.py` |

根目录脚本：

- `setup_and_start.py`：仅限本地开发，按“建库 → 初始化 → 启动模型服务 → 启动 Flask”顺序运行；`APP_ENV=production` 下会拒绝执行。
- `run_scheduler.py`：生产环境单独启动唯一的 APScheduler 进程。
- `generate_client_architecture_*.py`：生成架构图，属于文档工具，不参与应用启动。
- `fedlab_demo.py`、`test_login.py`：手工演示或登录检查工具。

`scripts/add_enterprise_wechat_columns.sql` 是历史手工 SQL；新的结构变更优先使用 `migrations/versions/`，不要再新增散落在 `scripts/` 根目录的迁移文件。

注意：`setup_and_start.py`、`db/create_db.py`、`db/create_test_accounts.py`、
`seed/fresh_init.py`、`seed/seed_all_data.py` 和密码修复类脚本均不是生产部署入口，
会修改数据库或写入演示账号；生产环境只使用 Alembic、Gunicorn、独立 Worker 和
`scripts/verify/production_smoke.py`。其中已知入口在 `APP_ENV=production` 下会拒绝执行。
