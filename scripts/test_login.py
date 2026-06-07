"""
链易配 - 登录功能测试脚本
测试政府端账号和企业端账号的登录及权限
"""
import requests
import json
import re

BASE_URL = "http://127.0.0.1:5000"

def test_login(username, password, expected_role):
    """测试登录功能"""
    print(f"\n{'='*50}")
    print(f"测试账号: {username}")
    print(f"{'='*50}")
    
    # 创建会话
    session = requests.Session()
    
    # 1. 获取首页（获取 CSRF token 等）
    print("\n[1] 访问首页...")
    resp = session.get(f"{BASE_URL}/")
    print(f"    状态码: {resp.status_code}")
    
    # 2. 尝试登录
    print(f"\n[2] 登录测试 (用户名: {username}, 密码: {password})...")
    login_data = {
        'name': username,
        'password': password
    }
    
    login_resp = session.post(
        f"{BASE_URL}/auth/login",
        data=login_data,
        headers={'X-Login-Modal': '1', 'Accept': 'application/json'},
        allow_redirects=False
    )
    
    print(f"    状态码: {login_resp.status_code}")
    print(f"    响应头: {dict(login_resp.headers)}")
    print(f"    响应内容: {login_resp.text}")
    
    if login_resp.status_code == 200:
        try:
            result = login_resp.json()
            print(f"    响应JSON: {json.dumps(result, ensure_ascii=False, indent=4)}")
            
            if result.get('ok'):
                print(f"    ✓ 登录成功!")
            else:
                print(f"    ✗ 登录失败: {result.get('error', '未知错误')}")
                return False
        except Exception as e:
            print(f"    解析JSON失败: {e}")
            print(f"    响应内容: {login_resp.text[:500]}")
            return False
    elif login_resp.status_code == 302:
        print(f"    ✓ 登录成功! 重定向到: {login_resp.headers.get('Location')}")
    elif login_resp.status_code == 401:
        try:
            result = login_resp.json()
            print(f"    ✗ 登录失败: {result.get('error', '未知错误')}")
        except:
            print(f"    ✗ 登录失败: {login_resp.text}")
        return False
    else:
        print(f"    ✗ 登录失败! 状态码: {login_resp.status_code}")
        return False
    
    # 3. 获取首页数据，检查用户信息
    print(f"\n[3] 获取用户信息...")
    home_resp = session.get(f"{BASE_URL}/")
    
    # 使用正则表达式提取 JSON 数据
    match = re.search(r'window\.__INITIAL_DATA__\s*=\s*(\{.*?\});', home_resp.text, re.DOTALL)
    
    if match:
        try:
            initial_data = json.loads(match.group(1))
            user_name = initial_data.get('user_name', '未知')
            user_role = initial_data.get('user_role', '未知')
            is_authenticated = initial_data.get('is_authenticated', False)
            
            print(f"    用户名: {user_name}")
            print(f"    角色: {user_role}")
            print(f"    已认证: {is_authenticated}")
            
            if user_role == expected_role:
                print(f"    ✓ 角色验证成功! 期望: {expected_role}, 实际: {user_role}")
            else:
                print(f"    ✗ 角色验证失败! 期望: {expected_role}, 实际: {user_role}")
                return False
        except Exception as e:
            print(f"    解析数据失败: {e}")
            return False
    else:
        print("    未找到用户数据，但登录已成功")
    
    # 4. 测试权限访问
    print(f"\n[4] 测试权限访问...")
    
    if expected_role == 'admin':
        # 政府端账号应该能访问政府大屏
        print("    测试政府大屏访问...")
        stats_resp = session.get(f"{BASE_URL}/dashboard/stats")
        print(f"    政府大屏状态码: {stats_resp.status_code}")
        if stats_resp.status_code == 200:
            print("    ✓ 政府大屏访问成功!")
        else:
            print("    ✗ 政府大屏访问失败!")
        
        # 政府端账号不应该能访问企业中心（会被重定向）
        print("    测试企业中心访问...")
        profile_resp = session.get(f"{BASE_URL}/enterprise/profile", allow_redirects=False)
        print(f"    企业中心状态码: {profile_resp.status_code}")
        if profile_resp.status_code in [302, 403]:
            print("    ✓ 企业中心访问被正确拒绝!")
        else:
            print("    ? 企业中心访问状态: " + str(profile_resp.status_code))
    
    else:  # enterprise
        # 企业端账号应该能访问企业中心
        print("    测试企业中心访问...")
        profile_resp = session.get(f"{BASE_URL}/enterprise/profile")
        print(f"    企业中心状态码: {profile_resp.status_code}")
        if profile_resp.status_code == 200:
            print("    ✓ 企业中心访问成功!")
        else:
            print("    ✗ 企业中心访问失败!")
        
        # 企业端账号不应该能访问政府大屏（会被重定向）
        print("    测试政府大屏访问...")
        stats_resp = session.get(f"{BASE_URL}/dashboard/stats", allow_redirects=False)
        print(f"    政府大屏状态码: {stats_resp.status_code}")
        if stats_resp.status_code in [302, 403]:
            print("    ✓ 政府大屏访问被正确拒绝!")
        else:
            print("    ? 政府大屏访问状态: " + str(stats_resp.status_code))
    
    # 5. 登出
    print(f"\n[5] 登出测试...")
    logout_resp = session.get(f"{BASE_URL}/auth/logout", allow_redirects=False)
    print(f"    登出状态码: {logout_resp.status_code}")
    if logout_resp.status_code == 302:
        print("    ✓ 登出成功!")
    
    return True

def main():
    print("\n" + "="*60)
    print("链易配 - 登录功能测试")
    print("="*60)
    
    # 测试政府端账号
    admin_ok = test_login('admin', 'admin', 'admin')
    
    # 测试企业端账号
    ent_ok = test_login('test_ent', '123456', 'enterprise')
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"政府端账号 (admin/admin): {'✓ 通过' if admin_ok else '✗ 失败'}")
    print(f"企业端账号 (test_ent/123456): {'✓ 通过' if ent_ok else '✗ 失败'}")
    print("="*60)

if __name__ == '__main__':
    main()
