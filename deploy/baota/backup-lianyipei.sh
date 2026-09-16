#!/usr/bin/env bash
set -Eeuo pipefail

# 宝塔计划任务：每天 03:30 执行。
# 运行前把 APP_DIR、BACKUP_DIR、DB_USER、DB_PASSWORD 改成服务器上的值，
# 或让脚本从项目 .env 读取（不把密码写入脚本）。

APP_DIR="${LIANYIPEI_APP_DIR:-/www/wwwroot/lianyipei}"
BACKUP_DIR="${LIANYIPEI_BACKUP_DIR:-/www/backup/lianyipei}"
KEEP_DAYS="${LIANYIPEI_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

PYTHON_BIN="${LIANYIPEI_PYTHON_BIN:-$APP_DIR/.venv/bin/python}"
read -r DB_HOST DB_PORT DB_USER DB_PASSWORD DB_NAME < <(
  LIANYIPEI_APP_DIR="$APP_DIR" \
  "$PYTHON_BIN" - <<'PY'
from os.path import join
from urllib.parse import unquote, urlparse
from dotenv import dotenv_values

app_dir = __import__("os").environ.get("LIANYIPEI_APP_DIR", "/www/wwwroot/lianyipei")
env = dotenv_values(join(app_dir, ".env"))
raw = env.get("DATABASE_URL") or __import__("os").environ.get("DATABASE_URL", "")
if not raw:
    raise SystemExit("DATABASE_URL 未配置")
parsed = urlparse(raw)
if not parsed.hostname or not parsed.path.strip("/"):
    raise SystemExit("DATABASE_URL 格式无效")
print(
    parsed.hostname,
    parsed.port or 3306,
    unquote(parsed.username or ""),
    unquote(parsed.password or ""),
    parsed.path.strip("/").split("/", 1)[0],
)
PY
)

MYSQL_PWD="$DB_PASSWORD" mysqldump \
  --protocol=tcp \
  --host="${DB_HOST:-127.0.0.1}" \
  --port="${DB_PORT:-3306}" \
  --user="$DB_USER" \
  --single-transaction --routines --events --triggers \
  --default-character-set=utf8mb4 "$DB_NAME" > "$WORK_DIR/mysql.sql"

# 上传文件是数据库之外的业务数据，必须一并保存。
if [[ -d "$APP_DIR/uploads" ]]; then
  tar -C "$APP_DIR" -czf "$WORK_DIR/uploads.tar.gz" uploads
fi

tar -C "$WORK_DIR" -czf "$BACKUP_DIR/lianyipei_$STAMP.tar.gz" .
find "$BACKUP_DIR" -type f -name 'lianyipei_*.tar.gz' -mtime "+$KEEP_DAYS" -delete
echo "backup created: $BACKUP_DIR/lianyipei_$STAMP.tar.gz"
