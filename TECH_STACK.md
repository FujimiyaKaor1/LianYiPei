# 链易配 - 技术栈实现说明

## 实现状态总览

| 技术方向 | 推荐项目 | 实现状态 | 说明 |
|---------|---------|---------|------|
| LLM应用 | DB-GPT | ✅ 已实现 | Text-to-SQL 自然语言查询产业链数据 |
| 图算法 | GraphBolt / NetworkX | ✅ 已实现 | PageRank、社区发现，产业图谱分析 |
| 时序预测 | Time-Series-Library / statsmodels | ✅ 已实现 | 供需趋势预测（指数平滑） |
| 联邦学习 | FedLab | ✅ 已实现 | 演示脚本 `scripts/fedlab_demo.py` |
| 多模态 | CLIP | ✅ 已实现 | 图文匹配，企业宣传图与产品关联 |
| 可视化 | PyEcharts + AntV | ✅ 已实现 | PyEcharts 柱状图 + AntV G2 图表 |

---

## 1. LLM 应用 - 自然语言查询（支持本地模型服务）

- **位置**: `app/services/llm_query.py`, `/ai-query` 页面, `/api/ai-query` 接口
- **功能**: 用户用自然语言提问，系统生成 SQL 并查询 MySQL 返回结果
- **调用方式（推荐）**: 通过 `LLMBASEURL/LLM_BASE_URL` 调用 OpenAI 兼容接口（本机 **Ollama** 示例：`http://localhost:11434/v1`；或远程 **model_service** / Qwen，见 `MODEL_SERVICE.md`）
- **兜底**: 未配置 `LLM_BASE_URL` 时，可选回退到 `OPENAI_API_KEY`（OpenAI SDK）；再不行则使用规则匹配常见问题（企业数量、供需数量等）

---

## 2. 图算法 - 产业图谱分析

- **位置**: `app/services/graph_algorithms.py`
- **功能**:
  - PageRank：识别产业链关键产品节点
  - 社区发现：划分产业链集群（需 `python-louvain`，否则退化为连通分量）
  - 关键路径：某产品的上下游扩展
- **依赖**: `networkx`
- **入口**: 产业链图谱页面 → 点击「PageRank 关键节点」「社区发现」

---

## 3. 时序预测

- **位置**: `app/services/forecaster.py`, `/dashboard/api/forecast`
- **功能**: 基于历史供需数据，预测未来数月趋势
- **依赖**: `statsmodels`（或简单移动平均兜底）
- **入口**: 政府大屏「供需趋势」图表

---

## 4. 联邦学习 - FedLab

- **位置**: `scripts/fedlab_demo.py`
- **功能**: 演示 FedLab 框架可用性，说明多企业联合训练场景
- **运行**: `python scripts/fedlab_demo.py`
- **依赖**: `pip install fedlab`（可选）

---

## 5. 多模态 CLIP

- **位置**: `app/services/clip_matcher.py`, `/clip-match` 页面
- **功能**: 上传企业宣传图，匹配平台中的相关产品
- **依赖**: `pip install open-clip-torch torch`（可选）
- **模型**: Product 表新增 `image_path` 字段（需手动迁移或重建表）

---

## 6. 可视化 - PyEcharts + AntV

- **PyEcharts**: 政府大屏柱状图，后端生成
- **AntV G2**: 通过 CDN 引入，政府大屏玫瑰图/柱状图
- **依赖**: `pyecharts`（已纳入 requirements.txt）

---

## 安装与配置

```bash
# 核心依赖
pip install -r requirements.txt

# 可选：智能问答接入大模型（Ollama 或 model_service）
# 见 MODEL_SERVICE.md，在 .env 中设置 LLMBASEURL（如 http://localhost:11434/v1）

# 可选：社区发现算法增强
pip install python-louvain

# 可选：CLIP 图文匹配
pip install open-clip-torch torch

# 可选：FedLab 演示
pip install fedlab
```

---

## 数据库迁移（CLIP 产品图片）

若已存在数据库，需为 `products` 表添加 `image_path` 列：

```sql
ALTER TABLE products ADD COLUMN image_path VARCHAR(255) DEFAULT NULL;
```
