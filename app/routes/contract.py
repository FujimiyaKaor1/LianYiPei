"""
电子合同路由
"""
from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from io import BytesIO
from types import SimpleNamespace

from app import db
from app.models import Enterprise, Transaction
from app.services.econtract_service import get_econtract_service
from app.services.collaboration_service import send_message
from app.services.fulfillment_service import trigger_fulfillment_backflow

bp = Blueprint('contract', __name__, url_prefix='/contract')


def _transaction_for_contract(contract_id: str):
    for tx in Transaction.query.all():
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        if info.get('contract_id') == contract_id:
            return tx
    return None


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_contract():
    """创建电子合同页面"""
    if request.method == 'GET':
        # 获取买卖方信息（从URL参数）
        buyer_id = request.args.get('buyer_id', type=int)
        seller_id = request.args.get('seller_id', type=int)
        product_name = request.args.get('product_name', '')
        
        buyer = Enterprise.query.get(buyer_id) if buyer_id else None
        seller = Enterprise.query.get(seller_id) if seller_id else None
        
        return render_template(
            'contract/create.html',
            buyer=buyer,
            seller=seller,
            product_name=product_name,
        )
    
    # POST: 生成合同
    try:
        buyer_id = request.form.get('buyer_id', type=int)
        seller_id = request.form.get('seller_id', type=int)
        product_name = request.form.get('product_name', '')
        
        # 合同条款
        terms = {
            'quantity': request.form.get('quantity', type=int),
            'unit': request.form.get('unit', ''),
            'price': request.form.get('price', type=float),
            'total_amount': request.form.get('total_amount', type=float),
            'delivery_time': request.form.get('delivery_time', ''),
            'quality_requirements': request.form.get('quality_requirements', ''),
            'payment_terms': request.form.get('payment_terms', ''),
        }
        
        # 生成合同
        service = get_econtract_service()
        contract_id = service.generate_contract(buyer_id, seller_id, product_name, terms)
        
        # 发送通知给买卖双方
        send_message(
            recipient_id=buyer_id,
            message_type='transaction',
            title='电子合同已生成',
            content=f'您与{Enterprise.query.get(seller_id).name}的合同已生成，请尽快签署。',
            link_url=f'/contract/sign/{contract_id}',
            priority='high',
        )
        
        send_message(
            recipient_id=seller_id,
            message_type='transaction',
            title='电子合同已生成',
            content=f'您与{Enterprise.query.get(buyer_id).name}的合同已生成，请尽快签署。',
            link_url=f'/contract/sign/{contract_id}',
            priority='high',
        )
        
        flash('合同生成成功，请双方签署', 'success')
        return redirect(url_for('contract.sign_page', contract_id=contract_id))
        
    except Exception as e:
        flash(f'合同生成失败: {str(e)}', 'danger')
        return redirect(url_for('contract.create_contract'))


@bp.route('/sign/<contract_id>', methods=['GET', 'POST'])
@login_required
def sign_page(contract_id: str):
    """合同签署页面"""
    service = get_econtract_service()
    
    if request.method == 'GET':
        # 获取合同状态
        status = service.check_contract_status(contract_id)
        
        # 获取合同详情（从撮合码或其他来源）
        # 这里简化处理，实际应从数据库查询
        contract_details = {
            'contract_id': contract_id,
            'status': status,
        }
        
        return render_template(
            'contract/sign.html',
            contract=contract_details,
            contract_id=contract_id,
        )
    
    # POST: 签署合同
    try:
        signature_data = {
            'signature_type': request.form.get('signature_type', 'digital'),
            'signature_image': request.form.get('signature_image', ''),
            'timestamp': request.form.get('timestamp', ''),
        }
        
        # 签署合同
        success = service.sign_contract(contract_id, current_user.id, signature_data)
        
        if success:
            # 检查是否双方都已签署
            status = service.check_contract_status(contract_id)
            
            if status == 'signed':
                # 双方都已签署，生成撮合码
                collab_code = service.generate_collaboration_code(contract_id)
                
                flash(f'合同签署成功！撮合码: {collab_code}', 'success')
                return redirect(url_for('contract.view_contract', contract_id=contract_id))
            else:
                flash('签署成功，等待对方签署', 'success')
                return redirect(url_for('contract.sign_page', contract_id=contract_id))
        else:
            flash('签署失败，请重试', 'danger')
            return redirect(url_for('contract.sign_page', contract_id=contract_id))
            
    except Exception as e:
        flash(f'签署失败: {str(e)}', 'danger')
        return redirect(url_for('contract.sign_page', contract_id=contract_id))


@bp.route('/view/<contract_id>')
@login_required
def view_contract(contract_id: str):
    """查看合同详情"""
    service = get_econtract_service()
    
    # 获取合同状态
    status = service.check_contract_status(contract_id)
    
    tx = _transaction_for_contract(contract_id)
    contract_details = {
        'contract_id': contract_id,
        'status': status,
        'collaboration_code': tx.match_code if tx else None,
    }
    
    return render_template(
        'contract/view.html',
        contract=contract_details,
    )


@bp.route('/download/<contract_id>')
@login_required
def download_contract(contract_id: str):
    """下载合同PDF"""
    try:
        service = get_econtract_service()
        pdf_content = service.download_contract(contract_id)
        
        # 返回PDF文件
        return send_file(
            BytesIO(pdf_content),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'contract_{contract_id}.pdf',
        )
        
    except Exception as e:
        flash(f'下载失败: {str(e)}', 'danger')
        return redirect(url_for('contract.view_contract', contract_id=contract_id))


@bp.route('/list')
@login_required
def list_contracts():
    """合同列表页面"""
    txs = (
        Transaction.query.filter(
            (Transaction.buyer_id == current_user.id)
            | (Transaction.seller_id == current_user.id)
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
    rows = []
    for tx in txs:
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        cid = info.get('contract_id') or ''
        rows.append(
            SimpleNamespace(
                contract_id=cid,
                code=tx.match_code or '',
                product_name=tx.product_name,
                amount_range=info.get('amount_range') or '未披露',
                fulfillment_status=tx.fulfillment_status or 'pending',
                created_at=tx.created_at,
            )
        )

    return render_template(
        'contract/list.html',
        contracts=rows,
    )


# API接口

@bp.route('/api/status/<contract_id>', methods=['GET'])
@login_required
def api_contract_status(contract_id: str):
    """获取合同状态API"""
    try:
        service = get_econtract_service()
        status = service.check_contract_status(contract_id)
        
        return jsonify({
            'code': 200,
            'data': {
                'contract_id': contract_id,
                'status': status,
            }
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': str(e),
        }), 500


@bp.route('/api/sign', methods=['POST'])
@login_required
def api_sign_contract():
    """签署合同API"""
    try:
        data = request.get_json()
        contract_id = data.get('contract_id')
        signature_data = data.get('signature_data', {})
        
        service = get_econtract_service()
        success = service.sign_contract(contract_id, current_user.id, signature_data)
        
        if success:
            # 检查是否双方都已签署
            status = service.check_contract_status(contract_id)
            
            collab_code = None
            if status == 'signed':
                # 生成撮合码
                collab_code = service.generate_collaboration_code(contract_id)
            
            return jsonify({
                'code': 200,
                'message': '签署成功',
                'data': {
                    'status': status,
                    'collaboration_code': collab_code,
                }
            })
        else:
            return jsonify({
                'code': 400,
                'message': '签署失败',
            }), 400
            
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': str(e),
        }), 500


@bp.route('/api/fulfill', methods=['POST'])
@login_required
def api_fulfill_contract():
    """
    标记合同履约完成并触发数据回流。
    需求: 6.5, 69.5, 69.6
    """
    try:
        data = request.get_json() or {}
        contract_id = data.get('contract_id', '')
        invoice_info = data.get('invoice_info', {})

        if not contract_id or not invoice_info:
            return jsonify({'code': 400, 'message': '缺少合同ID或发票信息'}), 400

        # 查找撮合码获取买卖方
        tx = _transaction_for_contract(contract_id)
        if not tx or not tx.match_code:
            return jsonify({'code': 404, 'message': '合同对应的撮合码不存在'}), 404

        result = trigger_fulfillment_backflow(
            collaboration_code=tx.match_code,
            invoice_info=invoice_info,
            buyer_id=tx.buyer_id,
            seller_id=tx.seller_id,
        )

        return jsonify({'code': 200, 'data': result})

    except Exception as e:
        return jsonify({'code': 500, 'message': str(e)}), 500
