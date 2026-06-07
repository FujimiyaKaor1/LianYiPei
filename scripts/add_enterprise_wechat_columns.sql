-- 仅当无法执行 flask db upgrade 时，在 MySQL 客户端中按需执行（已存在的列会报错，请先检查 information_schema）。
-- 与 app.models.Enterprise 微信字段及 migrations/versions/36cf823dcdfc 中 enterprises 新增列一致。
-- 手工补列后，请在确认整库与 Alembic 迁移预期一致后再考虑: flask db stamp head

ALTER TABLE enterprises ADD COLUMN wechat_bound TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE enterprises ADD COLUMN wechat_work_userid VARCHAR(100) NULL;
ALTER TABLE enterprises ADD COLUMN wechat_work_openid VARCHAR(100) NULL;
ALTER TABLE enterprises ADD COLUMN wechat_service_openid VARCHAR(100) NULL;
ALTER TABLE enterprises ADD COLUMN wechat_bound_at DATETIME NULL;
ALTER TABLE enterprises ADD COLUMN wechat_push_preference VARCHAR(20) NOT NULL DEFAULT 'all';
