"""
图算法 - 产业图谱分析
使用 NetworkX 实现 PageRank、社区发现等，适用于产业图谱动态更新与关键节点分析
（可扩展为 GraphBolt 大规模图采样与训练）
"""
import networkx as nx
from app.services.graph_manager import get_full_graph


def _build_nx_graph():
    """从 Neo4j 导出图并构建 NetworkX 有向图"""
    nodes, links = get_full_graph()
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["name"], category=n.get("category", ""))
    for l in links:
        G.add_edge(l["source"], l["target"])
    return G


def pagerank_products(top_k=10) -> list[dict]:
    """
    PageRank 算法：识别产业链中的关键产品节点
    返回重要性排名前 top_k 的产品
    """
    try:
        G = _build_nx_graph()
        if G.number_of_nodes() == 0:
            return []
        pr = nx.pagerank(G)
        sorted_nodes = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"product": name, "pagerank": round(score, 4)} for name, score in sorted_nodes]
    except Exception as e:
        print(f"PageRank error: {e}")
        return []


def community_detection() -> list[dict]:
    """
    社区发现：将产业链图划分为若干子群（产业链集群）
    使用 Louvain 方法（无向化后）
    """
    try:
        G = _build_nx_graph()
        if G.number_of_nodes() < 2:
            return []
        G_undir = G.to_undirected()
        # Louvain 需要 python-louvain
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(G_undir)
        except ImportError:
            # 退化为连通分量
            comps = list(nx.connected_components(G_undir))
            partition = {}
            for i, comp in enumerate(comps):
                for n in comp:
                    partition[n] = i
        # 按社区分组
        from collections import defaultdict
        groups = defaultdict(list)
        for node, cid in partition.items():
            groups[cid].append(node)
        return [{"community_id": cid, "products": products} for cid, products in groups.items()]
    except Exception as e:
        print(f"Community detection error: {e}")
        return []
