"""
验证测试框架配置
快速检查测试环境是否正确设置
"""
import sys
import os

def check_dependencies():
    """检查测试依赖是否安装"""
    print("=" * 60)
    print("检查测试依赖")
    print("=" * 60)
    
    required_packages = [
        'pytest',
        'pytest_flask',
        'pytest_cov',
        'hypothesis',
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✓ {package} 已安装")
        except ImportError:
            print(f"✗ {package} 未安装")
            missing.append(package)
    
    if missing:
        print(f"\n缺少依赖: {', '.join(missing)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("\n✓ 所有测试依赖已安装")
    return True


def check_test_structure():
    """检查测试目录结构"""
    print("\n" + "=" * 60)
    print("检查测试目录结构")
    print("=" * 60)
    
    required_files = [
        'tests/__init__.py',
        'tests/conftest.py',
        'tests/test_config.py',
        'tests/test_credit_engine.py',
        'pytest.ini',
    ]
    
    missing = []
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path} 存在")
        else:
            print(f"✗ {file_path} 不存在")
            missing.append(file_path)
    
    if missing:
        print(f"\n缺少文件: {', '.join(missing)}")
        return False
    
    print("\n✓ 测试目录结构完整")
    return True


def check_pytest_config():
    """检查pytest配置"""
    print("\n" + "=" * 60)
    print("检查pytest配置")
    print("=" * 60)
    
    if not os.path.exists('pytest.ini'):
        print("✗ pytest.ini 不存在")
        return False
    
    with open('pytest.ini', 'r', encoding='utf-8') as f:
        content = f.read()
        
        checks = [
            ('testpaths', 'testpaths = tests'),
            ('markers', 'markers ='),
            ('coverage', '--cov=app'),
        ]
        
        for name, pattern in checks:
            if pattern in content:
                print(f"✓ {name} 配置正确")
            else:
                print(f"✗ {name} 配置缺失")
                return False
    
    print("\n✓ pytest配置正确")
    return True


def run_simple_test():
    """运行简单测试验证"""
    print("\n" + "=" * 60)
    print("运行简单测试")
    print("=" * 60)
    
    try:
        import pytest
        
        # 运行配置测试
        exit_code = pytest.main([
            'tests/test_config.py',
            '-v',
            '--tb=short',
            '-p', 'no:warnings'
        ])
        
        if exit_code == 0:
            print("\n✓ 测试运行成功")
            return True
        else:
            print(f"\n✗ 测试失败，退出码: {exit_code}")
            return False
            
    except Exception as e:
        print(f"\n✗ 运行测试时出错: {str(e)}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("测试框架配置验证")
    print("=" * 60 + "\n")
    
    checks = [
        ("依赖检查", check_dependencies),
        ("目录结构检查", check_test_structure),
        ("配置检查", check_pytest_config),
    ]
    
    all_passed = True
    for name, check_func in checks:
        if not check_func():
            all_passed = False
            print(f"\n✗ {name}失败")
            break
    
    if all_passed:
        print("\n" + "=" * 60)
        print("✓ 测试框架配置验证通过")
        print("=" * 60)
        print("\n可以运行以下命令开始测试:")
        print("  pytest                    # 运行所有测试")
        print("  pytest -m unit            # 只运行单元测试")
        print("  pytest -m credit          # 只运行信用分测试")
        print("  pytest --cov=app          # 运行测试并生成覆盖率报告")
        print("\n详细使用说明请查看: tests/README.md")
        return 0
    else:
        print("\n" + "=" * 60)
        print("✗ 测试框架配置验证失败")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(main())
