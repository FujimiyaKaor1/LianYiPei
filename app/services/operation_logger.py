"""
操作日志：写入标准 logging（原 operation_logs 表已删除）。
"""

import logging
from typing import Optional

from flask import has_request_context, request

logger = logging.getLogger("app.ops")


def log_operation(
    user_id: int,
    operation_type: str,
    operation_target: str,
    target_id: Optional[int] = None,
    operation_detail: str = "",
    result: str = "success",
    error_message: str = "",
):
    try:
        ip = request.remote_addr if has_request_context() else None
        ua = (request.headers.get("User-Agent", "") if has_request_context() else "")[:255]
        logger.info(
            "op user=%s type=%s target=%s id=%s result=%s ip=%s detail=%s err=%s ua=%s",
            user_id,
            operation_type,
            operation_target,
            target_id,
            result,
            ip,
            operation_detail,
            error_message,
            ua,
        )
    except Exception as e:
        logger.warning("log_operation failed: %s", e)
