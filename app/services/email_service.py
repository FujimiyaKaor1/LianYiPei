"""SMTP email helper used by account notification tests."""

from __future__ import annotations

import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
from typing import Optional, Tuple

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ENV_PATH = _PROJECT_ROOT / ".env"


def _load_dotenv_values() -> dict[str, str]:
    if not _PROJECT_ENV_PATH.is_file():
        return {}
    values: dict[str, str] = {}
    for key, value in dotenv_values(_PROJECT_ENV_PATH).items():
        if key is None or value is None:
            continue
        cleaned_key = str(key).strip()
        if cleaned_key and not cleaned_key.startswith("#"):
            values[cleaned_key] = str(value).strip()
    return values


def _smtp_config() -> dict[str, object]:
    values = _load_dotenv_values()
    return {
        "host": values.get("SMTP_HOST", "").strip(),
        "port": int(values.get("SMTP_PORT", "587").strip() or 587),
        "username": values.get("SMTP_USERNAME", "").strip(),
        "password": values.get("SMTP_PASSWORD", "").strip(),
        "from_name": values.get("SMTP_FROM_NAME", "链易配").strip(),
        "from_email": values.get("SMTP_FROM_EMAIL", "").strip(),
        "use_tls": values.get("SMTP_USE_TLS", "true").strip().lower() in {"true", "1", "yes", "on"},
    }


def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
) -> Tuple[bool, str]:
    """Send an email via SMTP and return (success, message)."""
    cfg = _smtp_config()
    missing = [
        env_key
        for env_key, cfg_key in {
            "SMTP_HOST": "host",
            "SMTP_USERNAME": "username",
            "SMTP_PASSWORD": "password",
            "SMTP_FROM_EMAIL": "from_email",
        }.items()
        if not cfg.get(cfg_key)
    ]
    if missing:
        return False, f'缺少 SMTP 配置：{", ".join(missing)}，请在 .env 中填写'

    if not to_email or "@" not in to_email:
        return False, "无效的收件人邮箱地址"

    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = Header(subject, "utf-8").encode()
        message["From"] = formataddr((str(cfg["from_name"]), str(cfg["from_email"])))
        message["To"] = to_email
        message.attach(MIMEText(body, "plain", "utf-8"))
        if html_body:
            message.attach(MIMEText(html_body, "html", "utf-8"))

        server = smtplib.SMTP(str(cfg["host"]), int(cfg["port"]), timeout=15)
        try:
            if cfg["use_tls"]:
                server.ehlo()
                server.starttls()
                server.ehlo()
            server.login(str(cfg["username"]), str(cfg["password"]))
            server.sendmail(str(cfg["from_email"]), [to_email], message.as_string())
        finally:
            server.quit()

        logger.info("[Email] email sent to %s, subject=%s", to_email, subject)
        return True, "ok"
    except smtplib.SMTPAuthenticationError:
        logger.error("[Email] SMTP authentication failed")
        return False, "SMTP 认证失败，请检查用户名/密码（授权码）"
    except smtplib.SMTPConnectError:
        logger.error("[Email] cannot connect to SMTP server %s:%s", cfg["host"], cfg["port"])
        return False, f'无法连接到 SMTP 服务器 {cfg["host"]}:{cfg["port"]}，请检查 host/port'
    except smtplib.SMTPRecipientsRefused as exc:
        logger.error("[Email] recipient refused: %s", exc)
        return False, f"收件人邮箱被拒绝：{exc}"
    except Exception as exc:
        logger.error("[Email] send failed: %s", exc)
        return False, f"发送邮件异常：{exc}"
