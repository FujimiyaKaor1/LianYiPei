"""
链易配 - 一键初始化并启动
执行顺序：创建数据库 -> 初始化数据 -> 启动应用
"""
import sys
import os
import subprocess
import socket
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))
except Exception:
    pass

def run(cmd, desc):
    print(f"\n>>> {desc}")
    r = subprocess.run(cmd, shell=True)
    if r.returncode != 0:
        print(f"失败: {cmd}")
        return False
    return True

def main():
    print("=" * 55)
    print("  链易配 - 数据库初始化 & 启动")
    print("=" * 55)

    # 1. 创建数据库
    if not run("python scripts/create_db.py", "创建 MySQL 数据库"):
        print("\n请检查 MySQL 是否启动，.env 中 DATABASE_URL 是否正确")
        return

    # 2. 初始化数据
    if not run("python scripts/seed_all_data.py", "初始化数据"):
        print("\n数据初始化失败，请检查 Neo4j 是否启动")
        print("（Neo4j 失败时可忽略，MySQL 数据仍会导入）")

    print("\n" + "=" * 55)
    print("  启动应用: python run.py")
    print("  访问: http://localhost:5000")
    print("  政府账号: admin / admin  |  企业账号: test_ent / 123456")
    print("=" * 55)

    # 3. 启动（增加：自动启动 model_service + 等待端口就绪）

    def _port_open(host: str, port: int, timeout_sec: float = 0.5) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout_sec)
        try:
            return s.connect_ex((host, port)) == 0
        finally:
            try:
                s.close()
            except Exception:
                pass

    # 3.1 若未配置 Ollama，则尝试启动自建 model_service（默认监听 5001）
    ollama_base = (os.environ.get("OLLAMA_BASE_URL") or "").strip()
    legacy = (
        os.environ.get("LLMBASEURL") or os.environ.get("LLM_BASE_URL") or ""
    ).strip()
    use_ollama = "11434" in ollama_base or "11434" in legacy
    llm_port = int(os.environ.get("MODEL_SERVICE_PORT", "5001"))
    llm_host = os.environ.get("MODEL_SERVICE_HOST", "127.0.0.1")
    if use_ollama:
        print("\n已配置 Ollama（端口 11434），跳过自动启动 model_service。")
    elif not _port_open(llm_host, llm_port):
        print(f"\n检测到 model_service 未启动，尝试后台启动（{llm_host}:{llm_port}）...")
        subprocess.Popen(
            [sys.executable, os.path.join(ROOT, "model_service", "app.py")],
            cwd=os.path.join(ROOT, "model_service"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # 3.2 启动主应用（默认 5000）
    main_port = int(os.environ.get("APP_PORT", "5000"))
    main_host = os.environ.get("APP_HOST", "127.0.0.1")

    print(f"\n启动主应用：python run.py （{main_host}:{main_port}）")
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "run.py")])

    # 等待主服务端口就绪，避免用户立刻访问出现“拒绝连接”
    start_ts = time.time()
    while time.time() - start_ts < 60:
        if _port_open(main_host, main_port):
            break
        time.sleep(0.5)

    if not _port_open(main_host, main_port):
        print("\n主应用端口未能在 60 秒内就绪，请查看 run.py 控制台/终端输出定位启动错误。")
    else:
        print("\n服务已就绪：访问 http://localhost:5000")

    # 阻塞等待主进程退出
    proc.wait()

if __name__ == '__main__':
    main()
