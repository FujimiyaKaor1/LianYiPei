"""
消息中心服务
提供统一的消息创建、查询、管理功能
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import or_, and_
from app.models import db, Message, Enterprise


class MessageService:
    """消息服务类"""
    
    # 消息类型常量
    TYPE_TRANSACTION = 'transaction'
    TYPE_ALERT = 'alert'
    TYPE_SYSTEM = 'system'
    TYPE_INQUIRY = 'inquiry'
    TYPE_CREDIT = 'credit'
    
    # 优先级常量
    PRIORITY_HIGH = 'high'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_LOW = 'low'
    
    @staticmethod
    def create_message(
        recipient_id: int,
        message_type: str,
        title: str,
        content: str = None,
        link_url: str = None,
        priority: str = 'normal',
        mode: str = 'procurement',
    ) -> Message:
        """
        创建消息

        Args:
            recipient_id: 接收者企业ID
            message_type: 消息类型 (transaction/alert/system/inquiry/credit)
            title: 消息标题
            content: 消息内容
            link_url: 跳转链接
            priority: 优先级 (high/normal/low)
            mode: 视角模式 (procurement/sales)，采购视角或销售视角

        Returns:
            Message: 创建的消息对象
        """
        message = Message(
            recipient_id=recipient_id,
            message_type=message_type,
            title=title,
            content=content,
            link_url=link_url,
            priority=priority,
            mode=mode,
            is_read=False,
            created_at=datetime.utcnow()
        )
        
        db.session.add(message)
        db.session.commit()
        
        return message
    
    @staticmethod
    def create_transaction_message(recipient_id: int, title: str, content: str, link_url: str = None) -> Message:
        """创建交易消息"""
        return MessageService.create_message(
            recipient_id=recipient_id,
            message_type=MessageService.TYPE_TRANSACTION,
            title=title,
            content=content,
            link_url=link_url,
            priority=MessageService.PRIORITY_NORMAL
        )
    
    @staticmethod
    def create_alert_message(recipient_id: int, title: str, content: str, link_url: str = None) -> Message:
        """创建预警消息（高优先级）"""
        return MessageService.create_message(
            recipient_id=recipient_id,
            message_type=MessageService.TYPE_ALERT,
            title=title,
            content=content,
            link_url=link_url,
            priority=MessageService.PRIORITY_HIGH
        )
    
    @staticmethod
    def create_system_message(recipient_id: int, title: str, content: str, link_url: str = None) -> Message:
        """创建系统消息"""
        return MessageService.create_message(
            recipient_id=recipient_id,
            message_type=MessageService.TYPE_SYSTEM,
            title=title,
            content=content,
            link_url=link_url,
            priority=MessageService.PRIORITY_NORMAL
        )
    
    @staticmethod
    def create_inquiry_message(recipient_id: int, title: str, content: str, link_url: str = None) -> Message:
        """创建询价消息"""
        return MessageService.create_message(
            recipient_id=recipient_id,
            message_type=MessageService.TYPE_INQUIRY,
            title=title,
            content=content,
            link_url=link_url,
            priority=MessageService.PRIORITY_NORMAL
        )
    
    @staticmethod
    def create_credit_message(recipient_id: int, title: str, content: str, link_url: str = None) -> Message:
        """创建信用分变更消息"""
        return MessageService.create_message(
            recipient_id=recipient_id,
            message_type=MessageService.TYPE_CREDIT,
            title=title,
            content=content,
            link_url=link_url,
            priority=MessageService.PRIORITY_NORMAL
        )
    
    @staticmethod
    def get_messages(
        recipient_id: int,
        message_type: str = None,
        is_read: bool = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict:
        """
        获取消息列表（分页）
        
        Args:
            recipient_id: 接收者企业ID
            message_type: 消息类型筛选（可选）
            is_read: 已读状态筛选（可选）
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 包含消息列表和分页信息
        """
        query = Message.query.filter_by(recipient_id=recipient_id)
        
        # 类型筛选
        if message_type:
            query = query.filter_by(message_type=message_type)
        
        # 已读状态筛选
        if is_read is not None:
            query = query.filter_by(is_read=is_read)
        
        # 排序：预警消息置顶，然后按创建时间倒序
        query = query.order_by(
            db.case(
                (Message.message_type == MessageService.TYPE_ALERT, 0),
                else_=1
            ),
            Message.created_at.desc()
        )
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'messages': pagination.items,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    
    @staticmethod
    def get_unread_count(recipient_id: int, message_type: str = None) -> int:
        """
        获取未读消息数量
        
        Args:
            recipient_id: 接收者企业ID
            message_type: 消息类型筛选（可选）
            
        Returns:
            int: 未读消息数量
        """
        query = Message.query.filter_by(
            recipient_id=recipient_id,
            is_read=False
        )
        
        if message_type:
            query = query.filter_by(message_type=message_type)
        
        return query.count()
    
    @staticmethod
    def mark_as_read(message_id: int, recipient_id: int) -> bool:
        """
        标记消息为已读
        
        Args:
            message_id: 消息ID
            recipient_id: 接收者企业ID（用于验证权限）
            
        Returns:
            bool: 是否成功
        """
        message = Message.query.filter_by(
            id=message_id,
            recipient_id=recipient_id
        ).first()
        
        if not message:
            return False
        
        if not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.session.commit()
        
        return True
    
    @staticmethod
    def mark_as_unread(message_id: int, recipient_id: int) -> bool:
        """
        标记消息为未读
        
        Args:
            message_id: 消息ID
            recipient_id: 接收者企业ID（用于验证权限）
            
        Returns:
            bool: 是否成功
        """
        message = Message.query.filter_by(
            id=message_id,
            recipient_id=recipient_id
        ).first()
        
        if not message:
            return False
        
        if message.is_read:
            message.is_read = False
            message.read_at = None
            db.session.commit()
        
        return True
    
    @staticmethod
    def mark_all_as_read(recipient_id: int, message_type: str = None) -> int:
        """
        标记所有消息为已读
        
        Args:
            recipient_id: 接收者企业ID
            message_type: 消息类型筛选（可选）
            
        Returns:
            int: 标记的消息数量
        """
        query = Message.query.filter_by(
            recipient_id=recipient_id,
            is_read=False
        )
        
        if message_type:
            query = query.filter_by(message_type=message_type)
        
        count = query.update({
            'is_read': True,
            'read_at': datetime.utcnow()
        })
        
        db.session.commit()
        return count
    
    @staticmethod
    def delete_message(message_id: int, recipient_id: int) -> bool:
        """
        删除消息
        
        Args:
            message_id: 消息ID
            recipient_id: 接收者企业ID（用于验证权限）
            
        Returns:
            bool: 是否成功
        """
        message = Message.query.filter_by(
            id=message_id,
            recipient_id=recipient_id
        ).first()
        
        if not message:
            return False
        
        db.session.delete(message)
        db.session.commit()
        return True
    
    @staticmethod
    def delete_messages(message_ids: List[int], recipient_id: int) -> int:
        """
        批量删除消息
        
        Args:
            message_ids: 消息ID列表
            recipient_id: 接收者企业ID（用于验证权限）
            
        Returns:
            int: 删除的消息数量
        """
        count = Message.query.filter(
            Message.id.in_(message_ids),
            Message.recipient_id == recipient_id
        ).delete(synchronize_session=False)
        
        db.session.commit()
        return count
    
    @staticmethod
    def cleanup_old_messages(days: int = 90) -> int:
        """
        清理超过指定天数的消息
        
        Args:
            days: 保留天数（默认90天）
            
        Returns:
            int: 删除的消息数量
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        count = Message.query.filter(
            Message.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.session.commit()
        return count
    
    @staticmethod
    def get_message_stats(recipient_id: int) -> Dict:
        """
        获取消息统计信息
        
        Args:
            recipient_id: 接收者企业ID
            
        Returns:
            Dict: 统计信息
        """
        total = Message.query.filter_by(recipient_id=recipient_id).count()
        unread = Message.query.filter_by(recipient_id=recipient_id, is_read=False).count()
        
        # 按类型统计未读数量
        type_counts = {}
        for msg_type in [
            MessageService.TYPE_TRANSACTION,
            MessageService.TYPE_ALERT,
            MessageService.TYPE_SYSTEM,
            MessageService.TYPE_INQUIRY,
            MessageService.TYPE_CREDIT
        ]:
            count = Message.query.filter_by(
                recipient_id=recipient_id,
                message_type=msg_type,
                is_read=False
            ).count()
            type_counts[msg_type] = count
        
        return {
            'total': total,
            'unread': unread,
            'read': total - unread,
            'unread_by_type': type_counts
        }
