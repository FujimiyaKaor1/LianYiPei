"""
合作闭环路由：撮合码、履约数据、消息中心、报价池
"""
import logging
from typing import Optional, Tuple

from flask import Blueprint, jsonify, request, render_template
from flask_login import current_user, login_required
from app.authz import role_required
from app.errors import (
    APIError,
    ERR_MISSING_PARAM, ERR_INVALID_PARAM, ERR_FORBIDDEN,
    ERR_QUOTE_LIMIT, ERR_QUOTE_PRICE_INVALID, ERR_INQUIRY_NOT_FOUND,
    ERR_MESSAGE_NOT_FOUND, ERR_MESSAGE_FORBIDDEN,
    ERR_CODE_NOT_FOUND, ERR_CODE_API_KEY_INVALID,
)
from app.models import Message, Quote, Enterprise, Inquiry, Transaction
from app import db
from app.services.collaboration_service import (
    generate_collaboration_code,
    verify_collaboration_code,
    record_fulfillment,
    send_message,
    get_unread_count,
    mark_messages_read,
    collaboration_code_manager,
)
from app.services.quote_pool import add_quote, get_price_index, get_quotes_for_inquiry
from app.services.credit_engine import update_credit_score
from app.services.invoice_validator import validate_invoice, store_fulfillment_data

collab_bp = Blueprint('collab', __name__)
logger = logging.getLogger(__name__)

_INVOICE_ALLOWED_EXT = {'pdf', 'jpg', 'jpeg', 'png'}
# 部分客户端对 JPEG 使用非标准 type
_MIME_TO_EXT = {
    'application/pdf': 'pdf',
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/pjpeg': 'jpg',
    'image/png': 'png',
    'image/x-png': 'png',
}


def _parse_quality_rating(raw: object, default: int = 5) -> int:
    if raw is None or raw == '':
        return default
    try:
        return int(raw)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return default


def _invoice_upload_file_ext_and_disk_name(file_storage, user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """
    从原始文件名与 Content-Type 解析扩展名，并生成安全的磁盘文件名。
    不能先用 secure_filename 再取后缀：中文文件名常被清空，导致误判「格式不支持」。
    """
    import time
    from werkzeug.utils import secure_filename

    raw = (file_storage.filename or '').strip()
    ext = ''
    if '.' in raw:
        ext = raw.rsplit('.', 1)[1].lower()

    if ext not in _INVOICE_ALLOWED_EXT:
        ext = ''

    ct = (file_storage.content_type or '').split(';')[0].strip().lower()
    if ext not in _INVOICE_ALLOWED_EXT and ct in _MIME_TO_EXT:
        ext = _MIME_TO_EXT[ct]

    if ext == 'jpeg':
        ext = 'jpg'

    if ext not in {'pdf', 'jpg', 'png'}:
        return None, None

    base = secure_filename(raw) if raw else ''
    ext_ok = (
        base
        and '.' in base
        and base.rsplit('.', 1)[1].lower() in _INVOICE_ALLOWED_EXT
    )
    if not ext_ok:
        base = f'invoice_{user_id}_{int(time.time())}.{ext}'
    disk_name = f'{user_id}_{int(time.time())}_{base}'
    return ext, disk_name


# ── 撮合码 ────────────────────────────────────────────────────────────────

@collab_bp.route('/api/collaboration-code/generate', methods=['POST'])
@role_required('enterprise')
def generate_code():
    """生成撮合码（合同签署后调用）。"""
    data = request.get_json() or {}
    seller_id = data.get('seller_id')
    product_name = data.get('product_name', '')
    amount_range = data.get('amount_range', '')

    if not seller_id:
        return jsonify({'error': '缺少 seller_id'}), 400

    cc = generate_collaboration_code(
        buyer_id=current_user.id,
        seller_id=int(seller_id),
        product_name=product_name,
        amount_range=amount_range,
    )
    return jsonify({
        'code': cc.match_code,
        'created_at': cc.created_at.isoformat(),
    })


@collab_bp.route('/api/collaboration-code/verify', methods=['POST'])
def verify_code():
    """验证撮合码（供外部系统/银行调用）。需要 X-API-Key 请求头。"""
    data = request.get_json() or {}
    code = (data.get('code') or '').strip()
    api_key_value = request.headers.get('X-API-Key', '')

    if not code:
        return jsonify({'error': '缺少撮合码'}), 400
    if not api_key_value:
        collaboration_code_manager.log_verification(
            code=code, caller_api_key='', caller_name='',
            ip_address=request.remote_addr, result='unauthorized',
        )
        return jsonify({'error': '缺少 X-API-Key 请求头'}), 401

    payload, err = verify_collaboration_code(code, api_key_value, request.remote_addr or '')
    if err:
        collaboration_code_manager.log_verification(
            code=code, caller_api_key=api_key_value, caller_name='',
            ip_address=request.remote_addr, result='unauthorized' if '密钥' in err else 'not_found',
        )
        status = 401 if '密钥' in err else 404
        return jsonify({'error': err}), status

    collaboration_code_manager.log_verification(
        code=code, caller_api_key=api_key_value, caller_name='external',
        ip_address=request.remote_addr, result='success',
    )
    return jsonify(payload)


@collab_bp.route('/api/collaboration-code/<string:code>', methods=['GET'])
@role_required('enterprise')
def get_code_detail(code: str):
    """获取撮合码详情（内部使用，返回完整未脱敏信息）。"""
    details = collaboration_code_manager.get_code_details(code)
    if not details:
        return jsonify({'error': '撮合码不存在'}), 404

    # 只有买卖双方或管理员可查看
    if current_user.id not in (details['buyer_id'], details['seller_id']) and current_user.role != 'admin':
        return jsonify({'error': '无权限'}), 403

    return jsonify(details)


# ── 履约数据 ──────────────────────────────────────────────────────────────

@collab_bp.route('/invoice/upload', methods=['GET'])
@role_required('enterprise')
def invoice_upload_page():
    """发票上传页面"""
    return render_template('invoice/upload.html')


@collab_bp.route('/api/invoice/upload', methods=['POST'])
@role_required('enterprise')
def upload_invoice():
    """
    上传发票并验证
    支持PDF、JPG、PNG格式，最大16MB
    
    流程:
    1. 验证文件类型和大小
    2. 保存文件到服务器
    3. 调用发票验证服务
    4. 存储履约数据
    5. 更新信用分
    
    返回:
    {
        'success': bool,
        'message': str,
        'invoice_info': dict,  # 验证成功时
        'error': str,  # 验证失败时
        'manual_review_required': bool  # 是否需要人工审核
    }
    """
    import os

    # 1. 检查是否有文件
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '未上传文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400

    seller_id_raw = (request.form.get('seller_id') or '').strip()
    if not seller_id_raw:
        return jsonify({'success': False, 'error': '缺少卖方企业ID（seller_id）'}), 400
    try:
        seller_id_int = int(seller_id_raw)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': '卖方企业ID格式不正确'}), 400

    # 2. 验证文件类型（扩展名优先，其次 Content-Type；兼容中文文件名）
    file_ext, unique_filename = _invoice_upload_file_ext_and_disk_name(file, current_user.id)
    if not file_ext or not unique_filename:
        return jsonify({
            'success': False,
            'error': f'不支持的文件格式，仅支持: {", ".join(sorted(_INVOICE_ALLOWED_EXT))}',
        }), 400

    # 3. 验证文件大小（16MB）
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    max_size = 16 * 1024 * 1024  # 16MB
    if file_size > max_size:
        return jsonify({
            'success': False,
            'error': f'文件大小超过限制（最大16MB），当前文件: {file_size / 1024 / 1024:.2f}MB'
        }), 400

    # 4. 保存文件
    from flask import current_app
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    file_path = os.path.join(upload_folder, unique_filename)
    
    try:
        file.save(file_path)
        logger.info(f"发票文件已保存: {file_path}")
    except Exception as e:
        logger.error(f"保存文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'保存文件失败: {str(e)}'
        }), 500
    
    # 5. 获取表单数据
    invoice_data = {
        'invoice_no': request.form.get('invoice_no', '').strip(),
        'invoice_code': request.form.get('invoice_code', '').strip(),
        'invoice_date': request.form.get('invoice_date', '').strip(),
        'invoice_amount': request.form.get('invoice_amount', 0),
        'buyer_tax_no': request.form.get('buyer_tax_no', '').strip(),
        'seller_tax_no': request.form.get('seller_tax_no', '').strip(),
        'collaboration_code': request.form.get('collaboration_code', '').strip(),
        'delivery_date': request.form.get('delivery_date', '').strip(),
        'quality_rating': _parse_quality_rating(request.form.get('quality_rating'), default=5),
        'file_path': file_path
    }
    
    # 6. 验证发票（带重试机制，最多3次）
    max_retries = 3
    validation_result = None
    
    for attempt in range(max_retries):
        try:
            validation_result = validate_invoice(invoice_data)
            
            # 如果验证成功或明确失败（非网络错误），跳出重试
            if validation_result.get('valid') or not validation_result.get('error', '').startswith('税务API'):
                break
                
            # 网络错误，重试
            if attempt < max_retries - 1:
                logger.warning(f"发票验证失败，重试 {attempt + 1}/{max_retries}")
                import time
                time.sleep(1)  # 等待1秒后重试
                
        except Exception as e:
            logger.error(f"发票验证异常: {str(e)}")
            if attempt == max_retries - 1:
                validation_result = {
                    'valid': False,
                    'error': f'发票验证异常: {str(e)}',
                    'manual_review_required': False
                }
    
    # 7. 处理验证结果
    if not validation_result or not validation_result.get('valid'):
        # 验证失败，删除文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"验证失败，已删除文件: {file_path}")
        except Exception as e:
            logger.warning(f"删除文件失败: {str(e)}")
        
        error_msg = validation_result.get('error', '发票验证失败') if validation_result else '发票验证失败'
        manual_review = validation_result.get('manual_review_required', False) if validation_result else False
        
        response = {
            'success': False,
            'error': error_msg,
            'manual_review_required': manual_review
        }
        
        if manual_review:
            response['message'] = '发票验证失败次数过多，已提交人工审核'
        
        return jsonify(response), 400
    
    # 8. 存储履约数据（seller_id 已在保存文件前校验）
    fulfillment = store_fulfillment_data(
        invoice_info=validation_result,
        buyer_id=current_user.id,
        seller_id=seller_id_int
    )
    
    if not fulfillment:
        logger.error("存储履约数据失败")
        return jsonify({
            'success': False,
            'error': '存储履约数据失败，请稍后重试'
        }), 500
    
    # 9. 更新卖方信用分
    try:
        update_credit_score(
            enterprise_id=seller_id_int,
            change_type='fulfillment',
            change_value=5.0,
            reason='完成履约并上传发票'
        )
        logger.info(f"已更新卖方信用分: seller_id={seller_id_int}")
    except Exception as e:
        logger.error(f"更新信用分失败: {str(e)}")
        # 不影响主流程，继续返回成功
    
    # 10. 返回成功结果
    return jsonify({
        'success': True,
        'message': '发票验证成功，履约数据已记录',
        'invoice_info': {
            'invoice_no': validation_result.get('invoice_no'),
            'amount': validation_result.get('amount'),
            'date': validation_result.get('date'),
            'buyer': validation_result.get('buyer'),
            'seller': validation_result.get('seller')
        },
        'fulfillment_id': fulfillment.id
    })


@collab_bp.route('/api/invoice/validate', methods=['POST'])
@role_required('enterprise')
def validate_invoice_api():
    """
    验证发票信息（不上传文件）
    用于快速验证发票真伪
    """
    data = request.get_json() or {}
    
    invoice_data = {
        'invoice_no': data.get('invoice_no', ''),
        'invoice_code': data.get('invoice_code', ''),
        'invoice_date': data.get('invoice_date', ''),
        'invoice_amount': data.get('invoice_amount', 0),
        'buyer_tax_no': data.get('buyer_tax_no', ''),
        'seller_tax_no': data.get('seller_tax_no', ''),
    }
    
    # 验证发票
    validation_result = validate_invoice(invoice_data)
    
    return jsonify({
        'success': validation_result.get('valid', False),
        'result': validation_result
    })


@collab_bp.route('/api/fulfillment/record', methods=['POST'])
@role_required('enterprise')
def record_fulfillment_api():
    """记录履约数据（买方确认后调用）。"""
    data = request.get_json() or {}
    seller_id = data.get('seller_id')
    on_time = data.get('on_time', True)
    quality_rating = data.get('quality_rating', 4)
    invoice_no = data.get('invoice_no', '')
    invoice_amount = data.get('invoice_amount', 0.0)
    collaboration_code = data.get('collaboration_code', '')

    if not seller_id:
        return jsonify({'error': '缺少 seller_id'}), 400

    fd = record_fulfillment(
        buyer_id=current_user.id,
        seller_id=int(seller_id),
        on_time=bool(on_time),
        quality_rating=int(quality_rating),
        invoice_no=invoice_no,
        invoice_amount=float(invoice_amount) if invoice_amount else 0.0,
        collaboration_code=collaboration_code,
    )
    return jsonify({
        'success': True,
        'fulfillment_id': fd.id,
        'message': '履约数据已记录，信用分已更新',
    })


@collab_bp.route('/api/fulfillment/dashboard', methods=['GET'])
@role_required('enterprise')
def fulfillment_dashboard():
    """企业履约数据看板。"""
    from datetime import datetime, timedelta

    from app.services.credit_engine import get_credit_history

    ent_id = current_user.id
    ent = Enterprise.query.get(ent_id)
    cutoff = datetime.utcnow() - timedelta(days=365)

    q = (
        Transaction.query.filter(
            Transaction.seller_id == ent_id,
            Transaction.created_at >= cutoff,
        )
        .order_by(Transaction.created_at.desc())
        .limit(50)
    )
    records = []
    for tx in q.all():
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        if info.get('verified'):
            records.append(tx)

    total = len(records)
    on_time_count = sum(
        1
        for r in records
        if (r.invoice_info or {}).get('on_time', True)
    )
    on_time_rate = round(on_time_count / total * 100, 1) if total > 0 else 0

    credit_history = get_credit_history(ent_id, limit=10)

    return jsonify({
        'credit_score': float(ent.credit_score or 60.0),
        'on_time_rate': on_time_rate,
        'total_fulfillments': total,
        'on_time_count': on_time_count,
        'credit_history': credit_history,
    })


# ── 报价池 ────────────────────────────────────────────────────────────────

@collab_bp.route('/api/quotes', methods=['GET'])
@login_required
def list_quotes():
    """获取最近报价列表 (支持前端 QuotePool 页面)。"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    q = Quote.query.filter_by(status='active').order_by(Quote.created_at.desc())
    total = q.count()
    quotes = q.offset((page - 1) * per_page).limit(per_page).all()
    result = []
    for qt in quotes:
        supplier = Enterprise.query.get(qt.supplier_id)
        result.append({
            'id': qt.id,
            'product_name': qt.product_name,
            'supplier_name': supplier.name if supplier else '未知',
            'price': qt.price,
            'quantity': qt.quantity,
            'unit': qt.unit,
            'delivery_days': qt.delivery_days,
            'status': qt.status,
            'created_at': qt.created_at.isoformat() if qt.created_at else None,
        })
    return jsonify({'success': True, 'quotes': result, 'total': total, 'page': page})

@collab_bp.route('/api/quotes', methods=['POST'])
@role_required('enterprise')
def submit_quote():
    """提交报价。"""
    data = request.get_json() or {}
    inquiry_id = data.get('inquiry_id')
    price = data.get('price')
    product_name = (data.get('product_name') or '').strip()

    if not inquiry_id:
        raise APIError.bad_request('缺少 inquiry_id', ERR_MISSING_PARAM)
    if price is None:
        raise APIError.bad_request('缺少 price', ERR_MISSING_PARAM)

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise APIError.bad_request('price 格式无效', ERR_QUOTE_PRICE_INVALID)

    if price <= 0:
        raise APIError.bad_request('报价金额必须大于0', ERR_QUOTE_PRICE_INVALID)

    if not Inquiry.query.get(int(inquiry_id)):
        raise APIError.not_found('询价单不存在', ERR_INQUIRY_NOT_FOUND)

    quote, error = add_quote(
        inquiry_id=int(inquiry_id),
        supplier_id=current_user.id,
        product_name=product_name,
        price=price,
        quantity=data.get('quantity', 0),
        unit=data.get('unit', ''),
        delivery_days=data.get('delivery_days', 0),
        remarks=data.get('remarks', ''),
    )

    if error:
        raise APIError(error, code=ERR_QUOTE_LIMIT, http_status=400)

    from app.services.credit_engine import check_credit_privileges
    privileges = check_credit_privileges(current_user.id)
    limit = privileges.get('daily_quote_limit', 3)
    remaining = '不限' if limit == 'unlimited' else max(0, limit - (current_user.daily_quote_count or 0))

    return jsonify({
        'success': True,
        'quote_id': quote.id,
        'remaining_quotes_today': remaining,
    })


@collab_bp.route('/api/price-index/<string:product_name>', methods=['GET'])
def get_price_index_api(product_name: str):
    """获取产品价格指数。"""
    result = get_price_index(product_name)
    return jsonify(result)


@collab_bp.route('/api/quotes/inquiry/<int:inquiry_id>', methods=['GET'])
@role_required('enterprise')
def get_inquiry_quotes(inquiry_id: int):
    """获取询价单的所有报价。"""
    quotes = get_quotes_for_inquiry(inquiry_id)
    return jsonify({'quotes': quotes})


@collab_bp.route('/inquiry/<int:inquiry_id>', methods=['GET'])
@role_required('enterprise')
def inquiry_detail(inquiry_id: int):
    """询价单详情页（含价格指数展示）。需求: 16.3, 16.7, 16.8"""
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    allowed = {inquiry.poster_id, inquiry.buyer_id, inquiry.seller_id}
    allowed.discard(None)
    if current_user.id not in allowed and current_user.role != 'admin':
        from flask import abort
        abort(403)
    return render_template('match/inquiry_detail.html', inquiry=inquiry)


# ── 消息中心 ──────────────────────────────────────────────────────────────

@collab_bp.route('/api/messages', methods=['GET', 'POST'])
@login_required
def messages_collection():
    """GET：收件箱列表（支持 mode 过滤）。POST：发送站内消息（如卖方意向报价回执给买方）。"""
    if request.method == 'POST':
        data = request.get_json() or {}
        receiver_raw = data.get('receiver_id')
        try:
            receiver_id = int(receiver_raw)
        except (TypeError, ValueError):
            raise APIError.bad_request('缺少或无效的 receiver_id', ERR_MISSING_PARAM)
        if receiver_id == current_user.id:
            raise APIError.bad_request('不能向自己发送消息', ERR_INVALID_PARAM)

        recipient = Enterprise.query.get(receiver_id)
        if not recipient:
            raise APIError.bad_request('接收企业不存在', ERR_INVALID_PARAM)

        product_name = (data.get('product_name') or '').strip()
        title = (data.get('title') or '').strip() or (
            f'意向报价：{product_name}' if product_name else '意向报价通知'
        )
        content = (data.get('content') or '').strip()
        quote_price = data.get('quote_price')
        delivery_days = data.get('delivery_days')
        inquiry_id = data.get('inquiry_id')
        try:
            inquiry_int = int(inquiry_id) if inquiry_id is not None else None
        except (TypeError, ValueError):
            inquiry_int = None

        lines = []
        if content:
            lines.append(content)
        if quote_price is not None and quote_price != '':
            try:
                lines.append(f'报价单价(元): {float(quote_price):.2f}')
            except (TypeError, ValueError):
                lines.append(f'报价单价(元): {quote_price}')
        if delivery_days is not None and delivery_days != '':
            lines.append(f'预计交期(天): {delivery_days}')
        full_content = '\n'.join(lines) if lines else '您有一条新的意向报价，请登录查看。'

        q_parts = [f'seller_id={current_user.id}', f'buyer_id={receiver_id}']
        if inquiry_int is not None:
            q_parts.append(f'inquiry_id={inquiry_int}')
        link_url = '/sales-console?' + '&'.join(q_parts)
        if len(link_url) > 250:
            if inquiry_int is not None:
                link_url = (
                    f'/sales-console?inquiry_id={inquiry_int}&buyer_id={receiver_id}'
                    f'&seller_id={current_user.id}'
                )
            else:
                link_url = f'/sales-console?buyer_id={receiver_id}&seller_id={current_user.id}'

        # 卖方发送报价回执给买方 → mode='sales'
        msg_mode = data.get('mode', 'procurement')
        if msg_mode not in ('procurement', 'sales'):
            msg_mode = 'procurement'

        msg = send_message(
            recipient_id=receiver_id,
            message_type='inquiry',
            title=title[:200],
            content=full_content,
            link_url=link_url[:255] if len(link_url) > 255 else link_url,
            priority='high',
            mode=msg_mode,
        )
        return jsonify(
            {
                'success': True,
                'message_id': msg.id,
                'unread_count': get_unread_count(receiver_id),
            }
        )

    msg_type = request.args.get('type')
    is_read = request.args.get('is_read')
    msg_mode = request.args.get('mode')  # procurement / sales / None(全部)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if page < 1:
        raise APIError.bad_request('page 须大于0')
    if per_page < 1 or per_page > 100:
        raise APIError.bad_request('per_page 须在 1-100 之间')

    q = Message.query.filter_by(recipient_id=current_user.id)
    if msg_type:
        valid_types = ('transaction', 'alert', 'system', 'inquiry', 'credit')
        if msg_type not in valid_types:
            raise APIError.bad_request(f'type 须为 {", ".join(valid_types)} 之一', ERR_INVALID_PARAM)
        q = q.filter_by(message_type=msg_type)
    if is_read is not None:
        q = q.filter_by(is_read=(is_read.lower() == 'true'))
    # 按 mode 过滤（采购/销售视角分离）
    if msg_mode in ('procurement', 'sales'):
        q = q.filter_by(mode=msg_mode)

    # 预警消息置顶，其余按时间倒序
    from sqlalchemy import case as sa_case
    q = q.order_by(
        sa_case((Message.message_type == 'alert', 0), else_=1),
        Message.created_at.desc(),
    )

    total = q.count()
    messages = q.offset((page - 1) * per_page).limit(per_page).all()
    unread_count = get_unread_count(current_user.id)

    return jsonify({
        'success': True,
        'total': total,
        'unread_count': unread_count,
        'page': page,
        'per_page': per_page,
        'messages': [
            {
                'id': m.id,
                'type': m.message_type,
                'title': m.title,
                'content': m.content,
                'link_url': m.link_url,
                'is_read': m.is_read,
                'priority': m.priority,
                'mode': m.mode,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    })


@collab_bp.route('/api/messages/<int:message_id>/read', methods=['PUT'])
@login_required
def mark_read(message_id: int):
    """标记消息为已读。"""
    msg = Message.query.get(message_id)
    if not msg:
        raise APIError.not_found('消息不存在', ERR_MESSAGE_NOT_FOUND)
    if msg.recipient_id != current_user.id:
        raise APIError.forbidden('无权操作该消息', ERR_MESSAGE_FORBIDDEN)
    mark_messages_read(current_user.id, [message_id])
    return jsonify({'success': True, 'unread_count': get_unread_count(current_user.id)})


@collab_bp.route('/api/messages/read-all', methods=['PUT'])
@login_required
def mark_all_read():
    """标记所有消息为已读。"""
    mark_messages_read(current_user.id)
    return jsonify({'success': True})


# ── 举报机制 ──────────────────────────────────────────────────────────────

@collab_bp.route('/api/reports', methods=['POST'])
@role_required('enterprise')
def submit_report():
    """提交举报。"""
    data = request.get_json() or {}
    reported_id = data.get('reported_id')
    report_type = data.get('report_type', 'unreliable_quote')
    description = (data.get('description') or '').strip()

    if not reported_id:
        return jsonify({'error': '缺少 reported_id'}), 400
    if not description:
        return jsonify({'error': '请填写举报说明'}), 400
    if int(reported_id) == current_user.id:
        return jsonify({'error': '不能举报自己'}), 400

    from app.services.report_records_service import append_report

    rid, _reported_ent = append_report(
        reporter_id=current_user.id,
        reported_id=int(reported_id),
        report_type=report_type,
        description=description,
        target_type=data.get('target_type'),
        target_id=data.get('target_id'),
    )

    # 通知管理员
    admins = Enterprise.query.filter_by(role='admin').all()
    for admin in admins:
        send_message(
            recipient_id=admin.id,
            message_type='system',
            title=f'新举报：{report_type}',
            content=f'企业 {current_user.name} 举报了企业ID {reported_id}。\n说明：{description}',
            link_url='/admin/reports',
            priority='high',
        )

    db.session.commit()
    return jsonify({'success': True, 'report_id': rid, 'message': '举报已提交，将在3个工作日内处理'})


# ── 拼单/集采（Inquiry.is_group_buy + match_context）──────────────────────

def _group_ctx(inq: Inquiry) -> dict:
    mc = inq.match_context if isinstance(inq.match_context, dict) else {}
    return mc.get('group_buy') or {}


def _parse_iso_dt(s):
    if not s or not isinstance(s, str):
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None


@collab_bp.route('/api/group-purchases', methods=['POST'])
@role_required('enterprise')
def create_group_purchase():
    """发起拼单。"""
    from datetime import datetime, timedelta

    data = request.get_json() or {}
    product_name = (data.get('product_name') or '').strip()
    target_quantity = data.get('target_quantity', 0)
    days = data.get('deadline_days', 7)

    if not product_name:
        return jsonify({'error': '缺少产品名称'}), 400

    deadline_dt = datetime.utcnow() + timedelta(days=int(days))
    qty0 = int(data.get('quantity', 0))
    min_cs = float(data.get('min_credit_score', 60.0))
    tq = int(target_quantity) if target_quantity else None

    members = [
        {
            'enterprise_id': current_user.id,
            'quantity': qty0,
            'joined_at': datetime.utcnow().isoformat() + 'Z',
        }
    ]
    gb = {
        'deadline': deadline_dt.isoformat() + 'Z',
        'min_credit_score': min_cs,
        'target_quantity': tq,
        'current_quantity': qty0,
        'participant_count': 1,
    }
    inq = Inquiry(
        poster_id=current_user.id,
        direction='demand',
        product_name=product_name,
        quantity=tq,
        status='open',
        is_group_buy=True,
        group_members=members,
        match_context={'group_buy': gb},
    )
    db.session.add(inq)
    db.session.commit()

    return jsonify({'success': True, 'group_purchase_id': inq.id})


@collab_bp.route('/api/group-purchases/<int:gp_id>/join', methods=['POST'])
@role_required('enterprise')
def join_group_purchase(gp_id: int):
    """加入拼单。"""
    from datetime import datetime

    data = request.get_json() or {}
    quantity = int(data.get('quantity', 0))

    inq = Inquiry.query.get_or_404(gp_id)
    if not inq.is_group_buy or inq.status != 'open':
        return jsonify({'error': '拼单已关闭'}), 400

    gb = _group_ctx(inq)
    min_cs = float(gb.get('min_credit_score') or 60.0)
    ent = Enterprise.query.get(current_user.id)
    if float(ent.credit_score or 60.0) < min_cs:
        return jsonify({'error': f'信用分不足，需要{min_cs}分以上'}), 400

    members = list(inq.group_members) if isinstance(inq.group_members, list) else []
    if any(m.get('enterprise_id') == current_user.id for m in members if isinstance(m, dict)):
        return jsonify({'error': '已参与该拼单'}), 400

    members.append(
        {
            'enterprise_id': current_user.id,
            'quantity': quantity,
            'joined_at': datetime.utcnow().isoformat() + 'Z',
        }
    )
    inq.group_members = members
    mc = dict(inq.match_context) if isinstance(inq.match_context, dict) else {}
    gbx = dict(mc.get('group_buy') or {})
    gbx['current_quantity'] = int(gbx.get('current_quantity') or 0) + quantity
    gbx['participant_count'] = int(gbx.get('participant_count') or 0) + 1
    mc['group_buy'] = gbx
    inq.match_context = mc
    db.session.commit()
    return jsonify(
        {
            'success': True,
            'total_quantity': gbx['current_quantity'],
            'participants': gbx['participant_count'],
        }
    )


@collab_bp.route('/api/group-purchases', methods=['GET'])
@login_required
def list_group_purchases():
    """获取开放中的拼单列表。"""
    from datetime import datetime

    now = datetime.utcnow()
    rows = (
        Inquiry.query.filter_by(is_group_buy=True, status='open')
        .order_by(Inquiry.created_at.desc())
        .limit(50)
        .all()
    )
    out = []
    for inq in rows:
        gb = _group_ctx(inq)
        dl = _parse_iso_dt(gb.get('deadline'))
        if dl and now > (dl.replace(tzinfo=None) if getattr(dl, 'tzinfo', None) else dl):
            continue
        out.append(
            {
                'id': inq.id,
                'product_name': inq.product_name,
                'target_quantity': gb.get('target_quantity'),
                'current_quantity': gb.get('current_quantity'),
                'participant_count': gb.get('participant_count'),
                'deadline': gb.get('deadline'),
                'min_credit_score': gb.get('min_credit_score'),
            }
        )
    return jsonify({'group_purchases': out[:20]})


# ── 合作案例库（Enterprise.cooperation_cases）─────────────────────────────

@collab_bp.route('/api/case-library/<int:supplier_id>', methods=['GET'])
@login_required
def get_case_library(supplier_id: int):
    """获取供应商公开合作案例。"""
    ent = Enterprise.query.get_or_404(supplier_id)
    raw = ent.cooperation_cases if isinstance(ent.cooperation_cases, list) else []
    cases = [c for c in raw if isinstance(c, dict) and c.get('is_public', True)]

    return jsonify({
        'cases': [
            {
                'id': c.get('id'),
                'buyer_name_masked': c.get('buyer_name_masked'),
                'product_category': c.get('product_category'),
                'cooperation_time': c.get('cooperation_time'),
                'amount_range': c.get('amount_range'),
            }
            for c in cases
        ]
    })


@collab_bp.route('/api/case-library/<string:case_id>/toggle-public', methods=['PUT'])
@role_required('enterprise')
def toggle_case_public(case_id: str):
    """切换案例公开状态（案例 id 为 cooperation_cases 条目的字符串 id）。"""
    ent = Enterprise.query.get(current_user.id)
    if not ent:
        return jsonify({'error': '企业不存在'}), 404
    raw = list(ent.cooperation_cases) if isinstance(ent.cooperation_cases, list) else []
    found = False
    new_pub = True
    for i, c in enumerate(raw):
        if isinstance(c, dict) and str(c.get('id')) == str(case_id):
            new_pub = not bool(c.get('is_public', False))
            c['is_public'] = new_pub
            raw[i] = c
            found = True
            break
    if not found:
        return jsonify({'error': '案例不存在'}), 404
    ent.cooperation_cases = raw
    db.session.commit()
    return jsonify({'success': True, 'is_public': new_pub})
