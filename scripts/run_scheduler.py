"""Run the APScheduler process separately from Gunicorn web workers.

Production deployment uses Supervisor to keep exactly one scheduler process.
The process-specific environment override is set before importing the Flask app,
so the shared project .env can keep the rest of the application configuration.
"""

import os
import signal
import threading


os.environ["LIANYIPEI_SCHEDULER_ENABLED"] = "1"

from app import create_app  # noqa: E402
from app.services.scheduler import get_scheduler, shutdown_scheduler  # noqa: E402


app = create_app()
if get_scheduler() is None:
    raise RuntimeError("调度器未启动，请检查 SCHEDULER_ENABLED 和数据库配置")

_stop = threading.Event()


def _handle_stop(signum, _frame):
    shutdown_scheduler()
    _stop.set()


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)

if __name__ == "__main__":
    _stop.wait()
