"""
Enterprise JSON 字段约定与用法示例（资质、授权、案例、专利、扩展、信用流水）。

import json  # 若使用 JSON_CONTAINS 等示例

表结构清单（10 张关系表，其余信息进 JSON 或 config）：
  enterprises, products, inquiries, quotes, transactions, match_feedbacks,
  recruitment_tasks, alerts, price_indices, messages

示例 — 读取「资质」列表中某类标签：
    ent = Enterprise.query.get(1)
    rows = ent.qualifications if isinstance(ent.qualifications, list) else []
    iso_rows = [r for r in rows if isinstance(r, dict) and r.get("label_type") == "iso9001"]

示例 — 更新 data_auth 中某一数据类型：
    m = dict(ent.data_auth) if isinstance(ent.data_auth, dict) else {}
    m["power_consumption"] = {"authorized": True, "authorized_at": "...", "sync_status": "pending"}
    ent.data_auth = m
    db.session.commit()

示例 — 向 extras 追加举报记录（不改变表结构）：
    ex = dict(ent.extras) if isinstance(ent.extras, dict) else {}
    ex.setdefault("reports_received", []).append({"status": "pending", "detail": "..."})
    ent.extras = ex
    db.session.commit()

示例 — MySQL 按 JSON 内部字段筛选（需 MySQL 5.7+）：
    from sqlalchemy import text
    db.session.execute(text(
        "SELECT id FROM enterprises WHERE JSON_CONTAINS(qualifications, :frag, '$')",
    ), {"frag": json.dumps({"label_type": "绿色工厂"})})
"""

# 供外部导入的只读清单（与 app.models 一致）
CORE_TABLES = (
    "enterprises",
    "products",
    "inquiries",
    "quotes",
    "transactions",
    "match_feedbacks",
    "recruitment_tasks",
    "alerts",
    "price_indices",
    "messages",
)
