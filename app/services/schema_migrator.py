import json
import logging
import os
from datetime import datetime
from typing import Iterable, Optional, Set

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.schema import Column, Table

logger = logging.getLogger(__name__)


def _table_exists(conn, engine, dialect_name: str, table_name: str) -> bool:
    if dialect_name == "mysql":
        try:
            q = text(
                """
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND LOWER(TABLE_NAME) = LOWER(:tname)
                """
            )
            n = conn.execute(q, {"tname": table_name}).scalar()
            return int(n or 0) > 0
        except Exception as e:
            logger.warning("information_schema table check failed for %s: %s", table_name, e)
    elif dialect_name == "sqlite":
        try:
            r = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND lower(name)=lower(:t)"),
                {"t": table_name},
            )
            return r.fetchone() is not None
        except Exception as e:
            logger.warning("sqlite_master check failed for %s: %s", table_name, e)
    try:
        insp = sa_inspect(engine)
        return table_name in insp.get_table_names()
    except Exception as e:
        logger.warning("Inspector table check failed for %s: %s", table_name, e)
        return False


def _column_exists(conn, engine, dialect_name: str, table_name: str, column_name: str) -> bool:
    """ADD COLUMN 前检查，避免 1060 Duplicate column（MySQL 用 information_schema）。"""
    if dialect_name == "mysql":
        try:
            q = text(
                """
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND LOWER(TABLE_NAME) = LOWER(:tname)
                  AND LOWER(COLUMN_NAME) = LOWER(:cname)
                """
            )
            n = conn.execute(q, {"tname": table_name, "cname": column_name}).scalar()
            return int(n or 0) > 0
        except Exception as e:
            logger.warning(
                "information_schema check failed for %s.%s: %s", table_name, column_name, e
            )
    elif dialect_name == "sqlite":
        try:
            r = conn.execute(text(f'PRAGMA table_info("{table_name}")'))
            for row in r:
                if row[1] == column_name:
                    return True
            return False
        except Exception as e:
            logger.warning("PRAGMA table_info failed for %s: %s", table_name, e)

    try:
        insp = sa_inspect(engine)
        cols = insp.get_columns(table_name)
        return any(c.get("name") == column_name for c in cols)
    except Exception as e:
        logger.warning("Inspector column check failed for %s.%s: %s", table_name, column_name, e)
        return True


def _inspector_column_names(engine, table_name: str) -> Set[str]:
    """用于与模型列比对（小写集合）。"""
    try:
        insp = sa_inspect(engine)
        return {str(c["name"]).lower() for c in insp.get_columns(table_name)}
    except Exception as e:
        logger.warning("inspector.get_columns failed for %s: %s", table_name, e)
        return set()


def _quote_ident(dialect, name: str) -> str:
    prep = getattr(dialect, "identifier_preparer", None)
    if prep is not None:
        return prep.quote(name)
    return f'"{name}"'


def _compile_type(column: Column, dialect) -> str:
    try:
        return column.type.compile(dialect=dialect)
    except Exception as e:
        logger.warning("compile type for %s: %s", column.key, e)
        return "TEXT"


def _add_column_ddl_fragment(column: Column, dialect, dialect_name: str) -> str:
    """生成 ADD COLUMN 后的类型 + NULL/NOT NULL + DEFAULT（尽量安全，避免非空无默认导致 ALTER 失败）。"""
    type_sql = _compile_type(column, dialect)
    parts = [type_sql.strip()]

    effective_nullable = column.nullable
    server_default_sql: Optional[str] = None
    if column.server_default is not None:
        try:
            sd = column.server_default.arg
            if hasattr(sd, "text"):
                server_default_sql = str(sd.text)
            elif isinstance(sd, str):
                server_default_sql = f"'{sd.replace(chr(39), chr(39)+chr(39))}'" if not sd.startswith("'") else sd
            else:
                server_default_sql = str(sd)
        except Exception:
            server_default_sql = None

    # 非空且无数据库默认值：在已有数据的表上 ADD 常失败，改为可空并打日志
    if not effective_nullable and server_default_sql is None:
        if dialect_name == "mysql":
            d = column.default
            if d is not None and hasattr(d, "arg") and d.arg is not None:
                arg = d.arg
                if isinstance(arg, bool):
                    server_default_sql = "1" if arg else "0"
                elif isinstance(arg, (int, float)):
                    server_default_sql = str(arg)
                elif isinstance(arg, str):
                    server_default_sql = "'" + arg.replace("'", "''") + "'"
        if server_default_sql is None:
            logger.info(
                "schema_migrator: relax NOT NULL for new column %s (no server default)",
                column.key,
            )
            effective_nullable = True

    if effective_nullable:
        parts.append("NULL")
    else:
        parts.append("NOT NULL")
        if server_default_sql:
            parts.append("DEFAULT " + server_default_sql)

    return " ".join(parts)


def _execute_add_column(
    conn,
    engine,
    dialect_name: str,
    table_name: str,
    column: Column,
    ddl_inner: str,
) -> bool:
    qcol = _quote_ident(engine.dialect, column.name)
    sql = f"ALTER TABLE {_quote_ident(engine.dialect, table_name)} ADD COLUMN {qcol} {ddl_inner}"
    try:
        conn.execute(text(sql))
        conn.commit()
        logger.info("Added column %s.%s", table_name, column.name)
        return True
    except Exception as e:
        if "JSON" in ddl_inner.upper() or "json" in ddl_inner.lower():
            try:
                fb = "TEXT NULL" if column.nullable else "TEXT NOT NULL"
                sql_fb = f"ALTER TABLE {_quote_ident(engine.dialect, table_name)} ADD COLUMN {qcol} {fb}"
                conn.execute(text(sql_fb))
                conn.commit()
                logger.info("Added column %s.%s as TEXT (JSON fallback)", table_name, column.name)
                return True
            except Exception:
                pass
        logger.warning("Failed to add %s.%s: %s", table_name, column.name, e)
        return False


def sync_model_columns(conn, engine, dialect_name: str, model) -> None:
    """根据 SQLAlchemy 模型与 inspector 对比，补齐缺失列。"""
    table: Table = model.__table__
    tname = table.name
    if not _table_exists(conn, engine, dialect_name, tname):
        logger.info("schema_migrator: skip %s (table not yet present)", tname)
        return

    existing = _inspector_column_names(engine, tname)
    dialect = engine.dialect

    for column in table.columns:
        cname = column.name
        if cname.lower() in existing:
            continue
        if _column_exists(conn, engine, dialect_name, tname, cname):
            existing.add(cname.lower())
            continue

        ddl_inner = _add_column_ddl_fragment(column, dialect, dialect_name)
        if _execute_add_column(conn, engine, dialect_name, tname, column, ddl_inner):
            existing.add(cname.lower())


def _coerce_json_list(val) -> list:
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        return []
    if isinstance(val, str):
        try:
            d = json.loads(val)
            return d if isinstance(d, list) else []
        except Exception:
            return []
    return []


def _migrate_legacy_credit_history(conn, engine, dialect_name: str) -> None:
    """将 credit_score_history 表数据并入 enterprises.credit_score_events 后删除旧表。"""
    if not _table_exists(conn, engine, dialect_name, "credit_score_history"):
        return
    if not _column_exists(conn, engine, dialect_name, "enterprises", "credit_score_events"):
        return
    try:
        rows = conn.execute(
            text(
                "SELECT id, enterprise_id, old_score, new_score, change_value, change_type, reason, created_at "
                "FROM credit_score_history ORDER BY enterprise_id, id"
            )
        ).fetchall()
    except Exception as e:
        logger.warning("migrate legacy credit_score_history: read failed: %s", e)
        return
    if not rows:
        try:
            conn.execute(text("DROP TABLE IF EXISTS credit_score_history"))
            conn.commit()
            logger.info("Dropped empty legacy credit_score_history")
        except Exception as e:
            logger.warning("Drop legacy credit_score_history: %s", e)
        return

    by_eid = {}
    for row in rows:
        eid = row[1]
        by_eid.setdefault(eid, []).append(row)

    for eid, ev_rows in by_eid.items():
        try:
            cur = conn.execute(
                text("SELECT credit_score_events FROM enterprises WHERE id = :eid"),
                {"eid": eid},
            ).scalar()
        except Exception:
            cur = None
        existing = _coerce_json_list(cur)
        have_ids = {str(x.get("id")) for x in existing if isinstance(x, dict)}
        for row in ev_rows:
            rid = row[0]
            lid = f"legacy-{rid}"
            if lid in have_ids:
                continue
            created = row[7]
            if hasattr(created, "isoformat"):
                ts = created.isoformat()
            else:
                ts = str(created) if created is not None else datetime.utcnow().isoformat()
            if ts and not ts.endswith("Z") and "T" in ts:
                ts = ts + "Z"
            existing.append(
                {
                    "id": lid,
                    "old_score": float(row[2] or 0),
                    "new_score": float(row[3] or 0),
                    "change_value": float(row[4] or 0),
                    "change_type": row[5] or "",
                    "reason": row[6] or "",
                    "created_at": ts,
                }
            )
        payload = json.dumps(existing, ensure_ascii=False)
        try:
            conn.execute(
                text("UPDATE enterprises SET credit_score_events = :js WHERE id = :eid"),
                {"js": payload, "eid": eid},
            )
            conn.commit()
        except Exception as e:
            logger.warning("migrate credit_score_events enterprise %s: %s", eid, e)

    try:
        conn.execute(text("DROP TABLE IF EXISTS credit_score_history"))
        conn.commit()
        logger.info("Dropped legacy table credit_score_history after migration to JSON")
    except Exception as e:
        logger.warning("Could not drop credit_score_history: %s", e)


def ensure_schema(db) -> None:
    """启动时按 10 张核心表的 SQLAlchemy 模型自动补齐缺失列（ALTER TABLE ADD COLUMN）。

    - 使用 inspector.get_columns 与模型列比对，并用 information_schema 二次确认，避免 1060。
    - 不删列、不改类型；非空且无默认的新列会放宽为可空，以免旧表有数据时 ALTER 失败。
    - 设 SCHEMA_MIGRATOR_DISABLED=1 可跳过。
    """
    if os.environ.get("SCHEMA_MIGRATOR_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("ensure_schema skipped (SCHEMA_MIGRATOR_DISABLED)")
        return

    dialect_name = getattr(db.engine.dialect, "name", "") or ""

    # 延迟导入，避免循环依赖；与「10 张表」清单一致
    from app.models import (
        Alert,
        Enterprise,
        HermesPendingAction,
        Inquiry,
        MatchFeedback,
        Message,
        PriceIndex,
        Product,
        Quote,
        RecruitmentTask,
        Transaction,
    )

    core_models: Iterable = (
        Enterprise,
        Product,
        Inquiry,
        Quote,
        Transaction,
        MatchFeedback,
        RecruitmentTask,
        Alert,
        HermesPendingAction,
        PriceIndex,
        Message,
    )

    with db.engine.connect() as conn:
        for model in core_models:
            try:
                sync_model_columns(conn, db.engine, dialect_name, model)
            except Exception as e:
                logger.warning("sync_model_columns %s: %s", model.__name__, e)

        try:
            if _column_exists(conn, db.engine, dialect_name, "enterprises", "role"):
                conn.execute(
                    text(
                        "UPDATE enterprises SET role = 'admin' WHERE is_admin = 1 AND role = 'enterprise'"
                    )
                )
                conn.commit()
        except Exception as e:
            logger.warning("Role backfill from is_admin skipped: %s", e)

        _migrate_legacy_credit_history(conn, db.engine, dialect_name)
