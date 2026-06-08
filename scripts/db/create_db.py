import os
import re
import pymysql
from pymysql import Error

def _parse_db_url():
    """从 DATABASE_URL 解析 host, user, password"""
    url = os.environ.get('DATABASE_URL', '')
    if not url or 'mysql' not in url:
        return None, None, None, None
    # mysql+pymysql://user:password@host:port/dbname
    m = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/(\w+)', url)
    if m:
        return m.group(1), m.group(2), m.group(3), m.group(5)
    return None, None, None, None

def create_database():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    except Exception:
        pass

    user, pwd, host, dbname = _parse_db_url()
    if not user:
        user = os.environ.get('MYSQL_USER', 'root')
        pwd = os.environ.get('MYSQL_PASSWORD', '123456')
        host = os.environ.get('MYSQL_HOST', 'localhost')
    dbname = dbname or 'lianyipei'

    try:
        connection = pymysql.connect(
            host=host, user=user, password=pwd, charset='utf8mb4'
        )
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {dbname} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print(f"数据库 '{dbname}' 创建成功！")
        cursor.close()
        connection.close()
        return True
    except Error as e:
        print(f"错误: {e}")
        print("\n请手动在 MySQL 中执行：")
        print("CREATE DATABASE lianyipei CHARACTER SET utf8mb4;")
        return False

if __name__ == "__main__":
    create_database()
