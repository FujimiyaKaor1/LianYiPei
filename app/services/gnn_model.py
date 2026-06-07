import json
import os
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.data import HeteroData
from torch_geometric.nn import HANConv

from app import db
from app.models import Enterprise, Inquiry, Product, Transaction

try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None


DEFAULT_EMBEDDING_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "enterprise_embeddings"
)


@dataclass
class HanBprConfig:
    embedding_dim: int = 64
    hidden_dim: int = 64
    heads: int = 2
    dropout: float = 0.2
    lr: float = 1e-3
    weight_decay: float = 1e-5
    epochs: int = 30
    batch_size: int = 256
    neg_samples: int = 3
    max_pos_samples: Optional[int] = 5000  # 为了训练可控的上限
    device: Optional[str] = None


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _as_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _enterprise_feature(ent: Enterprise) -> np.ndarray:
    """构造企业数值特征（小维度，便于 HAN 训练）。"""
    # 这些字段在你现有模型里大多是可用的；若为空则回退 0。
    credit = _as_float(getattr(ent, "credit_score", 0.0))
    capacity = _as_float(getattr(ent, "capacity", 0.0))
    current_orders = _as_float(getattr(ent, "current_orders", 0.0))
    max_capacity = getattr(ent, "max_capacity", None)
    max_capacity_f = _as_float(max_capacity, capacity)
    patent_count = _as_float(getattr(ent, "patent_count", 0.0))
    rd_investment = _as_float(getattr(ent, "rd_investment", 0.0))
    lat = _as_float(getattr(ent, "latitude", 0.0))
    lng = _as_float(getattr(ent, "longitude", 0.0))

    # 简单归一化，避免量级差过大。
    feats = np.array(
        [
            credit / 100.0,
            capacity / 100.0,
            current_orders / max(1.0, max_capacity_f),
            patent_count / 100.0,
            rd_investment / 1000.0,
            lat / 90.0,
            lng / 180.0,
            1.0,  # bias term
        ],
        dtype=np.float32,
    )
    return feats


def _product_feature(p: Product, dim: int = 16) -> np.ndarray:
    """构造产品特征：优先使用 Product.embedding；否则用 0 向量。"""
    emb = getattr(p, "embedding", None)
    if isinstance(emb, list) and emb:
        v = np.asarray([float(x) for x in emb], dtype=np.float32)
        if v.size >= dim:
            return v[:dim].astype(np.float32)
        out = np.zeros((dim,), dtype=np.float32)
        out[: v.size] = v
        return out
    # embedding 不存在则回退 0
    return np.zeros((dim,), dtype=np.float32)


def build_hetero_graph() -> Tuple[HeteroData, List[int], Dict[int, int]]:
    """构建异构图（企业/产品）：
    - 企业-生产-产品（企业 produces 产品）
    - 产品-被需求-企业（需求中 demand 的企业 demanded_by 产品）
    - 企业-合作-企业（交易 completed 的买卖双方 cooperates）

    你给出的元路径示例：
    - 企业-生产-产品-被需求-企业：enterprise -> product -> enterprise
    - 企业-合作-企业：enterprise -> enterprise
    """
    enterprises = Enterprise.query.all()
    products = Product.query.all()
    demands = Inquiry.query.filter(Inquiry.direction == "demand").all()
    txns = Transaction.query.filter(Transaction.status == "completed").all()

    ent_ids = [e.id for e in enterprises]
    prod_ids = [p.id for p in products]

    ent_id_to_idx = {eid: i for i, eid in enumerate(ent_ids)}
    prod_id_to_idx = {pid: i for i, pid in enumerate(prod_ids)}

    ent_x = np.stack([_enterprise_feature(e) for e in enterprises], axis=0)
    prod_x = np.stack([_product_feature(p, dim=16) for p in products], axis=0)

    data = HeteroData()
    data["enterprise"].x = torch.from_numpy(ent_x)
    data["product"].x = torch.from_numpy(prod_x)

    # Edge: enterprise produces product
    produces_src: List[int] = []
    produces_dst: List[int] = []
    for p in products:
        if p.enterprise_id in ent_id_to_idx:
            produces_src.append(ent_id_to_idx[p.enterprise_id])
            produces_dst.append(prod_id_to_idx[p.id])

    data[("enterprise", "produces", "product")].edge_index = torch.tensor(
        [produces_src, produces_dst], dtype=torch.long
    )

    # Edge: product demanded_by enterprise (来自 demand.type == demand)
    demanded_by_src: List[int] = []  # product idx
    demanded_by_dst: List[int] = []  # enterprise idx
    for d in demands:
        if d.product_id in prod_id_to_idx and d.poster_id in ent_id_to_idx:
            demanded_by_src.append(prod_id_to_idx[d.product_id])
            demanded_by_dst.append(ent_id_to_idx[d.poster_id])

    data[("product", "demanded_by", "enterprise")].edge_index = torch.tensor(
        [demanded_by_src, demanded_by_dst], dtype=torch.long
    )

    # Edge: enterprise cooperates enterprise (buy -> sell)
    cooperates_src: List[int] = []
    cooperates_dst: List[int] = []
    for t in txns:
        if t.buyer_id in ent_id_to_idx and t.seller_id in ent_id_to_idx:
            cooperates_src.append(ent_id_to_idx[t.buyer_id])
            cooperates_dst.append(ent_id_to_idx[t.seller_id])

    data[("enterprise", "cooperates", "enterprise")].edge_index = torch.tensor(
        [cooperates_src, cooperates_dst], dtype=torch.long
    )

    return data, ent_ids, ent_id_to_idx


class HanBprModel(nn.Module):
    def __init__(
        self,
        metadata: Tuple[List[str], List[Tuple[str, str, str]]],
        in_channels: Dict[str, int],
        hidden_dim: int,
        out_dim: int,
        heads: int = 2,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.conv1 = HANConv(
            in_channels=in_channels,
            out_channels=hidden_dim,
            metadata=metadata,
            heads=heads,
            dropout=dropout,
        )
        self.conv2 = HANConv(
            # HANConv 的多头输出维度在当前版本实现中不额外乘 heads
            # (conv1 输出维度为 hidden_dim)，因此 conv2 输入应使用 hidden_dim。
            in_channels=hidden_dim,
            out_channels=out_dim,
            metadata=metadata,
            heads=1,
            dropout=dropout,
        )

    def forward(self, x_dict: Dict[str, torch.Tensor], edge_index_dict: Dict) -> Dict[str, torch.Tensor]:
        h = self.conv1(x_dict, edge_index_dict)
        h = {k: F.relu(v) for k, v in h.items()}
        h = self.conv2(h, edge_index_dict)
        return h


def _bpr_loss(
    ent_emb: torch.Tensor,
    pos_u: torch.Tensor,
    pos_i: torch.Tensor,
    neg_j: torch.Tensor,
) -> torch.Tensor:
    """
    ent_emb: [num_enterprises, dim]
    pos_u: [B]
    pos_i: [B]
    neg_j: [B, K]
    """
    u = ent_emb[pos_u]  # [B, D]
    i = ent_emb[pos_i]  # [B, D]
    j = ent_emb[neg_j]  # [B, K, D]

    u = F.normalize(u, p=2, dim=-1)
    i = F.normalize(i, p=2, dim=-1)
    j = F.normalize(j, p=2, dim=-1)

    pos_score = (u * i).sum(dim=-1)  # cosine sim in [-1,1]
    neg_score = (u.unsqueeze(1) * j).sum(dim=-1)  # [B, K]

    # BPR: maximize pos > neg
    loss = -torch.log(torch.sigmoid(pos_score.unsqueeze(1) - neg_score) + 1e-8).mean()
    return loss


def save_enterprise_embeddings_faiss(
    enterprise_ids: List[int],
    embeddings: np.ndarray,
    out_dir: str = DEFAULT_EMBEDDING_DIR,
) -> None:
    _ensure_dir(out_dir)
    mapping_path = os.path.join(out_dir, "enterprise_id_map.json")
    emb_path = os.path.join(out_dir, "enterprise_embeddings.npy")

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(enterprise_ids, f)
    np.save(emb_path, embeddings.astype(np.float32))

    if faiss is None:
        return

    x = embeddings.astype(np.float32)
    norms = np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
    x = x / norms
    index = faiss.IndexFlatIP(x.shape[1])
    index.add(x)
    faiss_path = os.path.join(out_dir, "enterprise_embeddings_faiss.index")
    try:
        faiss.write_index(index, faiss_path)
    except RuntimeError:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".index", delete=False) as tmp:
            tmp_path = tmp.name
        faiss.write_index(index, tmp_path)
        import shutil
        shutil.copy(tmp_path, faiss_path)
        os.remove(tmp_path)


def load_enterprise_embeddings(out_dir: str = DEFAULT_EMBEDDING_DIR) -> Tuple[Optional[List[int]], Optional[np.ndarray]]:
    mapping_path = os.path.join(out_dir, "enterprise_id_map.json")
    emb_path = os.path.join(out_dir, "enterprise_embeddings.npy")
    if not os.path.exists(mapping_path) or not os.path.exists(emb_path):
        return None, None
    with open(mapping_path, "r", encoding="utf-8") as f:
        ids = json.load(f)
    emb = np.load(emb_path)
    return ids, emb


_EMB_CACHE: Dict[str, object] = {}


def get_enterprise_embedding(enterprise_id: int) -> Optional[np.ndarray]:
    """根据企业 id 获取向量（来自训练完成后的文件/缓存）。"""
    cache_key = "enterprise_embeddings"
    if cache_key not in _EMB_CACHE:
        ids, emb = load_enterprise_embeddings()
        if ids is None or emb is None:
            _EMB_CACHE[cache_key] = (None, None, None)  # ids, emb, id_to_idx
        else:
            id_to_idx = {eid: i for i, eid in enumerate(ids)}
            _EMB_CACHE[cache_key] = (ids, emb, id_to_idx)
    ids, emb, id_to_idx = _EMB_CACHE[cache_key]
    if ids is None or emb is None or id_to_idx is None:
        return None
    idx = id_to_idx.get(int(enterprise_id))
    if idx is None:
        return None
    return emb[idx]


def train_han_bpr(config: HanBprConfig = HanBprConfig()) -> str:
    """训练 HAN + BPR，并将企业嵌入写入 FAISS/文件。"""
    from flask import current_app

    device = config.device or ("cuda" if torch.cuda.is_available() else "cpu")

    data, ent_ids, ent_id_to_idx = build_hetero_graph()
    if data["enterprise"].x.size(0) == 0:
        raise RuntimeError("No enterprise nodes found; cannot train.")
    if data["product"].x.size(0) == 0:
        raise RuntimeError("No product nodes found; cannot train.")

    node_types = ["enterprise", "product"]
    edge_types = list(data.edge_types)
    # edge_types 格式为 (src_type, rel_type, dst_type)
    metadata = (node_types, edge_types)

    in_channels = {ntype: data[ntype].x.size(-1) for ntype in node_types}

    model = HanBprModel(
        metadata=metadata,
        in_channels=in_channels,
        hidden_dim=config.hidden_dim,
        out_dim=config.embedding_dim,
        heads=config.heads,
        dropout=config.dropout,
    ).to(device)

    data = data.to(device)

    # 构建正样本 (buyer -> seller)
    txns = Transaction.query.filter(Transaction.status == "completed").all()
    pos_pairs: List[Tuple[int, int]] = []
    for t in txns:
        if t.buyer_id in ent_id_to_idx and t.seller_id in ent_id_to_idx:
            pos_pairs.append((ent_id_to_idx[t.buyer_id], ent_id_to_idx[t.seller_id]))

    if not pos_pairs:
        raise RuntimeError("No positive samples (completed transactions) found.")

    if config.max_pos_samples and len(pos_pairs) > config.max_pos_samples:
        pos_pairs = random.sample(pos_pairs, config.max_pos_samples)

    num_ents = len(ent_ids)
    pos_pairs_arr = np.asarray(pos_pairs, dtype=np.int64)
    pos_u_all = pos_pairs_arr[:, 0]
    pos_i_all = pos_pairs_arr[:, 1]

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.lr, weight_decay=config.weight_decay
    )

    # 训练循环：全图前向 + 采样三元组计算 BPR
    model.train()
    for epoch in range(config.epochs):
        # shuffle positive pairs
        idx = np.random.permutation(len(pos_pairs_arr))
        total_loss = 0.0
        steps = 0

        for start in range(0, len(pos_pairs_arr), config.batch_size):
            end = min(start + config.batch_size, len(pos_pairs_arr))
            batch_idx = idx[start:end]
            pos_u = torch.from_numpy(pos_u_all[batch_idx]).to(device)
            pos_i = torch.from_numpy(pos_i_all[batch_idx]).to(device)

            # negative sampling: sample suppliers different from pos_i
            B = pos_u.size(0)
            neg_j = torch.empty((B, config.neg_samples), dtype=torch.long, device=device)
            for k in range(config.neg_samples):
                # oversample and mask out equals
                sampled = torch.randint(0, num_ents, (B,), device=device)
                sampled = torch.where(sampled == pos_i, (sampled + 1) % num_ents, sampled)
                neg_j[:, k] = sampled

            optimizer.zero_grad(set_to_none=True)
            x_dict = {ntype: data[ntype].x for ntype in node_types}
            edge_index_dict = {etype: data[etype].edge_index for etype in data.edge_types}
            out = model(x_dict, edge_index_dict)
            ent_emb = out["enterprise"]
            loss = _bpr_loss(ent_emb, pos_u, pos_i, neg_j)
            loss.backward()
            optimizer.step()

            total_loss += float(loss.item())
            steps += 1

        avg_loss = total_loss / max(1, steps)
        print(f"[gnn_model] epoch {epoch+1}/{config.epochs} avg_loss={avg_loss:.6f}")

    # 输出最终企业向量
    model.eval()
    with torch.no_grad():
        x_dict = {ntype: data[ntype].x for ntype in node_types}
        edge_index_dict = {etype: data[etype].edge_index for etype in data.edge_types}
        out = model(x_dict, edge_index_dict)
        ent_emb = out["enterprise"].detach().cpu().numpy()

    # 写入 FAISS
    save_enterprise_embeddings_faiss(ent_ids, ent_emb)
    return DEFAULT_EMBEDDING_DIR


if __name__ == "__main__":  # pragma: no cover
    from app import create_app

    app = create_app()
    with app.app_context():
        train_han_bpr()

