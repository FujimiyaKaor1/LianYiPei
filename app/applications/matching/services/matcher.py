from app.models import Enterprise, Product, Transaction
from app import db
from sqlalchemy import or_
from geopy.distance import geodesic
import math
import json
import re
from typing import Optional, Tuple, Dict, Any, List
import threading

import app.services.map_service as map_service

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    # 仅用于类型检查，运行时在 match_suppliers 中懒加载，避免循环导入
    from app.services.ranking_model import extract_features, predict_score


def _calc_product_score(supplier, products, demand_product, demand_industry_code):
    """产品匹配度：基于产品目录名称和行业编码双重匹配，满分100"""
    matched = [p for p in products if p.enterprise_id == supplier.id]
    if not matched:
        return 0, '无匹配产品'

    def _text_hit(p):
        if not demand_product:
            return False
        if demand_product in p.name:
            return True
        cat = getattr(p, "category", None) or ""
        return bool(cat and demand_product in cat)

    name_hit = any(_text_hit(p) for p in matched) if demand_product else False
    code_hit = any(demand_industry_code and p.industry_code == demand_industry_code for p in matched) if demand_industry_code else False

    if name_hit and code_hit:
        return 100, '产品名称+行业编码完全匹配'
    if name_hit:
        return 85, '产品名称匹配'
    if code_hit:
        return 70, '行业编码匹配'
    return 55, '关联产品匹配'


def _calc_distance_score(distance_km: Optional[float]) -> float:
    """
    根据真实的物理距离（公里）计算距离匹配度得分 (0-100)
    衰减策略：
    - 50公里以内（同城/临近）：100分满分
    - 50~300公里（省内/邻省）：80~100分平滑衰减
    - 300~1000公里（跨区域）：40~80分中度衰减
    - 1000公里以上（长途物流）：0~40分重度衰减
    """
    if distance_km is None or distance_km < 0:
        return 60.0  # 测距失败兜底

    if distance_km <= 50:
        return 100.0
    elif distance_km <= 300:
        return 100.0 - ((distance_km - 50) / 250.0) * 20.0
    elif distance_km <= 1000:
        return 80.0 - ((distance_km - 300) / 700.0) * 40.0
    else:
        return max(0.0, 40.0 - ((distance_km - 1000) / 1000.0) * 40.0)


def _buyer_coord_dict(demand_location: Optional[Dict], buyer: Optional[Enterprise]) -> Optional[Dict[str, float]]:
    """需求侧坐标：优先请求里的 lat/lng，否则已登录买方企业库内坐标。"""
    if demand_location is not None:
        lat = demand_location.get("lat")
        lng = demand_location.get("lng")
        if lat is not None and lng is not None:
            try:
                return {"longitude": float(lng), "latitude": float(lat)}
            except (TypeError, ValueError):
                pass
    if buyer is not None and buyer.latitude is not None and buyer.longitude is not None:
        try:
            return {"longitude": float(buyer.longitude), "latitude": float(buyer.latitude)}
        except (TypeError, ValueError):
            pass
    return None


def _resolve_distance_km(
    demand_location: Optional[Dict],
    supplier: Enterprise,
    buyer: Optional[Enterprise],
) -> Optional[float]:
    """
    优先高德驾车距离（米→公里）；失败或未配置 Key 时回退球面大圆距离（公里）。
    """
    coord1 = _buyer_coord_dict(demand_location, buyer)
    if not coord1 or supplier.latitude is None or supplier.longitude is None:
        return None
    try:
        coord2: Dict[str, float] = {
            "longitude": float(supplier.longitude),
            "latitude": float(supplier.latitude),
        }
        r: Dict[str, Any] = map_service.calculate_distance(coord1, coord2, mode="driving")
        m = r.get("meters")
        if m is not None:
            return round(float(m) / 1000.0, 4)
    except Exception:
        pass
    try:
        return round(
            geodesic(
                (coord1["latitude"], coord1["longitude"]),
                (float(supplier.latitude), float(supplier.longitude)),
            ).km,
            4,
        )
    except Exception:
        return None


def _distance_desc_from_km(dist_km: Optional[float]) -> str:
    if dist_km is None:
        return "未提供位置信息"
    d = round(dist_km, 2)
    if d <= 50:
        tag = "同城/临近"
    elif d <= 300:
        tag = "省内/邻省"
    elif d <= 1000:
        tag = "跨区域"
    else:
        tag = "长途"
    mode_note = "驾车/路网优先"
    return f"{d}km · {tag}（{mode_note}）"


def _compute_distance_dimension(
    demand_location: Optional[Dict],
    supplier: Enterprise,
    buyer: Optional[Enterprise],
) -> Tuple[float, str, Optional[float]]:
    """距离维度：(0~100 分, 说明, 公里数)。"""
    dist_km = _resolve_distance_km(demand_location, supplier, buyer)
    if dist_km is None:
        return 60.0, "未提供位置信息", None
    score = _calc_distance_score(dist_km)
    return score, _distance_desc_from_km(dist_km), dist_km


def get_capacity_signal(supplier) -> dict:
    """
    计算供应商产能信号。
    需求: 17.1, 17.2, 17.3, 17.4, 17.5, 17.7

    返回:
        {
            'utilization_rate': float | None,  # 0.0-1.0，None 表示未授权
            'label': str,                       # '产能充足' / '产能正常' / '产能紧张' / '未公开'
            'color': str,                       # 'success' / 'warning' / 'danger' / 'secondary'
            'icon': str,                        # Bootstrap icon class
            'bargaining_hint': str,             # 议价空间提示
            'authorized': bool,                 # 是否已授权产能数据
        }
    """
    max_cap = supplier.max_capacity if supplier.max_capacity is not None else supplier.capacity
    current = supplier.current_orders

    # 未授权产能数据（max_capacity 未设置且 current_orders 为 None）
    if max_cap is None or max_cap <= 0 or current is None:
        return {
            'utilization_rate': None,
            'label': '未公开',
            'color': 'secondary',
            'icon': 'bi-dash-circle',
            'bargaining_hint': '产能数据未公开',
            'authorized': False,
        }

    utilization = min(1.0, current / max_cap)

    if utilization < 0.5:
        return {
            'utilization_rate': round(utilization, 4),
            'label': '产能充足',
            'color': 'success',
            'icon': 'bi-check-circle-fill',
            'bargaining_hint': '议价空间较大',
            'authorized': True,
        }
    elif utilization <= 0.8:
        return {
            'utilization_rate': round(utilization, 4),
            'label': '产能正常',
            'color': 'warning',
            'icon': 'bi-exclamation-circle-fill',
            'bargaining_hint': '议价空间适中',
            'authorized': True,
        }
    else:
        return {
            'utilization_rate': round(utilization, 4),
            'label': '产能紧张',
            'color': 'danger',
            'icon': 'bi-x-circle-fill',
            'bargaining_hint': '议价空间较小',
            'authorized': True,
        }


def _calc_capacity_score(supplier, demand_quantity):
    """产能匹配度：基于可用产能（max_capacity - current_orders）与需求量的匹配程度，满分100"""
    if not demand_quantity or demand_quantity <= 0:
        return 50, '未指定需求量'
    max_cap = supplier.max_capacity if supplier.max_capacity is not None else supplier.capacity
    current = supplier.current_orders or 0
    available = max(0, max_cap - current)
    load_pct = round(current / max_cap * 100) if max_cap > 0 else 0
    load_info = f'该供应商当前负荷为{load_pct}%'
    if available < demand_quantity:
        return 0, f'可用产能{available}不足，需求{demand_quantity}。{load_info}'
    ratio = available / max(1, demand_quantity / 100)
    ratio = min(ratio, 2.0)
    if ratio >= 1.0:
        score = min(100, 70 + ratio * 15)
        return round(score), f'可用产能{available}，富余{round((ratio - 1) * 100)}%。{load_info}'
    score = max(10, ratio * 70)
    return round(score), f'可用产能{available}，缺口{round((1 - ratio) * 100)}%。{load_info}'


_EMBEDDER = None  # 进程内缓存 SentenceTransformer 实例
_EMBEDDER_LOADING = False  # 是否有后台线程正在加载


def _get_embedder():
    """获取 sentence-transformers 模型，用于在线将需求文本向量化。

    注意：
    - 第一次调用会加载 `sentence-transformers/all-MiniLM-L6-v2`，可能稍慢；
    - 后续请求会复用同一个进程内模型，不再重复加载。
    """
    global _EMBEDDER, _EMBEDDER_LOADING
    if _EMBEDDER is not None:
        return _EMBEDDER
    if _EMBEDDER_LOADING:
        # 当前请求不等待模型加载，避免阻塞页面
        return False

    _EMBEDDER_LOADING = True

    def _load():
        global _EMBEDDER, _EMBEDDER_LOADING
        try:
            from sentence_transformers import SentenceTransformer

            _EMBEDDER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        except Exception:
            _EMBEDDER = False
        finally:
            _EMBEDDER_LOADING = False

    threading.Thread(target=_load, daemon=True).start()
    return False


def _encode_text(text: str) -> Optional[list]:
    embedder = _get_embedder()
    if embedder is False:
        return None
    try:
        vec = embedder.encode([text], normalize_embeddings=False)[0]
        try:
            return vec.tolist()
        except Exception:
            return [float(x) for x in vec]
    except Exception:
        return None


def _cosine_similarity(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = 0.0
    na = 0.0
    nb = 0.0
    for i in range(n):
        x = float(a[i])
        y = float(b[i])
        dot += x * y
        na += x * x
        nb += y * y
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / denom))


def _calc_semantic_score(demand_text: str, supplier, products) -> Tuple[float, str]:
    """语义匹配分：将需求文本向量化，与供应产品向量做余弦相似度，返回 0~1。"""
    if not demand_text:
        return 0.0, "未提供需求文本"
    demand_vec = _encode_text(demand_text)
    if demand_vec is None:
        return 0.0, "语义模型不可用"

    matched = [p for p in products if p.enterprise_id == supplier.id]
    best = 0.0
    has_any = False
    for p in matched:
        emb = getattr(p, "embedding", None)
        if not emb:
            continue
        has_any = True
        sim = _cosine_similarity(demand_vec, emb)
        if sim > best:
            best = sim

    if not has_any:
        return 0.0, "供应产品未生成向量"
    return round(best, 4), f"语义相似度{round(best * 100)}%"


def _calc_tech_score(supplier, demand_industry_code):
    """技术匹配度：基于专利数量、技术关键词、行业编码，满分100"""
    score = 0
    details = []

    patent_count = supplier.patent_count or 0
    if patent_count > 0:
        score += min(40, patent_count * 5)
        details.append(f'{patent_count}项专利')

    if supplier.tech_keywords:
        kw_count = len([k for k in supplier.tech_keywords.split(',') if k.strip()])
        score += min(30, kw_count * 6)
        details.append(f'{kw_count}个技术领域')

    if demand_industry_code and supplier.industry_code == demand_industry_code:
        score += 30
        details.append('行业编码一致')

    score = min(100, score)
    desc = '、'.join(details) if details else '暂无技术数据'
    return score, desc


def _batch_history_counts(demand_ent_id, supplier_ids):
    """批量查询历史合作次数，避免 N+1 查询。返回 {seller_id: count}。"""
    if not demand_ent_id or not supplier_ids:
        return {}
    from sqlalchemy import func
    rows = db.session.query(
        Transaction.seller_id, func.count(Transaction.id)
    ).filter(
        Transaction.buyer_id == demand_ent_id,
        Transaction.seller_id.in_(supplier_ids)
    ).group_by(Transaction.seller_id).all()
    return {seller_id: cnt for seller_id, cnt in rows}


def _history_score_from_count(count):
    """根据合作次数返回 (score, desc)。"""
    if count == 0:
        return 0, '无合作记录'
    if count == 1:
        return 50, '合作过1次'
    if count <= 3:
        return 75, f'合作过{count}次'
    return 100, f'深度合作{count}次'


def _calc_gnn_score(demand_ent_id: int, supplier_id: int) -> Tuple[float, str]:
    """基于GNN嵌入计算企业相似度（0~1）。
    
    使用训练好的HAN+BPR模型生成的企业嵌入，计算需求企业与供应商的余弦相似度。
    """
    if not demand_ent_id:
        return 0.0, '未登录无法计算GNN相似度'
    
    try:
        from app.services.gnn_model import get_enterprise_embedding
        import numpy as np
        
        demand_emb = get_enterprise_embedding(demand_ent_id)
        supplier_emb = get_enterprise_embedding(supplier_id)
        
        if demand_emb is None or supplier_emb is None:
            return 0.0, 'GNN嵌入未生成'
        
        demand_emb = np.asarray(demand_emb, dtype=np.float32)
        supplier_emb = np.asarray(supplier_emb, dtype=np.float32)
        
        demand_norm = demand_emb / (np.linalg.norm(demand_emb) + 1e-12)
        supplier_norm = supplier_emb / (np.linalg.norm(supplier_emb) + 1e-12)
        
        sim = float(np.dot(demand_norm, supplier_norm))
        sim = max(0.0, min(1.0, (sim + 1) / 2))
        
        if sim >= 0.7:
            return sim, f'GNN高相似度{round(sim*100)}%'
        elif sim >= 0.4:
            return sim, f'GNN中等相似度{round(sim*100)}%'
        else:
            return sim, f'GNN相似度{round(sim*100)}%'
    except Exception:
        return 0.0, 'GNN计算异常'


def _calc_green_score(supplier) -> Tuple[float, str]:
    """绿色匹配度：基于绿色工厂认证、清洁能源、碳排放等级、环保专利，满分 100。"""
    score = 0.0
    details = []

    if getattr(supplier, 'is_green_factory', False):
        score += 25
        details.append('绿色工厂')

    certs = getattr(supplier, 'green_certification', None) or []
    if isinstance(certs, list) and certs:
        score += min(20, len(certs) * 10)
        details.append(f'{len(certs)}项绿色认证')

    clean = float(getattr(supplier, 'clean_energy_usage', 0) or 0)
    if clean > 0:
        score += clean * 20  # 0~1 → 0~20
        details.append(f'清洁能源{round(clean * 100)}%')

    level = getattr(supplier, 'carbon_emission_level', None) or ''
    level_map = {'A': 20, 'B': 14, 'C': 8, 'D': 0}
    score += level_map.get(level.upper(), 0)
    if level:
        details.append(f'碳排放{level}级')

    env_patents = int(getattr(supplier, 'environment_protection_patents', 0) or 0)
    if env_patents > 0:
        score += min(15, env_patents * 5)
        details.append(f'{env_patents}项环保专利')

    score = min(100.0, score)
    desc = '、'.join(details) if details else '暂无绿色数据'
    return round(score, 1), desc


def estimate_carbon(supplier, demand_location, demand_quantity) -> dict:
    """估算候选供应商的碳排放（简化模型）。返回 dict 包含 transport_kg / production_kg / total_kg。"""
    transport_kg = 0.0
    production_kg = 0.0

    # 运输碳排放：~0.1 kgCO₂ / (吨·km)，假设每件 50kg
    if demand_location and getattr(supplier, 'latitude', None) and getattr(supplier, 'longitude', None):
        try:
            dist_km = geodesic(
                (demand_location['lat'], demand_location['lng']),
                (supplier.latitude, supplier.longitude)
            ).km
        except Exception:
            dist_km = 200
    else:
        dist_km = 200

    weight_tonnes = (demand_quantity or 100) * 0.05
    transport_kg = round(dist_km * weight_tonnes * 0.1, 2)

    # 生产碳排放：按清洁能源比例衰减基准
    base_per_unit = 2.0  # kgCO₂ / 件 基准
    clean = float(getattr(supplier, 'clean_energy_usage', 0) or 0)
    production_kg = round((demand_quantity or 100) * base_per_unit * (1 - clean * 0.6), 2)

    return {
        'transport_kg': transport_kg,
        'production_kg': production_kg,
        'total_kg': round(transport_kg + production_kg, 2),
        'distance_km': round(dist_km, 2) if dist_km else None,
    }


DEFAULT_WEIGHTS = {
    'product': 0.22,
    'distance': 0.13,
    'capacity': 0.10,
    'semantic': 0.08,
    'tech': 0.07,
    'history': 0.12,
    'gnn': 0.05,
    'credit': 0.08,
    'green': 0.15,
}

GREEN_PRIORITY_WEIGHTS = {
    'product': 0.15,
    'distance': 0.08,
    'capacity': 0.08,
    'semantic': 0.05,
    'tech': 0.05,
    'history': 0.07,
    'gnn': 0.02,
    'credit': 0.05,
    'green': 0.45,
}


def _rewrite_query_with_qwen(query_text: str) -> List[str]:
    """
    使用本地 BizMind（Ollama）对检索词做语义纠错与扩充。
    返回去重后的短语列表（首个元素为主检索词），失败时回退为原词。
    """
    raw = (query_text or "").strip()
    if not raw:
        return []

    prompt = (
        "你是供应链检索词纠错与扩展助手。"
        "请返回 JSON，格式为"
        '{"primary":"主关键词","expansions":["扩展词1","扩展词2","扩展词3"]}。'
        "要求：1) 只返回 JSON；2) 关键词需简短；3) 避免重复。"
    )
    try:
        from app.services.ollama_client import invoke_ollama

        rewritten = (invoke_ollama(prompt, raw) or "").strip()
        if rewritten:
            primary = raw
            expansions: List[str] = []
            try:
                parsed = json.loads(rewritten)
                if isinstance(parsed, dict):
                    primary = str(parsed.get("primary") or raw).strip() or raw
                    exps = parsed.get("expansions") or []
                    if isinstance(exps, list):
                        expansions = [str(x).strip() for x in exps if str(x).strip()]
            except Exception:
                # 兼容模型未按 JSON 返回：按逗号/顿号/空格拆分
                tokens = re.split(r"[，,、\s]+", rewritten.replace("\n", " ").strip())
                expansions = [t.strip() for t in tokens if t.strip()]

            merged = [primary, raw, *expansions]
            dedup: List[str] = []
            for item in merged:
                term = item.strip()
                if not term or term in dedup:
                    continue
                dedup.append(term[:24])
            if dedup:
                return dedup[:6]
    except Exception:
        pass
    return [raw]


def _apply_deep_learning_rerank(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    深度学习二次精排：
    在原有规则分基础上，融合语义向量分和 GNN 分进行重排。
    语义/图谱缺失时不按 0 分惩罚，而作权重重分配或退回规则主导（优雅降级）。
    """
    _EPS = 1e-6
    for row in results:
        dimensions = row.get("dimensions") or {}
        semantic_score = float((dimensions.get("semantic") or {}).get("score") or 0.0)
        gnn_score = float((dimensions.get("gnn") or {}).get("score") or 0.0)
        rule_score = float(row.get("score") or 0.0) / 100.0
        rule_score = max(0.0, min(1.0, rule_score))

        has_sem = semantic_score > _EPS
        has_gnn = gnn_score > _EPS

        if not has_sem and not has_gnn:
            deep_score = rule_score
            explain = (
                "图谱数据稀疏，已降级为专家规则主导引擎 (100%)"
                f" · 规则基线约{round(rule_score * 100)}分"
            )
        elif not has_sem:
            wr, wg = 0.45, 0.20
            z = wr + wg
            wr, wg = wr / z, wg / z
            deep_score = wr * rule_score + wg * gnn_score
            explain = (
                f"语义未触发，权重已重分配：规则{round(wr * 100)}%·GNN{round(wg * 100)}%"
                f" · 示值 规则{round(rule_score * 100)}%·GNN{round(gnn_score * 100)}%"
            )
        elif not has_gnn:
            wr, ws = 0.45, 0.35
            z = wr + ws
            wr, ws = wr / z, ws / z
            deep_score = wr * rule_score + ws * semantic_score
            explain = (
                f"图谱嵌入缺失，权重已重分配：规则{round(wr * 100)}%·语义{round(ws * 100)}%"
                f" · 示值 规则{round(rule_score * 100)}%·语义{round(semantic_score * 100)}%"
            )
        else:
            deep_score = (
                0.45 * rule_score + 0.35 * semantic_score + 0.20 * gnn_score
            )
            explain = (
                f"规则{round(rule_score * 100)}%·语义{round(semantic_score * 100)}%"
                f"·GNN{round(gnn_score * 100)}%"
            )

        row["deep_learning_score"] = round(deep_score, 4)
        row["deep_learning_explain"] = explain
        row["score"] = round(deep_score * 100.0, 2)
        row["total_score"] = row["score"]
        # 大模型推荐理由仅由上游 LLM 填充；勿将算分公式写入 ai_match_reason
        row.pop("ai_match_reason", None)
        row["match_basis"] = "semantic"

    results.sort(
        key=lambda x: (
            x.get("deep_learning_score", 0.0),
            x.get("ranking_score", x.get("score", 0.0) / 100.0),
        ),
        reverse=True,
    )

    # 分数校准器：对“相关”的前3名做线性映射，输出更友好的匹配信心指数
    top3 = results[:3]
    related_rows = [
        row for row in top3
        if float(((row.get("dimensions") or {}).get("semantic") or {}).get("score") or 0.0) >= 0.45
        or "产品匹配" in (row.get("reasons") or [])
    ]
    if related_rows:
        raw_scores = [float(row.get("score") or 0.0) for row in related_rows]
        old_min = min(raw_scores)
        old_max = max(raw_scores)
        new_min, new_max = 85.0, 98.0
        span = old_max - old_min
        for idx, row in enumerate(related_rows):
            raw = float(row.get("score") or 0.0)
            if span < 1e-6:
                # 原始分完全相同：按当前候选顺序拉开梯度，避免映射塌缩到同一常数
                calibrated = 98.0 - (idx * 2.5)
                calibrated = max(new_min, min(new_max, calibrated))
            else:
                calibrated = new_min + (raw - old_min) * (new_max - new_min) / span
            row["confidence_index"] = round(calibrated, 2)
            row["score"] = row["confidence_index"]
            row["total_score"] = row["confidence_index"]
            row["deep_learning_explain"] = (
                f"{row.get('deep_learning_explain', '')} · 已校准为匹配信心指数"
            ).strip(" ·")

    for row in results:
        if "confidence_index" not in row:
            row["confidence_index"] = round(float(row.get("score") or 0.0), 2)
    return results


def match_suppliers(demand_product, demand_location=None, demand_quantity=100, demand_ent_id=None,
                    demand_industry_code=None, sort_by='score', custom_weights=None,
                    filters=None, green_priority=False, weights=None, buyer_id=None,
                    label_types=None, algorithm: str = 'rule'):
    """匹配供应商，返回多维得分明细。
    custom_weights / weights: 可选，dict 覆盖默认权重（weights 为别名，与 custom_weights 同时传入时以 weights 为准）
    buyer_id: 可选，需求方企业 id（与 demand_ent_id 同义；同时传入时以 buyer_id 为准）
    filters: 可选，dict额外筛选条件
    green_priority: 若为 True，使用绿色优先权重
    label_types: 可选，list[str] 按质量标签类型筛选（如 ['government_green', 'lead_inspection']）
    """
    if buyer_id is not None:
        demand_ent_id = buyer_id
    if weights is not None:
        custom_weights = weights
    algorithm = (algorithm or "rule").strip().lower()

    recall_terms: List[str] = []
    if demand_product and str(demand_product).strip():
        recall_terms = [str(demand_product).strip()]
    if algorithm == "deep_learning" and demand_product:
        recall_terms = _rewrite_query_with_qwen(str(demand_product))
        if recall_terms:
            demand_product = recall_terms[0]

    products = []
    # 需求关键字：名称或分类任一包含即召回（ilike 不区分大小写）
    text_patterns: List[str] = []
    for term in recall_terms:
        t = (term or "").strip()
        if t and t not in text_patterns:
            text_patterns.append(f"%{t}%")

    if demand_industry_code:
        if text_patterns:
            term_clauses = []
            for pattern in text_patterns:
                term_clauses.append(Product.name.ilike(pattern))
                term_clauses.append(Product.category.ilike(pattern))
            q = or_(Product.industry_code == demand_industry_code, *term_clauses)
        else:
            q = Product.industry_code == demand_industry_code
        products = Product.query.filter(q).all()

    if not products and text_patterns:
        fallback_clauses = []
        for pattern in text_patterns:
            fallback_clauses.append(Product.name.ilike(pattern))
            fallback_clauses.append(Product.category.ilike(pattern))
        products = Product.query.filter(or_(*fallback_clauses)).all()
    if not products:
        return []

    supplier_ids = list(set([p.enterprise_id for p in products]))
    suppliers = Enterprise.query.filter(Enterprise.id.in_(supplier_ids)).all()

    # 质量标签筛选：需求 18.5
    if label_types:
        try:
            from app.services.quality_label_service import filter_enterprises_by_labels
            filtered_ids = filter_enterprises_by_labels(supplier_ids, label_types, require_all=False)
            suppliers = [s for s in suppliers if s.id in set(filtered_ids)]
        except Exception:
            pass

    weights = dict(GREEN_PRIORITY_WEIGHTS if green_priority else DEFAULT_WEIGHTS)
    if custom_weights:
        weights.update(custom_weights)
        # 绿色优先开关：避免 LLM 返回的部分权重把「绿色」维度冲掉，导致前端 toggle 无效
        if green_priority:
            min_green = float(GREEN_PRIORITY_WEIGHTS.get('green', 0.45)) * 0.85
            weights['green'] = max(float(weights.get('green', 0) or 0), min_green)
        total_w = sum(weights.values())
        if total_w > 0:
            weights = {k: v / total_w for k, v in weights.items()}
    else:
        # 没有外部权重覆盖（例如用户聊天意图），允许 bandit 动态采样权重
        try:
            from app.services.bandit import get_current_match_weights

            weights = get_current_match_weights(weights)
        except Exception:
            pass

    filters = filters or {}

    # 批量预查询历史合作次数（1 次 SQL 代替 N 次）
    history_counts = _batch_history_counts(demand_ent_id, supplier_ids)

    # 需求方企业（用于距离测算：无 lat/lng 请求时可用库内坐标）
    buyer = Enterprise.query.get(demand_ent_id) if demand_ent_id else None

    # 预计算需求向量（只算一次，不是每个供应商各算一次）
    _demand_vec = _encode_text(demand_product) if demand_product else None

    # GNN 向量：预加载需求方向量（只读一次缓存）
    _demand_gnn_emb = None
    if demand_ent_id:
        try:
            from app.services.gnn_model import get_enterprise_embedding
            import numpy as np
            raw = get_enterprise_embedding(demand_ent_id)
            if raw is not None:
                _demand_gnn_emb = np.asarray(raw, dtype=np.float32)
                _demand_gnn_emb = _demand_gnn_emb / (np.linalg.norm(_demand_gnn_emb) + 1e-12)
        except Exception:
            _demand_gnn_emb = None

    results = []
    for supplier in suppliers:
        if filters.get('min_patent') and (supplier.patent_count or 0) < filters['min_patent']:
            continue
        if filters.get('min_capacity') and (supplier.capacity or 0) < filters['min_capacity']:
            continue

        product_score, product_desc = _calc_product_score(supplier, products, demand_product, demand_industry_code)
        distance_score, distance_desc, dist_km = _compute_distance_dimension(
            demand_location, supplier, buyer
        )
        capacity_score, capacity_desc = _calc_capacity_score(supplier, demand_quantity)

        # 语义分：复用预计算的需求向量
        if _demand_vec is not None:
            matched_prods = [p for p in products if p.enterprise_id == supplier.id]
            best_sim = 0.0
            has_emb = False
            for p in matched_prods:
                emb = getattr(p, "embedding", None)
                if emb:
                    has_emb = True
                    sim = _cosine_similarity(_demand_vec, emb)
                    if sim > best_sim:
                        best_sim = sim
            if has_emb:
                semantic_score = round(best_sim, 4)
                semantic_desc = f"语义相似度{round(best_sim * 100)}%"
            else:
                semantic_score, semantic_desc = 0.0, "供应产品未生成向量"
        else:
            semantic_score, semantic_desc = 0.0, "语义模型加载中"

        tech_score, tech_desc = _calc_tech_score(supplier, demand_industry_code)
        history_score, history_desc = _history_score_from_count(history_counts.get(supplier.id, 0))

        # GNN 分：复用预加载的需求方向量
        if _demand_gnn_emb is not None:
            try:
                import numpy as np
                raw_s = get_enterprise_embedding(supplier.id)
                if raw_s is not None:
                    s_emb = np.asarray(raw_s, dtype=np.float32)
                    s_emb = s_emb / (np.linalg.norm(s_emb) + 1e-12)
                    sim_val = float(np.dot(_demand_gnn_emb, s_emb))
                    gnn_score = max(0.0, min(1.0, (sim_val + 1) / 2))
                    gnn_desc = f'GNN相似度{round(gnn_score * 100)}%'
                else:
                    gnn_score, gnn_desc = 0.0, 'GNN嵌入未生成'
            except Exception:
                gnn_score, gnn_desc = 0.0, 'GNN计算异常'
        else:
            gnn_score, gnn_desc = 0.0, 'GNN嵌入未生成'

        credit_score = float(supplier.credit_score or 0.0)
        credit_score = max(0.0, min(100.0, credit_score))

        green_score, green_desc = _calc_green_score(supplier)
        carbon = estimate_carbon(supplier, demand_location, demand_quantity)

        if filters.get('max_distance') and dist_km is not None and dist_km > filters['max_distance']:
            continue
        if filters.get('green_only') and not getattr(supplier, 'is_green_factory', False):
            continue

        total = (
            product_score * weights['product']
            + distance_score * weights['distance']
            + capacity_score * weights['capacity']
            + (semantic_score * 100) * weights['semantic']
            + credit_score * weights['credit']
            + tech_score * weights['tech']
            + history_score * weights['history']
            + (gnn_score * 100) * weights['gnn']
            + green_score * weights.get('green', 0)
        )

        # 质量标签加分：需求 18.5
        label_boost = 0.0
        supplier_label_types: list = []
        try:
            from app.services.quality_label_service import get_label_boost_score, get_enterprise_label_types
            label_boost = get_label_boost_score(supplier.id)
            supplier_label_types = get_enterprise_label_types(supplier.id)
        except Exception:
            pass
        total = min(100.0, total + label_boost)
        # 细粒度 Tie-break：在规则模式下避免加权总分完全一致（信用与 id 连续微扰，不改变业务排序主语义）
        total += float(credit_score) * 0.001 + float(supplier.id % 10000) * 1e-6 + float(supplier.id) * 1e-9

        reasons = []
        if product_score >= 70:
            reasons.append('产品匹配')
        if distance_score >= 70:
            reasons.append('地理位置相近')
        if capacity_score >= 70:
            reasons.append('产能充足')
        if green_score >= 60:
            reasons.append('绿色低碳')
        if semantic_score >= 0.60:
            reasons.append('语义相似')
        if credit_score >= 80:
            reasons.append('信用优质')
        if tech_score >= 50:
            reasons.append('技术领域一致')
        if history_score >= 50:
            reasons.append('曾合作过')

        radar_scores: List[Dict[str, Any]] = [
            {"name": "产品匹配度", "value": round(float(product_score), 1)},
            {"name": "距离匹配度", "value": round(float(distance_score), 1)},
            {"name": "产能匹配度", "value": round(float(capacity_score), 1)},
            {"name": "技术匹配度", "value": round(float(tech_score), 1)},
            {"name": "历史合作度", "value": round(float(history_score), 1)},
        ]

        match_reason = (
            f"该企业主营符合您的需求。距离您约 "
            f"{round(dist_km, 1) if dist_km is not None else '未知'} 公里，"
            f"物流成本{'较低' if distance_score > 80 else '适中'}。"
        )

        result_row = {
            'id': supplier.id,
            'name': supplier.name,
            'enterprise_id': supplier.id,
            'enterprise_name': supplier.name,
            'address': supplier.address,
            'contact': supplier.contact,
            'phone': supplier.phone,
            'credit_score': supplier.credit_score,
            'capacity': supplier.capacity,
            'current_orders': supplier.current_orders,
            'max_capacity': supplier.max_capacity,
            'capacity_signal': get_capacity_signal(supplier),
            'is_green_factory': getattr(supplier, 'is_green_factory', False),
            'carbon_emission_level': getattr(supplier, 'carbon_emission_level', ''),
            'score': round(total, 6),
            'total_score': round(total, 6),
            'distance': dist_km,
            'distance_km': round(dist_km, 2) if dist_km is not None else "未知",
            'radar_scores': radar_scores,
            'match_reason': match_reason,
            'carbon': carbon,
            'reasons': reasons[:4],
            'quality_label_types': supplier_label_types,
            'dimensions': {
                'product':  {'score': product_score,  'desc': product_desc},
                'distance': {'score': distance_score, 'desc': distance_desc},
                'capacity': {'score': capacity_score, 'desc': capacity_desc},
                'green':    {'score': green_score,    'desc': green_desc},
                'semantic': {'score': semantic_score, 'desc': semantic_desc},
                'credit':   {'score': credit_score,   'desc': f'信用分{round(credit_score,2)}'},
                'tech':     {'score': tech_score,     'desc': tech_desc},
                'history':  {'score': history_score,  'desc': history_desc},
                'gnn':      {'score': gnn_score,      'desc': gnn_desc},
            }
        }
        results.append(result_row)

    # --------------------------------------------------------------
    #  可选：使用排序模型（XGBoost）进行精排
    #  1) 先对召回结果进行简单排序，截断为 Top 200
    #  2) 为每个候选提取特征，使用 ranking_model 预测成交概率
    #  3) 使用精排得分排序并截断为 Top 10
    # --------------------------------------------------------------
    if results:
        # 懒加载：避免 matcher <-> ranking_model 循环导入
        try:
            from app.services.ranking_model import extract_features, predict_score
        except Exception:
            extract_features = None
            predict_score = None

        # 个性化偏好（Redis 缓存）
        try:
            from app.services.recommender import (
                get_enterprise_preference_vec,
                personalized_similarity_score,
            )
        except Exception:
            get_enterprise_preference_vec = None
            personalized_similarity_score = None

        # 先按原有综合得分和距离做一个粗排，截断 200
        results.sort(key=lambda x: x['score'], reverse=True)
        candidates = results[:200]

        # 没有训练好的排序模型时跳过精排，避免 Top200 特征提取导致接口超时
        try:
            import os

            model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ranking_model.pkl")
            ranking_model_exists = os.path.exists(model_path)
        except Exception:
            ranking_model_exists = False

        personal_weight = 0.15  # 个性化融合权重（0~1）

        pref_vec = None
        seller_completed_count_map = {}
        if buyer and get_enterprise_preference_vec:
            try:
                pref_vec = get_enterprise_preference_vec(buyer.id)
            except Exception:
                pref_vec = None

            # 批量获取 buyer 的历史成交次数（用于特征中的 history_norm）
            try:
                txns = Transaction.query.filter_by(buyer_id=buyer.id, status='completed').all()
                for t in txns:
                    seller_completed_count_map[t.seller_id] = seller_completed_count_map.get(t.seller_id, 0) + 1
            except Exception:
                seller_completed_count_map = {}

        if (not ranking_model_exists) or extract_features is None or predict_score is None:
            results = candidates[:10]
        else:
            reranked = []
            for row in candidates:
                supplier = Enterprise.query.get(row['id'])
                if not supplier or not buyer:
                    # 若未登录或找不到 buyer，直接沿用原得分
                    row['ranking_score'] = row['score'] / 100.0
                    reranked.append(row)
                    continue

                feats_dict: Dict[str, float] = extract_features(
                    buyer=buyer,
                    supplier=supplier,
                    demand_product_name=demand_product or "",
                    demand_quantity=demand_quantity or 100,
                )
                ranking_prob = predict_score(feats_dict)

                # 将个性化相似度融合到精排得分
                personal_score = 0.0
                if pref_vec is not None and personalized_similarity_score is not None:
                    try:
                        personal_score = personalized_similarity_score(
                            buyer=buyer,
                            supplier=supplier,
                            pref_vec=pref_vec,
                            seller_completed_count=seller_completed_count_map.get(supplier.id, 0),
                        )
                    except Exception:
                        personal_score = 0.0

                # 规则：ranking_prob (0~1) 与 personal_score (0~1) 融合
                fused = (1.0 - personal_weight) * float(ranking_prob) + personal_weight * float(personal_score)
                row['ranking_score'] = fused
                reranked.append(row)

            reranked.sort(key=lambda x: x.get('ranking_score', x['score'] / 100.0), reverse=True)
            results = reranked[:10]

    # 保持 sort_by 兼容：最终只在 Top10 内做轻微重排
    if algorithm == "deep_learning":
        results = _apply_deep_learning_rerank(results)
    elif sort_by == 'distance':
        results.sort(key=lambda x: (x['distance'] if x['distance'] is not None else 9999, -x.get('ranking_score', x['score'] / 100.0)))
    elif sort_by == 'capacity':
        results.sort(key=lambda x: (-x['capacity'], -x.get('ranking_score', x['score'] / 100.0)))
    else:
        results.sort(key=lambda x: x.get('ranking_score', x['score'] / 100.0), reverse=True)

    return results[:10]
