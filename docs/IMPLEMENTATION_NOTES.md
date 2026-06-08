# AI意向报价功能实现说明

## 一、概述

本次实现为链易配系统添加了完整的**AI意向报价**相关功能，包括：
- 意向报价管理
- 供应商收藏
- 名片交换（基于现有逻辑增强）
- DeepSeek企业画像生成
- AI商机洞察消息

---

## 二、新增文件清单

### 2.1 数据模型（`app/models.py`）

新增3个数据模型：

| 模型 | 说明 | 状态 |
|:---|:---|:---|
| `FavoriteSupplier` | 收藏供应商记录 | ✅ 已添加 |
| `IntentQuote` | 意向报价记录 | ✅ 已添加 |
| `BusinessCard` | 名片交换记录 | ✅ 已添加 |

### 2.2 服务层（`app/services/`）

| 文件 | 说明 |
|:---|:---|
| `favorite_service.py` | 收藏服务：添加/移除/列表/批量询价 |
| `intent_quote_service.py` | 意向报价服务：创建/发送/确认/AI建议 |
| `deepseek_profile_service.py` | DeepSeek企业画像服务：生成公开画像 |

### 2.3 API路由（`app/routes/`）

| 文件 | 说明 | 路由前缀 |
|:---|:---|:---|
| `favorite.py` | 收藏API | `/api/favorites/*` |
| `intent_quote.py` | 意向报价API | `/api/intent-quote/*` |

### 2.4 脚本

| 文件 | 说明 |
|:---|:---|
| `scripts/migrate_new_tables.py` | 数据库迁移脚本 |

---

## 三、数据模型详情

### 3.1 FavoriteSupplier（收藏供应商）

```sql
CREATE TABLE favorite_suppliers (
    id INTEGER PRIMARY KEY,
    collector_id INTEGER,     -- 收藏方（采购商）
    supplier_id INTEGER,      -- 被收藏供应商
    product_name VARCHAR(100),
    match_score FLOAT,
    notes VARCHAR(500),
    created_at DATETIME,
    UNIQUE(collector_id, supplier_id)
);
```

### 3.2 IntentQuote（意向报价）

```sql
CREATE TABLE intent_quotes (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER,
    buyer_id INTEGER,         -- 采购方
    seller_id INTEGER,        -- 供应方
    match_record_id INTEGER,
    
    -- 报价信息
    product_name VARCHAR(100),
    quantity INTEGER,
    unit VARCHAR(20),
    target_price FLOAT,
    budget_range VARCHAR(50),
    
    -- AI辅助
    ai_suggested_price FLOAT,
    ai_price_basis TEXT,
    ai_delivery_estimate VARCHAR(100),
    
    -- 状态
    status VARCHAR(20),       -- draft/pending/accepted/rejected/expired
    buyer_confirmed BOOLEAN,
    seller_confirmed BOOLEAN,
    seller_reply_price FLOAT,
    seller_reply_notes TEXT,
    
    created_at DATETIME,
    updated_at DATETIME,
    expires_at DATETIME
);
```

### 3.3 BusinessCard（名片交换）

```sql
CREATE TABLE business_cards (
    id INTEGER PRIMARY KEY,
    initiator_id INTEGER,     -- 交换发起方
    recipient_id INTEGER,     -- 交换接收方
    intent_quote_id INTEGER,
    status VARCHAR(20),
    created_at DATETIME,
    UNIQUE(initiator_id, recipient_id)
);
```

---

## 四、API接口清单

### 4.1 收藏接口

| 方法 | 路径 | 说明 |
|:---:|:---|:---|
| POST | `/api/favorites/add` | 添加收藏 |
| POST | `/api/favorites/remove` | 取消收藏 |
| GET | `/api/favorites/list` | 收藏列表 |
| GET | `/api/favorites/check/<id>` | 检查是否收藏 |
| PUT | `/api/favorites/notes` | 更新备注 |
| POST | `/api/favorites/batch-inquiry` | 批量询价 |
| GET | `/api/favorites/supplier-count/<id>` | 供应商被收藏次数 |

### 4.2 意向报价接口

| 方法 | 路径 | 说明 |
|:---:|:---|:---|
| POST | `/api/intent-quote/create` | 创建意向报价 |
| GET | `/api/intent-quote/<id>` | 获取详情 |
| POST | `/api/intent-quote/<id>/send` | 发送报价 |
| POST | `/api/intent-quote/<id>/cancel` | 取消报价 |
| POST | `/api/intent-quote/<id>/accept` | 供应商接受 |
| POST | `/api/intent-quote/<id>/reject` | 供应商拒绝 |
| GET | `/api/intent-quote/buyer/list` | 采购方列表 |
| GET | `/api/intent-quote/seller/list` | 供应方列表 |
| POST | `/api/intent-quote/ai-suggestion` | AI报价建议 |
| POST | `/api/intent-quote/<id>/apply-ai-suggestion` | 应用AI建议 |
| GET | `/api/intent-quote/<id>/card-eligible` | 检查名片交换资格 |
| GET | `/api/intent-quote/enterprise-profile/<id>` | 企业画像 |
| POST | `/api/intent-quote/business-insight` | 商机洞察消息 |
| GET | `/api/intent-quote/recommendation/<id>` | AI推荐理由 |

---

## 五、功能流程

### 5.1 意向报价流程

```
采购商发起意向报价
        ↓
填写报价信息
   - 产品名称（自动带入）
   - 需求量（自动带入）
   - 目标单价（可获取AI建议）
   - 预算区间（选填）
        ↓
AI自动生成报价依据
   （调用DeepSeek分析）
        ↓
采购方确认发送
        ↓
供应方收到报价请求
        ↓
名片交换功能解锁
   （双向确认机制）
        ↓
供应方回应
   - 接受报价
   - 修改报价
   - 拒绝
        ↓
达成合作意向 → 进入订单流程
```

### 5.2 名片交换流程（现有逻辑）

```
现有 inquiry_chat.py 中的 /api/inquiry-chat/<id>/exchange-card 保持不变
        ↓
新增 BusinessCard 模型记录名片交换历史
        ↓
双方可交换的信息：
   - 企业名称
   - 地理位置（经纬度）
   - 联系方式（电话、联系人）
   - 主营业务
   - 信用评分
```

### 5.3 收藏功能

```
采购商点击收藏按钮
        ↓
记录 FavoriteSupplier
        ↓
可选填写备注
        ↓
收藏列表管理
   - 批量询价
   - 快速比较
   - 价格提醒订阅
```

---

## 六、AI商机洞察消息

### 6.1 消息格式

```json
{
  "type": "ai_business_insight",
  "enterprise_id": 123,
  "enterprise_name": "东莞宏宇塑胶材料有限公司",
  "insight_summary": "已为您提取商机：精密零部件。根据实时库存与产排计划分析：当前产能可评估，建议结合价格指数后快速报价。",
  "enterprise_profile": {
    "name": "东莞宏宇塑胶材料有限公司",
    "industry_code": "C29",
    "province": "广东",
    "city": "东莞",
    "capacity_status": "产能正常",
    "capacity_usage": "72%",
    "credit_score": 85.5,
    "credit_level": "AA+",
    "green_level": "B级",
    "patent_count": 3,
    "cooperation_risk": "低风险"
  },
  "actions": {
    "generate_quote": {
      "enabled": true,
      "label": "立即生成",
      "description": "一键生成意向报价单"
    }
  }
}
```

### 6.2 DeepSeek企业画像（不含敏感信息）

**✅ 包含的信息：**
- 企业名称
- 行业编码
- 省份/城市
- 经营范围
- 产能信息
- 信用评分
- 专利数量
- 绿色认证等级

**❌ 不包含的信息：**
- 联系人姓名
- 联系电话
- 详细地址
- 法人代表

---

## 七、前端集成建议

### 7.1 功能按钮布局

```
┌─────────────────────────────────────────────┐
│  对话消息区                                  │
├─────────────────────────────────────────────┤
│                                             │
│  [💰 意向报价] [📇 名片交换🔒] [⭐ 收藏]   │
│                                             │
└─────────────────────────────────────────────┘

说明：
- 意向报价：匹配成功即可使用
- 名片交换：需要双方确认意向报价后解锁 🔓
- 收藏：随时可用
```

### 7.2 调用示例

```javascript
// 收藏供应商
fetch('/api/favorites/add', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    supplier_id: 123,
    product_name: '精密电机',
    match_score: 88.5
  })
});

// 获取AI商机洞察
fetch('/api/intent-quote/business-insight', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    enterprise_id: 123,
    product_name: '精密电机'
  })
});

// 创建意向报价
fetch('/api/intent-quote/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    seller_id: 123,
    product_name: '精密电机',
    quantity: 1000,
    unit: '件',
    target_price: 45.0
  })
});
```

---

## 八、数据库迁移

运行以下命令创建新表：

```bash
cd "d:\大学\创赛\链易配"
python -m scripts.migrate_new_tables
```

或者重启应用，Flask-SQLAlchemy 会自动创建缺失的表：

```python
# app/__init__.py 中已配置
with app.app_context():
    db.create_all()  # 自动创建新表
```

---

## 九、现有代码整合

### 9.1 已增强的功能

| 文件 | 增强内容 |
|:---|:---|
| `app/routes/inquiry_chat.py` | 名片交换增加 BusinessCard 记录 |
| `app/__init__.py` | 注册新蓝图 |

### 9.2 服务层复用

| 服务 | 被以下文件使用 |
|:---|:---|
| `favorite_service.py` | `favorite.py`（API路由） |
| `intent_quote_service.py` | `intent_quote.py`（API路由） |
| `deepseek_profile_service.py` | `intent_quote.py`、`inquiry_chat.py` |

---

## 十、测试建议

### 10.1 功能测试

```bash
# 收藏功能测试
curl -X POST http://localhost:5000/api/favorites/add \
  -H "Content-Type: application/json" \
  -d '{"supplier_id": 2, "product_name": "电机"}'

# 意向报价测试
curl -X POST http://localhost:5000/api/intent-quote/create \
  -H "Content-Type: application/json" \
  -d '{"seller_id": 2, "product_name": "电机", "quantity": 100}'

# AI建议测试
curl -X POST http://localhost:5000/api/intent-quote/ai-suggestion \
  -H "Content-Type: application/json" \
  -d '{"seller_id": 2, "product_name": "电机", "quantity": 100}'
```

### 10.2 使用Apifox测试

1. 导入新接口文档
2. 设置认证环境
3. 编写测试用例
4. 执行自动化测试

---

## 十一、后续优化建议

1. **DeepSeek真实API集成**：当前为模拟实现，后续可接入真实DeepSeek API
2. **WebSocket实时推送**：名片交换、报价状态变更可推送通知
3. **消息推送集成**：与企业微信消息服务集成
4. **前端页面开发**：根据UI设计开发完整的交互页面
