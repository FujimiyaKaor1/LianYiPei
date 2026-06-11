"""
SaaS订单管理工具路由
提供订单创建、查看、更新、删除和导出功能
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from datetime import datetime, date
from app.services.order_service import OrderService
from app.errors import _error_response as error_response
import io
import csv


def _date_to_str(value):
    """兼容 date/datetime/ISO 字符串，统一输出 YYYY-MM-DD 或 None。"""
    if not value:
        return None
    if hasattr(value, 'strftime'):
        try:
            return value.strftime('%Y-%m-%d')
        except Exception:
            pass
    text = str(value).strip()
    if not text:
        return None
    return text[:10]


def _estimate_progress(order_date, delivery_date, status):
    """给前端提供稳定进度值，避免各端重复推导。"""
    if status == 'completed':
        return 100
    if status != 'in_progress':
        return 0
    try:
        if not order_date or not delivery_date:
            return 50
        start = datetime.strptime(str(order_date)[:10], '%Y-%m-%d').date()
        end = datetime.strptime(str(delivery_date)[:10], '%Y-%m-%d').date()
        today = date.today()
        total_days = (end - start).days
        if total_days <= 0:
            return 50
        elapsed = (today - start).days
        progress = int(round((elapsed / total_days) * 100))
        return max(5, min(95, progress))
    except Exception:
        return 50

bp = Blueprint('orders', __name__, url_prefix='/orders')


@bp.route('', strict_slashes=False)
@bp.route('/', strict_slashes=False)
@login_required
def index():
    """React 订单工作流入口，避免直达 /orders 时落回旧 Bootstrap 页面。"""
    from app.routes.main import _render_spa

    return _render_spa('订单工作流 - 链易配')


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """创建订单"""
    if request.method == 'POST':
        try:
            product_name = request.form.get('product_name')
            quantity = request.form.get('quantity', type=int)
            unit = request.form.get('unit')
            customer_name = request.form.get('customer_name')
            order_date_str = request.form.get('order_date')
            delivery_date_str = request.form.get('delivery_date')
            notes = request.form.get('notes', '')
            
            # 验证必填字段
            if not all([product_name, quantity, unit, customer_name, order_date_str]):
                flash('请填写所有必填字段', 'error')
                return redirect(url_for('orders.create'))
            
            # 转换日期
            order_date = datetime.strptime(order_date_str, '%Y-%m-%d').date()
            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date() if delivery_date_str else None
            
            # 创建订单
            order = OrderService.create_order(
                enterprise_id=current_user.id,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                customer_name=customer_name,
                order_date=order_date,
                delivery_date=delivery_date,
                notes=notes
            )
            
            flash(f'订单 {order.order_no} 创建成功', 'success')
            return redirect(url_for('orders.detail', order_id=order.id))
            
        except Exception as e:
            flash(f'创建订单失败: {str(e)}', 'error')
            return redirect(url_for('orders.create'))
    
    return render_template('orders/create.html')


@bp.route('/<int:order_id>')
@login_required
def detail(order_id):
    """订单详情"""
    order = OrderService.get_order_by_id(order_id)
    
    # 验证权限
    if order.enterprise_id != current_user.id and not current_user.is_admin:
        flash('无权访问此订单', 'error')
        return redirect(url_for('orders.index'))
    
    return render_template('orders/detail.html', order=order)


@bp.route('/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(order_id):
    """编辑订单"""
    order = OrderService.get_order_by_id(order_id)
    
    # 验证权限
    if order.enterprise_id != current_user.id:
        flash('无权编辑此订单', 'error')
        return redirect(url_for('orders.index'))
    
    if request.method == 'POST':
        try:
            # 获取表单数据
            product_name = request.form.get('product_name')
            quantity = request.form.get('quantity', type=int)
            unit = request.form.get('unit')
            customer_name = request.form.get('customer_name')
            order_date_str = request.form.get('order_date')
            delivery_date_str = request.form.get('delivery_date')
            notes = request.form.get('notes', '')
            
            # 转换日期
            order_date = datetime.strptime(order_date_str, '%Y-%m-%d').date()
            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date() if delivery_date_str else None
            
            # 更新订单
            OrderService.update_order(
                order_id=order_id,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                customer_name=customer_name,
                order_date=order_date,
                delivery_date=delivery_date,
                notes=notes
            )
            
            flash('订单更新成功', 'success')
            return redirect(url_for('orders.detail', order_id=order_id))
            
        except Exception as e:
            flash(f'更新订单失败: {str(e)}', 'error')
    
    return render_template('orders/edit.html', order=order)


@bp.route('/<int:order_id>/update-status', methods=['POST'])
@login_required
def update_status(order_id):
    """更新订单状态"""
    order = OrderService.get_order_by_id(order_id)
    
    # 验证权限
    if order.enterprise_id != current_user.id:
        return jsonify({'success': False, 'message': '无权操作此订单'}), 403
    
    try:
        status = request.json.get('status')
        actual_delivery_date_str = request.json.get('actual_delivery_date')
        
        actual_delivery_date = None
        if actual_delivery_date_str:
            actual_delivery_date = datetime.strptime(actual_delivery_date_str, '%Y-%m-%d').date()
        
        OrderService.update_order_status(
            order_id=order_id,
            status=status,
            actual_delivery_date=actual_delivery_date
        )
        
        return jsonify({'success': True, 'message': '状态更新成功'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/<int:order_id>/delete', methods=['POST'])
@login_required
def delete(order_id):
    """删除订单"""
    order = OrderService.get_order_by_id(order_id)
    
    # 验证权限
    if order.enterprise_id != current_user.id:
        return jsonify({'success': False, 'message': '无权删除此订单'}), 403
    
    try:
        OrderService.delete_order(order_id)
        return jsonify({'success': True, 'message': '订单删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/export')
@login_required
def export():
    """导出订单数据为CSV"""
    status = request.args.get('status', '')
    start_date_str = request.args.get('start_date', '')
    end_date_str = request.args.get('end_date', '')
    
    # 转换日期
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
    
    # 获取订单数据
    data = OrderService.export_orders_data(
        enterprise_id=current_user.id,
        status=status if status else None,
        start_date=start_date,
        end_date=end_date
    )
    
    # 创建CSV文件
    output = io.StringIO()
    if data:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    # 转换为字节流
    output.seek(0)
    bytes_output = io.BytesIO()
    bytes_output.write(output.getvalue().encode('utf-8-sig'))  # 使用utf-8-sig以支持Excel打开
    bytes_output.seek(0)
    
    # 生成文件名
    filename = f'orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return send_file(
        bytes_output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


# API接口
@bp.route('/api/orders', methods=['GET'])
@login_required
def api_get_orders():
    """获取订单列表API"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    result = OrderService.get_orders(
        enterprise_id=current_user.id,
        status=status if status else None,
        page=page,
        per_page=20
    )
    
    orders_data = []
    for order in result['orders']:
        order_date = _date_to_str(order.order_date)
        delivery_date = _date_to_str(order.delivery_date)
        actual_delivery_date = _date_to_str(order.actual_delivery_date)
        orders_data.append({
            'id': order.id,
            'order_no': order.order_no,
            'product_name': order.product_name,
            'quantity': order.quantity,
            'unit': order.unit,
            'customer_name': order.customer_name,
            'order_date': order_date,
            'delivery_date': delivery_date,
            'actual_delivery_date': actual_delivery_date,
            'status': order.status,
            'notes': order.notes,
            'progress': _estimate_progress(order_date, delivery_date, order.status),
        })
    
    return jsonify({
        'success': True,
        'orders': orders_data,
        'total': result['total'],
        'page': result['page'],
        'pages': result['pages']
    })


@bp.route('/api/statistics', methods=['GET'])
@login_required
def api_statistics():
    """获取订单统计API"""
    stats = OrderService.get_order_statistics(current_user.id)
    return jsonify({'success': True, 'statistics': stats})



@bp.route('/capacity-calendar')
@login_required
def capacity_calendar():
    """产能日历页面"""
    from datetime import datetime
    
    # 获取年月参数
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    # 获取产能日历数据
    calendar_data = OrderService.get_capacity_calendar(
        enterprise_id=current_user.id,
        year=year,
        month=month
    )
    
    return render_template('orders/capacity_calendar.html',
                         calendar_data=calendar_data,
                         year=year,
                         month=month)


@bp.route('/api/capacity-calendar/<int:year>/<int:month>')
@login_required
def api_capacity_calendar(year, month):
    """获取产能日历数据API"""
    calendar_data = OrderService.get_capacity_calendar(
        enterprise_id=current_user.id,
        year=year,
        month=month
    )
    
    return jsonify({'success': True, 'data': calendar_data})


@bp.route('/api/orders-by-date/<date_str>')
@login_required
def api_orders_by_date(date_str):
    """获取指定日期的订单列表API"""
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        orders = OrderService.get_orders_by_date(current_user.id, target_date)
        
        orders_data = []
        for order in orders:
            orders_data.append({
                'id': order.id,
                'order_no': order.order_no,
                'product_name': order.product_name,
                'quantity': order.quantity,
                'unit': order.unit,
                'customer_name': order.customer_name,
                'status': order.status,
                'order_date': order.order_date.strftime('%Y-%m-%d') if order.order_date else None,
                'delivery_date': order.delivery_date.strftime('%Y-%m-%d') if order.delivery_date else None
            })
        
        return jsonify({'success': True, 'orders': orders_data})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400


@bp.route('/capacity-calendar/<int:enterprise_id>')
@login_required
def view_calendar(enterprise_id):
    """查看其他企业的产能日历"""
    from datetime import datetime
    
    # 检查权限
    if not OrderService.can_view_calendar(current_user.id, enterprise_id):
        flash('您没有权限查看该企业的产能日历', 'error')
        return redirect(url_for('dashboard.main'))
    
    # 获取年月参数
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    
    # 获取产能日历数据
    calendar_data = OrderService.get_capacity_calendar(
        enterprise_id=enterprise_id,
        year=year,
        month=month
    )
    
    # 获取企业信息
    from app.models import Enterprise
    enterprise = Enterprise.query.get_or_404(enterprise_id)
    
    return render_template('orders/capacity_calendar.html',
                         calendar_data=calendar_data,
                         year=year,
                         month=month,
                         enterprise=enterprise,
                         is_owner=(current_user.id == enterprise_id))


@bp.route('/settings/calendar-visibility', methods=['GET', 'POST'])
@login_required
def calendar_visibility_settings():
    """产能日历公开范围设置"""
    if request.method == 'POST':
        try:
            visibility = request.form.get('visibility')
            OrderService.update_calendar_visibility(current_user.id, visibility)
            flash('产能日历公开范围设置成功', 'success')
            return redirect(url_for('orders.capacity_calendar'))
        except Exception as e:
            flash(f'设置失败: {str(e)}', 'error')
    
    return render_template('orders/calendar_settings.html',
                         current_visibility=current_user.capacity_calendar_visibility)


@bp.route('/api/calendar-visibility', methods=['POST'])
@login_required
def api_update_calendar_visibility():
    """更新产能日历公开范围API"""
    try:
        visibility = request.json.get('visibility')
        OrderService.update_calendar_visibility(current_user.id, visibility)
        return jsonify({'success': True, 'message': '设置成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
