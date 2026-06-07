"""
链易配 Mock API — 无需数据库的演示/开发接口

所有端点返回逼真的模拟数据，带可配置延迟（500-1000ms）以测试前端加载状态。
注册于 /mock/api/ 前缀，不与正式接口冲突。

端点清单：
  GET  /mock/api/match-results?keyword=xxx    匹配企业列表(五维得分)
  POST /mock/api/chat-adjust                  AI对话调权 + 重排
  GET  /mock/api/docs                         交互式接口文档
"""

import time
import random
from flask import Blueprint, request, jsonify, render_template_string

mock_api = Blueprint('mock_api', __name__)

# ── 默认权重 ─────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    'product':  0.30,
    'distance': 0.20,
    'capacity': 0.15,
    'tech':     0.15,
    'history':  0.20,
}

# ── 模拟企业数据库 ─────────────────────────────────────────
MOCK_COMPANIES = [
    {
        'id': 'c001',
        'name': '成都精密机械制造有限公司',
        'address': '四川省成都市高新区天府大道888号',
        'contact': '张经理', 'phone': '028-8888-1001',
        'credit_score': 92, 'capacity': 95,
        'patent_count': 5,
        'tags': ['电机', '减速器', '精密加工', '数控机床', '通用设备'],
        'dims': {
            'product':  {'score': 95, 'desc': '产品名称+行业编码完全匹配'},
            'distance': {'score': 88, 'desc': '12.5km · 近距离'},
            'capacity': {'score': 98, 'desc': '产能95，富余60%'},
            'tech':     {'score': 82, 'desc': '5项专利、3个技术领域'},
            'history':  {'score': 75, 'desc': '合作过3次'},
        },
    },
    {
        'id': 'c002',
        'name': '深圳芯联电子科技股份有限公司',
        'address': '广东省深圳市南山区科技园南路66号',
        'contact': '李总', 'phone': '0755-2666-2002',
        'credit_score': 88, 'capacity': 80,
        'patent_count': 12,
        'tags': ['电路板', 'PCB', '芯片封装', '电子元器件', 'SMT'],
        'dims': {
            'product':  {'score': 90, 'desc': '产品名称匹配'},
            'distance': {'score': 40, 'desc': '1850km · 远距离'},
            'capacity': {'score': 85, 'desc': '产能80，富余35%'},
            'tech':     {'score': 96, 'desc': '12项专利、5个技术领域'},
            'history':  {'score': 50, 'desc': '合作过1次'},
        },
    },
    {
        'id': 'c003',
        'name': '重庆恒力特种钢材有限公司',
        'address': '重庆市九龙坡区西彭工业园区A栋',
        'contact': '王工', 'phone': '023-6543-3003',
        'credit_score': 85, 'capacity': 120,
        'patent_count': 2,
        'tags': ['特种钢材', '不锈钢', '合金钢', '钢板', '黑色金属'],
        'dims': {
            'product':  {'score': 85, 'desc': '产品名称匹配'},
            'distance': {'score': 65, 'desc': '320km · 中距离'},
            'capacity': {'score': 100, 'desc': '产能120，富余100%'},
            'tech':     {'score': 45, 'desc': '2项专利'},
            'history':  {'score': 0,  'desc': '无合作记录'},
        },
    },
    {
        'id': 'c004',
        'name': '武汉光谷激光装备有限公司',
        'address': '湖北省武汉市东湖高新区光谷大道77号',
        'contact': '陈博士', 'phone': '027-8765-4004',
        'credit_score': 95, 'capacity': 60,
        'patent_count': 18,
        'tags': ['激光设备', '光学仪器', '精密仪表', '激光切割', '专用设备'],
        'dims': {
            'product':  {'score': 70, 'desc': '行业编码匹配'},
            'distance': {'score': 55, 'desc': '980km · 中距离'},
            'capacity': {'score': 62, 'desc': '产能60，缺口15%'},
            'tech':     {'score': 100, 'desc': '18项专利、8个技术领域、行业编码一致'},
            'history':  {'score': 100, 'desc': '深度合作5次'},
        },
    },
    {
        'id': 'c005',
        'name': '绵阳精工汽车零部件有限公司',
        'address': '四川省绵阳市经开区南湖路200号',
        'contact': '刘厂长', 'phone': '0816-2233-5005',
        'credit_score': 78, 'capacity': 70,
        'patent_count': 3,
        'tags': ['汽车零部件', '发动机配件', '变速箱', '汽车制造', '压铸件'],
        'dims': {
            'product':  {'score': 80, 'desc': '产品名称匹配'},
            'distance': {'score': 100, 'desc': '8.2km · 同城'},
            'capacity': {'score': 72, 'desc': '产能70，富余5%'},
            'tech':     {'score': 55, 'desc': '3项专利、2个技术领域'},
            'history':  {'score': 0,  'desc': '无合作记录'},
        },
    },
    {
        'id': 'c006',
        'name': '苏州纳微新材料科技有限公司',
        'address': '江苏省苏州市工业园区星湖街328号',
        'contact': '赵总监', 'phone': '0512-6789-6006',
        'credit_score': 90, 'capacity': 45,
        'patent_count': 8,
        'tags': ['新材料', '碳纤维', '复合材料', '纳米涂层', '高分子'],
        'dims': {
            'product':  {'score': 55, 'desc': '关联产品匹配'},
            'distance': {'score': 35, 'desc': '1600km · 远距离'},
            'capacity': {'score': 48, 'desc': '产能45，缺口30%'},
            'tech':     {'score': 88, 'desc': '8项专利、4个技术领域'},
            'history':  {'score': 75, 'desc': '合作过3次'},
        },
    },
    {
        'id': 'c007',
        'name': '佛山市南海铝业集团有限公司',
        'address': '广东省佛山市南海区狮山镇工业大道1号',
        'contact': '黄副总', 'phone': '0757-8899-7007',
        'credit_score': 82, 'capacity': 200,
        'patent_count': 1,
        'tags': ['铝型材', '铝合金', '门窗型材', '工业铝材', '金属制品'],
        'dims': {
            'product':  {'score': 60, 'desc': '关联产品匹配'},
            'distance': {'score': 42, 'desc': '1400km · 远距离'},
            'capacity': {'score': 100, 'desc': '产能200，富余100%'},
            'tech':     {'score': 30, 'desc': '1项专利'},
            'history':  {'score': 50, 'desc': '合作过1次'},
        },
    },
    {
        'id': 'c008',
        'name': '德阳东方电气配套有限公司',
        'address': '四川省德阳市旌阳区天山路128号',
        'contact': '孙经理', 'phone': '0838-2255-8008',
        'credit_score': 87, 'capacity': 85,
        'patent_count': 6,
        'tags': ['电气设备', '发电机组', '变压器', '电气机械', '输配电'],
        'dims': {
            'product':  {'score': 88, 'desc': '产品名称匹配'},
            'distance': {'score': 92, 'desc': '15km · 近距离'},
            'capacity': {'score': 88, 'desc': '产能85，富余40%'},
            'tech':     {'score': 72, 'desc': '6项专利、3个技术领域'},
            'history':  {'score': 100, 'desc': '深度合作6次'},
        },
    },
    {
        'id': 'c009',
        'name': '宁波海天注塑科技有限公司',
        'address': '浙江省宁波市北仑区大碶街道海天路88号',
        'contact': '周工程师', 'phone': '0574-8677-9009',
        'credit_score': 93, 'capacity': 110,
        'patent_count': 15,
        'tags': ['注塑机', '模具', '塑料制品', '专用设备', '精密模具'],
        'dims': {
            'product':  {'score': 75, 'desc': '行业编码匹配'},
            'distance': {'score': 30, 'desc': '1800km · 远距离'},
            'capacity': {'score': 95, 'desc': '产能110，富余80%'},
            'tech':     {'score': 92, 'desc': '15项专利、6个技术领域'},
            'history':  {'score': 0,  'desc': '无合作记录'},
        },
    },
    {
        'id': 'c010',
        'name': '乐山金力达电缆有限公司',
        'address': '四川省乐山市市中区肖坝路66号',
        'contact': '吴厂长', 'phone': '0833-2100-0010',
        'credit_score': 75, 'capacity': 90,
        'patent_count': 0,
        'tags': ['电缆', '电线', '光缆', '铜线', '电气机械'],
        'dims': {
            'product':  {'score': 65, 'desc': '关联产品匹配'},
            'distance': {'score': 85, 'desc': '28km · 近距离'},
            'capacity': {'score': 90, 'desc': '产能90，富余50%'},
            'tech':     {'score': 0,  'desc': '暂无技术数据'},
            'history':  {'score': 50, 'desc': '合作过1次'},
        },
    },
]

# ── 意图识别规则 ──────────────────────────────────────────
INTENT_TABLE = [
    {
        'keywords': ['距离近', '近一点', '近的', '同城', '本地', '附近'],
        'action': 'boost_distance',
        'delta': {'distance': 0.20},
        'reply': '好的，已优先考虑距离因素，为您重新排序。距离近的供应商会排在前面。',
    },
    {
        'keywords': ['便宜', '价格低', '性价比', '成本', '省钱', '实惠'],
        'action': 'boost_cost',
        'delta': {'capacity': 0.15, 'product': -0.05},
        'reply': '好的，已优先推荐产能充足、通常报价更优的供应商。',
    },
    {
        'keywords': ['急单', '加急', '紧急', '赶工', '快速交付', '着急'],
        'action': 'boost_urgent',
        'delta': {'capacity': 0.20},
        'reply': '好的，已筛选产能较高、能接急单的供应商，并提升产能权重。',
    },
    {
        'keywords': ['专利', '技术强', '研发', '有专利', '创新', '技术实力'],
        'action': 'boost_tech',
        'delta': {'tech': 0.25},
        'reply': '好的，已优先推荐拥有专利的技术型企业。',
    },
    {
        'keywords': ['大厂', '规模大', '产能大', '量大', '大批量'],
        'action': 'boost_capacity',
        'delta': {'capacity': 0.25},
        'reply': '好的，已优先推荐产能较大的供应商，适合大批量采购。',
    },
    {
        'keywords': ['信誉好', '信用好', '可靠', '靠谱', '信用高'],
        'action': 'boost_credit',
        'delta': {},
        'reply': '好的，已筛选信用评分较高的优质供应商。',
    },
    {
        'keywords': ['合作过', '老供应商', '历史', '熟悉'],
        'action': 'boost_history',
        'delta': {'history': 0.25},
        'reply': '好的，已优先展示有过历史合作记录的供应商。',
    },
    {
        'keywords': ['重置', '恢复默认', '清除', '重新来'],
        'action': 'reset',
        'delta': {},
        'reply': '好的，已恢复为默认匹配权重。',
    },
]


def _simulate_delay():
    time.sleep(random.uniform(0.5, 1.0))


def _match_intent(msg):
    lower = msg.strip().lower()
    for rule in INTENT_TABLE:
        for kw in rule['keywords']:
            if kw in lower:
                return rule
    return None


def _score_and_sort(companies, weights, keyword=None):
    """用当前权重对企业列表重新打分排序，可按关键词过滤。"""
    pool = companies
    if keyword:
        kw = keyword.lower()
        pool = [c for c in companies if any(kw in t for t in c['tags'])]
        if not pool:
            pool = companies

    total_w = sum(weights.values()) or 1.0
    w = {k: v / total_w for k, v in weights.items()}

    results = []
    for c in pool:
        d = c['dims']
        total = (
            d['product']['score']  * w['product']
            + d['distance']['score'] * w['distance']
            + d['capacity']['score'] * w['capacity']
            + d['tech']['score']     * w['tech']
            + d['history']['score']  * w['history']
        )
        reasons = []
        if d['product']['score']  >= 70: reasons.append('产品匹配')
        if d['distance']['score'] >= 70: reasons.append('地理位置相近')
        if d['capacity']['score'] >= 70: reasons.append('产能充足')
        if d['tech']['score']     >= 50: reasons.append('技术领域一致')
        if d['history']['score']  >= 50: reasons.append('曾合作过')

        results.append({
            'id': c['id'],
            'name': c['name'],
            'address': c['address'],
            'contact': c['contact'],
            'phone': c['phone'],
            'credit_score': c['credit_score'],
            'capacity': c['capacity'],
            'score': round(total, 2),
            'distance': float(d['distance']['desc'].split('km')[0]) if 'km' in d['distance']['desc'] else None,
            'reasons': reasons[:3],
            'dimensions': {
                'product':  {'score': d['product']['score'],  'desc': d['product']['desc']},
                'distance': {'score': d['distance']['score'], 'desc': d['distance']['desc']},
                'capacity': {'score': d['capacity']['score'], 'desc': d['capacity']['desc']},
                'tech':     {'score': d['tech']['score'],     'desc': d['tech']['desc']},
                'history':  {'score': d['history']['score'],  'desc': d['history']['desc']},
            },
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@mock_api.route('/api/match-results', methods=['GET'])
def match_results():
    """GET /mock/api/match-results?keyword=电机&delay=1

    返回匹配企业列表。keyword 用于在 tags 中模糊筛选，
    不传则返回全部 10 家企业。delay=0 可跳过模拟延迟。
    """
    keyword = request.args.get('keyword', '').strip()
    skip_delay = request.args.get('delay', '1') == '0'

    if not skip_delay:
        _simulate_delay()

    results = _score_and_sort(MOCK_COMPANIES, DEFAULT_WEIGHTS, keyword or None)
    return jsonify({
        'success': True,
        'keyword': keyword,
        'count': len(results),
        'weights': {k: round(v * 100) for k, v in DEFAULT_WEIGHTS.items()},
        'results': results,
    })


@mock_api.route('/api/chat-adjust', methods=['POST'])
def chat_adjust():
    """POST /mock/api/chat-adjust

    请求体：
      { "message": "距离近的", "currentWeights": {...}, "keyword": "电机" }

    返回：
      { "reply": "...", "action": "...", "adjustedWeights": {...},
        "weightsRaw": {...}, "newResults": [...], "local_resort": bool }
    """
    data = request.get_json() or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'error': '请输入内容'}), 400

    current = data.get('currentWeights') or dict(DEFAULT_WEIGHTS)
    keyword = data.get('keyword', '').strip()

    _simulate_delay()

    rule = _match_intent(msg)

    if rule and rule['action'] == 'reset':
        new_weights = dict(DEFAULT_WEIGHTS)
        reply = rule['reply']
        action = 'reset'
    elif rule:
        new_weights = dict(current)
        for k, v in rule['delta'].items():
            new_weights[k] = max(0.05, new_weights.get(k, 0.15) + v)
        reply = rule['reply']
        action = rule['action']
    else:
        new_weights = dict(current)
        action = None
        reply = (
            '我是链易配AI助手，可以帮您调整匹配偏好。试试对我说：\n'
            '• "距离近的" — 优先附近供应商\n'
            '• "便宜一点" — 性价比优先\n'
            '• "能接急单" — 筛选产能充足企业\n'
            '• "有专利的" — 优先技术型企业\n'
            '• "合作过的" — 优先历史合作伙伴\n'
            '• "信誉好的" — 筛选高信用企业\n'
            '• "重置" — 恢复默认权重'
        )

    total_w = sum(new_weights.values()) or 1.0
    weights_pct = {k: round(v / total_w * 100) for k, v in new_weights.items()}
    weights_raw = {k: round(v / total_w, 4) for k, v in new_weights.items()}

    results = _score_and_sort(MOCK_COMPANIES, new_weights, keyword or None)

    return jsonify({
        'success': True,
        'reply': reply,
        'action': action,
        'adjustedWeights': weights_pct,
        'weightsRaw': weights_raw,
        'newResults': results,
        'local_resort': False,
        # 兼容正式接口字段名
        'weights': weights_pct,
        'weights_raw': weights_raw,
        'results': results,
    })


@mock_api.route('/api/company/<company_id>', methods=['GET'])
def company_detail(company_id):
    """GET /mock/api/company/c001  — 单个企业详情"""
    for c in MOCK_COMPANIES:
        if c['id'] == company_id:
            return jsonify({'success': True, 'company': c})
    return jsonify({'success': False, 'error': '企业不存在'}), 404


# ═══════════════════════════════════════════════════════════
#  API DOCS PAGE
# ═══════════════════════════════════════════════════════════

DOCS_HTML = r'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mock API 文档 - 链易配</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.0/font/bootstrap-icons.css" rel="stylesheet">
<style>
body { background: #f5f6fa; }
.api-card { border-radius: 12px; border: none; box-shadow: 0 2px 8px rgba(0,0,0,.06); margin-bottom: 1.5rem; }
.method-badge { font-size: .75rem; padding: 3px 10px; border-radius: 6px; font-weight: 600; }
.method-get  { background: #e8f5e9; color: #2e7d32; }
.method-post { background: #e3f2fd; color: #1565c0; }
pre { background: #1e1e2e; color: #cdd6f4; border-radius: 10px; padding: 1rem; font-size: .82rem; overflow-x: auto; }
.try-btn { border-radius: 20px; font-size: .8rem; }
#response-output { min-height: 120px; max-height: 400px; overflow: auto; }
.hero { background: linear-gradient(135deg,#667eea,#764ba2); color: #fff; border-radius: 16px; padding: 2rem; margin-bottom: 2rem; }
</style>
</head>
<body>
<div class="container py-4" style="max-width:900px">

<div class="hero">
  <h3><i class="bi bi-plug"></i> 链易配 Mock API</h3>
  <p class="mb-1 opacity-75">无需数据库的模拟接口 · 用于前端开发 & 答辩演示</p>
  <small class="opacity-50">基地址: <code style="color:#ffd;background:rgba(255,255,255,.15);padding:2px 8px;border-radius:4px">/mock/api</code> · 延迟 500-1000ms</small>
</div>

<!-- EP1 -->
<div class="card api-card">
<div class="card-body">
  <div class="d-flex align-items-center gap-2 mb-2">
    <span class="method-badge method-get">GET</span>
    <code class="fs-6">/mock/api/match-results</code>
  </div>
  <p class="text-muted small mb-2">根据关键词返回匹配企业列表（含五维得分）。10 家模拟企业，按综合得分降序。</p>
  <table class="table table-sm small mb-3">
    <thead><tr><th>参数</th><th>类型</th><th>说明</th></tr></thead>
    <tbody>
      <tr><td><code>keyword</code></td><td>string</td><td>产品关键词（可选），如 "电机"、"钢材"</td></tr>
      <tr><td><code>delay</code></td><td>0|1</td><td>设为 0 跳过模拟延迟（默认 1）</td></tr>
    </tbody>
  </table>
  <button class="btn btn-sm btn-outline-primary try-btn" onclick="tryApi('/mock/api/match-results?keyword=电机&delay=0')">
    <i class="bi bi-play-fill"></i> 试一试
  </button>
</div>
</div>

<!-- EP2 -->
<div class="card api-card">
<div class="card-body">
  <div class="d-flex align-items-center gap-2 mb-2">
    <span class="method-badge method-post">POST</span>
    <code class="fs-6">/mock/api/chat-adjust</code>
  </div>
  <p class="text-muted small mb-2">AI 对话调权：发送自然语言偏好，返回调整后的权重与重新排序的企业列表。</p>
  <p class="small mb-1"><b>请求体 (JSON):</b></p>
<pre>{
  "message": "距离近的",
  "keyword": "电机",
  "currentWeights": {
    "product": 0.30, "distance": 0.20,
    "capacity": 0.15, "tech": 0.15, "history": 0.20
  }
}</pre>
  <p class="small mt-2 mb-1"><b>支持的意图关键词:</b></p>
  <div class="d-flex flex-wrap gap-1 mb-3">
    <span class="badge bg-light text-dark border">距离近</span>
    <span class="badge bg-light text-dark border">便宜</span>
    <span class="badge bg-light text-dark border">急单</span>
    <span class="badge bg-light text-dark border">有专利</span>
    <span class="badge bg-light text-dark border">大厂</span>
    <span class="badge bg-light text-dark border">信誉好</span>
    <span class="badge bg-light text-dark border">合作过</span>
    <span class="badge bg-light text-dark border">重置</span>
  </div>
  <button class="btn btn-sm btn-outline-primary try-btn" onclick="tryChatApi()">
    <i class="bi bi-play-fill"></i> 试一试 (距离近)
  </button>
</div>
</div>

<!-- EP3 -->
<div class="card api-card">
<div class="card-body">
  <div class="d-flex align-items-center gap-2 mb-2">
    <span class="method-badge method-get">GET</span>
    <code class="fs-6">/mock/api/company/{id}</code>
  </div>
  <p class="text-muted small mb-2">获取单个企业的完整模拟数据。ID 范围: c001 ~ c010。</p>
  <button class="btn btn-sm btn-outline-primary try-btn" onclick="tryApi('/mock/api/company/c001?delay=0')">
    <i class="bi bi-play-fill"></i> 试一试 (c001)
  </button>
</div>
</div>

<!-- Response -->
<div class="card api-card">
<div class="card-header bg-white"><i class="bi bi-terminal"></i> 响应预览</div>
<div class="card-body p-0">
  <pre id="response-output" class="m-0 rounded-0 rounded-bottom" style="min-height:150px">点击上方 "试一试" 查看返回数据…</pre>
</div>
</div>

<!-- Data Schema -->
<div class="card api-card">
<div class="card-body">
  <h6><i class="bi bi-braces"></i> 单条企业数据结构</h6>
<pre>{
  "id": "c001",
  "name": "成都精密机械制造有限公司",
  "address": "四川省成都市高新区天府大道888号",
  "contact": "张经理",
  "phone": "028-8888-1001",
  "credit_score": 92,
  "capacity": 95,
  "score": 89.35,
  "distance": 12.5,
  "reasons": ["产品匹配", "地理位置相近", "产能充足"],
  "dimensions": {
    "product":  { "score": 95, "desc": "产品名称+行业编码完全匹配" },
    "distance": { "score": 88, "desc": "12.5km · 近距离" },
    "capacity": { "score": 98, "desc": "产能95，富余60%" },
    "tech":     { "score": 82, "desc": "5项专利、3个技术领域" },
    "history":  { "score": 75, "desc": "合作过3次" }
  }
}</pre>
</div>
</div>

</div>

<script>
var out = document.getElementById('response-output');
function tryApi(url) {
  out.textContent = '请求中…';
  fetch(url).then(r => r.json()).then(d => {
    out.textContent = JSON.stringify(d, null, 2);
  }).catch(e => { out.textContent = '错误: ' + e.message; });
}
function tryChatApi() {
  out.textContent = '请求中…';
  fetch('/mock/api/chat-adjust', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      message: '距离近的',
      keyword: '电机',
      currentWeights: {product:.3,distance:.2,capacity:.15,tech:.15,history:.2}
    })
  }).then(r => r.json()).then(d => {
    out.textContent = JSON.stringify(d, null, 2);
  }).catch(e => { out.textContent = '错误: ' + e.message; });
}
</script>
</body>
</html>
'''


@mock_api.route('/docs')
def docs():
    """交互式 API 文档页面"""
    return render_template_string(DOCS_HTML)


# ═══════════════════════════════════════════════════════════
#  E-CONTRACT MOCK API
# ═══════════════════════════════════════════════════════════

@mock_api.route('/api/econtract/contract/create', methods=['POST'])
def mock_econtract_create():
    """模拟电子合同生成"""
    data = request.get_json() or {}
    _simulate_delay()
    
    buyer_id = data.get('buyer', {}).get('id')
    seller_id = data.get('seller', {}).get('id')
    
    if not buyer_id or not seller_id:
        return jsonify({'error': '买卖方信息不完整'}), 400
    
    # 生成模拟合同ID
    import time
    timestamp = int(time.time())
    contract_id = f"CT-{buyer_id}-{seller_id}-{timestamp}"
    
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'status': 'pending',
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    })


@mock_api.route('/api/econtract/contract/sign', methods=['POST'])
def mock_econtract_sign():
    """模拟合同签署"""
    data = request.get_json() or {}
    _simulate_delay()
    
    contract_id = data.get('contract_id')
    if not contract_id:
        return jsonify({'error': '合同ID不能为空'}), 400
    
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'status': 'signed',
        'signed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
    })


@mock_api.route('/api/econtract/contract/status', methods=['POST'])
def mock_econtract_status():
    """模拟查询合同状态"""
    data = request.get_json() or {}
    _simulate_delay()
    
    contract_id = data.get('contract_id')
    if not contract_id:
        return jsonify({'error': '合同ID不能为空'}), 400
    
    # 模拟状态：根据合同ID的哈希值决定状态
    import hashlib
    hash_val = int(hashlib.md5(contract_id.encode()).hexdigest()[:8], 16)
    
    if hash_val % 3 == 0:
        status = 'signed'
    elif hash_val % 3 == 1:
        status = 'pending'
    else:
        status = 'fulfilled'
    
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'status': status,
    })


@mock_api.route('/api/econtract/contract/details', methods=['POST'])
def mock_econtract_details():
    """模拟获取合同详情"""
    data = request.get_json() or {}
    _simulate_delay()
    
    contract_id = data.get('contract_id')
    if not contract_id:
        return jsonify({'error': '合同ID不能为空'}), 400
    
    # 从合同ID解析买卖方信息
    parts = contract_id.split('-')
    if len(parts) >= 3:
        buyer_id = int(parts[1])
        seller_id = int(parts[2])
    else:
        buyer_id = 1
        seller_id = 2
    
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'buyer_id': buyer_id,
        'seller_id': seller_id,
        'product_name': '精密轴承',
        'amount_range': '10-50万',
        'status': 'signed',
    })


@mock_api.route('/api/econtract/contract/download', methods=['POST'])
def mock_econtract_download():
    """模拟合同下载"""
    data = request.get_json() or {}
    _simulate_delay()
    
    contract_id = data.get('contract_id')
    if not contract_id:
        return jsonify({'error': '合同ID不能为空'}), 400
    
    # 返回模拟的下载URL
    return jsonify({
        'success': True,
        'contract_id': contract_id,
        'download_url': f'/mock/api/econtract/download/{contract_id}.pdf',
    })
