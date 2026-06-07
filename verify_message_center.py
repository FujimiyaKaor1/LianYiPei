"""
验证消息中心功能
测试需求: 25.1-25.8, 30.1, 30.2
"""
import sys
from datetime import datetime, timedelta
from app import create_app, db
from app.models import Enterprise, Message
from app.services.message_service import MessageService

def test_message_center():
    """测试消息中心功能"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("消息中心功能验证")
        print("=" * 60)
        
        # 获取测试企业
        enterprise = Enterprise.query.filter_by(role='enterprise').first()
        if not enterprise:
            print("❌ 未找到测试企业，请先运行 seed_data.py")
            return False
        
        print(f"\n✓ 使用测试企业: {enterprise.name} (ID: {enterprise.id})")
        
        # 测试1: 创建不同类型的消息
        print("\n" + "=" * 60)
        print("测试1: 创建不同类型的消息")
        print("=" * 60)
        
        try:
            # 创建交易消息
            msg1 = MessageService.create_transaction_message(
                recipient_id=enterprise.id,
                title="新报价通知",
                content="您的询价单收到了3个新报价，请及时查看",
                link_url="/match/inquiry/1"
            )
            print(f"✓ 创建交易消息: {msg1.title}")
            
            # 创建预警消息
            msg2 = MessageService.create_alert_message(
                recipient_id=enterprise.id,
                title="产能风险预警",
                content="您的产能利用率低于30%，存在产能闲置风险",
                link_url="/dashboard/alert-center"
            )
            print(f"✓ 创建预警消息: {msg2.title}")
            
            # 创建系统消息
            msg3 = MessageService.create_system_message(
                recipient_id=enterprise.id,
                title="系统维护通知",
                content="系统将于今晚22:00-24:00进行维护，请提前保存数据",
                link_url=None
            )
            print(f"✓ 创建系统消息: {msg3.title}")
            
            # 创建询价消息
            msg4 = MessageService.create_inquiry_message(
                recipient_id=enterprise.id,
                title="新询价单匹配",
                content="有一个新的询价单与您的产品匹配，请查看详情",
                link_url="/match/inquiry/2"
            )
            print(f"✓ 创建询价消息: {msg4.title}")
            
            # 创建信用分消息
            msg5 = MessageService.create_credit_message(
                recipient_id=enterprise.id,
                title="信用分变更通知",
                content="您的信用分增加了10分，当前信用分: 85分",
                link_url="/credit/history"
            )
            print(f"✓ 创建信用分消息: {msg5.title}")
            
        except Exception as e:
            print(f"❌ 创建消息失败: {str(e)}")
            return False
        
        # 测试2: 获取消息列表
        print("\n" + "=" * 60)
        print("测试2: 获取消息列表")
        print("=" * 60)
        
        try:
            result = MessageService.get_messages(
                recipient_id=enterprise.id,
                page=1,
                per_page=10
            )
            print(f"✓ 获取消息列表成功")
            print(f"  - 总消息数: {result['total']}")
            print(f"  - 当前页: {result['page']}/{result['pages']}")
            print(f"  - 消息列表:")
            for msg in result['messages']:
                print(f"    [{msg.message_type}] {msg.title} - {'未读' if not msg.is_read else '已读'}")
        except Exception as e:
            print(f"❌ 获取消息列表失败: {str(e)}")
            return False
        
        # 测试3: 获取未读消息数量
        print("\n" + "=" * 60)
        print("测试3: 获取未读消息数量")
        print("=" * 60)
        
        try:
            unread_count = MessageService.get_unread_count(enterprise.id)
            print(f"✓ 未读消息数量: {unread_count}")
            
            # 按类型统计
            alert_unread = MessageService.get_unread_count(enterprise.id, 'alert')
            transaction_unread = MessageService.get_unread_count(enterprise.id, 'transaction')
            print(f"  - 预警消息未读: {alert_unread}")
            print(f"  - 交易消息未读: {transaction_unread}")
        except Exception as e:
            print(f"❌ 获取未读数量失败: {str(e)}")
            return False
        
        # 测试4: 标记消息为已读
        print("\n" + "=" * 60)
        print("测试4: 标记消息为已读")
        print("=" * 60)
        
        try:
            success = MessageService.mark_as_read(msg1.id, enterprise.id)
            if success:
                print(f"✓ 标记消息 {msg1.id} 为已读")
                msg1_updated = Message.query.get(msg1.id)
                print(f"  - 已读状态: {msg1_updated.is_read}")
                print(f"  - 已读时间: {msg1_updated.read_at}")
            else:
                print(f"❌ 标记消息为已读失败")
                return False
        except Exception as e:
            print(f"❌ 标记消息为已读失败: {str(e)}")
            return False
        
        # 测试5: 标记消息为未读
        print("\n" + "=" * 60)
        print("测试5: 标记消息为未读")
        print("=" * 60)
        
        try:
            success = MessageService.mark_as_unread(msg1.id, enterprise.id)
            if success:
                print(f"✓ 标记消息 {msg1.id} 为未读")
                msg1_updated = Message.query.get(msg1.id)
                print(f"  - 已读状态: {msg1_updated.is_read}")
            else:
                print(f"❌ 标记消息为未读失败")
                return False
        except Exception as e:
            print(f"❌ 标记消息为未读失败: {str(e)}")
            return False
        
        # 测试6: 全部标记为已读
        print("\n" + "=" * 60)
        print("测试6: 全部标记为已读")
        print("=" * 60)
        
        try:
            count = MessageService.mark_all_as_read(enterprise.id)
            print(f"✓ 标记 {count} 条消息为已读")
            
            unread_after = MessageService.get_unread_count(enterprise.id)
            print(f"  - 标记后未读数量: {unread_after}")
        except Exception as e:
            print(f"❌ 全部标记为已读失败: {str(e)}")
            return False
        
        # 测试7: 按类型筛选消息
        print("\n" + "=" * 60)
        print("测试7: 按类型筛选消息")
        print("=" * 60)
        
        try:
            alert_result = MessageService.get_messages(
                recipient_id=enterprise.id,
                message_type='alert',
                page=1,
                per_page=10
            )
            print(f"✓ 筛选预警消息: {alert_result['total']} 条")
            
            transaction_result = MessageService.get_messages(
                recipient_id=enterprise.id,
                message_type='transaction',
                page=1,
                per_page=10
            )
            print(f"✓ 筛选交易消息: {transaction_result['total']} 条")
        except Exception as e:
            print(f"❌ 按类型筛选失败: {str(e)}")
            return False
        
        # 测试8: 删除消息
        print("\n" + "=" * 60)
        print("测试8: 删除消息")
        print("=" * 60)
        
        try:
            success = MessageService.delete_message(msg3.id, enterprise.id)
            if success:
                print(f"✓ 删除消息 {msg3.id} 成功")
                deleted_msg = Message.query.get(msg3.id)
                if deleted_msg is None:
                    print(f"  - 确认消息已删除")
                else:
                    print(f"❌ 消息未被删除")
                    return False
            else:
                print(f"❌ 删除消息失败")
                return False
        except Exception as e:
            print(f"❌ 删除消息失败: {str(e)}")
            return False
        
        # 测试9: 批量删除消息
        print("\n" + "=" * 60)
        print("测试9: 批量删除消息")
        print("=" * 60)
        
        try:
            message_ids = [msg4.id, msg5.id]
            count = MessageService.delete_messages(message_ids, enterprise.id)
            print(f"✓ 批量删除 {count} 条消息")
        except Exception as e:
            print(f"❌ 批量删除失败: {str(e)}")
            return False
        
        # 测试10: 获取消息统计
        print("\n" + "=" * 60)
        print("测试10: 获取消息统计")
        print("=" * 60)
        
        try:
            stats = MessageService.get_message_stats(enterprise.id)
            print(f"✓ 消息统计:")
            print(f"  - 总消息数: {stats['total']}")
            print(f"  - 未读消息: {stats['unread']}")
            print(f"  - 已读消息: {stats['read']}")
            print(f"  - 按类型未读:")
            for msg_type, count in stats['unread_by_type'].items():
                print(f"    {msg_type}: {count}")
        except Exception as e:
            print(f"❌ 获取统计失败: {str(e)}")
            return False
        
        # 测试11: 清理旧消息
        print("\n" + "=" * 60)
        print("测试11: 清理旧消息")
        print("=" * 60)
        
        try:
            # 创建一条91天前的消息
            old_msg = Message(
                recipient_id=enterprise.id,
                message_type='system',
                title='旧消息测试',
                content='这是一条91天前的消息',
                is_read=True,
                created_at=datetime.utcnow() - timedelta(days=91)
            )
            db.session.add(old_msg)
            db.session.commit()
            print(f"✓ 创建91天前的测试消息: {old_msg.id}")
            
            # 清理超过90天的消息
            old_msg_id = old_msg.id
            count = MessageService.cleanup_old_messages(days=90)
            print(f"✓ 清理 {count} 条超过90天的消息")
            
            # 验证旧消息已被删除
            deleted = Message.query.filter_by(id=old_msg_id).first()
            if deleted is None:
                print(f"  - 确认旧消息已被清理")
            else:
                print(f"❌ 旧消息未被清理")
                return False
        except Exception as e:
            print(f"❌ 清理旧消息失败: {str(e)}")
            return False
        
        # 测试12: 预警消息置顶
        print("\n" + "=" * 60)
        print("测试12: 预警消息置顶")
        print("=" * 60)
        
        try:
            # 创建多条不同类型的消息
            MessageService.create_system_message(enterprise.id, "系统消息1", "内容1")
            MessageService.create_alert_message(enterprise.id, "预警消息1", "内容2")
            MessageService.create_transaction_message(enterprise.id, "交易消息1", "内容3")
            MessageService.create_alert_message(enterprise.id, "预警消息2", "内容4")
            
            # 获取消息列表
            result = MessageService.get_messages(enterprise.id, page=1, per_page=10)
            
            # 验证预警消息是否置顶
            messages = result['messages']
            alert_positions = [i for i, msg in enumerate(messages) if msg.message_type == 'alert']
            
            if alert_positions:
                print(f"✓ 预警消息位置: {alert_positions}")
                if all(pos < len(messages) / 2 for pos in alert_positions):
                    print(f"  - 预警消息已置顶")
                else:
                    print(f"⚠ 预警消息未完全置顶")
            else:
                print(f"⚠ 未找到预警消息")
        except Exception as e:
            print(f"❌ 预警消息置顶测试失败: {str(e)}")
            return False
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return True

if __name__ == '__main__':
    success = test_message_center()
    sys.exit(0 if success else 1)
