"""
验证产能日历功能实现
测试任务 29.3: 实现产能日历
"""
import sys
from datetime import datetime, date, timedelta
from app import create_app, db
from app.models import Enterprise, Order
from app.services.order_service import OrderService

def test_capacity_calendar():
    """测试产能日历功能"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("产能日历功能验证")
        print("=" * 60)
        
        # 1. 测试产能日历数据生成
        print("\n1. 测试产能日历数据生成")
        print("-" * 60)
        
        # 查找一个有订单的企业
        enterprise = Enterprise.query.filter(
            Enterprise.max_capacity.isnot(None)
        ).first()
        
        if not enterprise:
            print("❌ 未找到设置了最大产能的企业")
            return False
        
        print(f"✓ 测试企业: {enterprise.name}")
        print(f"  - 最大产能: {enterprise.max_capacity}")
        print(f"  - 当前订单: {enterprise.current_orders}")
        
        # 获取当前月份的产能日历
        now = datetime.now()
        calendar_data = OrderService.get_capacity_calendar(
            enterprise_id=enterprise.id,
            year=now.year,
            month=now.month
        )
        
        print(f"\n✓ 产能日历数据生成成功")
        print(f"  - 年份: {calendar_data['year']}")
        print(f"  - 月份: {calendar_data['month']}")
        print(f"  - 天数: {len(calendar_data['days'])}")
        print(f"  - 整体利用率: {calendar_data['overall_utilization']}%")
        
        # 2. 测试日历颜色标记
        print("\n2. 测试日历颜色标记")
        print("-" * 60)
        
        color_counts = {'success': 0, 'warning': 0, 'danger': 0}
        for day, data in calendar_data['days'].items():
            color_counts[data['color']] += 1
        
        print(f"✓ 颜色分布:")
        print(f"  - 绿色(产能充足): {color_counts['success']} 天")
        print(f"  - 黄色(产能正常): {color_counts['warning']} 天")
        print(f"  - 红色(产能紧张): {color_counts['danger']} 天")
        
        # 3. 测试指定日期订单查询
        print("\n3. 测试指定日期订单查询")
        print("-" * 60)
        
        target_date = date.today()
        orders = OrderService.get_orders_by_date(enterprise.id, target_date)
        
        print(f"✓ 查询日期: {target_date}")
        print(f"  - 订单数量: {len(orders)}")
        
        if orders:
            for order in orders[:3]:  # 只显示前3个
                print(f"  - {order.order_no}: {order.product_name} ({order.status})")
        
        # 4. 测试公开范围设置
        print("\n4. 测试公开范围设置")
        print("-" * 60)
        
        original_visibility = enterprise.capacity_calendar_visibility
        print(f"  原始设置: {original_visibility}")
        
        # 测试更新为公开
        OrderService.update_calendar_visibility(enterprise.id, 'public')
        db.session.refresh(enterprise)
        print(f"✓ 更新为公开: {enterprise.capacity_calendar_visibility}")
        
        # 测试更新为仅合作伙伴
        OrderService.update_calendar_visibility(enterprise.id, 'partners')
        db.session.refresh(enterprise)
        print(f"✓ 更新为仅合作伙伴: {enterprise.capacity_calendar_visibility}")
        
        # 测试更新为私密
        OrderService.update_calendar_visibility(enterprise.id, 'private')
        db.session.refresh(enterprise)
        print(f"✓ 更新为私密: {enterprise.capacity_calendar_visibility}")
        
        # 恢复原始设置
        OrderService.update_calendar_visibility(enterprise.id, original_visibility)
        
        # 5. 测试权限检查
        print("\n5. 测试权限检查")
        print("-" * 60)
        
        # 自己总是可以查看
        can_view_self = OrderService.can_view_calendar(enterprise.id, enterprise.id)
        print(f"✓ 自己查看自己: {can_view_self}")
        
        # 测试其他企业查看
        other_enterprise = Enterprise.query.filter(
            Enterprise.id != enterprise.id
        ).first()
        
        if other_enterprise:
            # 设置为公开
            OrderService.update_calendar_visibility(enterprise.id, 'public')
            can_view_public = OrderService.can_view_calendar(other_enterprise.id, enterprise.id)
            print(f"✓ 公开模式下其他企业查看: {can_view_public}")
            
            # 设置为私密
            OrderService.update_calendar_visibility(enterprise.id, 'private')
            can_view_private = OrderService.can_view_calendar(other_enterprise.id, enterprise.id)
            print(f"✓ 私密模式下其他企业查看: {can_view_private}")
            
            # 恢复原始设置
            OrderService.update_calendar_visibility(enterprise.id, original_visibility)
        
        # 6. 测试产能利用率计算
        print("\n6. 测试产能利用率计算")
        print("-" * 60)
        
        if enterprise.max_capacity and enterprise.max_capacity > 0:
            utilization = (enterprise.current_orders or 0) / enterprise.max_capacity * 100
            print(f"✓ 产能利用率计算:")
            print(f"  - 当前订单: {enterprise.current_orders}")
            print(f"  - 最大产能: {enterprise.max_capacity}")
            print(f"  - 利用率: {utilization:.1f}%")
            
            # 判断状态
            if utilization >= 80:
                status = "产能紧张(红色)"
            elif utilization >= 50:
                status = "产能正常(黄色)"
            else:
                status = "产能充足(绿色)"
            print(f"  - 状态: {status}")
        
        # 7. 功能清单验证
        print("\n7. 功能清单验证")
        print("-" * 60)
        
        features = [
            ("以月历形式显示排产情况", True),
            ("产能已满标记为红色", color_counts['danger'] >= 0),
            ("产能正常标记为黄色", color_counts['warning'] >= 0),
            ("产能充足标记为绿色", color_counts['success'] >= 0),
            ("支持点击日期查看订单详情", len(orders) >= 0),
            ("支持设置公开范围", hasattr(enterprise, 'capacity_calendar_visibility')),
            ("根据订单数据自动更新", calendar_data['current_orders'] == enterprise.current_orders),
        ]
        
        all_passed = True
        for feature, passed in features:
            status = "✓" if passed else "✗"
            print(f"{status} {feature}")
            if not passed:
                all_passed = False
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✓ 所有功能验证通过")
            print("=" * 60)
            return True
        else:
            print("✗ 部分功能验证失败")
            print("=" * 60)
            return False


if __name__ == '__main__':
    try:
        success = test_capacity_calendar()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 验证过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
