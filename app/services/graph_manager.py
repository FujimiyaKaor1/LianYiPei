from neo4j import GraphDatabase
import os
import time

_driver = None

def get_driver():
    global _driver
    if _driver is None:
        try:
            uri = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
            user = os.environ.get('NEO4J_USER', 'neo4j')
            password = os.environ.get('NEO4J_PASSWORD', 'password')
            
            print(f"Connecting to Neo4j: {uri}")
            
            _driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                connection_acquisition_timeout=8.0,
                max_transaction_retry_time=5.0,
            )
            
            _driver.verify_connectivity()
            print(f"Neo4j connected successfully!")
            return _driver
        except Exception as e:
            print(f"Neo4j connection error: {e}")
            _driver = None
            return None
    return _driver

def run_query(query, parameters=None, retry=3, retry_sleep=0.5):
    driver = get_driver()
    if not driver:
        return None

    for attempt in range(retry):
        try:
            with driver.session() as session:
                result = session.run(query, parameters or {})
                records = [record.data() for record in result]
                return records
        except Exception as e:
            print(f"Query error (attempt {attempt+1}/{retry}): {e}")
            if attempt < retry - 1:
                time.sleep(retry_sleep)
            else:
                return None
    return None

def create_product_node(name, category=None):
    query = """
    MERGE (p:Product {name: $name})
    SET p.category = $category
    RETURN p
    """
    result = run_query(query, {"name": name, "category": category})
    return result is not None

def create_relation(upstream_product, downstream_product):
    query = """
    MERGE (up:Product {name: $upstream})
    MERGE (down:Product {name: $downstream})
    MERGE (up)-[:SUPPLIES_TO]->(down)
    RETURN up.name as upstream, down.name as downstream
    """
    result = run_query(query, {"upstream": upstream_product, "downstream": downstream_product})
    return result is not None

def get_full_graph(max_nodes: int | None = None, max_links: int | None = None):
    """
    从 Neo4j 读取 Product 供应链图。兼容 name / product_name / id 等常见属性，避免空字段导致前端无节点。
    max_nodes / max_links：限制返回规模，降低政府端大屏与 API 延迟。
    """
    node_limit = int(max_nodes) if max_nodes and max_nodes > 0 else None
    link_limit = int(max_links) if max_links and max_links > 0 else None

    lim_nodes = f"\nLIMIT {node_limit}" if node_limit else ""
    lim_links = f"\nLIMIT {link_limit}" if link_limit else ""

    nodes_query = f"""
    MATCH (n:Product)
    WITH n,
         coalesce(n.name, n.product_name, n.title, toString(id(n))) AS name,
         coalesce(n.category, n.type, '') AS category
    WHERE name IS NOT NULL AND trim(toString(name)) <> ''
    RETURN DISTINCT name AS name, category AS category
    {lim_nodes}
    """
    links_query = f"""
    MATCH (a:Product)-[:SUPPLIES_TO]->(b:Product)
    WITH coalesce(a.name, a.product_name, a.title, toString(id(a))) AS source,
         coalesce(b.name, b.product_name, b.title, toString(id(b))) AS target
    WHERE source IS NOT NULL AND target IS NOT NULL
      AND trim(toString(source)) <> '' AND trim(toString(target)) <> ''
    RETURN DISTINCT source AS source, target AS target
    {lim_links}
    """

    nodes = run_query(nodes_query) or []
    links = run_query(links_query) or []

    formatted_nodes = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        raw_name = n.get("name")
        if raw_name is None:
            continue
        name = str(raw_name).strip()
        if not name:
            continue
        cat = n.get("category")
        formatted_nodes.append({"name": name, "category": "" if cat is None else str(cat)})

    formatted_links = []
    for l in links:
        if not isinstance(l, dict):
            continue
        s, t = l.get("source"), l.get("target")
        if s is None or t is None:
            continue
        s, t = str(s).strip(), str(t).strip()
        if s and t:
            formatted_links.append({"source": s, "target": t})

    if not formatted_nodes:
        fb_nodes, fb_links = _mysql_fallback_graph(
            node_limit if node_limit else 200,
            link_limit if link_limit else 600,
        )
        if fb_nodes:
            return fb_nodes, fb_links

    return formatted_nodes, formatted_links


def _mysql_fallback_graph(max_nodes: int, max_links: int):
    """
    Neo4j 未启动、无数据或查询失败时，用 MySQL 产品表生成简易链式图，保证政府端/大屏有可视结果。
    须在 Flask 应用上下文中调用。
    """
    max_nodes = max(1, min(int(max_nodes or 200), 2000))
    max_links = max(0, min(int(max_links or 600), 5000))
    try:
        from app.models import Product

        rows = Product.query.order_by(Product.id.asc()).limit(max_nodes).all()
    except Exception as e:
        print(f"MySQL fallback graph: query failed: {e}")
        return [], []

    if not rows:
        return [], []

    nodes = []
    seen = set()
    names_order = []
    for p in rows:
        base = (p.name or "").strip() or f"产品{p.id}"
        name = base
        if name in seen:
            name = f"{base}#{p.id}"
        seen.add(name)
        cat = (getattr(p, "category", None) or "")
        if isinstance(cat, str):
            cat = cat.strip()
        else:
            cat = str(cat) if cat is not None else ""
        nodes.append({"name": name, "category": cat})
        names_order.append(name)

    links = []
    for i in range(min(len(names_order) - 1, max_links)):
        links.append({"source": names_order[i], "target": names_order[i + 1]})

    return nodes, links


def generate_graph_html(container_id: str = "knowledge-graph-embed") -> str:
    """
    生成可注入 Jinja 模板的占位 HTML：固定高度容器 + 内联数据。
    页面需已引入 echarts.min.js；在 DOMContentLoaded 后 init，保证容器已有尺寸。
    """
    import json
    import html as html_lib

    nodes, links = get_full_graph()
    payload = json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False)
    safe = payload.replace("</", "<\\/")
    cid_attr = html_lib.escape(container_id)

    return f"""<div id="{cid_attr}" class="le-graph-shell" style="width:100%;min-height:400px;height:100%;background:transparent;"></div>
<script>
(function() {{
  function boot() {{
    var el = document.getElementById({json.dumps(container_id)});
    if (!el || !window.echarts) return;
    var raw = {safe};
    var chart = echarts.init(el, null, {{ renderer: 'canvas' }});
    chart.setOption({{
      backgroundColor: 'transparent',
      series: [{{
        type: 'graph', layout: 'force', roam: true,
        data: (raw.nodes || []).map(function(n) {{
          return {{
            name: n.name,
            category: n.category || '',
            symbolSize: 28,
            itemStyle: {{
              color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
                {{ offset: 0, color: '#3AC9A0' }},
                {{ offset: 1, color: '#6EE7B7' }}
              ])
            }}
          }};
        }}),
        links: (raw.links || []).map(function(l) {{
          return {{ source: l.source, target: l.target }};
        }}),
        force: {{ repulsion: 400, edgeLength: 80 }},
        label: {{ show: true, color: '#666', fontSize: 11 }},
        lineStyle: {{ color: '#E2E8E5', width: 1.2 }}
      }}]
    }});
    requestAnimationFrame(function() {{ chart.resize(); }});
    window.addEventListener('resize', function() {{ try {{ chart.resize(); }} catch (e) {{}} }});
  }}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}})();
</script>"""

def import_relations_from_csv(csv_path):
    import csv
    
    count = 0
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                upstream = row.get('上游产品') or row.get('upstream')
                downstream = row.get('下游产品') or row.get('downstream')
                
                if upstream and downstream:
                    if create_relation(upstream, downstream):
                        count += 1
                        print(f"Created: {upstream} -> {downstream}")
    except Exception as e:
        print(f"Error importing relations: {e}")
    
    return count

def create_index():
    query = "CREATE INDEX product_name IF NOT EXISTS FOR (p:Product) ON (p.name)"
    run_query(query)
    return True

def clear_all_products():
    query = "MATCH (n:Product) DETACH DELETE n"
    run_query(query)
    print("All products cleared")
    return True
