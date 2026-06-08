"""
测试定时任务调度器
验证调度器初始化和任务注册
"""
from app import create_app
from app.services.scheduler import get_scheduler, get_job_status

def test_scheduler():
    """测试调度器功能"""
    print("=" * 60)
    print("测试定时任务调度器")
    print("=" * 60)
    
    # 创建应用
    app = create_app()
    
    with app.app_context():
        # 获取调度器
        scheduler = get_scheduler()
        
        if scheduler is None:
            print("❌ 调度器未初始化")
            return False
        
        print(f"✓ 调度器状态: {'运行中' if scheduler.running else '已停止'}")
        print()
        
        # 获取任务状态
        jobs = get_job_status()
        print(f"✓ 已注册任务数量: {len(jobs)}")
        print()
        
        # 显示任务详情
        for job in jobs:
            print(f"任务ID: {job['id']}")
            print(f"  名称: {job['name']}")
            print(f"  触发器: {job['trigger']}")
            print(f"  下次执行: {job['next_run_time']}")
            print()
        
        # 验证必需的任务
        job_ids = [job['id'] for job in jobs]
        required_jobs = [
            'reset_daily_quote_counts',
            'batch_recalculate_credit_scores'
        ]
        
        missing_jobs = [job_id for job_id in required_jobs if job_id not in job_ids]
        
        if missing_jobs:
            print(f"❌ 缺少必需任务: {', '.join(missing_jobs)}")
            return False
        
        print("✓ 所有必需任务已注册")
        print()
        print("=" * 60)
        print("✓ 调度器测试通过")
        print("=" * 60)
        
        return True

if __name__ == '__main__':
    success = test_scheduler()
    exit(0 if success else 1)
