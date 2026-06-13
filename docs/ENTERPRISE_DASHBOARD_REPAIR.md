# 企业看板修复与功能裁剪说明

更新时间：2026-06-12

## 1. 本次调整目标

本次调整聚焦企业端两个问题：

1. 删除“物流距离”“发票管理”“电子合同”三个独立功能模块，不再作为企业端页面、导航项或前端 API 能力暴露。
2. 修复“企业看板”没有真正实现的问题，让 `/dashboard` 成为企业经营驾驶舱，而不是误跳到销售控制台。

## 2. 怎么实现的

### 2.1 路由与导航

- `frontend/src/App.tsx` 将 `/dashboard` 从 `SalesConsole` 改为 `Dashboard`。
- `frontend/src/components/Sidebar.tsx` 将“企业看板”指向 `/dashboard`，将销售相关功能单独保留为“销售控制台”。
- `frontend/src/lib/rbac.ts` 将企业用户默认首页调整为 `/dashboard`。
- 删除 `/contracts`、`/invoice`、`/logistics` 三个企业端路由，直接访问会进入 404 页面。

### 2.2 企业看板数据

`frontend/src/pages/Dashboard.tsx` 现在聚合以下数据：

- 企业履约信用：`api.fetchCreditScore(user.id)`
- 风险预警：`api.getAlerts({ page: 1, per_page: 20 })`
- 智能匹配推荐：`api.fetchSuppliers({ query: '' })`
- 订单统计：`api.getOrderStatistics()`
- 报价池统计：`api.getQuotesList({ page: 1, per_page: 5 })`

页面由这些数据生成信用分、供应链健康度、待处理预警、待推进订单、匹配机会和报价数量。

### 2.3 企业看板动作入口

看板右侧的“经营动作建议”替代原来的发票验证弹窗，提供四个直接动作：

- 处理风险：进入 `/risk`
- 推进订单：进入 `/orders`
- 寻找客商：进入 `/matching`
- 维护报价：进入 `/quote-pool`

底部主按钮进入 `/fulfillment`，用于继续查看履约看板。

### 2.4 删除的功能

已移除的前端文件：

- `frontend/src/pages/ContractManagement.tsx`
- `frontend/src/pages/InvoiceManagement.tsx`
- `frontend/src/pages/LogisticsMap.tsx`
- `frontend/src/components/CollaborationModal.tsx`

已清理的前端 API 封装：

- 发票上传：`uploadInvoice`
- 合同列表、详情、签署、下载等合同 API 方法
- 地图距离与地址定位 API 方法

同时删除了此前为电子合同 SPA 页面新增的 `/api/contracts` JSON 接口和对应测试，避免页面删除后还保留同一功能的前后端入口。

## 3. 有什么用

修复后的企业看板是企业端的工作入口，作用是让企业用户打开系统后能先看到“今天该处理什么”：

- 先看信用分和履约健康度，判断企业当前经营状态。
- 先处理风险预警，减少供应链中断和履约异常。
- 继续推进订单和履约，避免订单卡在待处理状态。
- 快速进入匹配和报价，承接采购、销售和供需协同工作。

它不是单一销售页，也不是静态展示页，而是把企业端多个核心模块的数据汇总成一个驾驶舱。

## 4. 验证结果

已通过的校验：

- `frontend/ npm run lint`：通过
- `frontend/ npm run build`：通过
- `venv/bin/python -m py_compile app/routes/api.py app/routes/inquiry_chat.py`：通过
- `venv/bin/python -m pytest -q tests/test_order_workflow.py tests/test_intent_quote.py`：2 个测试通过
- Playwright 浏览器断言：4 个用例通过

Playwright 已验证：

- `/dashboard` 显示企业看板内容，包括“履约信用等级”“经营动作建议”“查看履约看板”“智能匹配推荐”。
- `/dashboard` 不再显示销售控制台内容。
- 企业端页面不再显示“电子合同”“发票管理”“物流距离”。
- `/contracts`、`/invoice`、`/logistics` 均进入 404。

## 5. 当前可用入口

企业端保留的主要入口：

- `/dashboard`：企业看板
- `/sales-console`：销售控制台
- `/risk`：风险监测
- `/enterprise-directory`：企业名录筛选
- `/matching`：智能供需匹配
- `/group-purchase`：集采拼单大厅
- `/quote-pool`：报价池
- `/fulfillment`：履约看板
- `/capacity-calendar`：产能日历
- `/orders`：订单工作流
- `/assets`：资产管理
- `/settings`：系统设置
