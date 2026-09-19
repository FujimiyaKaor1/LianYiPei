"""Seed an explicitly labelled Guangdong electronics/hardware Agent demo.

These records are never represented as real companies. Names contain “演示”,
all provenance entries carry is_mock=true, and production matching excludes
them. The seed exists only so the complete local Agent workflow can be shown.
"""
from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from flask import current_app

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app, db
from app.models import Enterprise, Product

PASSWORD = "DemoAgent2026!"
BUYER = {"name": "链易配演示·湾区采购中心", "city": "广州", "scope": "电子元器件、精密五金采购与供应链管理"}
SUPPLIERS = [
    {"name": "链易配演示·深圳精密连接器厂", "city": "深圳", "scope": "精密连接器、端子、线束组件制造", "qualifications": ["ISO 9001"], "products": [("精密连接器", "电子元器件"), ("线束组件", "电子元器件")]},
    {"name": "链易配演示·东莞精密五金厂", "city": "东莞", "scope": "CNC精密五金、冲压件、机加工结构件", "products": [("精密五金件", "五金"), ("CNC结构件", "五金")]},
    {"name": "链易配演示·佛山金属加工厂", "city": "佛山", "scope": "钣金、铝合金压铸、表面处理", "products": [("铝合金压铸件", "五金"), ("钣金件", "五金")]},
    {"name": "链易配演示·惠州电子制造厂", "city": "惠州", "scope": "PCB、SMT贴片、电子模组组装", "products": [("PCB控制板", "电子元器件"), ("电子模组", "电子元器件")]},
]


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _extras(kind: str) -> dict:
    return {
        "is_demo": True,
        "demo_dataset": "guangdong_agent_pilot_v1",
        "trust_profile": {
            "claim_status": "claimed",
            "contact_authorized": True,
            "authorization": "demo_only",
            "sources": [{"name": "guangdong_agent_demo_seed", "source_type": "demo_seed", "collected_at": _now().isoformat() + "Z", "is_mock": True}],
        },
        "record_kind": kind,
    }


def _upsert_company(data: dict, *, buyer: bool = False) -> Enterprise:
    company = Enterprise.query.filter_by(name=data["name"]).first() or Enterprise(name=data["name"])
    company.role = "enterprise"
    company.province = "广东"
    company.city = data["city"]
    company.address = f"广东省{data['city']}市演示产业园（虚构地址）"
    company.business_scope = data["scope"]
    company.tech_keywords = data["scope"]
    company.qualifications = list(data.get("qualifications") or [])
    company.contact = "演示联系人"
    company.phone = "000-0000-0000"
    company.credit_score = 88 if buyer else 85
    company.capacity = 1000 if buyer else 5000
    company.max_capacity = 1500 if buyer else 8000
    company.verification_status = "approved"
    company.is_verified = True
    company.last_data_update = _now()
    company.extras = _extras("buyer" if buyer else "supplier")
    company.set_password(PASSWORD)
    db.session.add(company)
    db.session.flush()
    return company


def seed() -> dict:
    if str(current_app.config.get("APP_ENV") or "development").lower() == "production":
        raise RuntimeError("演示数据脚本禁止在 production 环境执行")
    buyer = _upsert_company(BUYER, buyer=True)
    supplier_ids = []
    for data in SUPPLIERS:
        supplier = _upsert_company(data)
        supplier_ids.append(supplier.id)
        for name, category in data["products"]:
            product = Product.query.filter_by(enterprise_id=supplier.id, name=name).first() or Product(enterprise_id=supplier.id, name=name)
            product.category = category
            db.session.add(product)
    db.session.commit()
    return {"buyer_id": buyer.id, "supplier_ids": supplier_ids, "password": PASSWORD}


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        result = seed()
        print(f"Seeded Guangdong Agent demo: buyer_id={result['buyer_id']}, suppliers={len(result['supplier_ids'])}")
        print(f"Demo login: {BUYER['name']} / {result['password']}")
        print("All records are explicitly marked demo/mock and excluded from production matching.")
