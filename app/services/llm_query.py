"""
LLM应用 - 自然语言查询产业链数据
基于 Text-to-SQL，使用大模型将用户自然语言转换为数据库查询
支持 MySQL 产业链数据查询
"""
import re
import json
from app import db
from sqlalchemy import text
from app.services.graph_manager import run_query as run_cypher
from app.services.ollama_client import get_ollama_model_name, invoke_ollama

# 数据库表结构描述，供LLM生成SQL时参考
SCHEMA_DESC = """
产业链数据库表结构：
- enterprises: 企业表 (id, name, address, contact, phone, credit_score, capacity, industry_code, tech_keywords, rd_investment, registered_capital, business_scope, province, patent_count)
- products: 产品表 (id, name, category, industry_code, enterprise_id)
- demands: 供需表 (id, type='supply'|'demand', product_id, quantity, unit, description, enterprise_id, status)
- transactions: 交易表 (id, buyer_id, seller_id, product_name, quantity, price, status, created_at)
- alerts: 预警表 (id, product_name, message, level, dimension, is_active, suggestion)
- product_import_risks: 产品进口依赖度 (product_name, import_ratio, source_countries, hs_code, data_source)
- enterprise_patents: 企业专利 (enterprise_id, patent_no, title, patent_type, ipc_code, apply_date)
"""


NEO4J_SCHEMA_DESC = """
Neo4j 图数据库（产业链知识图谱）：
- 节点: (:Product {name, category})
- 关系: (:Product)-[:SUPPLIES_TO]->(:Product)
常用查询：
- 查询某产品的上游：MATCH (p:Product {name:$name})<-[:SUPPLIES_TO]-(up:Product) RETURN up.name
- 查询某产品的下游：MATCH (p:Product {name:$name})-[:SUPPLIES_TO]->(down:Product) RETURN down.name
"""


def _system_prompt() -> str:
    """Text-to-SQL/Cypher 提示词工程：要求模型输出结构化 JSON，便于解析执行。"""
    return f"""你是一个产业链数据库助手。你需要根据用户问题生成数据库查询，并以严格 JSON 返回。

【数据库信息】
{SCHEMA_DESC}

{NEO4J_SCHEMA_DESC}

【输出格式（必须严格 JSON，不要附加解释，不要 Markdown 代码块）】
{{"type":"sql","query":"SELECT ..."}}  或  {{"type":"cypher","query":"MATCH ... RETURN ..."}}

【约束】
- SQL 只能是 SELECT，只读查询，禁止 UPDATE/DELETE/INSERT/ALTER/DROP/CREATE/TRUNCATE。
- Cypher 只能读查询，必须以 MATCH/OPTIONAL MATCH 开头，并包含 RETURN。禁止 CREATE/MERGE/SET/DELETE/CALL。
- 若问题无法回答，请返回：{{"type":"error","message":"原因"}}。

【示例】
问题：有多少家企业入驻？
{{"type":"sql","query":"SELECT COUNT(*) AS count FROM enterprises"}}

问题：供应信息有多少条？
{{"type":"sql","query":"SELECT COUNT(*) AS count FROM demands WHERE type='supply' AND status='active'"}}

问题：电机的上游产品有哪些？
{{"type":"cypher","query":"MATCH (p:Product {{name:'电机'}})<-[:SUPPLIES_TO]-(up:Product) RETURN up.name AS name"}}
"""


def _extract_json(text_out: str) -> dict | None:
    """从模型输出中提取 JSON。支持代码块/前后噪声。"""
    if not text_out:
        return None
    # 去掉 ```json ``` 或 ``` 包裹
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text_out, flags=re.IGNORECASE)
    if m:
        text_out = m.group(1).strip()
    # 找到第一个 {...} 尝试解析
    m2 = re.search(r"\{[\s\S]*\}", text_out)
    if m2:
        text_out = m2.group(0).strip()
    try:
        return json.loads(text_out)
    except Exception:
        return None


def _safe_execute_cypher(cypher: str) -> tuple[list, str | None]:
    """安全执行只读 Cypher"""
    c = (cypher or "").strip()
    cu = c.upper()
    if not (cu.startswith("MATCH") or cu.startswith("OPTIONAL MATCH")):
        return [], "Cypher 仅支持 MATCH/OPTIONAL MATCH 开头的只读查询"
    if "RETURN" not in cu:
        return [], "Cypher 查询必须包含 RETURN"
    for kw in ("CREATE", "MERGE", "SET", "DELETE", "DETACH", "CALL", "LOAD CSV"):
        if kw in cu:
            return [], f"不允许包含 {kw} 操作"
    data = run_cypher(c) or []
    return data, None


def _call_llm(prompt: str) -> str:
    """通过 LangChain ChatOllama（Ollama 原生 API）生成 SQL/Cypher JSON。"""
    try:
        return invoke_ollama(_system_prompt(), prompt)
    except Exception as e:
        msg = (
            f"Ollama 调用失败：{e}。请确认本机已运行 Ollama，并已执行 `ollama pull {get_ollama_model_name()}`；"
            f"可选在 .env 中设置 OLLAMA_BASE_URL（默认 http://localhost:11434）。"
        )
        try:
            return json.dumps({"type": "error", "message": msg}, ensure_ascii=False)
        except Exception:
            return ""


def _extract_sql(text: str) -> str:
    """从LLM回复中提取SQL"""
    # 移除markdown代码块
    match = re.search(r'```(?:sql)?\s*([\s\S]*?)```', text)
    if match:
        return match.group(1).strip()
    # 查找SELECT开头的语句
    for line in text.split('\n'):
        s = line.strip().upper()
        if s.startswith('SELECT') and ';' in line:
            return line.split(';')[0].strip() + ';'
        if s.startswith('SELECT'):
            return line.strip()
    return text.strip()


def _safe_execute(sql: str) -> tuple[list, str | None]:
    """安全执行只读SQL"""
    sql_upper = sql.upper().strip()
    # 仅允许SELECT
    if not sql_upper.startswith('SELECT'):
        return [], "仅支持SELECT查询"
    for kw in ('DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE'):
        if kw in sql_upper:
            return [], f"不允许包含 {kw} 操作"
    
    try:
        result = db.session.execute(text(sql))
        rows = result.fetchall()
        cols = list(result.keys()) if rows else []
        data = [dict(zip(cols, row)) for row in rows]
        # 处理datetime等不可JSON序列化类型
        for row in data:
            for k, v in row.items():
                if hasattr(v, 'isoformat'):
                    row[k] = v.isoformat()
        return data, None
    except Exception as e:
        return [], str(e)


def _rule_based_query(question: str) -> tuple[list, str | None, str | None]:
    """规则兜底：常见问题的固定SQL。返回 (data, error, sql)"""
    sql = None
    if '企业数量' in question or '多少企业' in question or '入驻企业' in question or '几家' in question:
        sql = "SELECT COUNT(*) as count FROM enterprises"
    elif '供应' in question and ('数量' in question or '多少' in question):
        sql = "SELECT COUNT(*) as count FROM demands WHERE type='supply' AND status='active'"
    elif '需求' in question and ('数量' in question or '多少' in question):
        sql = "SELECT COUNT(*) as count FROM demands WHERE type='demand' AND status='active'"
    elif '预警' in question and ('数量' in question or '多少' in question):
        sql = "SELECT COUNT(*) as count FROM alerts WHERE is_active=1"
    elif '产品' in question and ('数量' in question or '多少' in question):
        sql = "SELECT COUNT(*) as count FROM products"
    elif '交易' in question or '成交' in question:
        sql = "SELECT COUNT(*) as count FROM transactions WHERE status='completed'"
    elif '信用' in question and ('企业' in question or '高' in question or '排行' in question):
        sql = "SELECT name, credit_score FROM enterprises ORDER BY credit_score DESC LIMIT 10"
    elif '产能' in question:
        sql = "SELECT name, capacity FROM enterprises ORDER BY capacity DESC LIMIT 10"
    
    if sql:
        data, err = _safe_execute(sql)
        return (data, err, sql)
    return [], None, None


def nl_query(question: str) -> dict:
    """
    自然语言查询产业链数据
    返回: {success, data, sql, error, answer}
    """
    if not question or len(question.strip()) < 2:
        return {"success": False, "error": "请输入查询问题"}
    
    # 1. 尝试规则匹配
    data, err, sql_used = _rule_based_query(question)
    
    # 2. 规则未命中时调用LLM
    if data == [] and err is None and sql_used is None:
        prompt = f"用户问题：{question}"
        llm_out = _call_llm(prompt)
        if llm_out:
            obj = _extract_json(llm_out)
            if obj and isinstance(obj, dict):
                qtype = (obj.get("type") or obj.get("query_type") or "").strip().lower()
                if qtype == "sql":
                    sql_used = (obj.get("query") or "").strip()
                    if sql_used and not sql_used.endswith(";"):
                        sql_used += ";"
                    if sql_used:
                        data, err = _safe_execute(sql_used)
                elif qtype == "cypher":
                    sql_used = (obj.get("query") or "").strip()
                    if sql_used:
                        data, err = _safe_execute_cypher(sql_used)
                elif qtype == "error":
                    return {"success": False, "error": obj.get("message") or "模型无法回答该问题"}
                else:
                    # 非预期结构，退回 SQL 提取
                    sql_used = _extract_sql(llm_out)
                    if sql_used and not sql_used.endswith(";"):
                        sql_used += ";"
                    if sql_used:
                        data, err = _safe_execute(sql_used)
            else:
                # 旧格式：直接返回 SQL
                sql_used = _extract_sql(llm_out)
                if sql_used and not sql_used.endswith(";"):
                    sql_used += ";"
                if sql_used:
                    data, err = _safe_execute(sql_used)
        else:
            return {
                "success": False,
                "error": (
                    "大模型未返回有效结果，无法使用智能查询。"
                    f"请确认 Ollama 可用且已拉取模型 `{get_ollama_model_name()}`；或使用预设问题如：有多少企业？供应数量多少？"
                ),
            }
    
    if err:
        return {"success": False, "error": err, "sql": sql_used}
    
    # 生成自然语言回答
    answer = _format_answer(question, data, sql_used)
    return {
        "success": True,
        "data": data[:50],  # 最多返回50条
        "sql": sql_used,
        "answer": answer
    }


def _format_answer(question: str, data: list, sql: str | None) -> str:
    """将查询结果格式化为自然语言回答"""
    if not data:
        return "未查询到相关数据。"
    
    # 单值统计
    if len(data) == 1 and len(data[0]) == 1:
        v = list(data[0].values())[0]
        return f"查询结果为：{v}"
    
    # 多行简要
    if len(data) <= 5:
        parts = []
        for row in data:
            parts.append("、".join(f"{k}:{v}" for k, v in row.items()))
        return "查询结果：\n" + "\n".join(parts)
    
    return f"查询到 {len(data)} 条记录。"