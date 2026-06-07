"""
招商决策路由
- GET  /recruitment/gaps                  - 产业链缺口分析页面
- GET  /recruitment/tasks                 - 招商任务管理页面
- GET  /api/recruitment/gaps              - 缺口数据 JSON API
- POST /api/recruitment/tasks             - 创建招商任务
- GET  /api/recruitment/tasks             - 招商任务列表
- PUT  /api/recruitment/tasks/<id>        - 更新任务进度
- GET  /api/recruitment/tasks/<id>        - 获取任务详情（进展跟踪）
需求: 36.1-36.7, 37.1-37.7, 38.1-38.8, 71.1-71.7
"""
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from app.authz import role_required

recruitment_bp = Blueprint('recruitment', __name__)


# ── 产业链缺口分析页面 ────────────────────────────────────────────────────

@recruitment_bp.route('/recruitment/gaps')
@login_required
@role_required('admin')
def gaps_page():
    """产业链缺口分析页面。需求: 36.1-36.7"""
    return render_template('recruitment/gaps.html')


# ── 招商任务管理页面 ──────────────────────────────────────────────────────

@recruitment_bp.route('/recruitment/tasks')
@login_required
@role_required('admin')
def tasks_page():
    """招商任务管理页面（看板视图）。需求: 38.1-38.8"""
    return render_template('recruitment/tasks.html')


# ── 缺口数据 API ──────────────────────────────────────────────────────────

@recruitment_bp.route('/api/recruitment/gaps', methods=['GET'])
@login_required
@role_required('admin')
def get_gaps():
    """
    获取产业链缺口分析数据。
    需求: 36.1, 36.2, 36.3, 36.4
    """
    try:
        from app.services.recruitment_service import analyze_supply_chain_gaps
        neo4j_flag = request.args.get('neo4j', '1').lower()
        include_neo4j = neo4j_flag not in ('0', 'false', 'no', 'off')
        gaps = analyze_supply_chain_gaps(include_neo4j=include_neo4j)
        return jsonify({
            'success': True,
            'total': len(gaps),
            'gaps': gaps,
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"缺口分析失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ── 潜在企业推荐 API ──────────────────────────────────────────────────────

@recruitment_bp.route('/api/recruitment/recommend', methods=['POST'])
@login_required
@role_required('admin')
def recommend_enterprises():
    """
    推荐潜在招商企业。
    需求: 37.1-37.7
    """
    data = request.get_json() or {}
    product_name = data.get('product_name', '')
    if not product_name:
        return jsonify({'error': '缺少 product_name 参数'}), 400

    from app.services.recruitment_service import recommend_potential_enterprises
    gap = {
        'product_name': product_name,
        'gap_type': data.get('gap_type', 'supplier_shortage'),
        'supplier_count': data.get('supplier_count', 0),
        'local_ratio': data.get('local_ratio', 1.0),
        'suggestion': {'enterprise_type': data.get('enterprise_type', '制造企业')},
    }
    enterprises = recommend_potential_enterprises(gap)
    return jsonify({'success': True, 'enterprises': enterprises})


# ── 创建招商任务 ──────────────────────────────────────────────────────────

@recruitment_bp.route('/api/recruitment/tasks', methods=['POST'])
@login_required
@role_required('admin')
def create_task():
    """
    从招商建议创建招商任务。
    需求: 34.6, 34.7, 38.1
    """
    data = request.get_json() or {}
    if not data.get('target_product'):
        return jsonify({'error': '缺少 target_product 参数'}), 400

    from app.services.recruitment_service import create_recruitment_task
    from datetime import date

    deadline = None
    if data.get('deadline'):
        try:
            deadline = date.fromisoformat(data['deadline'])
        except ValueError:
            pass

    task_data = {
        'task_name': data.get('task_name') or f'招商任务-{data["target_product"]}',
        'target_product': data['target_product'],
        'target_enterprise_name': data.get('target_enterprise_name'),
        'target_enterprise_location': data.get('target_enterprise_location'),
        'assigned_by': current_user.id,
        'assigned_to': data.get('assigned_to'),
        'priority': data.get('priority', 'normal'),
        'progress_notes': data.get('progress_notes'),
        'deadline': deadline,
    }

    task = create_recruitment_task(task_data)

    # 通知被分配人（需求 38.4）
    if task_data.get('assigned_to'):
        try:
            from app.services.alert_notifier import send_message
            send_message(
                recipient_id=task_data['assigned_to'],
                message_type='system',
                title=f'新招商任务：{task.task_name}',
                content=f'您有一个新的招商任务"{task.task_name}"，目标产品：{task.target_product}，请及时跟进。',
                link_url='/recruitment/tasks',
                priority='normal',
            )
        except Exception:
            pass

    return jsonify({
        'success': True,
        'task_id': task.id,
        'message': '招商任务已创建',
    }), 201


# ── 招商任务列表 ──────────────────────────────────────────────────────────

@recruitment_bp.route('/api/recruitment/tasks', methods=['GET'])
@login_required
@role_required('admin')
def list_tasks():
    """
    获取招商任务列表。
    需求: 38.2
    """
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    from app.services.recruitment_service import get_recruitment_tasks
    result = get_recruitment_tasks(status=status, page=page, per_page=per_page)
    return jsonify(result)


# ── 更新招商任务 ──────────────────────────────────────────────────────────

@recruitment_bp.route('/api/recruitment/tasks/<int:task_id>', methods=['PUT'])
@login_required
@role_required('admin')
def update_task(task_id: int):
    """
    更新招商任务进度。
    需求: 38.3, 38.5
    """
    data = request.get_json() or {}
    from app.services.recruitment_service import update_recruitment_task
    task = update_recruitment_task(task_id, data)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({'success': True, 'message': '任务已更新'})


# ── 获取任务详情（进展跟踪） ──────────────────────────────────────────────

@recruitment_bp.route('/api/recruitment/tasks/<int:task_id>', methods=['GET'])
@login_required
@role_required('admin')
def get_task(task_id: int):
    """
    获取招商任务详情及进展跟踪信息。
    需求: 38.5, 38.6, 38.7
    """
    from app.services.recruitment_service import track_task_progress
    detail = track_task_progress(task_id)
    if not detail:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({'success': True, 'task': detail})
