cd d:\大学\创赛\链易配\frontend
npm run dev"""
数据库迁移脚本：添加产能日历公开范围字段
"""
from app import create_app, db
from sqlalchemy import text

def run_migration():
    app = create_app()
    
    with app.app_context():
        print("开始迁移：添加产能日历公开范围字段...")
        
        try:
            # 检查字段是否已存在
            result = db.session.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'enterprises' 
                AND COLUMN_NAME = 'capacity_calendar_visibility'
            """))
            
            count = result.fetchone()[0]
            
            if count > 0:
                print("✓ 字段已存在，跳过迁移")
                return True
            
            # 添加字段
            db.session.execute(text("""
                ALTER TABLE enterprises 
                ADD COLUMN capacity_calendar_visibility VARCHAR(20) DEFAULT 'private'
            """))
            
            # 为现有记录设置默认值
            db.session.execute(text("""
                UPDATE enterprises 
                SET capacity_calendar_visibility = 'private' 
                WHERE capacity_calendar_visibility IS NULL
            """))
            
            db.session.commit()
            
            print("✓ 迁移完成：capacity_calendar_visibility 字段已添加")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"✗ 迁移失败: {str(e)}")
            return False

if __name__ == '__main__':
    success = run_migration()
    exit(0 if success else 1)
