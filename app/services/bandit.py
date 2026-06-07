import json
import os
import time
from typing import Dict, Optional, Tuple

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


# bandit 维度顺序：w1~w5
DIM_KEYS = ["product", "distance", "credit", "capacity", "history"]


DEFAULT_INIT_WEIGHTS = {
    "product": 0.30,
    "distance": 0.20,
    # 项目原始匹配里没有 credit 维度，这里给一个保守初始值
    "credit": 0.10,
    "capacity": 0.15,
    "history": 0.25,
}


class ThompsonBanditWeights:
    """基于 Thompson Sampling 的 Beta 多臂老虎机（Bernoulli 近似）。

    设计选择（用于落地）：
    - 每个维度维护一组 Beta(alpha, beta) 参数；
    - 每次采样得到一组 Beta 样本并归一化为权重；
    - 反馈记录时用维度得分做“软计数”：正反馈时 alpha += dim_score_norm，
      负反馈时 beta += dim_score_norm。
    """

    def __init__(
        self,
        redis_key: str = "bandit_beta_params:v1",
        feedback_prefix: str = "bandit_feedback:",
        prior_strength: float = 10.0,
        redis_ttl_seconds: int = 60 * 60 * 24 * 3,
    ):
        self.redis_key = redis_key
        self.feedback_prefix = feedback_prefix
        self.prior_strength = float(prior_strength)
        self.redis_ttl_seconds = int(redis_ttl_seconds)

    _redis_unavailable = False  # 连接失败后跳过后续尝试

    def _get_redis_client(self):
        if redis is None or ThompsonBanditWeights._redis_unavailable:
            return None
        try:
            from flask import current_app

            url = current_app.config.get("REDIS_URL") or os.environ.get("REDIS_URL")
            if not url:
                ThompsonBanditWeights._redis_unavailable = True
                return None
            client = redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
            client.ping()
            return client
        except Exception:
            ThompsonBanditWeights._redis_unavailable = True
            return None

    def _load_init_weights(self) -> Dict[str, float]:
        # 1) 读取配置文件（config.py）覆盖：BANDIT_W1~BANDIT_W5 或 BANDIT_INIT_WEIGHTS
        try:
            from config import Config  # type: ignore

            if hasattr(Config, "BANDIT_INIT_WEIGHTS"):
                raw = getattr(Config, "BANDIT_INIT_WEIGHTS")
                if raw:
                    try:
                        obj = json.loads(raw) if isinstance(raw, str) else dict(raw)
                        out = dict(DEFAULT_INIT_WEIGHTS)
                        for k in DIM_KEYS:
                            if k in obj:
                                out[k] = float(obj[k])
                        return out
                    except Exception:
                        pass

            # BANDIT_W1~BANDIT_W5
            mapping = {
                "BANDIT_W1": "product",
                "BANDIT_W2": "distance",
                "BANDIT_W3": "credit",
                "BANDIT_W4": "capacity",
                "BANDIT_W5": "history",
            }
            out = dict(DEFAULT_INIT_WEIGHTS)
            updated = False
            for env_key, key in mapping.items():
                if hasattr(Config, env_key):
                    out[key] = float(getattr(Config, env_key))
                    updated = True
            if updated:
                return out
        except Exception:
            pass

        # 2) 支持环境变量覆盖：BANDIT_INIT_WEIGHTS='{"product":0.3,"distance":0.2,...}'
        raw = os.environ.get("BANDIT_INIT_WEIGHTS")
        if raw:
            try:
                obj = json.loads(raw)
                out = dict(DEFAULT_INIT_WEIGHTS)
                for k in DIM_KEYS:
                    if k in obj:
                        out[k] = float(obj[k])
                return out
            except Exception:
                pass
        return dict(DEFAULT_INIT_WEIGHTS)

    def _init_beta_params(self) -> Dict[str, Dict[str, float]]:
        init_w = self._load_init_weights()
        # Beta mean = p，variance 由 prior_strength 控制
        # alpha = p*s, beta = (1-p)*s
        out: Dict[str, Dict[str, float]] = {}
        s = self.prior_strength
        for k in DIM_KEYS:
            p = float(init_w.get(k, 0.0))
            p = max(0.001, min(0.999, p))
            alpha = p * s + 1.0
            beta = (1.0 - p) * s + 1.0
            out[k] = {"alpha": alpha, "beta": beta}
        return out

    def _load_beta_params(self) -> Dict[str, Dict[str, float]]:
        r = self._get_redis_client()
        if r is None:
            # 无 Redis：退化为内存静态 prior（不更新）
            return self._init_beta_params()

        try:
            raw = r.get(self.redis_key)
            if not raw:
                params = self._init_beta_params()
                r.setex(self.redis_key, self.redis_ttl_seconds, json.dumps(params))
                return params
            params = json.loads(raw.decode("utf-8"))
            # 简单校验
            if not isinstance(params, dict):
                return self._init_beta_params()
            return params
        except Exception:
            return self._init_beta_params()

    def _save_beta_params(self, params: Dict[str, Dict[str, float]]) -> None:
        r = self._get_redis_client()
        if r is None:
            return
        try:
            r.setex(self.redis_key, self.redis_ttl_seconds, json.dumps(params))
        except Exception:
            pass

    def thompson_sample_weights(self) -> Dict[str, float]:
        """采样得到当前一组权重（product/distance/credit/capacity/history），和为 1。"""
        import random

        params = self._load_beta_params()
        raw_w: Dict[str, float] = {}
        for k in DIM_KEYS:
            a = float(params.get(k, {}).get("alpha", 1.0))
            b = float(params.get(k, {}).get("beta", 1.0))
            # Beta(a,b) 采样
            raw_w[k] = float(random.betavariate(a, b))

        s = sum(raw_w.values())
        if s <= 0:
            return dict(DEFAULT_INIT_WEIGHTS)
        return {k: raw_w[k] / s for k in DIM_KEYS}

    def log_feedback(
        self,
        ent_id: int,
        clicked: bool,
        dim_scores: Dict[str, float],
        day_key: Optional[str] = None,
    ) -> None:
        """记录一次推荐反馈（点击=正反馈，未点击=负反馈）。

        ent_id：用户/买家企业 id
        dim_scores：应包含 keys：product/distance/credit/capacity/history
                    每个维度的得分通常应是 0~100
        day_key：可指定 'YYYY-MM-DD'；不指定则使用当前日期
        """
        if day_key is None:
            day_key = time.strftime("%Y-%m-%d", time.localtime())

        r = self._get_redis_client()
        if r is None:
            # 不落库也不影响接口可用
            return

        key = f"{self.feedback_prefix}{day_key}"
        payload = {
            "ent_id": int(ent_id),
            "clicked": bool(clicked),
            "ts": int(time.time()),
            "dim_scores": {k: float(dim_scores.get(k, 0.0)) for k in DIM_KEYS},
        }
        try:
            r.rpush(key, json.dumps(payload))
            # 让数据存在到更新日前后即可
            r.expire(key, self.redis_ttl_seconds)
        except Exception:
            pass

    def update_from_feedback(self, day_key: Optional[str] = None) -> bool:
        """根据当天反馈更新 Beta 参数（并清空反馈队列）。"""
        if day_key is None:
            day_key = time.strftime("%Y-%m-%d", time.localtime(time.time() - 24 * 3600))

        r = self._get_redis_client()
        if r is None:
            return False

        key = f"{self.feedback_prefix}{day_key}"
        try:
            items = r.lrange(key, 0, -1)
            if not items:
                return False
        except Exception:
            return False

        params = self._load_beta_params()

        def _norm_score(x: float) -> float:
            # 把 0~100 映射为 0~1（并 clamp）
            try:
                x = float(x)
            except Exception:
                x = 0.0
            return max(0.0, min(1.0, x / 100.0))

        for raw in items:
            try:
                obj = json.loads(raw.decode("utf-8"))
                clicked = bool(obj.get("clicked", False))
                dim_scores = obj.get("dim_scores") or {}
            except Exception:
                continue

            for k in DIM_KEYS:
                dim_s = _norm_score(dim_scores.get(k, 0.0))
                if clicked:
                    params[k]["alpha"] = float(params[k].get("alpha", 1.0)) + dim_s
                else:
                    params[k]["beta"] = float(params[k].get("beta", 1.0)) + dim_s

        self._save_beta_params(params)

        # 清空反馈
        try:
            r.delete(key)
        except Exception:
            pass

        return True

    def update_from_mysql(self, day_key: Optional[str] = None) -> bool:
        """从MySQL读取反馈数据更新Beta参数（作为Redis的备选方案）"""
        if day_key is None:
            day_key = time.strftime("%Y-%m-%d", time.localtime(time.time() - 24 * 3600))

        try:
            from app.models import MatchFeedback
            from app import db
            from datetime import datetime, timedelta
            
            target_date = datetime.strptime(day_key, "%Y-%m-%d")
            next_date = target_date + timedelta(days=1)
            
            feedbacks = MatchFeedback.query.filter(
                MatchFeedback.created_at >= target_date,
                MatchFeedback.created_at < next_date
            ).all()
            
            if not feedbacks:
                return False
            
            params = self._load_beta_params()
            
            def _norm_score(x: float) -> float:
                try:
                    x = float(x)
                except Exception:
                    x = 0.0
                return max(0.0, min(1.0, x / 100.0))
            
            for fb in feedbacks:
                dim_scores = fb.dim_scores or {}
                clicked = bool(fb.clicked or fb.contacted)
                
                for k in DIM_KEYS:
                    dim_s = _norm_score(dim_scores.get(k, 0.0))
                    if clicked:
                        params[k]["alpha"] = float(params[k].get("alpha", 1.0)) + dim_s
                    else:
                        params[k]["beta"] = float(params[k].get("beta", 1.0)) + dim_s
            
            self._save_beta_params(params)
            return True
            
        except Exception as e:
            print(f"[bandit] update_from_mysql error: {e}")
            return False

    def get_current_match_weights(self, base_weights: Dict[str, float]) -> Dict[str, float]:
        """将 bandit 的 5 维权重映射到当前 match_suppliers 权重字典。

        - base_weights：来自 matcher.DEFAULT_WEIGHTS（可能包含 semantic / tech 等额外维度）
        - credit：会覆盖 base_weights['credit']（若不存在则新建）

        返回一个归一化后的 weights dict（和为 1）。
        """
        sampled = self.thompson_sample_weights()
        out = dict(base_weights)
        for k in DIM_KEYS:
            out[k] = sampled.get(k, out.get(k, 0.0))

        # 如果 base_weights 里没有 credit key，则 credit 被写入 out

        total = sum(out.values())
        if total <= 0:
            return dict(base_weights)
        return {k: v / total for k, v in out.items()}


_BANDIT_SINGLETON: Optional[ThompsonBanditWeights] = None


def _get_bandit() -> ThompsonBanditWeights:
    global _BANDIT_SINGLETON
    if _BANDIT_SINGLETON is None:
        # 可通过环境变量调整先验强度
        prior = os.environ.get("BANDIT_PRIOR_STRENGTH", "10")
        _BANDIT_SINGLETON = ThompsonBanditWeights(prior_strength=float(prior))
    return _BANDIT_SINGLETON


def get_current_match_weights(base_weights: Dict[str, float]) -> Dict[str, float]:
    """对外入口：返回当前 bandit 采样权重（归一化后）。"""
    return _get_bandit().get_current_match_weights(base_weights)

