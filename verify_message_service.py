"""
验证消息创建服务实现
测试统一的消息创建接口
"""
import sys
from datetime import datetime
from app import create_app, db
from app.models import Enterprise, Message
from app.services.message_service import MessageService


def test_message_creation_service():
    """测试消息创建服务的所有功能"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("测试消息创建服务")
        print("=" * 60)
        
        # 清理测试数据
        Message.query.delete()
        db.session.commit()
        
        # 获取或创建测试企业
        enterprise = Enterprise.query.first()
        if not enterprise:
            enterprise = Enterprise(
                name="测试企业",
                contact_person="张三",
                phone="13800138000",
                email="test@example.com",
                address="测试地址",
                business_scope="测试业务",
                credit_score=75.0
            )
            db.session.add(enterprise)
            db.session.commit()
        
        print(f"\n使用测试企业: {enterprise.name} (ID: {enterprise.id})")
        
        # 测试1: 统一消息创建接口
        print("\n" + "=" * 60)
        print("测试1: 统一消息创建接口")
        print("=" * 60)
        
        try:
            # 使用统一接口创建消息
            msg = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='transaction',
                title="测试统一接口",
                content="这是通过统一接口创建的消息",
                link_url="/test/link",
                priority='normal'
            )
            
            print(f"✓ 成功创建消息 ID: {msg.id}")
            print(f"  - 类型: {msg.message_type}")
            print(f"  - 标题: {msg.title}")
            print(f"  - 内容: {msg.content}")
            print(f"  - 链接: {msg.link_url}")
            print(f"  - 优先级: {msg.priority}")
            print(f"  - 已读状态: {msg.is_read}")
            
            assert msg.recipient_id == enterprise.id
            assert msg.message_type == 'transaction'
            assert msg.title == "测试统一接口"
            assert msg.content == "这是通过统一接口创建的消息"
            assert msg.link_url == "/test/link"
            assert msg.priority == 'normal'
            assert msg.is_read == False
            
            print("✓ 统一接口验证通过")
            
        except Exception as e:
            print(f"✗ 统一接口测试失败: {str(e)}")
            return False
        
        # 测试2: 不同消息类型
        print("\n" + "=" * 60)
        print("测试2: 支持不同消息类型")
        print("=" * 60)
        
        try:
            # 交易消息
            msg_transaction = MessageService.create_transaction_message(
                recipient_id=enterprise.id,
                title="新报价通知",
                content="您收到一条新报价",
                link_url="/quotes/123"
            )
            print(f"✓ 创建交易消息: {msg_transaction.message_type}")
            assert msg_transaction.message_type == MessageService.TYPE_TRANSACTION
            
            # 预警消息
            msg_alert = MessageService.create_alert_message(
                recipient_id=enterprise.id,
                title="产能风险预警",
                content="您的产能利用率过低",
                link_url="/alerts/456"
            )
            print(f"✓ 创建预警消息: {msg_alert.message_type}")
            assert msg_alert.message_type == MessageService.TYPE_ALERT
            assert msg_alert.priority == MessageService.PRIORITY_HIGH  # 预警消息应该是高优先级
            
            # 系统消息
            msg_system = MessageService.create_system_message(
                recipient_id=enterprise.id,
                title="系统维护通知",
                content="系统将于今晚维护",
                link_url="/system/notice"
            )
            print(f"✓ 创建系统消息: {msg_system.message_type}")
            assert msg_system.message_type == MessageService.TYPE_SYSTEM
            
            # 询价消息
            msg_inquiry = MessageService.create_inquiry_message(
                recipient_id=enterprise.id,
                title="新询价单匹配",
                content="有新的询价单匹配您的产品",
                link_url="/inquiries/789"
            )
            print(f"✓ 创建询价消息: {msg_inquiry.message_type}")
            assert msg_inquiry.message_type == MessageService.TYPE_INQUIRY
            
            # 信用分消息
            msg_credit = MessageService.create_credit_message(
                recipient_id=enterprise.id,
                title="信用分变更通知",
                content="您的信用分增加了10分",
                link_url="/credit/history"
            )
            print(f"✓ 创建信用分消息: {msg_credit.message_type}")
            assert msg_credit.message_type == MessageService.TYPE_CREDIT
            
            print("\n✓ 所有消息类型创建成功")
            print(f"  - 交易消息: {MessageService.TYPE_TRANSACTION}")
            print(f"  - 预警消息: {MessageService.TYPE_ALERT}")
            print(f"  - 系统消息: {MessageService.TYPE_SYSTEM}")
            print(f"  - 询价消息: {MessageService.TYPE_INQUIRY}")
            print(f"  - 信用分消息: {MessageService.TYPE_CREDIT}")
            
        except Exception as e:
            print(f"✗ 消息类型测试失败: {str(e)}")
            return False
        
        # 测试3: 消息优先级
        print("\n" + "=" * 60)
        print("测试3: 支持设置消息优先级")
        print("=" * 60)
        
        try:
            # 高优先级
            msg_high = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='system',
                title="紧急通知",
                content="紧急系统通知",
                priority=MessageService.PRIORITY_HIGH
            )
            print(f"✓ 创建高优先级消息: {msg_high.priority}")
            assert msg_high.priority == 'high'
            
            # 普通优先级
            msg_normal = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='system',
                title="普通通知",
                content="普通系统通知",
                priority=MessageService.PRIORITY_NORMAL
            )
            print(f"✓ 创建普通优先级消息: {msg_normal.priority}")
            assert msg_normal.priority == 'normal'
            
            # 低优先级
            msg_low = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='system',
                title="提示信息",
                content="低优先级提示",
                priority=MessageService.PRIORITY_LOW
            )
            print(f"✓ 创建低优先级消息: {msg_low.priority}")
            assert msg_low.priority == 'low'
            
            print("\n✓ 所有优先级设置成功")
            print(f"  - 高优先级: {MessageService.PRIORITY_HIGH}")
            print(f"  - 普通优先级: {MessageService.PRIORITY_NORMAL}")
            print(f"  - 低优先级: {MessageService.PRIORITY_LOW}")
            
        except Exception as e:
            print(f"✗ 优先级测试失败: {str(e)}")
            return False
        
        # 测试4: 跳转链接
        print("\n" + "=" * 60)
        print("测试4: 支持添加跳转链接")
        print("=" * 60)
        
        try:
            # 带链接的消息
            msg_with_link = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='transaction',
                title="查看详情",
                content="点击查看详细信息",
                link_url="/details/123"
            )
            print(f"✓ 创建带链接的消息")
            print(f"  - 链接: {msg_with_link.link_url}")
            assert msg_with_link.link_url == "/details/123"
            
            # 不带链接的消息
            msg_without_link = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='system',
                title="纯文本通知",
                content="这是一条纯文本通知"
            )
            print(f"✓ 创建不带链接的消息")
            print(f"  - 链接: {msg_without_link.link_url}")
            assert msg_without_link.link_url is None
            
            print("\n✓ 跳转链接功能验证通过")
            
        except Exception as e:
            print(f"✗ 跳转链接测试失败: {str(e)}")
            return False
        
        # 测试5: 消息查询和统计
        print("\n" + "=" * 60)
        print("测试5: 消息查询和统计功能")
        print("=" * 60)
        
        try:
            # 获取消息统计
            stats = MessageService.get_message_stats(enterprise.id)
            print(f"✓ 消息统计:")
            print(f"  - 总消息数: {stats['total']}")
            print(f"  - 未读消息数: {stats['unread']}")
            print(f"  - 已读消息数: {stats['read']}")
            print(f"  - 按类型未读数:")
            for msg_type, count in stats['unread_by_type'].items():
                print(f"    * {msg_type}: {count}")
            
            # 获取消息列表
            result = MessageService.get_messages(enterprise.id, page=1, per_page=10)
            print(f"\n✓ 消息列表查询:")
            print(f"  - 总数: {result['total']}")
            print(f"  - 当前页: {result['page']}")
            print(f"  - 每页数量: {result['per_page']}")
            print(f"  - 总页数: {result['pages']}")
            
            # 按类型筛选
            alert_result = MessageService.get_messages(
                enterprise.id,
                message_type=MessageService.TYPE_ALERT,
                page=1,
                per_page=10
            )
            print(f"\n✓ 预警消息筛选:")
            print(f"  - 预警消息数: {alert_result['total']}")
            
            print("\n✓ 查询和统计功能验证通过")
            
        except Exception as e:
            print(f"✗ 查询统计测试失败: {str(e)}")
            return False
        
        # 测试6: 消息管理功能
        print("\n" + "=" * 60)
        print("测试6: 消息管理功能")
        print("=" * 60)
        
        try:
            # 创建测试消息
            test_msg = MessageService.create_message(
                recipient_id=enterprise.id,
                message_type='system',
                title="测试管理功能",
                content="用于测试管理功能的消息"
            )
            
            # 标记为已读
            success = MessageService.mark_as_read(test_msg.id, enterprise.id)
            print(f"✓ 标记为已读: {success}")
            assert success == True
            
            # 验证已读状态
            db.session.refresh(test_msg)
            assert test_msg.is_read == True
            assert test_msg.read_at is not None
            print(f"  - 已读状态: {test_msg.is_read}")
            print(f"  - 已读时间: {test_msg.read_at}")
            
            # 标记为未读
            success = MessageService.mark_as_unread(test_msg.id, enterprise.id)
            print(f"✓ 标记为未读: {success}")
            assert success == True
            
            # 删除消息
            success = MessageService.delete_message(test_msg.id, enterprise.id)
            print(f"✓ 删除消息: {success}")
            assert success == True
            
            print("\n✓ 消息管理功能验证通过")
            
        except Exception as e:
            print(f"✗ 消息管理测试失败: {str(e)}")
            return False
        
        # 测试7: 批量操作
        print("\n" + "=" * 60)
        print("测试7: 批量操作功能")
        print("=" * 60)
        
        try:
            # 创建多条测试消息
            msg_ids = []
            for i in range(5):
                msg = MessageService.create_message(
                    recipient_id=enterprise.id,
                    message_type='system',
                    title=f"批量测试消息 {i+1}",
                    content=f"内容 {i+1}"
                )
                msg_ids.append(msg.id)
            
            print(f"✓ 创建了 {len(msg_ids)} 条测试消息")
            
            # 批量标记为已读
            count = MessageService.mark_all_as_read(enterprise.id, message_type='system')
            print(f"✓ 批量标记为已读: {count} 条")
            
            # 批量删除
            count = MessageService.delete_messages(msg_ids, enterprise.id)
            print(f"✓ 批量删除: {count} 条")
            
            print("\n✓ 批量操作功能验证通过")
            
        except Exception as e:
            print(f"✗ 批量操作测试失败: {str(e)}")
            return False
        
        # 最终统计
        print("\n" + "=" * 60)
        print("最终统计")
        print("=" * 60)
        
        final_stats = MessageService.get_message_stats(enterprise.id)
        print(f"总消息数: {final_stats['total']}")
        print(f"未读消息数: {final_stats['unread']}")
        print(f"已读消息数: {final_stats['read']}")
        
        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        print("\n消息创建服务功能验证:")
        print("✓ 统一的消息创建接口")
        print("✓ 支持不同消息类型 (transaction/alert/system/inquiry/credit)")
        print("✓ 支持设置消息优先级 (high/normal/low)")
        print("✓ 支持添加跳转链接")
        print("✓ 消息查询和统计")
        print("✓ 消息管理功能")
        print("✓ 批量操作功能")
        
        return True


if __name__ == '__main__':
    success = test_message_creation_service()
    sys.exit(0 if success else 1)
