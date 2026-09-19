#!/usr/bin/env python3
"""Run the production IMAP -> Chain XiaoYi email quote worker."""
from __future__ import annotations

from pathlib import Path
import sys
import argparse
import json

# Allow running this file directly from the repository root or Supervisor.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

# Keep secrets and process-level enablement supplied by Supervisor/secret
# managers authoritative over a checked-out .env file.
load_dotenv(ROOT / ".env", override=False)

from app.services.email_quote_poller import email_poll_config, poll_once, run_forever


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="链小易供应商邮件报价回收 Worker")
    parser.add_argument("--once", action="store_true", help="只轮询一轮后退出")
    parser.add_argument("--interval", type=int, default=30, help="连续模式轮询间隔（秒）")
    args = parser.parse_args()
    config = email_poll_config()
    if args.once:
        print(json.dumps(poll_once(config), ensure_ascii=False))
    else:
        run_forever(config, sleep_seconds=args.interval)
