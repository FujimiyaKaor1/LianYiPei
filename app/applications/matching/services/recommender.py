import json
import os
import time
from typing import Dict, Optional

import numpy as np

from app.models import Enterprise, Transaction


try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


FEATURE_DIM = 5
# feature order:
# 0: distance_score (higher is better, ~0~1)
# 1: credit_score_norm (credit_score/100)
# 2: available_capacity_norm ((max_capacity-current_orders)/max_capacity)
# 3: history_norm (completed interaction count normalized)
# 4: tech_jaccard (0~1)


_redis_unavailable = False

def _get_redis_client():
    global _redis_unavailable
    if redis is None or _redis_unavailable:
        return None
    try:
        from flask import current_app

        url = current_app.config.get("REDIS_URL") or os.environ.get("REDIS_URL")
        if not url:
            _redis_unavailable = True
            return None
        client = redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
        client.ping()
        return client
    except Exception:
        _redis_unavailable = True
        return None


def _jaccard_tech(a: str, b: str) -> float:
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    set_a = {k.strip() for k in a.split(",") if k.strip()}
    set_b = {k.strip() for k in b.split(",") if k.strip()}
    if not set_a or not set_b:
        return 0.0
    inter = set_a & set_b
    union = set_a | set_b
    return float(len(inter) / len(union)) if union else 0.0


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0:
        return 0.0
    sim = float(np.dot(a, b) / denom)
    # features are non-negative, so cosine usually >=0; clamp anyway
    return float(max(0.0, min(1.0, sim)))


def _distance_score(buyer: Enterprise, supplier: Enterprise) -> float:
    # higher is better
    if not (buyer.latitude and buyer.longitude and supplier.latitude and supplier.longitude):
        return 0.0
    try:
        from geopy.distance import geodesic

        dist_km = float(
            geodesic((buyer.latitude, buyer.longitude), (supplier.latitude, supplier.longitude)).km
        )
        return 1.0 / (1.0 + dist_km)
    except Exception:
        return 0.0


def _available_capacity_norm(supplier: Enterprise) -> float:
    max_cap = supplier.max_capacity if getattr(supplier, "max_capacity", None) is not None else supplier.capacity
    max_cap = float(max_cap or 0.0)
    current = float(getattr(supplier, "current_orders", 0) or 0.0)
    if max_cap <= 0:
        return 0.0
    available = max(0.0, max_cap - current)
    return float(available / max_cap)


def _history_norm(completed_count: int, cap: int = 5) -> float:
    # map count 0..cap -> 0..1
    completed_count = int(completed_count or 0)
    return float(min(completed_count, cap) / cap)


def _supplier_feature_vector(
    buyer: Enterprise,
    supplier: Enterprise,
    completed_count: int,
) -> np.ndarray:
    return np.asarray(
        [
            _distance_score(buyer, supplier),
            float((supplier.credit_score or 0.0) / 100.0),
            _available_capacity_norm(supplier),
            _history_norm(completed_count),
            _jaccard_tech(buyer.tech_keywords or "", supplier.tech_keywords or ""),
        ],
        dtype=np.float32,
    )


def learn_enterprise_preference(ent_id: int, redis_ttl_seconds: int = 86400, min_records: int = 2) -> Optional[np.ndarray]:
    """学习企业偏好向量，并缓存到 Redis。

    说明：
    - 目前项目没有“点击/联系日志”独立表，这里使用 `transactions` 中 buyer_id=ent_id 且 status='completed'
      的历史供应商列表作为“过去点击/联系供应商”的近似。
    - 偏好向量 = 历史供应商特征向量的均值。
    """
    buyer = Enterprise.query.get(ent_id)
    if not buyer:
        return None

    # history suppliers
    txns = Transaction.query.filter_by(buyer_id=ent_id, status="completed").all()
    if not txns:
        return None

    seller_counts: Dict[int, int] = {}
    for t in txns:
        seller_counts[t.seller_id] = seller_counts.get(t.seller_id, 0) + 1

    if len(seller_counts) < min_records:
        return None

    # compute mean feature vector
    features = []
    for seller_id, cnt in seller_counts.items():
        supplier = Enterprise.query.get(seller_id)
        if not supplier:
            continue
        vec = _supplier_feature_vector(buyer, supplier, cnt)
        features.append(vec)

    if not features:
        return None

    pref_vec = np.stack(features, axis=0).mean(axis=0)

    # cache to redis
    r = _get_redis_client()
    if r is not None:
        key = f"enterprise_preference_vec:{ent_id}"
        payload = json.dumps({"dim": FEATURE_DIM, "vec": [float(x) for x in pref_vec.tolist()]})
        try:
            r.setex(key, int(redis_ttl_seconds), payload)
        except Exception:
            pass

    return pref_vec


def get_enterprise_preference_vec(ent_id: int) -> Optional[np.ndarray]:
    """获取企业偏好向量（优先 Redis，失败则重算）。"""
    r = _get_redis_client()
    key = f"enterprise_preference_vec:{ent_id}"
    if r is not None:
        try:
            raw = r.get(key)
            if raw:
                obj = json.loads(raw.decode("utf-8"))
                vec = obj.get("vec")
                if isinstance(vec, list) and len(vec) == FEATURE_DIM:
                    return np.asarray(vec, dtype=np.float32)
        except Exception:
            pass
    return learn_enterprise_preference(ent_id)


def personalized_similarity_score(
    buyer: Enterprise,
    supplier: Enterprise,
    pref_vec: np.ndarray,
    seller_completed_count: int = 0,
) -> float:
    """计算候选供应商与偏好向量的相似度（0~1）。"""
    if pref_vec is None:
        return 0.0
    cand_vec = _supplier_feature_vector(buyer, supplier, seller_completed_count)
    return _cosine_similarity(cand_vec, pref_vec)

