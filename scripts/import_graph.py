import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.graph_manager import create_relation, get_driver, clear_all_products, import_relations_from_csv

def main():
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'relations.csv')
    
    print("=" * 50)
    print("链易配 - 产业链图谱数据导入")
    print("=" * 50)
    print(f"\nCSV文件路径: {csv_path}")
    
    print("\n[1/4] 连接 Neo4j Aura...")
    driver = get_driver()
    if not driver:
        print("❌ 连接失败！请检查：")
        print("   1. Neo4j Aura 服务是否正常运行")
        print("   2. .env 文件中的连接信息是否正确")
        print("   3. 网络是否可以访问 Neo4j Aura")
        return
    
    print("✅ 连接成功！")
    
    print("\n[2/4] 清空现有数据...")
    clear_all_products()
    print("✅ 清空完成")
    
    print("\n[3/4] 导入产业链关系...")
    count = import_relations_from_csv(csv_path)
    
    print(f"\n[4/4] 导入完成")
    print("=" * 50)
    print(f"✅ 成功导入 {count} 条产业链关系！")
    print("=" * 50)
    print("\n现在可以访问系统查看产业链图谱：")
    print("http://localhost:5000/dashboard/graph")

if __name__ == '__main__':
    main()
