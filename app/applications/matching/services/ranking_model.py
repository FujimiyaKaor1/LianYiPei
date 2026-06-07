import os
from typing import Dict, List, Tuple

import numpy as np

from app import db
from app.models import Enterprise, Product, Transaction
from app.services.graph_manager import run_query
from app.services.matcher import _calc_capacity_score, _calc_semantic_score, _cosine_similarity

FEATURE_NAMES: List[str] = [
    "gnn_similarity",      # 基于图谱的产品相似度（0~1）
    "semantic_score",      # 语义匹配分（0~1）
    "distance_km",         # 直线距离（km）
    "credit_score",        # 供应商信用分
    "capacity_score",      # 产能匹配得分（0~100）
    "history_score",       # 历史合作得分（0~100）
    "tech_jaccard",        # 技术标签 Jaccard 相似度（0~1）
]

_MODEL_CACHE = None  # type: ignore[var-annotated]


def _get_gnn_similarity(product_a: str, product_b: str, max_hops: int = 4) -> float:
    """使用 Neo4j 的最短路径长度近似 GNN 相似度，返回 0~1。

    说明：项目中还没有真正的 GNN 模型，这里用图最短路径长度做一个可用的近似：
    - 若两产品在 1~max_hops 跳内可达，则相似度 = 1 / (1 + hops)
    - 否则相似度 = 0
    """
    if not product_a or not product_b:
        return 0.0

    cypher = """
    MATCH (a:Product {name: $a}), (b:Product {name: $b})
    MATCH p = shortestPath((a)-[:SUPPLIES_TO*..$max_hops]-(b))
    RETURN length(p) AS hops
    LIMIT 1
    """
    records = run_query(cypher, {"a": product_a, "b": product_b, "max_hops": max_hops})
    if not records:
        return 0.0
    hops = records[0].get("hops")
    if not isinstance(hops, int) or hops <= 0:
        return 0.0
    return float(1.0 / (1.0 + hops))


def _tech_jaccard(ent_a: Enterprise, ent_b: Enterprise) -> float:
    """计算两个企业技术关键词的 Jaccard 相似度。"""
    a = (ent_a.tech_keywords or "").strip()
    b = (ent_b.tech_keywords or "").strip()
    if not a or not b:
        return 0.0
    set_a = {k.strip() for k in a.split(",") if k.strip()}
    set_b = {k.strip() for k in b.split(",") if k.strip()}
    if not set_a or not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    return float(len(inter) / len(union)) if union else 0.0


def _distance_km(ent_a: Enterprise, ent_b: Enterprise) -> float:
    from geopy.distance import geodesic

    if not (ent_a.latitude and ent_a.longitude and ent_b.latitude and ent_b.longitude):
        return 1e6
    try:
        return float(
            geodesic((ent_a.latitude, ent_a.longitude), (ent_b.latitude, ent_b.longitude)).km
        )
    except Exception:
        return 1e6


def _semantic_score_for_pair(demand_text: str, supplier: Enterprise) -> float:
    """使用已有产品向量 + matcher 中的语义得分逻辑，返回 0~1。"""
    if not demand_text:
        return 0.0
    products = Product.query.filter_by(enterprise_id=supplier.id).all()
    if not products:
        return 0.0
    score, _ = _calc_semantic_score(demand_text, supplier, products)
    # _calc_semantic_score 返回 0~1
    return float(score)


def _history_score_for_pair(buyer_id: int, seller_id: int) -> float:
    """简单重用 matcher 中的逻辑：基于交易次数的得分（0~100）。"""
    txns = Transaction.query.filter_by(buyer_id=buyer_id, seller_id=seller_id).all()
    count = len(txns)
    if count == 0:
        return 0.0
    if count == 1:
        return 50.0
    if count <= 3:
        return 75.0
    return 100.0


def extract_features(
    buyer: Enterprise,
    supplier: Enterprise,
    demand_product_name: str,
    demand_quantity: int,
) -> Dict[str, float]:
    """对一个候选供应商提取排序特征。"""
    # GNN 相似度：需求产品名 vs 供应商主打产品名（这里用名称包含匹配的第一个产品）
    main_product = (
        Product.query.filter(
            Product.enterprise_id == supplier.id,
            Product.name.contains(demand_product_name),
        )
        .order_by(Product.id.asc())
        .first()
    ) or Product.query.filter_by(enterprise_id=supplier.id).order_by(Product.id.asc()).first()

    if main_product:
        gnn_sim = _get_gnn_similarity(demand_product_name, main_product.name)
    else:
        gnn_sim = 0.0

    # 语义匹配分：需求文本 vs 供应产品 embedding
    semantic_score = _semantic_score_for_pair(demand_product_name, supplier)

    # 距离
    distance = _distance_km(buyer, supplier)

    # 信用分
    credit = float(supplier.credit_score or 0.0)

    # 产能匹配分（0~100）
    capacity_score, _ = _calc_capacity_score(supplier, demand_quantity)
    capacity_score = float(capacity_score or 0.0)

    # 历史合作得分（0~100）
    history_score = _history_score_for_pair(buyer.id, supplier.id) if buyer.id else 0.0

    # 技术标签 Jaccard
    tech_jaccard = _tech_jaccard(buyer, supplier)

    return {
        "gnn_similarity": float(gnn_sim),
        "semantic_score": float(semantic_score),
        "distance_km": float(distance),
        "credit_score": credit,
        "capacity_score": capacity_score,
        "history_score": history_score,
        "tech_jaccard": float(tech_jaccard),
    }


def prepare_training_data(limit_per_class: int | None = None) -> Tuple[np.ndarray, np.ndarray]:
    """从历史成交/未成交样本中构造训练数据。

    简化实现：
    - 正样本：Transaction.status == 'completed'
    - 负样本：为同一买家随机采样若干当前未有交易记录的供应商
    """
    from sqlalchemy import func

    positives = (
        Transaction.query.filter_by(status="completed")
        .order_by(Transaction.created_at.desc())
        .all()
    )
    if limit_per_class:
        positives = positives[:limit_per_class]

    X: List[List[float]] = []
    y: List[int] = []

    # 正样本
    for tx in positives:
        buyer = Enterprise.query.get(tx.buyer_id)
        seller = Enterprise.query.get(tx.seller_id)
        if not buyer or not seller:
            continue
        feats = extract_features(
            buyer,
            seller,
            demand_product_name=tx.product_name or "",
            demand_quantity=tx.quantity or 100,
        )
        X.append([feats[name] for name in FEATURE_NAMES])
        y.append(1)

    # 负样本：对每个买家采样若干未合作供应商
    buyers = {tx.buyer_id for tx in positives}
    for buyer_id in buyers:
        buyer = Enterprise.query.get(buyer_id)
        if not buyer:
            continue
        completed_seller_ids = {
            s.seller_id
            for s in Transaction.query.with_entities(Transaction.seller_id)
            .filter_by(buyer_id=buyer_id)
            .distinct()
        }
        # 取部分其它企业作为负样本
        candidates = (
            Enterprise.query.filter(Enterprise.id.notin_(completed_seller_ids | {buyer_id}))
            .order_by(func.rand())
            .limit(limit_per_class or 50)
            .all()
        )
        for supplier in candidates:
            feats = extract_features(
                buyer,
                supplier,
                demand_product_name="",  # 无明确产品名时，语义 / GNN 特征为 0
                demand_quantity=100,
            )
            X.append([feats[name] for name in FEATURE_NAMES])
            y.append(0)

    if not X:
        raise RuntimeError("No training data constructed; please check transactions data.")

    return np.asarray(X, dtype=float), np.asarray(y, dtype=int)


def train_model(model_path: str | None = None, limit_per_class: int | None = None) -> str:
    """训练 XGBoost 排序模型并保存到文件。"""
    try:
        from xgboost import XGBClassifier  # type: ignore[import]
    except Exception as e:  # pragma: no cover - 依赖问题
        raise RuntimeError(
            "xgboost 未安装，请先在虚拟环境中执行 `pip install xgboost`。\n"
            f"原始错误：{e}"
        )

    import joblib

    X, y = prepare_training_data(limit_per_class=limit_per_class)

    model = XGBClassifier(
        max_depth=5,
        n_estimators=200,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
    )
    model.fit(X, y)

    payload = {"model": model, "features": FEATURE_NAMES}

    if model_path is None:
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ranking_model.pkl")

    joblib.dump(payload, model_path)
    return model_path


def _load_model(model_path: str | None = None):
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE

    import joblib

    if model_path is None:
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ranking_model.pkl")
    if not os.path.exists(model_path):
        _MODEL_CACHE = None
        return None
    _MODEL_CACHE = joblib.load(model_path)
    return _MODEL_CACHE


def predict_score(feature_dict: Dict[str, float], model_path: str | None = None) -> float:
    """对单个候选供应商预测成交概率（0~1），作为精排分数。"""
    payload = _load_model(model_path)
    if not payload:
        # 模型尚未训练，返回一个简单的规则分数占位
        # 这里用部分特征做一个启发式分数，避免接口报错。
        score = 0.0
        score += max(0.0, min(1.0, feature_dict.get("gnn_similarity", 0.0))) * 0.25
        score += max(0.0, min(1.0, feature_dict.get("semantic_score", 0.0))) * 0.25
        score += (feature_dict.get("credit_score", 0.0) / 100.0) * 0.2
        score += (feature_dict.get("capacity_score", 0.0) / 100.0) * 0.2
        score += max(0.0, min(1.0, feature_dict.get("tech_jaccard", 0.0))) * 0.1
        return float(max(0.0, min(1.0, score)))

    model = payload["model"]
    features = payload["features"]
    x = np.asarray([[float(feature_dict.get(name, 0.0)) for name in features]], dtype=float)
    prob = float(model.predict_proba(x)[0, 1])
    return prob


if __name__ == "__main__":  # 简单 CLI：python -m app.services.ranking_model
    from app import create_app

    app = create_app()
    with app.app_context():
        path = train_model()
        print(f"[ranking_model] model trained and saved to: {path}")

