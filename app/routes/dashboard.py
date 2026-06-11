from flask import Blueprint, render_template, jsonify, request, send_file, abort, redirect
from flask_login import login_required
from app.authz import role_required
from config import DEFAULT_ALERT_THRESHOLDS

from app.models import Enterprise, Inquiry, Alert, Product
from app.services.graph_manager import get_full_graph
from app.services.alerter import run_all_checks, generate_chain_risk_report, get_threshold
from app.services.graph_algorithms import pagerank_products, community_detection
from app.services.forecaster import forecast_supply_demand
import io

# 无前缀：所有规则显式以 /dashboard/... 开头，便于与 SPA 通配写法一致
dashboard = Blueprint('dashboard', __name__)

# ---------------------------------------------------------------------------
# React 看板 vs Jinja 后台：路径隔离
#
# 显式路由（/dashboard/alerts、/dashboard/api/*、/dashboard/settings/thresholds 重定向等）
# 优先匹配；其余 /dashboard 及任意深度子路径由下方通配交给 React。
#
# 通配中下列「首段」不得返回 SPA（未注册更具体路由时 404）：
#   api / settings / auth / static
#
# spa.html：统一 main._render_spa() → window.__INITIAL_DATA__
# ---------------------------------------------------------------------------
DASHBOARD_SPA_EXCLUDED_FIRST_SEGMENTS = frozenset({'api', 'settings', 'auth', 'static'})


def _dashboard_spa_segment_excluded(rel_path: str) -> bool:
    """相对 /dashboard/ 的剩余 path（不含前缀）：首段在排除表则禁止 SPA。"""
    if not rel_path:
        return False
    first = rel_path.split('/', 1)[0].strip().lower()
    return first in DASHBOARD_SPA_EXCLUDED_FIRST_SEGMENTS


@dashboard.route('/dashboard/stats')
@role_required('admin')
def dashboard_spa_stats():
    from app.routes.main import _render_spa

    return _render_spa()


@dashboard.route('/dashboard/graph')
@role_required('admin')
def dashboard_spa_graph():
    """独立图谱页已并入首页：旧链接重定向到首页并聚焦图谱区域。"""
    return redirect('/?focus=graph')


@dashboard.route('/dashboard/alerts')
@role_required('admin')
def alerts():
    alerts = Alert.query.filter_by(is_active=True).order_by(Alert.created_at.desc()).all()
    return render_template('dashboard/alerts.html', alerts=alerts)


@dashboard.route('/dashboard/api/graph-data')
@role_required('admin')
def graph_data():
    """
    返回 Neo4j 产业链图。默认限制规模以控制延迟；?full=1 可全量（慎用）。
    ?max_nodes=&max_links= 可覆盖默认上限。
    """
    try:
        full = request.args.get('full', '').lower() in ('1', 'true', 'yes')
        max_nodes = request.args.get('max_nodes', type=int)
        max_links = request.args.get('max_links', type=int)
        if full:
            nodes, links = get_full_graph(
                max_nodes=max_nodes,
                max_links=max_links,
            )
        else:
            mn = max_nodes if max_nodes is not None and max_nodes > 0 else 500
            ml = max_links if max_links is not None and max_links > 0 else 1500
            nodes, links = get_full_graph(max_nodes=mn, max_links=ml)
        return jsonify({'nodes': nodes, 'links': links})
    except Exception as e:
        return jsonify({'error': str(e), 'nodes': [], 'links': []})


@dashboard.route('/dashboard/api/stats')
@role_required('admin')
def api_stats():
    enterprise_count = Enterprise.query.count()
    supply_count = Inquiry.query.filter(
        Inquiry.direction == "supply", Inquiry.status.in_(("open", "active"))
    ).count()
    demand_count = Inquiry.query.filter(
        Inquiry.direction == "demand", Inquiry.status.in_(("open", "active"))
    ).count()
    alert_count = Alert.query.filter_by(is_active=True).count()

    return jsonify({
        'enterprise_count': enterprise_count,
        'supply_count': supply_count,
        'demand_count': demand_count,
        'alert_count': alert_count
    })


@dashboard.route('/dashboard/api/alerts')
@role_required('admin')
def api_alerts():
    alerts = Alert.query.filter_by(is_active=True).order_by(Alert.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': a.id,
        'product_name': a.product_name,
        'message': a.message,
        'level': a.level,
        'dimension': a.dimension,
        'suggestion': getattr(a, 'suggestion', None),
        'created_at': a.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for a in alerts])


@dashboard.route('/dashboard/api/graph-pagerank')
@role_required('admin')
def api_graph_pagerank():
    """图算法：PageRank 关键产品节点"""
    try:
        data = pagerank_products(top_k=15)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@dashboard.route('/dashboard/api/graph-communities')
@role_required('admin')
def api_graph_communities():
    """图算法：社区发现（产业链集群）"""
    try:
        data = community_detection()
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@dashboard.route('/dashboard/api/forecast')
@role_required('admin')
def api_forecast():
    """时序预测：供需趋势"""
    try:
        data = forecast_supply_demand(horizon=6)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)})


@dashboard.route('/dashboard/api/run-alerts', methods=['POST'])
@role_required('admin')
def run_alerts():
    try:
        alerts = run_all_checks()
        return jsonify({'success': True, 'count': len(alerts)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def _threshold_payload():
    return {
        'import_threshold': float(get_threshold('import', 0.6)),
        'interprovincial_threshold': float(get_threshold('interprovincial', 0.7)),
        'local_threshold': int(get_threshold('local', 3)),
    }


@dashboard.route('/dashboard/api/thresholds', methods=['GET'])
@role_required('admin')
def api_thresholds_get():
    return jsonify({'success': True, **_threshold_payload()})


@dashboard.route('/dashboard/api/thresholds', methods=['POST'])
@role_required('admin')
def api_thresholds_post():
    data = request.get_json(silent=True) or {}
    mapping = [
        ('import', 'import_threshold', float, (0.0, 1.0)),
        ('interprovincial', 'interprovincial_threshold', float, (0.0, 1.0)),
        ('local', 'local_threshold', int, (1, 20)),
    ]
    for dim, key, caster, (lo, hi) in mapping:
        if key not in data:
            continue
        try:
            v = caster(data[key])
            if v < lo or v > hi:
                continue
            DEFAULT_ALERT_THRESHOLDS[dim] = float(v) if dim != "local" else int(v)
        except (TypeError, ValueError):
            pass
    return jsonify({'success': True, **_threshold_payload()})


@dashboard.route('/dashboard/settings/thresholds', methods=['GET'])
def threshold_settings():
    """旧独立页已废弃：统一进入 SPA 首页内的预警设置模块。"""
    return redirect('/?view=thresholds')


@dashboard.route('/dashboard/report')
@role_required('admin')
def download_report():
    """下载补链风险报告"""
    from datetime import datetime
    report = generate_chain_risk_report()
    buf = io.BytesIO(report.encode('utf-8'))
    fname = f'补链风险报告_{datetime.now().strftime("%Y%m%d_%H%M")}.md'
    return send_file(buf, as_attachment=True, download_name=fname, mimetype='text/markdown')


# ---------------------------------------------------------------------------
# SPA 通配：与 @bp.route('/dashboard/', ...) + @bp.route('/dashboard/<path:path>') 等价
# （另注册 /dashboard 无尾斜杠，避免重定向丢参）
# ---------------------------------------------------------------------------
@dashboard.route('/dashboard', defaults={'path': ''}, strict_slashes=False)
@dashboard.route('/dashboard/<path:path>', strict_slashes=False)
@login_required
def dashboard_spa(path):
    from app.routes.main import _render_spa

    if _dashboard_spa_segment_excluded(path):
        abort(404)
    return _render_spa()
