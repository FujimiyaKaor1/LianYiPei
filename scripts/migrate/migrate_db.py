"""数据库迁移脚本 - 添加新字段与新表"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _column_exists(conn, table, col):
    from sqlalchemy import text
    r = conn.execute(text(f"""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table}' AND COLUMN_NAME='{col}'
    """))
    return r.fetchone() is not None

def migrate():
    from app import create_app, db
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        db.create_all()  # 创建所有表（含新表）

        try:
            conn = db.engine.connect()
            # enterprises 新字段
            for col, ddl in [
                ('patent_category', 'VARCHAR(100)'),
                ('tech_keywords', 'VARCHAR(500)'),
                ('rd_investment', 'FLOAT'),
                ('industry_code', 'VARCHAR(50)'),
                ('registered_capital', 'FLOAT'),
                ('business_scope', 'TEXT'),
                ('province', 'VARCHAR(20)'),
                ('patent_count', 'INT'),
            ]:
                if not _column_exists(conn, 'enterprises', col):
                    conn.execute(text(f"ALTER TABLE enterprises ADD COLUMN {col} {ddl}"))
                    conn.commit()
                    print(f"  已添加 enterprises.{col}")

            if not _column_exists(conn, 'products', 'industry_code'):
                conn.execute(text("ALTER TABLE products ADD COLUMN industry_code VARCHAR(50)"))
                conn.commit()
                print("  已添加 products.industry_code")
            if not _column_exists(conn, 'products', 'image_path'):
                conn.execute(text("ALTER TABLE products ADD COLUMN image_path VARCHAR(255)"))
                conn.commit()
                print("  已添加 products.image_path")
            if not _column_exists(conn, 'alerts', 'suggestion'):
                conn.execute(text("ALTER TABLE alerts ADD COLUMN suggestion TEXT"))
                conn.commit()
                print("  已添加 alerts.suggestion")

            for col, ddl in [
                ('is_green_factory', 'TINYINT(1) DEFAULT 0'),
                ('green_certification', 'JSON NULL'),
                ('clean_energy_usage', 'FLOAT DEFAULT 0.0'),
                ('carbon_emission_level', 'VARCHAR(10) NULL'),
                ('environment_protection_patents', 'INT DEFAULT 0'),
                ('green_supplier_rank', 'VARCHAR(20) NULL'),
            ]:
                if not _column_exists(conn, 'enterprises', col):
                    conn.execute(text(f"ALTER TABLE enterprises ADD COLUMN {col} {ddl}"))
                    conn.commit()
                    print(f"  已添加 enterprises.{col}")

            conn.close()
        except Exception as e:
            print(f"迁移执行: {e}")

        print("迁移完成")

if __name__ == '__main__':
    migrate()
