"""
API 测试脚本
=============

测试新的API接口是否正常工作。
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from app import create_app, db
from app.models import Enterprise


def test_apis():
    app = create_app()
    with app.app_context():
        print("[测试] 检查数据库连接...")
        
        # 测试企业数据
        enterprise = Enterprise.query.first()
        if enterprise:
            print(f"[OK] 企业数据存在: {enterprise.name} (ID: {enterprise.id})")
        else:
            print("[ERROR] 没有企业数据，请先创建数据")
            return
        
        print("\n[测试] 检查API蓝图注册...")
        
        # 检查蓝图是否注册
        registered_bps = [bp.name for bp in app.blueprints.values()]
        print(f"已注册的蓝图: {registered_bps}")
        
        if 'intent_quote' in registered_bps:
            print("[OK] intent_quote 蓝图已注册")
        else:
            print("[ERROR] intent_quote 蓝图未注册")
            
        if 'favorite' in registered_bps:
            print("[OK] favorite 蓝图已注册")
        else:
            print("[ERROR] favorite 蓝图未注册")
        
        print("\n[测试] 尝试调用API路由...")
        
        with app.test_client() as client:
            # 测试企业画像API
            resp = client.get(f'/api/intent-quote/enterprise-profile/{enterprise.id}')
            print(f"GET /api/intent-quote/enterprise-profile/{enterprise.id} -> {resp.status_code}")
            if resp.status_code == 200:
                data = resp.get_json()
                print(f"[OK] 返回数据: {data}")
            elif resp.status_code == 401:
                print("[INFO] 需要登录认证 (这是正常的)")
            else:
                print(f"[ERROR] {resp.status_code}: {resp.get_json()}")
            
            # 测试收藏列表API
            resp = client.get('/api/favorites/list')
            print(f"\nGET /api/favorites/list -> {resp.status_code}")
            if resp.status_code == 200:
                data = resp.get_json()
                print(f"[OK] 返回数据: {data}")
            elif resp.status_code == 401:
                print("[INFO] 需要登录认证 (这是正常的)")
            else:
                print(f"[ERROR] {resp.status_code}: {resp.get_json()}")
        
        print("\n[测试完成]")


if __name__ == "__main__":
    test_apis()
