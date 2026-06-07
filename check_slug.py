"""临时诊断：列出 AnythingLLM 工作区名称与 SLUG（读 .env 中的 ANYTHING_LLM_API_KEY）。"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("ANYTHING_LLM_API_KEY", "45YBDHE-K9X43T4-JF82XZP-X0TKTXB")
URL = "http://127.0.0.1:3001/api/v1/workspaces"

headers = {"Authorization": f"Bearer {API_KEY}", "accept": "application/json"}
try:
    res = requests.get(URL, headers=headers, timeout=30)
    data = res.json()
    print("--- 发现的工作区列表 ---")
    for ws in data.get("workspaces", []):
        print(f"名称: {ws.get('name')} | 标识符(SLUG): {ws.get('slug')}")
    if res.status_code != 200:
        print(f"(HTTP {res.status_code}) 原始响应: {data}")
except Exception as e:
    print(f"请求失败: {e}")
