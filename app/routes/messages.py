"""
消息中心路由
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.services.message_service import MessageService
from app.models import Message

bp = Blueprint('messages', __name__, url_prefix='/messages')


@bp.route('/')
@login_required
def index():
    """消息中心首页"""
    # 获取筛选参数
    message_type = request.args.get('type', '')
    is_read = request.args.get('read', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # 处理已读状态筛选
    read_filter = None
    if is_read == 'true':
        read_filter = True
    elif is_read == 'false':
        read_filter = False
    
    # 获取消息列表
    result = MessageService.get_messages(
        recipient_id=current_user.id,
        message_type=message_type if message_type else None,
        is_read=read_filter,
        page=page,
        per_page=per_page
    )
    
    # 获取统计信息
    stats = MessageService.get_message_stats(current_user.id)
    
    return render_template(
        'messages/index.html',
        messages=result['messages'],
        pagination={
            'page': result['page'],
            'pages': result['pages'],
            'total': result['total'],
            'has_next': result['has_next'],
            'has_prev': result['has_prev']
        },
        stats=stats,
        current_type=message_type,
        current_read=is_read
    )


@bp.route('/api/unread-count')
@login_required
def get_unread_count():
    """获取未读消息数量（API）"""
    message_type = request.args.get('type')
    
    count = MessageService.get_unread_count(
        recipient_id=current_user.id,
        message_type=message_type
    )
    
    return jsonify({
        'success': True,
        'count': count
    })


@bp.route('/api/stats')
@login_required
def get_stats():
    """获取消息统计信息（API）"""
    stats = MessageService.get_message_stats(current_user.id)
    
    return jsonify({
        'success': True,
        'stats': stats
    })


@bp.route('/<int:message_id>')
@login_required
def detail(message_id):
    """消息详情"""
    message = Message.query.filter_by(
        id=message_id,
        recipient_id=current_user.id
    ).first_or_404()
    
    # 自动标记为已读
    if not message.is_read:
        MessageService.mark_as_read(message_id, current_user.id)
    
    return render_template('messages/detail.html', message=message)


@bp.route('/<int:message_id>/mark-read', methods=['POST'])
@login_required
def mark_read(message_id):
    """标记消息为已读"""
    success = MessageService.mark_as_read(message_id, current_user.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': '已标记为已读' if success else '操作失败'
        })
    
    if success:
        flash('已标记为已读', 'success')
    else:
        flash('操作失败', 'error')
    
    return redirect(request.referrer or url_for('messages.index'))


@bp.route('/<int:message_id>/mark-unread', methods=['POST'])
@login_required
def mark_unread(message_id):
    """标记消息为未读"""
    success = MessageService.mark_as_unread(message_id, current_user.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': '已标记为未读' if success else '操作失败'
        })
    
    if success:
        flash('已标记为未读', 'success')
    else:
        flash('操作失败', 'error')
    
    return redirect(request.referrer or url_for('messages.index'))


@bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """标记所有消息为已读"""
    message_type = request.form.get('type')
    
    count = MessageService.mark_all_as_read(
        recipient_id=current_user.id,
        message_type=message_type if message_type else None
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'count': count,
            'message': f'已标记 {count} 条消息为已读'
        })
    
    flash(f'已标记 {count} 条消息为已读', 'success')
    return redirect(url_for('messages.index'))


@bp.route('/<int:message_id>/delete', methods=['POST'])
@login_required
def delete(message_id):
    """删除消息"""
    success = MessageService.delete_message(message_id, current_user.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': success,
            'message': '删除成功' if success else '删除失败'
        })
    
    if success:
        flash('删除成功', 'success')
    else:
        flash('删除失败', 'error')
    
    return redirect(url_for('messages.index'))


@bp.route('/delete-batch', methods=['POST'])
@login_required
def delete_batch():
    """批量删除消息"""
    message_ids = request.form.getlist('message_ids[]', type=int)
    
    if not message_ids:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': '请选择要删除的消息'
            })
        flash('请选择要删除的消息', 'error')
        return redirect(url_for('messages.index'))
    
    count = MessageService.delete_messages(message_ids, current_user.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'count': count,
            'message': f'已删除 {count} 条消息'
        })
    
    flash(f'已删除 {count} 条消息', 'success')
    return redirect(url_for('messages.index'))
