#!/usr/bin/env python3
"""
Append Tianxia Gongchang company CSV data into the local enterprises table.

Unlike older seed scripts, this importer does not truncate existing tables.
It skips duplicate enterprise names and stores source metadata in extras.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app import create_app, db
from app.models import Enterprise

DEFAULT_CSV = ROOT / "data" / "external" / "tianxiagongchang" / "tianxiagongchang_companies_platform.csv"
DEFAULT_PASSWORD = "123456"
BATCH_SIZE = 500


def _truncate(value: str | None, max_len: int) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    return value[:max_len]


def _float_or_none(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _parse_dt(value: str | None) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            parsed = datetime.strptime(value.replace("Z", "+0000"), fmt)
            return parsed.replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _extras(row: dict[str, str]) -> dict[str, Any]:
    return {
        "source": row.get("source"),
        "source_company_id": row.get("source_company_id"),
        "source_url": row.get("source_url"),
        "source_query": row.get("source_query"),
        "uscc": row.get("uscc"),
        "establishment_date": row.get("establishment_date"),
        "website": row.get("website"),
        "phones_count": _float_or_none(row.get("phones_count")),
        "crucial_count": _float_or_none(row.get("crucial_count")),
        "tags": [v for v in (row.get("tags") or "").split(",") if v],
        "raw_industries": [v for v in (row.get("raw_industries") or "").split(",") if v],
        "scraped_at": row.get("scraped_at"),
    }


def import_csv(csv_path: Path, default_password: str) -> tuple[int, int, int]:
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)

    password_hash = generate_password_hash(default_password)
    inserted = 0
    skipped_duplicate = 0
    skipped_bad = 0
    batch: list[Enterprise] = []

    def flush() -> None:
        nonlocal inserted, batch
        if not batch:
            return
        db.session.add_all(batch)
        db.session.commit()
        inserted += len(batch)
        logging.info("Inserted batch of %s; total inserted=%s", len(batch), inserted)
        batch.clear()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _truncate(row.get("name"), 100)
            if not name:
                skipped_bad += 1
                continue
            if Enterprise.query.filter_by(name=name).first():
                skipped_duplicate += 1
                continue

            ent = Enterprise(
                name=name,
                address=_truncate(row.get("address"), 200),
                province=_truncate(row.get("province"), 20),
                city=_truncate(row.get("city"), 200),
                business_scope=row.get("business_scope") or None,
                contact=_truncate(row.get("contact"), 50) or "导入",
                phone=_truncate(row.get("phone"), 20) or "00000000000",
                registered_capital=_float_or_none(row.get("registered_capital")),
                business_status=_truncate(row.get("business_status"), 20),
                industry_code=_truncate(row.get("industry_code"), 50),
                tech_keywords=_truncate(row.get("tech_keywords"), 500),
                credit_score=_float_or_none(row.get("credit_score")) or 80.0,
                role=row.get("role") or "enterprise",
                is_verified=_bool(row.get("is_verified")),
                verification_status=row.get("verification_status") or "pending",
                password_hash=password_hash,
                extras=_extras(row),
                biz_data_updated_at=_parse_dt(row.get("scraped_at")),
                last_data_update=_parse_dt(row.get("scraped_at")),
            )
            batch.append(ent)

            if len(batch) >= BATCH_SIZE:
                flush()

    flush()
    return inserted, skipped_duplicate, skipped_bad


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Tianxia Gongchang CSV into enterprises")
    parser.add_argument("-i", "--input", type=Path, default=DEFAULT_CSV)
    parser.add_argument("-p", "--password", default=DEFAULT_PASSWORD)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = create_app()
    with app.app_context():
        try:
            inserted, dupes, bad = import_csv(args.input, args.password)
        except Exception:
            db.session.rollback()
            logging.exception("Import failed")
            return 1

    logging.info("Done. inserted=%s duplicates=%s bad_rows=%s", inserted, dupes, bad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
