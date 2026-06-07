# 文件名：test_data_baseline.py
# 作用：一键统计系统当前数据量，证明系统具备真实的产业链数据
import time
from app import create_app, db
from app.models import Enterprise, Product, Transaction, Inquiry


def export_test_data():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始扫描链易配系统底层数据库...")
    app = create_app()
    with app.app_context():
        ent_count = Enterprise.query.count()
        prod_count = Product.query.count()
        trans_count = Transaction.query.count()
        inq_count = Inquiry.query.count()

        print("-" * 30)
        print(f"  企业节点数: {ent_count} 家")
        print(f"  产品节点数: {prod_count} 种")
        print(f"  历史交易数: {trans_count} 笔")
        print(f"  询价记录数: {inq_count} 条")
        print("-" * 30)

        if (ent_count + prod_count) >= 500:
            print("  [OK] 图谱规模 >= 500 节点，满足大屏实时渲染要求！")
        else:
            print(f"  [INFO] 当前图谱节点数为 {ent_count + prod_count}，可通过数据导入补充至 500+")


if __name__ == '__main__':
    export_test_data()
