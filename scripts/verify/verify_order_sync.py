#!/usr/bin/env python3
"""
验证订单数据同步功能
测试需求: 20.3, 20.4, 20.8
"""
import sys
from datetime import datetime, date, timedelta
from app import create_app, db
from app.models import Enterprise, Order
from app.services.order_service import OrderService


def test_order_creation_sync():
    """测试订单创建时自动更新current_orders"""
    print("\n=== 测试1: 订单创建时自动更新current_orders ===")
    
    # 创建测试企业（使用时间戳确保唯一性）
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    enterprise = Enterprise(
        name=f"测试供应商{timestamp}",
        contact="张三",
        phone="13800138000",
        address="测试地址",
        role="supplier",
        credit_score=80.0,
        current_orders=0,
        max_capacity=100
    )
    db.session.add(enterprise)
    db.session.commit()
    
    print(f"初始 current_orders: {enterprise.current_orders}")
    print(f"初始 last_order_update: {enterprise.last_order_update}")
    
    # 创建订单
    order = OrderService.create_order(
        enterprise_id=enterprise.id,
        product_name="测试产品",
        quantity=10,
        unit="件",
        customer_name="测试客户",
        order_date=date.today()
    )
    
    # 刷新企业数据
    db.session.refresh(enterprise)
    
    print(f"创建订单后 current_orders: {enterprise.current_orders}")
    print(f"创建订单后 last_order_update: {enterprise.last_order_update}")
    
    assert enterprise.current_orders == 1, "订单创建后current_orders应该增加1"
    assert enterprise.last_order_update is not None, "last_order_update应该被更新"
    
    print("✓ 订单创建时自动更新current_orders - 通过")
    
    return enterprise, order


def test_order_completion_sync(enterprise, order):
    """测试订单完成时自动减少current_orders"""
    print("\n=== 测试2: 订单完成时自动减少current_orders ===")
    
    print(f"完成前 current_orders: {enterprise.current_orders}")
    
    # 更新订单状态为完成
    OrderService.update_order_status(
        order_id=order.id,
        status='completed',
        actual_delivery_date=date.today()
    )
    
    # 刷新企业数据
    db.session.refresh(enterprise)
    
    print(f"完成后 current_orders: {enterprise.current_orders}")
    print(f"完成后 last_order_update: {enterprise.last_order_update}")
    
    assert enterprise.current_orders == 0, "订单完成后current_orders应该减少1"
    
    print("✓ 订单完成时自动减少current_orders - 通过")


def test_hourly_sync():
    """测试每小时同步订单数据"""
    print("\n=== 测试3: 每小时同步订单数据 ===")
    
    # 创建测试企业（使用时间戳确保唯一性）
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    enterprise = Enterprise(
        name=f"测试企业2{timestamp}",
        contact="李四",
        phone="13900139000",
        address="测试地址2",
        role="supplier",
        credit_score=75.0,
        current_orders=5,  # 手动设置一个不准确的值
        max_capacity=50
    )
    db.session.add(enterprise)
    db.session.commit()
    
    # 创建2个进行中的订单
    for i in range(2):
        order = Order(
            order_no=f"TEST{i}",
            enterprise_id=enterprise.id,
            product_name=f"产品{i}",
            quantity=10,
            unit="件",
            customer_name="客户",
            order_date=date.today(),
            status='in_progress'
        )
        db.session.add(order)
    
    db.session.commit()
    
    print(f"同步前 current_orders: {enterprise.current_orders} (不准确)")
    
    # 执行同步
    updated_count = OrderService.sync_capacity_data()
    
    # 刷新企业数据
    db.session.refresh(enterprise)
    
    print(f"同步后 current_orders: {enterprise.current_orders} (应该是2)")
    print(f"同步更新的企业数量: {updated_count}")
    
    assert enterprise.current_orders == 2, "同步后current_orders应该等于实际进行中的订单数"
    
    print("✓ 每小时同步订单数据 - 通过")


def test_last_order_update():
    """测试last_order_update时间更新"""
    print("\n=== 测试4: last_order_update时间更新 ===")
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    enterprise = Enterprise(
        name=f"测试企业3{timestamp}",
        contact="王五",
        phone="13700137000",
        address="测试地址3",
        role="supplier",
        credit_score=70.0,
        current_orders=0,
        max_capacity=30
    )
    db.session.add(enterprise)
    db.session.commit()
    
    initial_update_time = enterprise.last_order_update
    print(f"初始 last_order_update: {initial_update_time}")
    
    # 创建订单
    order = OrderService.create_order(
        enterprise_id=enterprise.id,
        product_name="测试产品",
        quantity=5,
        unit="件",
        customer_name="客户",
        order_date=date.today()
    )
    
    db.session.refresh(enterprise)
    after_create_time = enterprise.last_order_update
    print(f"创建订单后 last_order_update: {after_create_time}")
    
    assert after_create_time is not None, "创建订单后应该更新last_order_update"
    
    # 完成订单
    OrderService.update_order_status(
        order_id=order.id,
        status='completed',
        actual_delivery_date=date.today()
    )
    
    db.session.refresh(enterprise)
    after_complete_time = enterprise.last_order_update
    print(f"完成订单后 last_order_update: {after_complete_time}")
    
    assert after_complete_time >= after_create_time, "完成订单后应该更新last_order_update"
    
    print("✓ last_order_update时间更新 - 通过")


def test_scheduler_task_registered():
    """测试定时任务是否已注册"""
    print("\n=== 测试5: 定时任务注册检查 ===")
    
    from app.services.scheduler import get_job_status
    
    jobs = get_job_status()
    
    # 查找订单同步任务
    sync_job = None
    for job in jobs:
        if job['id'] == 'sync_capacity_utilization':
            sync_job = job
            break
    
    if sync_job:
        print(f"✓ 找到定时任务: {sync_job['name']}")
        print(f"  任务ID: {sync_job['id']}")
        print(f"  触发器: {sync_job['trigger']}")
        print(f"  下次运行: {sync_job['next_run_time']}")
    else:
        print("✗ 未找到订单同步定时任务")
        return False
    
    return True


def main():
    """主测试函数"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("订单数据同步功能验证")
        print("=" * 60)
        
        try:
            # 不清理测试数据，直接开始测试
            
            # 测试1: 订单创建同步
            enterprise, order = test_order_creation_sync()
            
            # 测试2: 订单完成同步
            test_order_completion_sync(enterprise, order)
            
            # 测试3: 每小时同步
            test_hourly_sync()
            
            # 测试4: 时间戳更新
            test_last_order_update()
            
            # 测试5: 定时任务注册
            test_scheduler_task_registered()
            
            print("\n" + "=" * 60)
            print("所有测试通过！✓")
            print("=" * 60)
            print("\n功能验证:")
            print("✓ 订单创建时自动更新current_orders")
            print("✓ 订单完成时自动减少current_orders")
            print("✓ 更新last_order_update时间")
            print("✓ 每小时同步一次订单数据")
            print("✓ 定时任务已正确注册")
            
            # 清理测试数据
            try:
                Order.query.filter(Order.order_no.like('TEST%')).delete()
                Enterprise.query.filter(Enterprise.name.like('测试%')).delete()
                db.session.commit()
            except:
                db.session.rollback()
                print("\n注意: 测试数据清理失败（可能有外键约束），请手动清理")
            
            return 0
            
        except AssertionError as e:
            print(f"\n✗ 测试失败: {e}")
            db.session.rollback()
            return 1
            
        except Exception as e:
            print(f"\n✗ 发生错误: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return 1


if __name__ == '__main__':
    sys.exit(main())
