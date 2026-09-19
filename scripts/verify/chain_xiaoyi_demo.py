#!/usr/bin/env python3
"""Run the complete Chain XiaoYi pilot flow against the local demo dataset.

This command is development-only. It requires ``DEEPSEEK_API_KEY`` in the
process environment, seeds only records explicitly marked ``is_demo=true``,
simulates one supplier quote, and stops at an auditable order draft unless
``--confirm-order`` is supplied. ``--simulate-fulfillment`` continues through
the explicit contract/payment confirmations and signed ERP delivery callbacks.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SUPPORTED_MATERIAL_SUFFIXES = {".csv", ".xlsx", ".pdf", ".docx"}


def validate_material_paths(raw_paths: list[str] | tuple[str, ...] | None) -> list[Path]:
    """Validate local demo inputs before any application state is changed."""
    values = list(raw_paths or [])
    if not values:
        raise ValueError("至少提供一个材料文件")
    paths: list[Path] = []
    for raw in values[:20]:
        path = Path(str(raw)).expanduser()
        if not path.is_file():
            raise ValueError("材料文件不存在")
        if path.suffix.lower() not in SUPPORTED_MATERIAL_SUFFIXES:
            raise ValueError("仅支持 CSV、XLSX、PDF 和 DOCX 材料")
        paths.append(path)
    return paths


def _payload(response) -> dict:
    value = response.get_json(silent=True)
    return value if isinstance(value, dict) else {}


def material_demo_summary(payload: dict) -> dict:
    """Return bounded, auditable material details for the demo report.

    The report intentionally includes extracted values and their source
    evidence, but never includes the uploaded file bytes or storage key.
    """
    payload = payload if isinstance(payload, dict) else {}
    file_info = payload.get("file") if isinstance(payload.get("file"), dict) else {}
    preview = file_info.get("preview") if isinstance(file_info.get("preview"), dict) else {}
    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    raw_fields = draft.get("fields") if isinstance(draft.get("fields"), dict) else {}
    fields: dict = {}
    for key, raw_field in list(raw_fields.items())[:30]:
        if not isinstance(raw_field, dict):
            continue
        fields[str(key)[:80]] = {
            "value": raw_field.get("value"),
            "evidence": raw_field.get("evidence") if isinstance(raw_field.get("evidence"), dict) else {},
        }
    security_scan = file_info.get("security_scan") if isinstance(file_info.get("security_scan"), dict) else preview.get("security_scan")
    if not isinstance(security_scan, dict):
        security_scan = {}
    return {
        "id": file_info.get("id"),
        "filename": str(file_info.get("filename") or "")[:200],
        "scan_status": str(file_info.get("scan_status") or security_scan.get("status") or "unknown"),
        "scan_engine": str(security_scan.get("engine") or "")[:100],
        "missing_required": [str(item)[:80] for item in (draft.get("missing_required") or [])[:30]],
        "fields": fields,
    }


def resolve_intent_provider(message_payload: dict, intent: dict) -> str | None:
    """Report the provider that actually handled the confirmation turn.

    Material-derived intents are deliberately extracted from evidenced rows,
    so they do not carry the chat parser's ``confidence`` marker.  The demo
    still performs a real model confirmation request after upload; use that
    response as the provider source instead of reporting ``null`` and making
    a valid DeepSeek run look like a silent rules fallback.
    """
    direct = str((intent or {}).get("confidence") or "").strip().lower()
    if direct in {"deepseek", "local", "rules"}:
        return direct
    status = (message_payload or {}).get("model_status")
    active = str(status.get("active_provider") or "").strip().lower() if isinstance(status, dict) else ""
    return active if active in {"deepseek", "local", "rules"} else None


def read_api_key_from_hidden_input() -> str:
    """Read a provider key without putting it in argv, files, or reports."""
    try:
        value = getpass.getpass("DeepSeek API key（不会回显）：")
    except (EOFError, KeyboardInterrupt):
        value = ""
    value = str(value or "").strip()
    if not value:
        raise ValueError("未读取到有效 DeepSeek API key")
    return value


def _signed_callback(client, path: str, payload: dict, secret: str):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return client.post(
        path,
        data=raw,
        content_type="application/json",
        headers={"X-Lianyipei-Signature": signature},
    )


def run_demo(*, prompt: str, quote_price: float, quote_delivery_days: int, confirm_order: bool = False, simulate_fulfillment: bool = False, material_paths: list[str] | tuple[str, ...] | None = None) -> dict:
    """Execute one real-model demo and return a redacted JSON-safe report."""
    if not (os.getenv("DEEPSEEK_API_KEY") or "").strip():
        raise RuntimeError("DEEPSEEK_API_KEY 未注入当前进程；演示不会静默降级到规则模式")
    material_files = validate_material_paths(material_paths) if material_paths else []

    from app import create_app
    from app.models import IntentQuote
    from app.models_chain_xiaoyi import ChainXiaoYiOutboundRecord
    from app.services.chain_xiaoyi.orchestrator import ChainXiaoYiOrchestrator
    from app.services.chain_xiaoyi.model_router import get_model_status
    from scripts.seed.seed_guangdong_agent_demo import BUYER, PASSWORD, seed

    app = create_app()
    if str(app.config.get("APP_ENV") or "development").lower() == "production":
        raise RuntimeError("演示数据脚本禁止在 production 环境执行")
    # Test-client requests still exercise the real Flask routes and auth
    # boundary, without starting a second listening server for this probe.
    app.config["TESTING"] = True
    # Exercise the same authenticated callback boundary used by email/WeCom
    # adapters. The secret is process-local and never written to a file.
    callback_secret = secrets.token_urlsafe(32)
    app.config["RFQ_QUOTE_CALLBACK_SECRET"] = callback_secret
    fulfillment_secret = secrets.token_urlsafe(32)
    app.config["FULFILLMENT_CALLBACK_SECRET"] = fulfillment_secret

    with app.app_context():
        if get_model_status().active_provider != "deepseek":
            raise RuntimeError("当前模型路由未启用 DeepSeek；请检查 CHAINXIAOYI_CLOUD_ENABLED")
        seed_result = seed()
        client = app.test_client()
        login = client.post(
            "/auth/login",
            data={"name": BUYER["name"], "password": PASSWORD},
            headers={"X-Login-Modal": "1"},
        )
        if login.status_code != 200:
            raise RuntimeError(f"演示采购方登录失败（HTTP {login.status_code}）")

        created = client.post("/api/chain-xiaoyi/sessions", json={"surface": "enterprise"})
        session_payload = _payload(created)
        if created.status_code not in {200, 201} or not session_payload.get("session"):
            raise RuntimeError("链小易会话创建失败")
        session_id = int(session_payload["session"]["id"])

        material_task_id = None
        material_parent_task_id = None
        material_summaries: list[dict] = []
        message_payload: dict = {}
        if material_files:
            # Exercise the same multipart endpoint used by the browser. The
            # parser creates an evidenced procurement task; candidate matching
            # remains deterministic and therefore does not invent enterprise
            # facts for a material-derived row.
            material_response = None
            for material_file in material_files:
                with material_file.open("rb") as handle:
                    material_response = client.post(
                        f"/api/chain-xiaoyi/sessions/{session_id}/files",
                        data={"file": (handle, material_file.name)},
                        content_type="multipart/form-data",
                    )
                material_payload = _payload(material_response)
                if material_response.status_code != 200 or not material_payload.get("task"):
                    raise RuntimeError("采购材料解析失败")
                material_summaries.append(material_demo_summary(material_payload))
                material_task_id = int(material_payload["task"]["id"])
            recomputed = client.post(f"/api/chain-xiaoyi/procurement-tasks/{material_task_id}/recompute")
            recomputed_payload = _payload(recomputed)
            if recomputed.status_code != 200:
                raise RuntimeError("采购材料候选检索失败")
            item_matches = recomputed_payload.get("item_matches") or []
            if len(item_matches) != 1:
                raise RuntimeError("演示材料必须合并为一个可执行采购项；多行材料请使用网页批量工作台")
            first_item = item_matches[0]
            intent = first_item.get("intent") or {}
            match_result = first_item.get("match_result") or {}
            # Keep the material route on the same real-model surface as chat:
            # DeepSeek confirms the extracted request, while database matching
            # and all commercial facts remain owned by deterministic services.
            model_check = client.post(
                f"/api/chain-xiaoyi/sessions/{session_id}/messages",
                json={
                    "content": (
                        "请仅确认这份采购材料的字段，不执行任何外发操作："
                        f"产品={intent.get('product')};数量={intent.get('quantity')};"
                        f"单位={intent.get('unit') or '件'}。"
                    )
                },
            )
            message_payload = _payload(model_check)
            if model_check.status_code != 200:
                raise RuntimeError("DeepSeek 材料确认失败")
        else:
            message = client.post(
                f"/api/chain-xiaoyi/sessions/{session_id}/messages",
                json={"content": prompt[:2000]},
            )
            message_payload = _payload(message)
            if message.status_code != 200:
                raise RuntimeError(f"DeepSeek 需求理解失败（HTTP {message.status_code}）")
            match_result = message_payload.get("match_result") or {}
            intent = message_payload.get("intent") or {}
        candidates = [row for row in match_result.get("results") or [] if row.get("contact_eligible")]
        if not candidates:
            raise RuntimeError("没有可授权触达的演示候选企业")
        supplier_id = int(candidates[0]["id"])
        workflow = message_payload.get("workflow") or {}
        if material_files:
            # The material route now exercises the same server-side shortcut
            # as the production workbench: recompute, select only claimed /
            # contact-authorized suppliers, and create one parent approval
            # card.  It still never sends during upload or planning.
            planned = client.post(
                f"/api/chain-xiaoyi/procurement-tasks/{material_task_id}/auto-plan",
                json={
                    "message": "请提供含税单价、MOQ、交期、模具费、运费和报价有效期。",
                    "channels": ["site"],
                },
            )
            planned_payload = _payload(planned)
            if planned.status_code not in {200, 201} or not planned_payload.get("rfq_tasks"):
                raise RuntimeError("材料询价审批预览创建失败")
            # The parent task owns the single approval; commercial callbacks
            # and progress continue against its first per-line RFQ child.
            material_parent_task_id = int(planned_payload["task"]["id"])
            task_id = int(planned_payload["rfq_tasks"][0]["id"])
        elif workflow.get("action") == "rfq_preview" and workflow.get("source_task_id"):
            # The natural-language request itself created the approval-ready
            # preview.  Do not create a second RFQ through the legacy button
            # endpoint.
            task_id = int(workflow["source_task_id"])
        else:
            # Keep custom prompts that do not ask to prepare an RFQ usable by
            # the verifier, while making the default path exercise the
            # one-sentence Agent workflow above.
            draft = client.post(
                f"/api/chain-xiaoyi/sessions/{session_id}/rfq-draft",
                json={
                    "intent": intent,
                    "supplier_ids": [supplier_id],
                    "message": "请提供含税单价、MOQ、交期、模具费、运费和报价有效期。",
                    "channels": ["site"],
                },
            )
            draft_payload = _payload(draft)
            if draft.status_code != 201:
                raise RuntimeError("询价预览创建失败")
            task_id = int(draft_payload["task"]["id"])

        if material_parent_task_id:
            approved = client.post(
                f"/api/chain-xiaoyi/tasks/{material_parent_task_id}/rfq-batch-approve",
                json={"confirm": True, "comment": "材料自动规划后的统一审批"},
            )
            if approved.status_code not in {200, 202}:
                raise RuntimeError("材料统一询价审批失败")
            processed = ChainXiaoYiOrchestrator.process_queued_rfq_tasks()
            sent_payload = {
                "sent": ChainXiaoYiOutboundRecord.query.filter_by(task_id=task_id, status="sent").count(),
                "failed": int(processed.get("failed") or 0),
            }
        else:
            approved = client.post(f"/api/chain-xiaoyi/tasks/{task_id}/approve", json={"confirm": True})
            if approved.status_code != 200:
                raise RuntimeError("询价审批失败")
            sent = client.post(f"/api/chain-xiaoyi/tasks/{task_id}/send")
            sent_payload = _payload(sent)
            if sent.status_code != 200 or sent_payload.get("failed"):
                raise RuntimeError("演示询价发送失败")

        quote = IntentQuote.query.filter_by(source_rfq_task_id=task_id, seller_id=supplier_id).one()
        callback_payload = {
            "event_id": f"demo-quote-{quote.id}-{secrets.token_hex(6)}",
            "quote_id": quote.id,
            "supplier_id": supplier_id,
            "confirmed": True,
            "reply_price": quote_price,
            "reply_notes": f"演示供应商回复：含税，{quote_delivery_days}天交付",
            "reply_details": {
                "tax_included": True,
                "tax_rate": 13,
                "delivery_days": quote_delivery_days,
                "moq": 100,
                "valid_until": "2026-12-31",
            },
        }
        callback_raw = json.dumps(callback_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        callback_signature = hmac.new(callback_secret.encode("utf-8"), callback_raw, hashlib.sha256).hexdigest()
        quote_callback = client.post(
            "/api/chain-xiaoyi/quote-callback/email",
            data=callback_raw,
            content_type="application/json",
            headers={"X-Lianyipei-Signature": callback_signature},
        )
        quote_callback_payload = _payload(quote_callback)
        if quote_callback.status_code != 200 or quote_callback_payload.get("status") != "accepted":
            raise RuntimeError("演示报价回收失败")

        quote_query = client.post(
            f"/api/chain-xiaoyi/sessions/{session_id}/messages",
            json={"content": "只看含税价最低且30天内能交付的一家"},
        )
        quote_query_payload = _payload(quote_query)
        if quote_query.status_code != 200 or (quote_query_payload.get("workflow") or {}).get("action") != "quote_query":
            raise RuntimeError("自然语言报价筛选失败")

        progress = _payload(client.get(f"/api/chain-xiaoyi/tasks/{task_id}/progress"))
        summary = _payload(client.get(f"/api/chain-xiaoyi/tasks/{task_id}/quote-summary"))
        order_draft = _payload(
            client.post(
                f"/api/chain-xiaoyi/tasks/{task_id}/order-draft",
                json={"supplier_id": supplier_id},
            )
        )
        if order_draft.get("order", {}).get("status") != "draft":
            raise RuntimeError("订单草稿生成失败")

        formal_order = None
        fulfillment = None
        if confirm_order:
            confirmed = client.post(
                f"/api/chain-xiaoyi/tasks/{task_id}/order-draft/confirm",
                json={"supplier_id": supplier_id, "confirm": True},
            )
            confirmed_payload = _payload(confirmed)
            if confirmed.status_code not in {200, 201}:
                raise RuntimeError("正式订单确认失败")
            formal_order = confirmed_payload.get("order")

        if simulate_fulfillment:
            if not formal_order:
                raise RuntimeError("模拟履约前必须先使用 --confirm-order 创建正式订单")
            order_id = int(formal_order["id"])
            for requirement, path in (("contract", "confirm-contract"), ("payment", "confirm-payment")):
                confirmed = client.post(f"/orders/{order_id}/{path}", json={"confirm": True})
                if confirmed.status_code != 200:
                    raise RuntimeError(f"订单{requirement}确认失败")
            for event_type, event_id, extra in (
                ("shipment_dispatched", "demo-shipment", {"tracking_no": "SF-DEMO-001"}),
                ("delivery_confirmed", "demo-delivery", {}),
            ):
                callback = _signed_callback(
                    client,
                    "/api/chain-xiaoyi/fulfillment-event-callback/erp",
                    {
                        "event_id": f"{event_id}-{order_id}-{secrets.token_hex(4)}",
                        "enterprise_id": int(seed_result["buyer_id"]),
                        "order_id": order_id,
                        "event_type": event_type,
                        **extra,
                    },
                    fulfillment_secret,
                )
                if callback.status_code != 200:
                    raise RuntimeError(f"履约回调失败：{event_type}")
            audit = _payload(client.get(f"/api/chain-xiaoyi/tasks/{task_id}/audit"))
            fulfillment = ((audit.get("task") or {}).get("output") or {}).get("fulfillment") or {}

        return {
            "success": True,
            "model_provider": (message_payload.get("model_status") or {}).get("active_provider"),
            "material_count": len(material_files),
            "material_task_id": material_task_id,
            "materials": material_summaries,
            "intent_provider": resolve_intent_provider(message_payload, intent),
            "intent": {
                key: intent.get(key)
                for key in ("product", "quantity", "unit", "region", "delivery_days", "soft_requirements")
                if intent.get(key) not in (None, "", [])
            },
            "candidate_count": int(match_result.get("total") or 0),
            "selected_supplier": candidates[0].get("name"),
            "rfq": {
                "task_id": task_id,
                "status": (progress.get("task") or {}).get("status") or sent_payload.get("status") or "sent",
                "sent": sent_payload.get("sent", 0),
                "replied": (progress.get("counts") or {}).get("replied", 0),
                "deadline": progress.get("deadline") or {},
                "quote_ingest": "signed_callback",
            },
            "quote": summary.get("recommendation") or {},
            "quote_query": {
                "query": "只看含税价最低且30天内能交付的一家",
                "criteria": (quote_query_payload.get("workflow") or {}).get("criteria") or {},
                "selected_count": len((quote_query_payload.get("workflow") or {}).get("quotes") or []),
                "evidence_only": bool((quote_query_payload.get("workflow") or {}).get("evidence_only")),
            },
            "order_draft": order_draft.get("order"),
            "formal_order": formal_order,
            "fulfillment": fulfillment,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="链小易 DeepSeek 一条龙演示")
    parser.add_argument("--prompt", default="帮我找广东能做精密连接器的工厂，采购2000件，30天内交付，最好支持出口，并准备询价")
    parser.add_argument("--quote-price", type=float, default=12.8)
    parser.add_argument("--quote-delivery-days", type=int, default=25)
    parser.add_argument("--confirm-order", action="store_true", help="额外确认并创建正式订单")
    parser.add_argument("--simulate-fulfillment", action="store_true", help="在正式订单后模拟合同/付款确认和 ERP 发货、交付回调")
    parser.add_argument("--material", action="append", default=[], help="直接上传采购材料（可重复；演示模式要求最终合并为一个采购项）")
    parser.add_argument(
        "--api-key-stdin",
        action="store_true",
        help="从不回显的标准输入读取 DeepSeek key；不会写入 .env 或命令行参数",
    )
    parser.add_argument("--json", action="store_true", help="只输出单行 JSON")
    args = parser.parse_args()
    if args.api_key_stdin:
        try:
            key = read_api_key_from_hidden_input()
        except ValueError as exc:
            parser.error(str(exc))
        # Keep the credential in this short-lived process only.  Do not echo
        # it, persist it, or include it in the redacted report.
        os.environ["DEEPSEEK_API_KEY"] = key.strip()
        os.environ.setdefault("CHAINXIAOYI_CLOUD_ENABLED", "true")
    try:
        report = run_demo(
            prompt=args.prompt,
            quote_price=args.quote_price,
            quote_delivery_days=args.quote_delivery_days,
            confirm_order=args.confirm_order,
            simulate_fulfillment=args.simulate_fulfillment,
            material_paths=args.material,
        )
    except Exception as exc:
        # Never include provider response bodies or environment values.
        print(json.dumps({"success": False, "error": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":") if args.json else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
