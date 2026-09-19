"""Auditable multi-channel RFQ delivery with privacy authorization checks."""
from __future__ import annotations

from datetime import datetime

from app.applications.fulfillment.services.collaboration_service import send_message
from app.models import Enterprise
from app.services.email_service import send_email
from app.services.wechat_push_service import wechat_push_service
from app.services.work_wechat_delivery import send_text as send_work_wechat_text


ALLOWED_CHANNELS = {"site", "email", "wechat", "work_wechat"}


def normalize_channels(channels, *, include_site: bool = True) -> list[str]:
    requested = channels if isinstance(channels, list) else []
    clean = [str(channel).strip().lower() for channel in requested if str(channel).strip().lower() in ALLOWED_CHANNELS]
    values = (["site"] if include_site else []) + clean
    return list(dict.fromkeys(values))


def deliver_rfq(supplier: Enterprise, title: str, content: str, channels=None, *, include_site: bool = True) -> dict:
    """Deliver one RFQ and report channel truthfully; never invent delivery."""
    now = datetime.utcnow().isoformat()
    requested = normalize_channels(channels, include_site=include_site)
    statuses: dict[str, dict] = {}
    if include_site:
        send_message(
            recipient_id=supplier.id,
            message_type="rfq",
            title=title[:200],
            content=content[:2000],
            link_url="/sales-console",
            priority="high",
            mode="sales",
        )
        statuses["site"] = {"status": "sent", "sent_at": now}

    extras = dict(supplier.extras or {})
    trust = extras.get("trust_profile") if isinstance(extras.get("trust_profile"), dict) else {}
    authorizations = extras.get("communication_authorizations") if isinstance(extras.get("communication_authorizations"), dict) else {}
    globally_authorized = trust.get("claim_status") == "claimed" and trust.get("contact_authorized") is True

    if "email" in requested:
        address = str(extras.get("email") or "").strip()
        if not globally_authorized or authorizations.get("email") is not True:
            statuses["email"] = {"status": "skipped", "reason": "supplier_email_not_authorized"}
        elif not address or "@" not in address:
            statuses["email"] = {"status": "skipped", "reason": "supplier_email_missing"}
        else:
            ok, message = send_email(address, title[:200], content[:4000])
            statuses["email"] = {"status": "sent", "sent_at": datetime.utcnow().isoformat()} if ok else {"status": "failed", "error": str(message)[:500]}

    if "wechat" in requested:
        if not globally_authorized or authorizations.get("wechat") is not True:
            statuses["wechat"] = {"status": "skipped", "reason": "supplier_wechat_not_authorized"}
        elif not supplier.wechat_bound:
            statuses["wechat"] = {"status": "skipped", "reason": "supplier_wechat_not_bound"}
        else:
            result = wechat_push_service.push_message(supplier.id, title[:200], content[:1000], url="/sales-console", is_urgent=True)
            statuses["wechat"] = {"status": "sent", "sent_at": datetime.utcnow().isoformat()} if result.get("wechat_ok") else {"status": "failed", "error": str(result.get("message") or "wechat_not_delivered")[:500]}

    if "work_wechat" in requested:
        if not globally_authorized or authorizations.get("work_wechat") is not True:
            statuses["work_wechat"] = {"status": "skipped", "reason": "supplier_work_wechat_not_authorized"}
        else:
            user_id = str(getattr(supplier, "wechat_work_userid", "") or "").strip()
            if not user_id:
                statuses["work_wechat"] = {"status": "skipped", "reason": "supplier_work_wechat_not_bound"}
            else:
                result = send_work_wechat_text(
                    user_id=user_id,
                    title=title[:200],
                    content=content[:1800],
                    url="/sales-console",
                )
                if result.get("wechat_ok"):
                    statuses["work_wechat"] = {
                        "status": "sent",
                        "sent_at": datetime.utcnow().isoformat(),
                        **({"provider_message_id": result["provider_message_id"]} if result.get("provider_message_id") else {}),
                    }
                else:
                    statuses["work_wechat"] = {"status": "failed", "error": str(result.get("reason") or "work_wechat_not_delivered")[:200]}

    successful = [channel for channel, state in statuses.items() if state.get("status") == "sent"]
    return {"requested": requested, "channels": statuses, "primary_channel": next((channel for channel in ("work_wechat", "wechat", "email", "site") if channel in successful), "site")}
