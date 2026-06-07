# 链易配 - 数据使用说明

本文档说明如何初始化、维护和使用 MySQL + Neo4j 数据。

---

## 一、环境准备

### 1. MySQL

- 已安装 MySQL（如 8.0）
- 创建数据库（可手动或运行 `create_db.py`）：

```sql
CREATE DATABASE lianyipei CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

- 在项目根目录创建 `.env` 文件：

```
DATABASE_URL=mysql+pymysql://root:你的密码@localhost/lianyipei
```

### 2. Neo4j Desktop

- 安装 [Neo4j Desktop](https://neo4j.com/download/)
- 创建数据库并启动（默认 bolt://localhost:7687）
- 在 `.env` 中配置（若使用默认可省略）：

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=你的密码
```

---

## 二、数据初始化

### 方式一：一键初始化（推荐）

首次使用或需要完整种子数据时：

```bash
# 在项目根目录执行
python scripts/seed_all_data.py
```

将自动完成：

- 创建 MySQL 所有表
- 若表为空，则导入企业、产品、供需、交易、进口依赖度、预警阈值、示例专利
- 导入 Neo4j 产业链图谱（`data/relations.csv`）

### 方式二：全新重置（开发环境）

清空所有数据并重新导入：

```bash
python scripts/fresh_init.py
```

### 方式三：分步执行

```bash
# 1. 仅创建 MySQL 表（无数据）
python scripts/init_db.py

# 2. 仅导入 Neo4j 图谱
python scripts/import_graph.py

# 3. 仅生成 MySQL 测试数据（旧脚本，数据较少）
python scripts/generate_test_data.py
```

### 已有数据库的迁移

若数据库已存在，需要添加新字段时：

```bash
python scripts/migrate_db.py
```

---

## 三、数据表说明

### MySQL

| 表名 | 说明 |
|-----|------|
| `enterprises` | 企业：工商信息、专利、研发、行业编码等 |
| `products` | 产品：名称、类别、行业编码、所属企业 |
| `demands` | 供需：供应/需求、数量、状态 |
| `transactions` | 交易：买卖方、产品、数量、价格 |
| `alerts` | 预警：产品、等级、维度、建议 |
| `alert_thresholds` | 预警阈值：政府自定义 |
| `product_import_risks` | 产品进口依赖度（对接海关等） |
| `enterprise_patents` | 企业专利（对接知识产权局等） |

### Neo4j

- **节点**：`Product`（产品名称、类别）
- **关系**：`SUPPLIES_TO`（上游产品 → 下游产品）

---

## 四、默认账号

| 账号 | 密码 | 说明 |
|-----|------|------|
| admin | admin123 | 管理员（政府大屏、预警设置） |
| 任意企业名 | 123456 | 如：成都精密机械制造有限公司 |

---

## 五、自定义数据

### 1. 修改产业链关系（Neo4j）

编辑 `data/relations.csv`，格式：

```csv
上游产品,下游产品
电机,工业机器人
芯片,电路板
```

然后执行：

```bash
python scripts/import_graph.py
```

### 2. 修改进口依赖度（MySQL）

在 `product_import_risks` 表中插入或更新，例如：

```sql
INSERT INTO product_import_risks (product_name, import_ratio, source_countries, hs_code, data_source)
VALUES ('某产品', 0.75, '日本,德国', '8486', '海关总署');
```

预警逻辑会优先使用该表数据。

### 3. 批量导入企业

可参考 `scripts/seed_all_data.py` 中的 `ENTERPRISES` 结构，按需扩展后重新运行种子脚本（或在清空后使用 `fresh_init.py`）。

---

## 六、常见问题

**Q: Neo4j 连接失败？**  
A: 确认 Neo4j Desktop 已启动，数据库处于 Running 状态，端口 7687 未被占用。

**Q: MySQL 连接失败？**  
A: 检查 `.env` 中的 `DATABASE_URL`，用户名、密码、数据库名是否正确。

**Q: 如何只更新 Neo4j，不碰 MySQL？**  
A: 执行 `python scripts/import_graph.py`。

**Q: 已有数据，不想被清空？**  
A: `seed_all_data.py` 在检测到已有企业数据时会跳过企业/产品/供需种子，只创建缺失的管理员。如需完全避免覆盖，不要运行 `fresh_init.py`。
