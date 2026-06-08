"""
链易配 - 全新初始化（清空所有数据后重新导入）
适用于开发环境重置
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == '__main__':
    from sqlalchemy import text

    from app import create_app, db
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "seed_all_data",
        os.path.join(os.path.dirname(__file__), "seed_all_data.py")
    )
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    seed_mysql = _mod.seed_mysql
    seed_neo4j = _mod.seed_neo4j

    print("=" * 50)
    print("链易配 - 全新初始化（将清空所有数据）")
    print("=" * 50)

    app = create_app()
    with app.app_context():
        print("\n[0/2] 清空并重建 MySQL 表...")
        dialect = db.engine.dialect.name
        if dialect == "mysql":
            # 必须在同一连接上关闭外键检查后再 drop；单独 db.drop_all() 会另取连接，无效。
            with db.engine.begin() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                db.metadata.drop_all(bind=conn)
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        else:
            db.drop_all()
        db.create_all()
        print("  完成")

    print("\n[1/2] MySQL 种子数据...")
    seed_mysql(app)

    print("\n[2/2] Neo4j 图谱...")
    seed_neo4j(app)

    print("\n" + "=" * 50)
    print("全新初始化完成！政府: admin / admin  |  企业: test_ent / 123456")
    print("=" * 50)
