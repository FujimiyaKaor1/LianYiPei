from pathlib import Path

from dotenv import load_dotenv

# 确保在 import app / config 之前加载项目根目录 .env（避免仅依赖 config 内 load_dotenv 的导入次序问题）
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from app import create_app
from apscheduler.schedulers.background import BackgroundScheduler

app = create_app()

def scheduled_alert_check():
    """定期执行预警检测（每日）"""
    with app.app_context():
        from app.services.alerter import run_all_checks
        run_all_checks()
        print('[Scheduler] 预警检测已执行')

def scheduled_bandit_update():
    """定期更新Bandit算法的Beta分布参数（每日）"""
    with app.app_context():
        from app.services.bandit import _get_bandit
        import time
        bandit = _get_bandit()
        day_key = time.strftime("%Y-%m-%d", time.localtime(time.time() - 24 * 3600))
        success = bandit.update_from_feedback(day_key)
        if not success:
            success = bandit.update_from_mysql(day_key)
        if success:
            print(f'[Scheduler] Bandit参数已更新 (day_key={day_key})')
        else:
            print(f'[Scheduler] Bandit更新失败或无数据 (day_key={day_key})')

scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_alert_check, 'cron', hour=8, minute=0)
scheduler.add_job(scheduled_bandit_update, 'cron', hour=2, minute=0)
scheduler.start()

if __name__ == '__main__':
    import sys, socket, os

    def _find_port(preferred=5000, fallback=5050):
        """自适应端口选择：macOS 上 5000 常被 AirPlay Receiver 占用。"""
        for port in (preferred, fallback):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        return 5100  # 最后兜底端口

    PORT = _find_port()
    PLATFORM = 'macOS' if sys.platform == 'darwin' else 'Windows'
    print(f'[链易配] 启动于 http://localhost:{PORT} (平台: {PLATFORM})')
    # disable=True：避免 Windows 上 stat reloader 触发 OSError 10038
    app.run(debug=True, host='0.0.0.0', port=PORT, use_reloader=False)
